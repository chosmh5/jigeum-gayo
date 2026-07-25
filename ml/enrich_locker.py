"""
locker CSV에 KOPIS 공연 정보를 조인합니다.
- 공연 기준으로 근처 보관함을 찾아 show_window 피처 생성
- is_show_window: 공연 시작 ±2시간 내 여부
- 결과: data-collector/data/enriched_locker.csv
         data-collector/data/performances.csv
"""
import sys, io, time, os, re
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "data-collector" / ".env", override=True)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "data-collector"))
from kopis_collector import get_venue_info, get_nearby_stats, haversine, _get, _text, NEARBY_KM

DATA_DIR = Path(__file__).parent.parent / "data-collector" / "data"
OUT_PATH = DATA_DIR / "enriched_locker.csv"
PERF_PATH = DATA_DIR / "performances.csv"
KOPIS_KEY = os.getenv("KOPIS_API_KEY", "")
BASE = "http://kopis.or.kr/openApi/restful"

DAY_KR = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}


def parse_date(s: str) -> str:
    s = s.strip().replace(".", "")
    return f"{s[:4]}-{s[4:6]}-{s[6:]}" if len(s) == 8 else s


def parse_runtime(prfruntime: str) -> float:
    """'2시간 30분' / '120분' / '1시간' → 시간(float). 파싱 실패 시 2.0 기본값."""
    if not prfruntime:
        return 2.0
    h = re.search(r'(\d+)\s*시간', prfruntime)
    m = re.search(r'(\d+)\s*분', prfruntime)
    minutes_only = re.match(r'^\s*(\d+)\s*분\s*$', prfruntime)
    if minutes_only:
        return int(minutes_only.group(1)) / 60
    total = 0.0
    if h:
        total += int(h.group(1))
    if m:
        total += int(m.group(1)) / 60
    return total if total > 0 else 2.0


def parse_dtguidance(dtguidance: str) -> dict[int, list[float]]:
    """dtguidance → {weekday(0=월): [공연시작시각(float hours)]}"""
    result: dict[int, list[float]] = {i: [] for i in range(7)}
    if not dtguidance:
        return result
    for match in re.finditer(r'([^()]+)\(([^)]+)\)', dtguidance):
        days_str = match.group(1).strip()
        times_str = match.group(2).strip()
        hours = []
        for t in times_str.split(','):
            m = re.match(r'(\d+):(\d+)', t.strip())
            if m:
                hours.append(int(m.group(1)) + int(m.group(2)) / 60)
        if not hours:
            continue
        days: set[int] = set()
        if '매일' in days_str:
            days = set(range(7))
        else:
            for part in re.split(r',\s*', days_str):
                part = part.strip()
                if '~' in part:
                    kr = [c for c in part if c in DAY_KR]
                    if len(kr) >= 2:
                        s, e = DAY_KR[kr[0]], DAY_KR[kr[-1]]
                        days.update(range(s, e + 1) if s <= e else list(range(s, 7)) + list(range(0, e + 1)))
                elif part in DAY_KR:
                    days.add(DAY_KR[part])
        for d in days:
            result[d].extend(hours)
    return result


