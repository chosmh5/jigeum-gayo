import React, { useState } from 'react'
import { fetchPrediction } from '../api'
import PredictChart from './PredictChart'

export default function FacilityCard({ facility }) {
  const [predictions, setPredictions] = useState(null)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const usedRatio = (facility.total_capacity - facility.current_available) / facility.total_capacity

  async function loadPredictions() {
    if (predictions) { setExpanded(e => !e); return }
    setLoading(true)
    try {
      const today = new Date().getDay() // 0=일 → 변환
      const dayOfWeek = today === 0 ? 6 : today - 1 // 0=월 기준
      const results = await Promise.all(
        Array.from({ length: 24 }, (_, h) => fetchPrediction(facility.id, h, dayOfWeek))
      )
      setPredictions(results)
      setExpanded(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div>
          <div style={styles.name}>{facility.name}</div>
          <div style={styles.sub}>수용 {facility.total_capacity}석 · 잔여 {facility.current_available}석</div>
        </div>
        <span className={`badge badge-${facility.congestion_label}`}>
          {facility.congestion_label}
        </span>
      </div>

      <div style={styles.bar}>
        <div style={{ ...styles.barFill, width: `${usedRatio * 100}%`, background: barColor(facility.congestion_label) }} />
      </div>

      <button onClick={loadPredictions} style={styles.btn} disabled={loading}>
        {loading ? '불러오는 중…' : expanded ? '시간대별 예측 접기' : '시간대별 예측 보기'}
      </button>

      {expanded && predictions && <PredictChart data={predictions} />}
    </div>
  )
}

function barColor(label) {
  return { 여유: '#2ecc71', 보통: '#f39c12', 혼잡: '#e74c3c' }[label] ?? '#ccc'
}

const styles = {
  card: { background: '#fff', borderRadius: 12, padding: 20, boxShadow: '0 1px 6px rgba(0,0,0,0.08)' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 },
  name: { fontWeight: 700, fontSize: 16 },
  sub: { fontSize: 13, color: '#666', marginTop: 2 },
  bar: { height: 8, background: '#eee', borderRadius: 4, overflow: 'hidden', marginBottom: 12 },
  barFill: { height: '100%', borderRadius: 4, transition: 'width 0.4s' },
  btn: { fontSize: 13, color: '#3498db', background: 'none', border: 'none', cursor: 'pointer', padding: 0 },
}
