import os
import csv
import json
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import holidays
from kopis_collector import get_active_venue_info, get_nearby_stats

load_dotenv()

PUBLIC_API_KEY = os.getenv("PUBLIC_API_KEY", "")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

KR_HOLIDAYS = holidays.KR()

PLR_BASE = "https://apis.data.go.kr/B551982/plr_v2"
PSL_BASE = "https://apis.data.go.kr/B551982/psl_v2"

COMMON_PARAMS = {
    "serviceKey": PUBLIC_API_KEY,
    "numOfRows": "1000",
    "pageNo": "1",
    "type": "json",
}

FIELDNAMES_LIBRARY = [
    "timestamp", "facility_id", "facility_name", "facility_type",
    "current_available", "total_capacity", "hour", "day_of_week", "is_holiday",
]

FIELDNAMES_LOCKER = [
    "timestamp", "facility_id", "facility_name", "facility_type",
    "current_available", "total_capacity", "hour", "day_of_week", "is_holiday",
    "nearby_event_count", "nearby_event_seats", "lat", "lon",
]


def _items(resp_json: dict) -> list:
    """공공데이터포털 JSON 응답에서 item 리스트 추출"""
    body = resp_json.get("body", {})
    item = body.get("item", [])
    # 단건이면 dict, 다건이면 list
    if isinstance(item, dict):
        return [item]
    return item or []


def _to_int(val) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def fetch_reading_rooms() -> list[dict]:
    """열람실 실시간 잔여좌석 수집 (전국)"""
    try:
        resp = requests.get(
            f"{PLR_BASE}/rlt_rdrm_info_v2",
            params=COMMON_PARAMS,
            timeout=15,
        )
        resp.raise_for_status()
        rows = []
        for item in _items(json.loads(resp.content.decode("utf-8"))):
            available = _to_int(item.get("rmndSeatCnt"))
            total = _to_int(item.get("tseatCnt"))
            if total == 0:
                continue
            rows.append({
                "facility_id": f"lib_{item.get('rdrmId', '')}",
                "facility_name": f"{item.get('pblibNm','')} {item.get('rdrmNm','')}",
                "facility_type": "library",
                "current_available": available,
                "total_capacity": total,
            })
        return rows
    except Exception as e:
        print(f"[WARN] 열람실 API 실패: {e}")
        return []


def fetch_lockers(venue_info: list) -> list[dict]:
    """물품보관함 실시간 사용가능수 수집 (전국)"""
    try:
        resp = requests.get(
            f"{PSL_BASE}/locker_realtime_use_v2",
            params=COMMON_PARAMS,
            timeout=15,
        )
        resp.raise_for_status()

        # 총 보관함 수는 별도 API에서 가져옴
        info_resp = requests.get(
            f"{PSL_BASE}/locker_info_v2",
            params=COMMON_PARAMS,
            timeout=15,
        )
        info_resp.raise_for_status()
        total_map = {
            item.get("stlckId"): _to_int(item.get("stlckCnt"))
            for item in _items(info_resp.json())
        }

        # 보관함 위치 정보 (lat/lon)
        loc_map = {
            item.get("stlckId"): (
                float(item.get("lat", 0) or 0),
                float(item.get("lot", 0) or 0),
            )
            for item in _items(info_resp.json())
        }

        rows = []
        for item in _items(resp.json()):
            stlck_id = item.get("stlckId", "")
            available = (
                _to_int(item.get("usePsbltyLrgszStlckCnt"))
                + _to_int(item.get("usePsbltyMdmszStlckCnt"))
                + _to_int(item.get("usePsbltySmlszStlckCnt"))
            )
            total = total_map.get(stlck_id, 0)
            if total == 0:
                continue
            lat, lon = loc_map.get(stlck_id, (0.0, 0.0))
            if lat and lon:
                nearby_count, nearby_seats = get_nearby_stats(lat, lon, venue_info)
            else:
                nearby_count, nearby_seats = 0, 0
            rows.append({
                "facility_id": f"locker_{stlck_id}",
                "facility_name": stlck_id,
                "facility_type": "locker",
                "current_available": available,
                "total_capacity": total,
                "nearby_event_count": nearby_count,
                "nearby_event_seats": nearby_seats,
                "lat": lat,
                "lon": lon,
            })
        return rows
    except Exception as e:
        print(f"[WARN] 물품보관함 API 실패: {e}")
        return []


def collect_once():
    if not PUBLIC_API_KEY:
        print("[ERROR] PUBLIC_API_KEY 없음 - .env 파일 확인")
        return

    now = datetime.now()
    is_holiday = int(now.date() in KR_HOLIDAYS)

    venue_info = []  # KOPIS 수집 비활성화 (데이터 수집 안정화 우선)

    rows_lib = fetch_reading_rooms()
    rows_lock = fetch_lockers(venue_info)

    if not rows_lib and not rows_lock:
        print(f"[{now.strftime('%H:%M:%S')}] 수집 결과 없음")
        return

    month = now.strftime('%Y%m')
    common = {
        "timestamp": now.isoformat(timespec="seconds"),
        "hour": now.hour,
        "day_of_week": now.weekday(),
        "is_holiday": is_holiday,
    }

    if rows_lib:
        lib_path = DATA_DIR / f"congestion_{month}_library.csv"
        write_header = not lib_path.exists()
        with open(lib_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES_LIBRARY)
            if write_header:
                writer.writeheader()
            for row in rows_lib:
                writer.writerow({**common, **row})

    if rows_lock:
        lock_path = DATA_DIR / f"congestion_{month}_locker.csv"
        write_header = not lock_path.exists()
        with open(lock_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES_LOCKER)
            if write_header:
                writer.writeheader()
            for row in rows_lock:
                writer.writerow({**common, **row})

    print(
        f"[{now.strftime('%H:%M:%S')}] "
        f"열람실 {len(rows_lib)}개 → congestion_{month}_library.csv | "
        f"보관함 {len(rows_lock)}개 → congestion_{month}_locker.csv"
    )


if __name__ == "__main__":
    collect_once()
