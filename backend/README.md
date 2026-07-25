# backend

FastAPI 기반 혼잡도 예측 API 서버입니다.

## 설치 및 실행

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health` | 헬스체크 |
| GET | `/facilities` | 시설 목록 + 현재 잔여 현황 |
| GET | `/predict/{facility_id}` | 혼잡도 예측 (`?hour=<int>&day=<int>`) |

## 환경변수

`.env` 파일 불필요 — 모델 경로는 `../ml/models/congestion_model.pkl` 기준.
