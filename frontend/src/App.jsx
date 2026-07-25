import React, { useEffect, useState } from 'react'
import { fetchFacilities } from './api'
import FacilityCard from './components/FacilityCard'
import KakaoMap from './components/KakaoMap'

export default function App() {
  const [facilities, setFacilities] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchFacilities()
      .then(setFacilities)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={styles.root}>
      <header style={styles.header}>
        <h1 style={styles.title}>지금 가볼까? 🗺️</h1>
        <p style={styles.sub}>공공시설 실시간 혼잡도 · 시간대별 예측</p>
      </header>

      <main style={styles.main}>
        <KakaoMap facilities={facilities} />

        {loading && <p style={styles.msg}>불러오는 중…</p>}
        {error && <p style={{ ...styles.msg, color: '#e74c3c' }}>서버 연결 실패: {error}<br /><small>백엔드가 실행 중인지 확인하세요.</small></p>}
        {!loading && !error && facilities.length === 0 && (
          <p style={styles.msg}>시설 정보가 없습니다.</p>
        )}
        <div style={styles.grid}>
          {facilities.map(f => (
            <FacilityCard key={f.id} facility={f} />
          ))}
        </div>
      </main>
    </div>
  )
}

const styles = {
  root: { minHeight: '100vh' },
  header: { background: '#fff', padding: '24px 24px 16px', borderBottom: '1px solid #eee' },
  title: { fontSize: 24, fontWeight: 800 },
  sub: { fontSize: 14, color: '#666', marginTop: 4 },
  main: { maxWidth: 720, margin: '0 auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 24 },
  grid: { display: 'flex', flexDirection: 'column', gap: 16 },
  msg: { textAlign: 'center', color: '#888', padding: '40px 0' },
}
