import sys
import pickle
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, GroupShuffleSplit, GroupKFold
from sklearn.metrics import classification_report
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE, ADASYN, BorderlineSMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

DATA_DIR = Path(__file__).parent.parent / "data-collector" / "data"
MODEL_DIR = Path(__file__).parent / "models"
REPORT_DIR = Path(__file__).parent / "reports"

LIBRARY_FEATURES = ["hour", "day_of_week", "is_holiday", "total_capacity"]
LOCKER_FEATURES = [
    "hour", "day_of_week", "capacity_bin",
    "nearby_event_count", "nearby_event_seats",
    "show_window_count", "show_window_seats", "is_show_window",
    "nearest_subway_km",
]
# 시설 규모 구간: 소형(≤10) / 중형(11~25) / 대형(26+)
CAPACITY_BINS = [0, 10, 25, float("inf")]
TARGET = "congestion_label"

LABEL_NAMES = {0: "여유", 1: "보통", 2: "혼잡"}


def label_congestion(row) -> int:
    ratio = row["current_available"] / row["total_capacity"]
    if ratio > 0.5:
        return 0
    elif ratio > 0.2:
        return 1
    else:
        return 2


def load_data(suffix: str) -> pd.DataFrame:
    """suffix: 'library' 또는 'locker'"""
    if suffix == "locker" and (DATA_DIR / "enriched_locker.csv").exists():
        csv_files = [DATA_DIR / "enriched_locker.csv"]
        print("[locker] enriched_locker.csv 사용 (KOPIS 조인 완료본)")
    else:
        csv_files = list(DATA_DIR.glob(f"congestion_*_{suffix}.csv"))
    if not csv_files:
        print(f"[ERROR] CSV 없음: congestion_*_{suffix}.csv in {DATA_DIR}")
        return pd.DataFrame()

    df = pd.concat([pd.read_csv(f, on_bad_lines="skip") for f in csv_files], ignore_index=True)
    df = df.dropna(subset=["current_available", "total_capacity"])
    df = df[df["total_capacity"] > 0]
    df[TARGET] = df.apply(label_congestion, axis=1)
    if "nearest_subway_km" in df.columns:
        df["nearest_subway_km"] = df["nearest_subway_km"].fillna(df["nearest_subway_km"].median())
    if suffix == "locker":
        df["capacity_bin"] = pd.cut(
            df["total_capacity"], bins=CAPACITY_BINS, labels=[0, 1, 2]
        ).astype(int)
    print(f"[{suffix}] CSV {len(csv_files)}개 로드 → {len(df)}행")
    return df


def train_one(df: pd.DataFrame, facility_type: str, features: list[str]):
    subset = df[df["facility_type"] == facility_type].copy().reset_index(drop=True)
    print(f"\n{'='*40}")
    print(f"[{facility_type}] 데이터 {len(subset)}행")
    print(subset[TARGET].map(LABEL_NAMES).value_counts().to_string())

    if len(subset) < 30:
        print("  → 데이터 부족 (30행 미만), 학습 건너뜀")
        return

    if subset[TARGET].nunique() < 2:
        print("  → 클래스가 1개뿐, 학습 건너뜀")
        return

    groups = subset["facility_id"].values
    n_fac = len(set(groups))
    print(f"  고유 시설 수: {n_fac}")

    # Leave-facility-out 분할 (시설 단위로 train/test 분리)
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(subset, subset[TARGET], groups))
    tr = subset.iloc[train_idx].copy().reset_index(drop=True)
    te = subset.iloc[test_idx].copy().reset_index(drop=True)
    groups_tr = tr["facility_id"].values
    print(f"  train {len(set(groups_tr))}개 시설 ({len(tr)}행) / test {len(set(te['facility_id']))}개 시설 ({len(te)}행)")

    X_train = tr[features]
    y_train = tr[TARGET]
    X_test  = te[features]
    y_test  = te[TARGET]
    sw_train = compute_sample_weight("balanced", y_train)

    def _xgb():
        return XGBClassifier(n_estimators=100, random_state=42, eval_metric="mlogloss", verbosity=0)

    candidates = {
        "RF(balanced)":       RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42),
        "XGBoost":            _xgb(),
        "XGBoost+SMOTE":      ImbPipeline([("s", SMOTE(random_state=42)),           ("clf", _xgb())]),
        "XGBoost+ADASYN":     ImbPipeline([("s", ADASYN(random_state=42)),          ("clf", _xgb())]),
        "XGBoost+BorderSMOTE":ImbPipeline([("s", BorderlineSMOTE(random_state=42)), ("clf", _xgb())]),
    }

    n_cv = min(5, len(set(groups_tr)))
    results = {}
    for name, model in candidates.items():
        scores = cross_val_score(model, X_train, y_train,
                                 cv=GroupKFold(n_splits=n_cv),
                                 groups=groups_tr, scoring="f1_macro")
        results[name] = {"model": model, "cv_f1": scores.mean(), "cv_std": scores.std()}
        print(f"  {name}: CV F1={scores.mean():.3f} ± {scores.std():.3f}")

    best_name = max(results, key=lambda k: results[k]["cv_f1"])
    best_model = results[best_name]["model"]
    print(f"  최적: {best_name}")

    if isinstance(best_model, ImbPipeline) or best_name == "RF(balanced)":
        best_model.fit(X_train, y_train)
    else:
        best_model.fit(X_train, y_train, sample_weight=sw_train)

    y_pred = best_model.predict(X_test)
    all_labels = sorted(subset[TARGET].unique())
    label_names = [LABEL_NAMES[c] for c in all_labels]
    report = classification_report(y_test, y_pred, labels=all_labels, target_names=label_names)
    print(report)

    MODEL_DIR.mkdir(exist_ok=True)
    model_path = MODEL_DIR / f"{facility_type}_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({"model": best_model, "features": features}, f)
    print(f"  저장 → {model_path}")

    REPORT_DIR.mkdir(exist_ok=True)
    report_path = REPORT_DIR / f"{facility_type}_model_comparison.md"
    lines = [f"# {facility_type} 모델 비교 (leave-facility-out)\n"]
    lines.append("| 모델 | CV F1 (macro) | std |")
    lines.append("|---|---|---|")
    for name, r in results.items():
        mark = " **✓**" if name == best_name else ""
        lines.append(f"| {name}{mark} | {r['cv_f1']:.3f} | {r['cv_std']:.3f} |")
    lines.append(f"\n## 테스트셋 성능 (미등장 시설)\n\n```\n{report}\n```")
    report_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    df_lib = load_data("library")
    if not df_lib.empty:
        train_one(df_lib, "library", LIBRARY_FEATURES)

    df_lock = load_data("locker")
    if not df_lock.empty:
        train_one(df_lock, "locker", LOCKER_FEATURES)
    else:
        print("\n[locker] 데이터 없음 - 건너뜀")
