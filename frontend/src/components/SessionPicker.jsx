import { useState, useEffect } from 'react'

export default function SessionPicker({ onSelect }) {
  const [sessions, setSessions] = useState(null)

  useEffect(() => {
    fetch('/api/sessions/')
      .then(r => r.json())
      .then(setSessions)
      .catch(() => setSessions([]))
  }, [])

  return (
    <div className="session-picker">
      <div className="sp-logo"><em>F1</em>_REPLAY<span className="blink">_</span></div>
      <div className="sp-subtitle">SELECT SESSION TO LOAD</div>

      <div className="sp-list">
        <div className="sp-row header">
          <div>YEAR</div>
          <div>EVENT</div>
          <div>SESSION</div>
          <div>DRIVERS</div>
        </div>

        {sessions === null && (
          <div className="sp-empty">CONNECTING TO MONGODB<span className="blink">...</span></div>
        )}

        {sessions?.length === 0 && (
          <div className="sp-empty">
            NO SESSIONS FOUND<br/>
            <span style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 8, display: 'block' }}>
              RUN: python load_race.py --year 2023 --event Monza --session Race --test
            </span>
          </div>
        )}

        {sessions?.map(s => (
          <div key={s._id} className="sp-row" onClick={() => onSelect(s)}>
            <div className="sp-year">{s.year}</div>
            <div className="sp-event">{s.event}</div>
            <div className="sp-type">{s.session_type}</div>
            <div className="sp-drivers">{s.drivers?.length ?? 0}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
