"""enriched_locker.csv에 nearest_subway_km 컬럼 추가 (Kakao 카테고리 검색)"""
import os
import time
import pandas as pd
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "data-collector" / ".env", override=True)

DATA_DIR = Path(__file__).parent.parent / "data-collector" / "data"
CSV_PATH = DATA_DIR / "enriched_locker.csv"
KAKAO_KEY = os.getenv("KAKAO_API_KEY", "")


def get_nearest_subway_km(lat: float, lon: float) -> float:
    try:
        resp = requests.get(
            "https://dapi.kakao.com/v2/local/search/category.json",
            params={
                "category_group_code": "SW8",
                "x": lon, "y": lat,
                "radius": 2000,
                "sort": "distance",
                "size": 1,
            },
            headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
            timeout=5,
        )
        docs = resp.json().get("documents", [])
        if docs:
            return float(docs[0]["distance"]) / 1000  # m → km
    except Exception as e:
        print(f"[WARN] {e}")
    return float("nan")


def main():
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

    if "nearest_subway_km" in df.columns:
        print("nearest_subway_km 이미 존재 — 덮어씁니다")

    facilities = df[["facility_id", "lat", "lon"]].drop_duplicates("facility_id")
    print(f"지하철역 거리 조회 중 ({len(facilities)}개 시설)...")

    subway_map = {}
    for i, (_, row) in enumerate(facilities.iterrows()):
        if pd.notna(row["lat"]) and pd.notna(row["lon"]):
            subway_map[row["facility_id"]] = get_nearest_subway_km(row["lat"], row["lon"])
        else:
            subway_map[row["facility_id"]] = float("nan")
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(facilities)}...")
        time.sleep(0.1)

    df["nearest_subway_km"] = df["facility_id"].map(subway_map)
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"\n저장 완료: {CSV_PATH}")
    print(df["nearest_subway_km"].describe().to_string())


if __name__ == "__main__":
    main()
