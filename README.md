# 지금 가볼까

서울시 공공시설(물품 보관함)의 **혼잡도를 예측**하는 웹 서비스입니다.
공공 API를 10분 주기로 수집해 시계열을 쌓고, 시설 유형별로 분류 모델을 학습해 카카오맵 위에 표시합니다.


---


## 데이터

| | 열람실 (library) | 보관함 (locker) |
|---|---|---|
| 수집 기간 | 2026-05-26 ~ 07-25 (약 2개월) | 동일 |
| 행 수 | 1,037,346 | 1,401,859 |
| 시설 수 | 21 | 360 |
| 출처 | 행정안전부 한국지역정보개발원 공공데이터포털 |

| 레이블 | 기준 (잔여율) |
|---|---|
| 여유 (0) | 50% 초과 |
| 보통 (1) | 20% ~ 50% |
| 혼잡 (2) | 20% 이하 |


### 피처

**보관함** — 위 항목에 더해:

| 피처 | 설명 |
|---|---|
| `capacity_bin` | 시설 규모 구간: 0=소형(≤10) / 1=중형(11~25) / 2=대형(26+) |
| `nearby_event_count` / `_seats` | 당일 반경 1km 내 공연 수 및 총 좌석 수 (하루치 배경 정보) |
| `show_window_count` / `_seats` | 현재 시각이 '공연 시작 2시간 전 ~ 종료' 구간에 걸치는 공연 수·좌석 수 |
| `is_show_window` | 위 구간에 걸치는 공연이 하나라도 있으면 1 |
| `nearest_subway_km` | 최근접 지하철역 거리(km), Kakao API |


## 프로젝트 구조

```
.
├── data-collector/
│   ├── collector.py         # 열람실·보관함 실시간 수집
│   ├── kopis_collector.py   # KOPIS 공연 정보 수집
│   ├── scheduler.py         # 10분 주기 자동 수집
│   └── data/                # 수집 CSV (gitignore)
├── ml/
│   ├── enrich_locker.py     # KOPIS 공연 피처 생성
│   ├── enrich_subway.py     # 지하철 거리 피처 추가
│   ├── train.py             # 시설 유형별 모델 학습 (5종 비교)
│   ├── analyze_event_impact.py
│   ├── models/              # 학습된 pkl (gitignore)
│   └── reports/             # 모델 비교 리포트
├── backend/
│   └── main.py              # FastAPI 서버
└── frontend/
    ├── kakaomap.html        # 카카오맵 UI (standalone)
    └── src/                 # React 버전
```
