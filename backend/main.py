import pickle
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

sys.path.insert(0, str(Path(__file__).parent.parent / "data-collector"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "data-collector" / ".env", override=True)

try:
    from kopis_collector import get_active_venue_info, get_nearby_stats
    _kopis_available = True
except Exception:
    _kopis_available = False

MODEL_DIR = Path(__file__).parent.parent / "ml" / "models"
MODEL_PATHS = {
    "library": MODEL_DIR / "library_model.pkl",
    "locker":  MODEL_DIR / "locker_model.pkl",
}

LABEL_MAP = {0: "여유", 1: "보통", 2: "혼잡"}
DATA_DIR   = Path(__file__).parent.parent / "data-collector" / "data"
# train.py의 CAPACITY_BINS와 동일하게 유지: 소형(≤10) / 중형(11~25) / 대형(26+)
_CAPACITY_BINS = [0, 10, 25, float("inf")]


def _capacity_bin(total: int) -> int:
    for i, edge in enumerate(_CAPACITY_BINS[1:], start=0):
        if total <= edge:
            return i
    return len(_CAPACITY_BINS) - 2
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
KAKAO_REST_KEY = "bf5e4f55316d783f7a9a320ef339b6be"

# 시설별 지하철 거리 정적 룩업 (nearest_subway_km)
_subway_map: dict[str, float] = {}
_SUBWAY_FALLBACK = 0.048  # 훈련 데이터 중앙값


def _load_static_features() -> None:
    global _subway_map
    csv = DATA_DIR / "enriched_locker.csv"
    if not csv.exists():
        return
    df = pd.read_csv(csv, usecols=["facility_id", "nearest_subway_km"],
                     encoding="utf-8-sig").drop_duplicates("facility_id").dropna()
    _subway_map = df.set_index("facility_id")["nearest_subway_km"].to_dict()


_load_static_features()


def _load_facilities_from_csv() -> list[dict]:
    import glob, csv
    result = {}
    for ftype in ("library", "locker"):
        pattern = str(DATA_DIR / f"congestion_*_{ftype}.csv")
        files = sorted(glob.glob(pattern))
        if not files:
            continue
        with open(files[-1], encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                name = row["facility_name"]
                lat  = float(row["lat"]) if row.get("lat") else None
                lon  = float(row["lon"]) if row.get("lon") else None
                if name not in result:
                    result[name] = {
                        "id":              row["facility_id"] + "_" + name,
                        "facility_id_raw": row["facility_id"],
                        "name":            name,
                        "type":            ftype,
                        "total_capacity":  int(row["total_capacity"]),
                        "current_available": int(row["current_available"]),
                        "updated_at":      row["timestamp"],
                        "lat": lat,
                        "lon": lon,
                    }
                else:
                    if row["timestamp"] > result[name]["updated_at"]:
                        result[name]["current_available"] = int(row["current_available"])
                        result[name]["updated_at"] = row["timestamp"]
    return list(result.values())


app = FastAPI(title="지금 가볼까? API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_model_cache: dict = {}


def get_model(facility_type: str):
    if facility_type not in _model_cache:
        path = MODEL_PATHS.get(facility_type)
        if not path or not path.exists():
            return None
        with open(path, "rb") as f:
            _model_cache[facility_type] = pickle.load(f)
    return _model_cache.get(facility_type)


@app.get("/api/region")
def get_region(lat: float, lon: float):
    res = requests.get(
        "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json",
        params={"x": lon, "y": lat},
        headers={"Authorization": f"KakaoAK {KAKAO_REST_KEY}"},
        timeout=5,
    )
    return res.json()


@app.get("/api/keyword")
def search_keyword(q: str):
    res = requests.get(
        "https://dapi.kakao.com/v2/local/search/keyword.json",
        params={"query": q},
        headers={"Authorization": f"KakaoAK {KAKAO_REST_KEY}"},
        timeout=5,
    )
    return res.json()


@app.get("/map", include_in_schema=False)
def serve_map():
    return FileResponse(FRONTEND_DIR / "kakaomap.html")


@app.get("/config.js", include_in_schema=False)
def serve_map_config():
    path = FRONTEND_DIR / "config.js"
    if not path.exists():
        path = FRONTEND_DIR / "config.example.js"
    return FileResponse(path, media_type="application/javascript")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "models": {k: v.exists() for k, v in MODEL_PATHS.items()},
        "kopis": _kopis_available,
        "subway_map_size": len(_subway_map),
    }


@app.get("/facilities")
def list_facilities():
    facilities = _load_facilities_from_csv()
    result = []
    for f in facilities:
        ratio = f["current_available"] / f["total_capacity"] if f["total_capacity"] else 1
        label = "여유" if ratio > 0.5 else ("보통" if ratio > 0.2 else "혼잡")
        result.append({**f, "congestion_label": label})
    return result


@app.get("/predict/{facility_id}")
def predict(
    facility_id: str,
    hour: int = Query(default=None, ge=0, le=23),
    day:  int = Query(default=None, ge=0, le=6),
    is_holiday: int = Query(default=0, ge=0, le=1),
):
    facility = next((f for f in _load_facilities_from_csv() if f["id"] == facility_id), None)
    if facility is None:
        raise HTTPException(status_code=404, detail="시설을 찾을 수 없습니다.")

    now  = datetime.now()
    hour = hour if hour is not None else now.hour
    day  = day  if day  is not None else now.weekday()

    ftype  = facility["type"]
    bundle = get_model(ftype)

    if bundle is None:
        busy_hours = range(9, 22)
        if hour in busy_hours and day in range(0, 5) and not is_holiday:
            label_idx = 2 if 11 <= hour <= 14 or 18 <= hour <= 21 else 1
        else:
            label_idx = 0
        return {
            "facility_id": facility_id, "hour": hour, "day_of_week": day,
            "congestion": LABEL_MAP[label_idx], "congestion_index": label_idx,
            "model": "rule_based",
        }

    model    = bundle["model"]
    features = bundle["features"]

    # KOPIS 기반 공연 피처 (6시간 캐시 적용)
    nearby_event_count, nearby_event_seats = 0, 0
    show_window_count, show_window_seats, is_show_window = 0, 0, 0
    lat, lon = facility.get("lat"), facility.get("lon")
    if _kopis_available and lat and lon:
        try:
            venue_info = get_active_venue_info()
            nearby_event_count, nearby_event_seats = get_nearby_stats(float(lat), float(lon), venue_info)
            # 공연 시간대 근사: 일반적인 공연 시간(13-22시)에 근처 공연이 있으면 show_window로 처리
            if nearby_event_count > 0 and 13 <= hour <= 22:
                is_show_window   = 1
                show_window_count = nearby_event_count
                show_window_seats = nearby_event_seats
        except Exception:
            pass

    nearest_subway_km = _subway_map.get(facility.get("facility_id_raw", ""), _SUBWAY_FALLBACK)

    row = {
        "hour":               hour,
        "day_of_week":        day,
        "is_holiday":         is_holiday,
        "capacity_bin":       _capacity_bin(facility["total_capacity"]),
        "nearby_event_count": nearby_event_count,
        "nearby_event_seats": nearby_event_seats,
        "show_window_count":  show_window_count,
        "show_window_seats":  show_window_seats,
        "is_show_window":     is_show_window,
        "nearest_subway_km":  nearest_subway_km,
    }
    X = pd.DataFrame([row])[features]

    label_idx = int(model.predict(X)[0])
    proba = model.predict_proba(X)[0].tolist() if hasattr(model, "predict_proba") else None

    return {
        "facility_id":    facility_id,
        "hour":           hour,
        "day_of_week":    day,
        "congestion":     LABEL_MAP[label_idx],
        "congestion_index": label_idx,
        "probabilities":  {"여유": proba[0], "보통": proba[1], "혼잡": proba[2]} if proba else None,
        "model":          "ml",
    }
