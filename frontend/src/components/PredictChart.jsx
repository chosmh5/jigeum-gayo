import React from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from 'recharts'

const COLOR = { 0: '#2ecc71', 1: '#f39c12', 2: '#e74c3c' }
const LABEL = { 0: '여유', 1: '보통', 2: '혼잡' }

export default function PredictChart({ data }) {
  const chartData = data.map(d => ({
    hour: `${d.hour}시`,
    혼잡도: d.congestion_index,
    label: LABEL[d.congestion_index],
  }))

  return (
    <div style={{ marginTop: 16 }}>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <XAxis dataKey="hour" tick={{ fontSize: 11 }} interval={2} />
          <YAxis domain={[0, 2]} ticks={[0, 1, 2]} tickFormatter={v => LABEL[v]} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(_, __, props) => [props.payload.label, '혼잡도']} />
          <Bar dataKey="혼잡도" radius={[3, 3, 0, 0]}>
            {chartData.map((d, i) => (
              <Cell key={i} fill={COLOR[d.혼잡도]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