def fetch_performances(stdate: str, eddate: str) -> list[dict]:
    """KOPIS 조회 → performances 리스트 (dtguidance 포함)"""
    entries = []
    page = 1
    while True:
        root = _get(f"{BASE}/pblprfr", {
            "service": KOPIS_KEY,
            "stdate": stdate,
            "eddate": eddate,
            "rows": "100",
            "cpage": str(page),
        })
        if root is None:
            break
        batch = root.findall("db")
        for db in batch:
            mid = _text(db, "mt20id")
            if mid:
                entries.append({
                    "mt20id": mid,
                    "prfpdfrom": parse_date(_text(db, "prfpdfrom")),
                    "prfpdto": parse_date(_text(db, "prfpdto")),
                })
        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.1)

    print(f"공연 총 {len(entries)}건 조회")

    venue_cache: dict[str, tuple[float, float, int] | None] = {}
    performances = []

    for i, e in enumerate(entries):
        detail = None
        for attempt in range(3):
            detail = _get(f"{BASE}/pblprfr/{e['mt20id']}", {"service": KOPIS_KEY})
            if detail is not None:
                break
            time.sleep(2 ** attempt)
        if detail is None:
            continue
        db = detail.find("db")
        if db is None:
            continue
        mt13id = _text(db, "mt13id")
        if not mt13id or "-" not in mt13id:
            continue
        mt10id = mt13id.rsplit("-", 1)[0]
        dtguidance = _text(db, "dtguidance")
        runtime_hours = parse_runtime(_text(db, "prfruntime"))

        if mt10id not in venue_cache:
            venue_cache[mt10id] = get_venue_info(mt10id)
            time.sleep(0.1)

        info = venue_cache[mt10id]
        if info:
            lat, lon, seats = info
            performances.append({
                "mt20id":     e["mt20id"],
                "prfpdfrom":  e["prfpdfrom"],
                "prfpdto":    e["prfpdto"],
                "lat":        lat,
                "lon":        lon,
                "seats":      seats,
                "dtguidance":    dtguidance,
                "runtime_hours": runtime_hours,
            })

        if (i + 1) % 50 == 0:
            print(f"  상세 조회 {i+1}/{len(entries)}...")
        time.sleep(0.5)

    print(f"공연장 포함 공연: {len(performances)}건 (고유 공연장: {len(venue_cache)}개)")
    return performances


def build_show_window_lookup(
    performances: list[dict],
    facilities: pd.DataFrame,
) -> dict[tuple[str, str], list[tuple[float, int]]]:
    """
    공연 기준으로 근처 보관함을 찾아 룩업 테이블 생성.
    반환: {(facility_id, date): [(show_start_hour, seats), ...]}
    """
    # {(facility_id, date): [(show_start_hour, show_end_hour, seats), ...]}
    lookup: dict[tuple[str, str], list[tuple[float, float, int]]] = {}

    fac_coords = {
        row["facility_id"]: (row["lat"], row["lon"])
        for _, row in facilities.iterrows()
        if pd.notna(row["lat"]) and pd.notna(row["lon"])
    }

    for p in performances:
        nearby_facs = [
            fid for fid, (flat, flon) in fac_coords.items()
            if haversine(flat, flon, p["lat"], p["lon"]) <= NEARBY_KM
        ]
        if not nearby_facs:
            continue

        show_times_by_weekday = parse_dtguidance(p["dtguidance"])
        runtime = p["runtime_hours"]

        cur = datetime.strptime(p["prfpdfrom"], "%Y-%m-%d")
        end = datetime.strptime(p["prfpdto"], "%Y-%m-%d")
        while cur <= end:
            date_str = cur.strftime("%Y-%m-%d")
            weekday = cur.weekday()
            show_hours = show_times_by_weekday.get(weekday, [])
            for fid in nearby_facs:
                key = (fid, date_str)
                if key not in lookup:
                    lookup[key] = []
                lookup[key].extend((h, h + runtime, p["seats"]) for h in show_hours)
            cur += timedelta(days=1)

    return lookup


