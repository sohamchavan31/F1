function formatTime(ms) {
  if (!ms) return '00:00'
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

export default function ReplayControls({
  state, currentT, tMin, tMax, speed,
  onPlay, onPause, onResume, onSeek, onSpeed,
}) {
  const progress = tMax > tMin ? (currentT - tMin) / (tMax - tMin) : 0
  const elapsed  = currentT - tMin

  return (
    <div className="controls-panel">
      {/* Play/Pause */}
      {state === 'idle' && (
        <button className="ctrl-btn" onClick={() => onPlay(tMin)}>▶ PLAY</button>
      )}
      {state === 'playing' && (
        <button className="ctrl-btn active" onClick={onPause}>⏸ PAUSE</button>
      )}
      {state === 'paused' && (
        <>
          <button className="ctrl-btn" onClick={() => onPlay(tMin)}>⏮ RESTART</button>
          <button className="ctrl-btn active" onClick={onResume}>▶ RESUME</button>
        </>
      )}
      {state === 'ended' && (
        <button className="ctrl-btn" onClick={() => onPlay(tMin)}>⏮ REPLAY</button>
      )}

      {/* Elapsed */}
      <span className="ctrl-time">
        {formatTime(elapsed)} / {formatTime(tMax - tMin)}
      </span>

      {/* Seek bar */}
      <input
        type="range"
        className="seek-bar"
        min={tMin}
        max={tMax || tMin + 1}
        value={currentT}
        step={200}
        onChange={e => onSeek(Number(e.target.value))}
      />

      {/* Speed selector */}
      <select
        className="speed-select"
        value={speed}
        onChange={e => onSpeed(Number(e.target.value))}
      >
        <option value={0.25}>0.25×</option>
        <option value={0.5}>0.5×</option>
        <option value={1}>1×</option>
        <option value={2}>2×</option>
        <option value={4}>4×</option>
        <option value={8}>8×</option>
      </select>

      {/* Raw timestamp */}
      <span style={{ color: 'var(--text-dim)', fontSize: 10, minWidth: 60 }}>
        t={currentT}
      </span>
    </div>
  )
}
