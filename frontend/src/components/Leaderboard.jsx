const COMPOUND_COLOR = {
  SOFT:         '#ff2244',
  MEDIUM:       '#ffcc00',
  HARD:         '#e8e8e8',
  INTERMEDIATE: '#00cc44',
  WET:          '#4488ff',
}

export default function Leaderboard({ cars, selectedDriver, onSelect }) {
  if (!cars) return (
    <div className="panel leaderboard-panel">
      <div className="panel-header">STANDINGS</div>
      <div className="leaderboard-list" style={{ padding: '12px', color: 'var(--text-dim)' }}>
        AWAITING SIGNAL...
      </div>
    </div>
  )

  const sorted = Object.entries(cars)
    .filter(([, c]) => c !== null)
    .sort((a, b) => (a[1].pos ?? 99) - (b[1].pos ?? 99))

  const leader = sorted[0]?.[1]

  return (
    <div className="panel leaderboard-panel">
      <div className="panel-header">
        STANDINGS <span>LAP {leader?.lap ?? '--'}</span>
      </div>
      <div className="leaderboard-list">
        {sorted.map(([code, car], i) => {
          const gap = i === 0
            ? 'LEADER'
            : leader
              ? `+${((car.lap - leader.lap) < 0 ? 'LAP' : formatGap(car, leader))}`
              : '--'

          return (
            <div
              key={code}
              className={`lb-row ${selectedDriver === code ? 'selected' : ''}`}
              onClick={() => onSelect?.(code)}
            >
              <div className="lb-pos">{car.pos ?? i + 1}</div>
              <div className="lb-code" style={{ color: car.color ?? 'var(--green)' }}>
                {code}
              </div>
              <div className="lb-speed" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {car.compound && COMPOUND_COLOR[car.compound?.toUpperCase()] && (
                  <span style={{
                    width: 7, height: 7, borderRadius: '50%',
                    background: COMPOUND_COLOR[car.compound.toUpperCase()],
                    display: 'inline-block', flexShrink: 0,
                  }} />
                )}
                <span>{car.speed}<span style={{ fontSize: 9, color: 'var(--text-dim)' }}>km/h</span></span>
              </div>
              <div className="lb-gap" style={{ color: i === 0 ? 'var(--yellow)' : 'var(--text-dim)' }}>
                {i === 0 ? 'LEAD' : `L${car.lap}`}
              </div>
            </div>
          )
        })}
        {sorted.length === 0 && (
          <div style={{ padding: '12px', color: 'var(--text-dim)' }}>NO DATA</div>
        )}
      </div>
    </div>
  )
}

function formatGap(car, leader) {
  const lapDiff = leader.lap - car.lap
  if (lapDiff > 0) return `${lapDiff}L`
  return '--'
}
