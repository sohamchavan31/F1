import { useState, useEffect, useRef, useCallback } from 'react'

export function useReplay(sessionId) {
  const ws          = useRef(null)
  const [state, setState]       = useState('idle')   // idle|playing|paused|ended
  const [frame, setFrame]       = useState(null)
  const [currentT, setCurrentT] = useState(0)
  const [speed, setSpeedState]  = useState(1.0)
  const [tMin, setTMin]         = useState(0)
  const [tMax, setTMax]         = useState(0)
  const [connected, setConnected] = useState(false)

  // Fetch t-range from first/last frames when session changes
  useEffect(() => {
    if (!sessionId) return
    Promise.all([
      fetch(`/api/frame/${sessionId}/0/`).catch(() => null),  // won't exist but fine
      fetch(`/api/sessions/${sessionId}/`),
    ]).then(async ([, sessRes]) => {
      if (!sessRes.ok) return
      // tMin/tMax will be discovered from first frames received
    })
  }, [sessionId])

  useEffect(() => {
    if (!sessionId) return

    const url = `ws://${location.hostname}:8000/ws/replay/${sessionId}/`
    const socket = new WebSocket(url)
    ws.current = socket

    socket.onopen  = () => setConnected(true)
    socket.onclose = () => { setConnected(false); setState('idle') }

    socket.onmessage = (evt) => {
      const msg = JSON.parse(evt.data)
      if (msg.type === 'frame') {
        const { type, ...f } = msg
        setFrame(f)
        setCurrentT(f.t)
        setTMin(prev => prev === 0 ? f.t : Math.min(prev, f.t))
        setTMax(prev => Math.max(prev, f.t))
      } else if (msg.type === 'status') {
        setState(msg.state)
        setCurrentT(msg.t ?? 0)
        if (msg.speed) setSpeedState(msg.speed)
      }
    }

    return () => socket.close()
  }, [sessionId])

  const send = useCallback((msg) => {
    if (ws.current?.readyState === WebSocket.OPEN)
      ws.current.send(JSON.stringify(msg))
  }, [])

  const play  = useCallback((t = currentT) => send({ action: 'play',   session_id: sessionId, t_start: t, speed }), [send, sessionId, currentT, speed])
  const pause = useCallback(() => send({ action: 'pause' }), [send])
  const resume= useCallback(() => send({ action: 'resume' }), [send])
  const seek  = useCallback((t) => { setCurrentT(t); send({ action: 'seek', t }) }, [send])
  const setSpeed = useCallback((s) => { setSpeedState(s); send({ action: 'speed', speed: s }) }, [send])

  return { connected, state, frame, currentT, tMin, tMax, speed, play, pause, resume, seek, setSpeed }
}
