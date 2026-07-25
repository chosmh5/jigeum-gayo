import { useEffect, useRef, useState } from 'react'

const CONGESTION_COLOR = { 여유: '#2ecc71', 보통: '#f39c12', 혼잡: '#e74c3c' }

export default function KakaoMap({ facilities }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const overlaysRef = useRef([])
  const [ready, setReady] = useState(false)

  const appKey = import.meta.env.VITE_KAKAO_MAP_APP_KEY

  // SDK 로드
  useEffect(() => {
    if (!appKey || appKey.includes('여기에')) return
    if (window.kakao?.maps) { setReady(true); return }

    const s = document.createElement('script')
    s.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${appKey}&autoload=false`
    s.onload = () => window.kakao.maps.load(() => setReady(true))
    document.head.appendChild(s)
  }, [appKey])

  // 지도 초기화
  useEffect(() => {
    if (!ready || !containerRef.current || mapRef.current) return
    mapRef.current = new window.kakao.maps.Map(containerRef.current, {
      center: new window.kakao.maps.LatLng(37.5665, 126.9780),
      level: 5,
    })
  }, [ready])

  // 마커 업데이트
  useEffect(() => {
    if (!mapRef.current || !facilities.length) return
    const { maps } = window.kakao

    // 이전 오버레이 제거
    overlaysRef.current.forEach(({ marker, info }) => {
      marker.setMap(null)
      info.close()
    })
    overlaysRef.current = []

    const valid = facilities.filter(f => f.lat && f.lon)
    if (!valid.length) return

    valid.forEach(f => {
      const pos = new maps.LatLng(f.lat, f.lon)
      const color = CONGESTION_COLOR[f.congestion_label] ?? '#aaa'

      const marker = new maps.Marker({ position: pos, map: mapRef.current })

      const info = new maps.InfoWindow({
        content: `<div style="padding:10px 14px;min-width:160px;font-family:sans-serif;font-size:13px">
          <div style="font-weight:700;margin-bottom:4px">${f.name}</div>
          <span style="color:${color};font-weight:600">${f.congestion_label}</span>
          <span style="color:#666;font-size:12px"> · 잔여 ${f.current_available}석</span>
        </div>`,
        removable: true,
      })

      maps.event.addListener(marker, 'click', () => {
        if (info.getMap()) info.close()
        else info.open(mapRef.current, marker)
      })

      overlaysRef.current.push({ marker, info })
    })

    // 범위 맞춤
    if (valid.length > 1) {
      const bounds = new maps.LatLngBounds()
      valid.forEach(f => bounds.extend(new maps.LatLng(f.lat, f.lon)))
      mapRef.current.setBounds(bounds)
    } else {
      mapRef.current.setCenter(new maps.LatLng(valid[0].lat, valid[0].lon))
    }
  }, [ready, facilities])

  if (!appKey || appKey.includes('여기에')) {
    return (
      <div style={styles.placeholder}>
        <p style={{ color: '#888', fontSize: 14, textAlign: 'center', lineHeight: 1.8 }}>
          카카오 지도를 표시하려면<br />
          <code style={{ background: '#eee', padding: '2px 6px', borderRadius: 4 }}>frontend/.env</code>에<br />
          <code style={{ background: '#eee', padding: '2px 6px', borderRadius: 4 }}>VITE_KAKAO_MAP_APP_KEY</code>를 설정하세요
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
