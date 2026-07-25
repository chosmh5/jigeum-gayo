# frontend

React + 네이버 지도 API 기반 혼잡도 시각화 UI입니다.

## 설치 및 실행

```bash
npm install
cp .env.example .env   # 환경변수 입력
npm run dev
```

## Vercel 배포

```bash
npm run build
vercel --prod
```

## 환경변수

| 변수명 | 설명 |
|---|---|
| `VITE_API_BASE_URL` | 백엔드 API 주소 (예: http://localhost:8000) |
| `VITE_NAVER_MAP_CLIENT_ID` | 네이버 지도 클라이언트 ID (없으면 빈 지도 렌더) |
