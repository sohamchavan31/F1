import { useEffect, useState, useRef } from 'react'

const PADDING = 0.06

export default function TrackMap({ event, year, cars, selectedDriver, onSelectDriver }) {
  const [trackPoints, setTrackPoints] = useState([])
  const svgRef = useRef(null)

  useEffect(() => {
    if (!event) return
    const url = year ? `/api/track-map/${event}/${year}/` : `/api/track-map/${event}/`
    fetch(url)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.points) setTrackPoints(data.points) })
      .catch(() => {})
  }, [event, year])

  const polylinePoints = trackPoints
    .map(p => `${p.x},${p.y}`)
    .join(' ')

  const activeCars = cars
    ? Object.entries(cars).filter(([, c]) => c !== null)
    : []

  return (
    <div className="panel track-panel" style={{ position: 'relative' }}>
      <div className="panel-header">
        TRACK MAP <span>{event ? `// ${event} ${year ?? ''}` : '// NO SESSION'}</span>
        <span style={{ color: 'var(--cyan)' }}>{activeCars.length} CARS</span>
      </div>
      <svg
        ref={svgRef}
        className="track-svg"
        viewBox={`${-PADDING} ${-PADDING} ${1 + PADDING * 2} ${1 + PADDING * 2}`}
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Track outline */}
        {polylinePoints && (
          <polyline
            className="track-path"
            points={polylinePoints}
          />
        )}

        {/* Pit lane ghost markers */}
        {trackPoints.length > 0 && (
          <circle cx={trackPoints[0]?.x} cy={trackPoints[0]?.y} r="0.01"
            fill="none" stroke="var(--yellow)" strokeWidth="0.004" opacity="0.5" />
        )}

        {/* Cars */}
        {activeCars.map(([code, car]) => (
          <g key={code} onClick={() => onSelectDriver?.(code)} style={{ cursor: 'pointer' }}>
            <circle
              className="car-dot"
              cx={car.x}
              cy={car.y}
              r={code === selectedDriver ? 0.018 : 0.013}
              fill={car.color ?? '#00ff41'}
              stroke={code === selectedDriver ? '#fff' : 'rgba(0,0,0,0.5)'}
              strokeWidth={code === selectedDriver ? 0.004 : 0.002}
              style={{ filter: `drop-shadow(0 0 3px ${car.color ?? '#00ff41'})` }}
            />
            {/* Driver code label */}
            <text
              x={car.x + 0.016}
              y={car.y + 0.007}
              className="car-label"
              fontSize="0.018"
              fill={code === selectedDriver ? '#fff' : 'var(--text-dim)'}
            >
              {code}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}
