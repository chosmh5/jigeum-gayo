"""
행사 규모(nearby_event_count, nearby_event_seats)가 보관함 점유율에
영향을 미치는지 분석합니다.
"""
import sys
import io
from pathlib import Path
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent.parent / "data-collector" / "data"

COLS_V1 = ["timestamp","facility_id","facility_name","facility_type",
           "current_available","total_capacity","hour","day_of_week","is_holiday"]
COLS_V2 = COLS_V1 + ["nearby_event_count"]
COLS_V3 = COLS_V2 + ["nearby_event_seats"]


def load_locker_data() -> pd.DataFrame:
    enriched = DATA_DIR / "enriched_locker.csv"
    if enriched.exists():
        print("enriched_locker.csv 사용")
        df = pd.read_csv(enriched, encoding="utf-8-sig", on_bad_lines="skip")
        df = df.dropna(subset=["current_available", "total_capacity"])
        df = df[df["total_capacity"] > 0]
        df["occupancy"] = 1 - df["current_available"] / df["total_capacity"]
        return df

    files = list(DATA_DIR.glob("congestion_*_locker.csv"))
    if not files:
        print("[ERROR] locker CSV 없음")
        return pd.DataFrame()

    frames = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            lines = fh.readlines()

        by_width: dict[int, list[str]] = {}
        for line in lines[1:]:
            w = line.count(",") + 1
            by_width.setdefault(w, []).append(line)

        for width, rows in by_width.items():
            if width == len(COLS_V1):
                cols = COLS_V1
            elif width == len(COLS_V2):
                cols = COLS_V2
            elif width == len(COLS_V3):
                cols = COLS_V3
            else:
                continue
            chunk = pd.read_csv(io.StringIO("".join(rows)), header=None, names=cols)
            frames.append(chunk)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["current_available", "total_capacity"])
    df = df[df["total_capacity"] > 0]
    df["occupancy"] = 1 - df["current_available"] / df["total_capacity"]
    return df


def sep(title: str):
    print(f"\n{'='*52}")
    print(f"  {title}")
    print('='*52)


def analyze():
    df = load_locker_data()
    if df.empty:
        return

    print(f"총 {len(df):,}행 | 타임스탬프 {df['timestamp'].nunique()}개 | 보관함 {df['facility_id'].nunique()}개")
    print(f"컬럼: {df.columns.tolist()}")

    if "nearby_event_count" not in df.columns:
        print("\n[WARN] nearby_event_count 없음 - 새 수집 후 재실행 필요")
        return

    df_ev = df.dropna(subset=["nearby_event_count"]).copy()
    df_ev["has_event"] = df_ev["nearby_event_count"] > 0

    sep("1. 행사 유무별 평균 점유율")
    g = df_ev.groupby("has_event")["occupancy"].agg(["mean", "std", "count"])
    g.index = g.index.map({False: "행사 없음", True: "행사 있음"})
    g.columns = ["평균 점유율", "표준편차", "샘플 수"]
    print(g.to_string(float_format="%.4f"))

    sep("2. 행사 수(nearby_event_count)별 평균 점유율")
    g2 = df_ev.groupby("nearby_event_count")["occupancy"].agg(["mean", "count"])
    g2.columns = ["평균 점유율", "샘플 수"]
    print(g2.to_string(float_format="%.4f"))

    sep("3. 상관관계 (Pearson r)")
    r_count = df_ev["nearby_event_count"].corr(df_ev["occupancy"])
    print(f"  nearby_event_count vs 점유율: r = {r_count:+.4f}")

    if "nearby_event_seats" in df_ev.columns:
        df_s = df_ev.dropna(subset=["nearby_event_seats"])
        if len(df_s) > 0:
            r_seats = df_s["nearby_event_seats"].corr(df_s["occupancy"])
            print(f"  nearby_event_seats vs 점유율: r = {r_seats:+.4f}")
    else:
        print("  nearby_event_seats: 아직 수집 안 됨 (다음 수집 후 재실행)")

    try:
        from scipy.stats import mannwhitneyu, pointbiserialr
        no_ev = df_ev[~df_ev["has_event"]]["occupancy"]
        yes_ev = df_ev[df_ev["has_event"]]["occupancy"]

        sep("4. Mann-Whitney U 검정 (행사 유무 vs 점유율)")
        if len(yes_ev) == 0:
            print("  행사 있는 보관함 데이터 없음")
        else:
            stat, p = mannwhitneyu(yes_ev, no_ev, alternative="greater")
            print(f"  U = {stat:.0f}, p = {p:.4f}")
            print(f"  -> {'유의미한 차이 있음 (p < 0.05)' if p < 0.05 else '유의미한 차이 없음 — 데이터 더 필요'}")
    except ImportError:
        sep("4. Mann-Whitney U 검정")
        print("  scipy 없음. pip install scipy")

    sep("5. 전체 점유율 기술 통계")
    print(df_ev["occupancy"].describe().apply(lambda x: f"{x:.4f}").to_string())


if __name__ == "__main__":
    analyze()
