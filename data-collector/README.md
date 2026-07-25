# data-collector

공공데이터포털 API를 주기적으로 호출하여 CSV에 저장하는 수집 모듈입니다.

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env   # API 키 입력
```

## 실행

```bash
python scheduler.py   # APScheduler로 10분 주기 수집
# 또는 1회 즉시 수집
python collector.py
```

## 수집 피처

| 컬럼 | 설명 |
|---|---|
| `timestamp` | 수집 시각 (ISO 8601) |
| `facility_id` | 시설 고유 ID |
| `current_available` | 현재 이용 가능 수 |
| `total_capacity` | 총 수용 인원 |
| `hour` | 시 (파생) |
| `day_of_week` | 요일 0=월 … 6=일 (파생) |
| `is_holiday` | 공휴일 여부 (파생) |
