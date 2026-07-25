# ml

EDA → 전처리 → 학습 → 모델 저장 파이프라인입니다.

## 설치

```bash
pip install -r requirements.txt
```

## 실행 순서

```bash
# 1. EDA (Jupyter)
jupyter notebook notebooks/01_eda.ipynb

# 2. 학습
python train.py

# 결과물: models/congestion_model.pkl
#         reports/model_comparison.md
```

## 혼잡도 레이블

| 값 | 의미 | 조건 |
|---|---|---|
| 0 | 여유 | 잔여율 > 50% |
| 1 | 보통 | 20% < 잔여율 ≤ 50% |
| 2 | 혼잡 | 잔여율 ≤ 20% |
