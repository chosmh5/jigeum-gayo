const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function fetchFacilities() {
  const res = await fetch(`${BASE}/facilities`)
  if (!res.ok) throw new Error('시설 목록 로드 실패')
  return res.json()
}

export async function fetchPrediction(facilityId, hour, day) {
  const res = await fetch(`${BASE}/predict/${facilityId}?hour=${hour}&day=${day}`)
  if (!res.ok) throw new Error('예측 실패')
  return res.json()
}
