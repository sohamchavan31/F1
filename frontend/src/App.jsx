import { useState, useEffect } from 'react'
import './terminal.css'

import SessionPicker   from './components/SessionPicker'
import TrackMap        from './components/TrackMap'
import Leaderboard     from './components/Leaderboard'
import TelemetryPanel  from './components/TelemetryPanel'
import ReplayControls  from './components/ReplayControls'
import Encyclopedia    from './components/Encyclopedia'
import { useReplay }   from './hooks/useReplay'

export default function App() {
  const [session, setSession]               = useState(null)
  const [selectedDriver, setSelectedDriver] = useState(null)

  const {
    connected, state, frame, currentT, tMin, tMax, speed,
    play, pause, resume, seek, setSpeed,
  } = useReplay(session?._id)

  // Build enriched cars map: merge frame data with session driver colors
  const driverColorMap = {}
  session?.drivers?.forEach(d => { driverColorMap[d.code] = d.color })

  const enrichedCars = frame?.cars
    ? Object.fromEntries(
        Object.entries(frame.cars).map(([code, car]) => [
          code,
          car ? { ...car, color: driverColorMap[code] ?? '#00ff41' } : null
        ])
      )
    : null

  // Auto-select lead driver if none selected
  useEffect(() => {
    if (!enrichedCars || selectedDriver) return
    const leader = Object.entries(enrichedCars)
      .filter(([, c]) => c !== null)
      .sort((a, b) => (a[1].pos ?? 99) - (b[1].pos ?? 99))[0]
    if (leader) setSelectedDriver(leader[0])
  }, [enrichedCars, selectedDriver])

  if (!session) return <SessionPicker onSelect={setSession} />

  const statusClass = { playing: 'live', paused: 'paused', ended: 'ended' }[state] ?? ''

  return (
    <div className="app">
      {/* ── Title bar ── */}
      <div className="titlebar">
        <div className="titlebar-logo"><em>F1</em>_REPLAY.exe</div>
        <div className="titlebar-session">
          SESSION: <strong>{session.year} {session.event} {session.session_type}</strong>
        </div>
        <div className="titlebar-status">
          <span>
            <span className={`status-dot ${statusClass}`} />
            {state.toUpperCase()}
          </span>
          <span style={{ color: connected ? 'var(--green)' : 'var(--red)' }}>
            {connected ? '⬤ WS LIVE' : '○ WS OFF'}
          </span>
          <button
            style={{
              background: 'none', border: '1px solid var(--text-dim)',
              color: 'var(--text-dim)', fontFamily: 'var(--font)',
              fontSize: 10, padding: '2px 8px', cursor: 'pointer'
            }}
            onClick={() => { setSession(null); setSelectedDriver(null) }}
          >
            ← SESSIONS
          </button>
        </div>
      </div>

      {/* ── Track map ── */}
      <TrackMap
        event={session.event}
        year={session.year}
        cars={enrichedCars}
        selectedDriver={selectedDriver}
        onSelectDriver={setSelectedDriver}
      />

      {/* ── Leaderboard ── */}
      <Leaderboard
        cars={enrichedCars}
        selectedDriver={selectedDriver}
        onSelect={setSelectedDriver}
      />

      {/* ── Replay controls ── */}
      <ReplayControls
        state={state}
        currentT={currentT}
        tMin={tMin}
        tMax={tMax}
        speed={speed}
        onPlay={play}
        onPause={pause}
        onResume={resume}
        onSeek={seek}
        onSpeed={setSpeed}
      />

      {/* ── Telemetry (right column) ── */}
      <TelemetryPanel cars={enrichedCars} selectedDriver={selectedDriver} />

      {/* ── Encyclopedia (bottom bar) ── */}
      <Encyclopedia />
    </div>
  )
}
