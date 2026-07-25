"""
KOPIS 공연 정보를 수집하여 각 보관함 근처(반경 내) 공연 수와 총 좌석 수를 반환합니다.
- 보관함 lat/lon + 공연장 lat/lon -> Haversine 거리 계산
- 공연장 seatscale(좌석 규모) 합산 -> nearby_event_seats 피쳐
"""
import os
import math
import xml.etree.ElementTree as ET
from datetime import datetime
from functools import lru_cache

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

BASE = "http://kopis.or.kr/openApi/restful"
HEADERS = {"Accept": "application/xml, text/xml, */*", "User-Agent": "Mozilla/5.0"}

NEARBY_KM = 1.0


def _get(url: str, params: dict) -> ET.Element | None:
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        first = root.find("db")
        if first is not None and first.findtext("returncode"):
            return None
        return root
    except Exception as e:
        print(f"[WARN] KOPIS 요청 실패 ({url}): {e}")
        return None


def _text(el: ET.Element, tag: str, default: str = "") -> str:
    node = el.find(tag)
    return node.text.strip() if node is not None and node.text else default


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@lru_cache(maxsize=512)
def get_venue_info(mt10id: str) -> tuple[float, float, int] | None:
    """공연장 ID -> (lat, lon, seat_scale). 동일 ID는 캐시 재사용."""
    root = _get(f"{BASE}/prfplc/{mt10id}", {"service": os.getenv("KOPIS_API_KEY", "")})
    if root is None:
        return None
    db = root.find("db")
    if db is None:
        return None
    try:
        lat = float(_text(db, "la"))
        lon = float(_text(db, "lo"))
        seats = int(_text(db, "seatscale").replace(",", "") or "0")
        return (lat, lon, seats)
    except ValueError:
        return None


_venue_cache: list[tuple[float, float, int]] = []
_venue_cache_time: datetime | None = None
_CACHE_TTL_SECONDS = 6 * 3600  # 6시간


def get_active_venue_info(date: str | None = None) -> list[tuple[float, float, int]]:
    """
    오늘 공연 중인 모든 공연장의 (lat, lon, seat_scale) 목록 반환.
    date: 'YYYYMMDD' 형식 (기본값: 오늘), 6시간 메모리 캐시 적용.
    """
    global _venue_cache, _venue_cache_time
    now = datetime.now()
    if _venue_cache_time and (now - _venue_cache_time).total_seconds() < _CACHE_TTL_SECONDS:
        return _venue_cache

    key = os.getenv("KOPIS_API_KEY", "")
    if not key:
        print("[WARN] KOPIS_API_KEY 없음 - .env 확인")
        return []

    today = date or datetime.now().strftime("%Y%m%d")

    # KOPIS API 최대 100건/페이지 — 페이지네이션으로 전체 수집
    mt20ids: list[str] = []
    page = 1
    while True:
        params = {
            "service": key,
            "stdate": today,
            "eddate": today,
            "rows": "100",
            "cpage": str(page),
        }
        perf_root = _get(f"{BASE}/pblprfr", params)
        if perf_root is None:
            break
        batch = [_text(db, "mt20id") for db in perf_root.findall("db") if _text(db, "mt20id")]
        mt20ids.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    print(f"[KOPIS] 오늘 공연 {len(mt20ids)}건 조회")

    venue_info = []
    seen_venues: set[str] = set()

    for mt20id in mt20ids:
        detail_root = _get(f"{BASE}/pblprfr/{mt20id}", {"service": key})
        if detail_root is None:
            continue
        db = detail_root.find("db")
        if db is None:
            continue

        mt13id = _text(db, "mt13id")
        if not mt13id or "-" not in mt13id:
            continue

        mt10id = mt13id.rsplit("-", 1)[0]
        if mt10id in seen_venues:
            continue
        seen_venues.add(mt10id)

        info = get_venue_info(mt10id)
        if info:
            venue_info.append(info)

    print(f"[KOPIS] 공연장 정보 수집 {len(venue_info)}개 (좌석 합계: {sum(s for _, _, s in venue_info):,}석)")
    _venue_cache = venue_info
    _venue_cache_time = now
    return venue_info


def get_nearby_stats(
    locker_lat: float,
    locker_lon: float,
    venue_info: list[tuple[float, float, int]],
    radius_km: float = NEARBY_KM,
) -> tuple[int, int]:
    """보관함 좌표 기준 반경 내 공연 수 및 총 좌석 수 반환."""
    count = 0
    seats = 0
    for lat, lon, seat_scale in venue_info:
        if haversine(locker_lat, locker_lon, lat, lon) <= radius_km:
            count += 1
            seats += seat_scale
    return count, seats
