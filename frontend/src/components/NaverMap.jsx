import { useEffect, useRef, useState } from 'react'

const CONGESTION_COLOR = { 여유: '#2ecc71', 보통: '#f39c12', 혼잡: '#e74c3c' }

export default function NaverMap({ facilities }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef([])
  const [ready, setReady] = useState(false)

  const clientId = import.meta.env.VITE_NAVER_MAP_CLIENT_ID

  // SDK 로드
  useEffect(() => {
    if (!clientId || clientId.includes('여기에')) return
    if (window.naver?.maps) { setReady(true); return }

    const s = document.createElement('script')
    s.src = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpClientId=${clientId}`
    s.onload = () => setReady(true)
    document.head.appendChild(s)
  }, [clientId])

  // 지도 초기화
  useEffect(() => {
    if (!ready || !containerRef.current || mapRef.current) return
    mapRef.current = new window.naver.maps.Map(containerRef.current, {
      center: new window.naver.maps.LatLng(37.5665, 126.9780),
      zoom: 12,
    })
  }, [ready])

  // 마커 업데이트
  useEffect(() => {
    if (!mapRef.current || !facilities.length) return

    // 이전 마커 제거
    markersRef.current.forEach(m => m.setMap(null))
    markersRef.current = []

    const valid = facilities.filter(f => f.lat && f.lon)
    if (!valid.length) return

    valid.forEach(f => {
      const pos = new window.naver.maps.LatLng(f.lat, f.lon)
      const color = CONGESTION_COLOR[f.congestion_label] ?? '#aaa'

      const marker = new window.naver.maps.Marker({
        position: pos,
        map: mapRef.current,
        icon: {
          content: `<div style="
            background:${color};color:#fff;
            padding:4px 8px;border-radius:12px;
            font-size:12px;font-weight:700;
            box-shadow:0 2px 6px rgba(0,0,0,0.25);
            white-space:nowrap;
          ">${f.congestion_label}</div>`,
          anchor: new window.naver.maps.Point(20, 12),
        },
      })

      const info = new window.naver.maps.InfoWindow({
        content: `<div style="padding:10px 14px;min-width:160px;font-family:sans-serif">
          <div style="font-weight:700;font-size:14px;margin-bottom:4px">${f.name}</div>
          <span style="color:${color};font-weight:600">${f.congestion_label}</span>
          <span style="color:#666;font-size:12px"> · 잔여 ${f.current_available}석</span>
        </div>`,
        borderWidth: 0,
        borderRadius: '8px',
        disableAnchor: false,
      })

      window.naver.maps.Event.addListener(marker, 'click', () => {
        if (info.getMap()) info.close()
        else info.open(mapRef.current, marker)
      })

      markersRef.current.push(marker)
    })

    // 마커가 2개 이상이면 bounds 맞춤
    if (valid.length > 1) {
      const bounds = new window.naver.maps.LatLngBounds()
      valid.forEach(f => bounds.extend(new window.naver.maps.LatLng(f.lat, f.lon)))
      mapRef.current.fitBounds(bounds, { top: 60, right: 60, bottom: 60, left: 60 })
    } else {
      mapRef.current.setCenter(new window.naver.maps.LatLng(valid[0].lat, valid[0].lon))
    }
  }, [ready, facilities])

  if (!clientId || clientId.includes('여기에')) {
    return (
      <div style={styles.placeholder}>
        <p style={{ color: '#888', fontSize: 14, textAlign: 'center', lineHeight: 1.6 }}>
          네이버 지도를 표시하려면<br />
          <code style={{ background: '#eee', padding: '2px 6px', borderRadius: 4 }}>frontend/.env</code>에<br />
          <code style={{ background: '#eee', padding: '2px 6px', borderRadius: 4 }}>VITE_NAVER_MAP_CLIENT_ID</code>를 설정하세요
        </p>
      </div>
    )
  }

  return <div ref={containerRef} style={styles.map} />
}

const styles = {
  map: { width: '100%', height: 400, borderRadius: 12, overflow: 'hidden' },
  placeholder: {
    height: 400, background: '#f5f5f5', borderRadius: 12,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
}