def apply_show_window_features(
    df: pd.DataFrame,
    lookup: dict[tuple[str, str], list[tuple[float, float, int]]],
    pre_show_hours: float = 2.0,
) -> pd.DataFrame:
    """공연 시작 2시간 전 ~ 공연 종료 시각 사이 보관함 기록에 피처 추가."""
    df["date"] = df["timestamp"].str[:10]
    df["hour_f"] = pd.to_datetime(df["timestamp"]).dt.hour + pd.to_datetime(df["timestamp"]).dt.minute / 60

    def _compute(row):
        shows = lookup.get((row["facility_id"], row["date"]), [])
        # h_start - 2h <= reading_time <= h_end
        in_window = [
            (h_start, s) for h_start, h_end, s in shows
            if h_start - pre_show_hours <= row["hour_f"] <= h_end
        ]
        return pd.Series({
            "show_window_count": len(in_window),
            "show_window_seats": sum(s for _, s in in_window),
            "is_show_window":    int(bool(in_window)),
        })

    print("show_window 피처 계산 중...")
    features = df.apply(_compute, axis=1)
    df = pd.concat([df, features], axis=1)
    df = df.drop(columns=["date", "hour_f"])
    return df


def main():
    files = sorted(DATA_DIR.glob("congestion_*_locker.csv"))
    if not files:
        print("[ERROR] locker CSV 없음")
        return

    df = pd.concat(
        [pd.read_csv(f, on_bad_lines="skip", encoding="utf-8-sig") for f in files],
        ignore_index=True,
    )
    df["date"] = df["timestamp"].str[:10]
    dates = sorted(df["date"].unique())
    stdate = dates[0].replace("-", "")
    eddate = dates[-1].replace("-", "")
    print(f"locker 데이터: {dates[0]} ~ {dates[-1]}, {len(df):,}행")
    print(f"KOPIS 기간 조회: {stdate} ~ {eddate}\n")
    df = df.drop(columns=["date"])

    performances = fetch_performances(stdate, eddate)

    # performances.csv 저장
    pd.DataFrame(performances).to_csv(PERF_PATH, index=False, encoding="utf-8-sig")
    print(f"performances.csv 저장: {PERF_PATH}\n")

    # 기존 날짜 기준 피처 (nearby_event_count, nearby_event_seats)
    df["date"] = df["timestamp"].str[:10]
    venue_list = [(p["lat"], p["lon"], p["seats"]) for p in performances]

    unique = df[["date", "facility_id", "lat", "lon"]].drop_duplicates()
    print(f"시설-날짜 고유 조합 {len(unique)}개 계산 중...")
    date_lookup: dict[tuple[str, str], tuple[int, int]] = {}
    for i, (_, row) in enumerate(unique.iterrows()):
        lat, lon = row["lat"], row["lon"]
        key = (row["date"], row["facility_id"])
        if pd.isna(lat) or pd.isna(lon) or not lat or not lon:
            date_lookup[key] = (0, 0)
        else:
            active = [
                (p["lat"], p["lon"], p["seats"])
                for p in performances
                if p["prfpdfrom"] <= row["date"] <= p["prfpdto"]
            ]
            date_lookup[key] = get_nearby_stats(float(lat), float(lon), active)
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(unique)}...")

    df["nearby_event_count"] = df.apply(lambda r: date_lookup.get((r["date"], r["facility_id"]), (0, 0))[0], axis=1)
    df["nearby_event_seats"] = df.apply(lambda r: date_lookup.get((r["date"], r["facility_id"]), (0, 0))[1], axis=1)
    df = df.drop(columns=["date"])

    # 시간 기준 show_window 피처 (공연 기준으로 보관함 찾기)
    facilities = df[["facility_id", "lat", "lon"]].drop_duplicates("facility_id")
    print(f"\n공연 기준 show_window 룩업 생성 중 (공연 {len(performances)}건)...")
    show_lookup = build_show_window_lookup(performances, facilities)
    print(f"룩업 엔트리: {len(show_lookup)}개 (facility×date)")

    df = apply_show_window_features(df, show_lookup)

    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"\n저장 완료: {OUT_PATH}")
    print(f"nearby_event_count > 0 : {(df['nearby_event_count'] > 0).sum():,}행")
    print(f"is_show_window == 1    : {(df['is_show_window'] == 1).sum():,}행")
    print(f"show_window_seats > 0  : {(df['show_window_seats'] > 0).sum():,}행")


if __name__ == "__main__":
    main()
