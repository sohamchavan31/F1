export default function TelemetryPanel({ cars, selectedDriver }) {
  const car = selectedDriver && cars ? cars[selectedDriver] : null

  if (!car) return (
    <div className="panel telemetry-bar">
      <div className="panel-header">TELEMETRY</div>
      <div style={{ color: 'var(--text-dim)', fontSize: 11, padding: 4 }}>
        SELECT DRIVER
      </div>
    </div>
  )

  return (
    <div className="panel telemetry-bar">
      <div className="panel-header">
        <span style={{ color: car.color ?? 'var(--green)' }}>{selectedDriver}</span>
        <span>P{car.pos} · LAP {car.lap}</span>
      </div>

      {/* Speed */}
      <div>
        <div className="tel-row">
          <span className="tel-label">SPD</span>
          <span className={`tel-value ${car.speed > 280 ? 'highlight' : ''}`}>
            {car.speed}<span style={{ fontSize: 9 }}>km/h</span>
          </span>
        </div>
        <div className="tel-bar-track">
          <div className="tel-bar-fill"
            style={{ width: `${Math.min(car.speed / 350 * 100, 100)}%`, background: 'var(--cyan)' }} />
        </div>
      </div>

      {/* Throttle */}
      <div>
        <div className="tel-row">
          <span className="tel-label">THR</span>
          <span className="tel-value">{car.throttle}<span style={{ fontSize: 9 }}>%</span></span>
        </div>
        <div className="tel-bar-track">
          <div className="tel-bar-fill"
            style={{ width: `${car.throttle}%`, background: 'var(--green)' }} />
        </div>
      </div>

      {/* Brake / Gear / DRS row */}
      <div className="tel-row" style={{ marginTop: 2 }}>
        <span className="tel-label">BRK</span>
        <span className={`tel-value ${car.brake ? 'danger' : ''}`}>
          {car.brake ? '■ ON' : '□ OFF'}
        </span>
      </div>
      <div className="tel-row">
        <span className="tel-label">GEAR</span>
        <span className="tel-value highlight">{car.gear}</span>
        <span className="tel-label" style={{ marginLeft: 8 }}>DRS</span>
        <span className="tel-value" style={{ color: car.drs ? 'var(--green)' : 'var(--text-dim)' }}>
          {car.drs ? '▶ OPEN' : '— CLSD'}
        </span>
      </div>
    </div>
  )
}
