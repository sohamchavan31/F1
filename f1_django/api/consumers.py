"""
Django Channels WebSocket consumer — F1 frame streaming.

Protocol
--------
Client → Server (JSON):
  { "action": "play",   "session_id": "<id>", "t_start": 0,    "speed": 1.0 }
  { "action": "pause" }
  { "action": "seek",   "t": 45000 }
  { "action": "speed",  "speed": 2.0 }

Server → Client (JSON):
  { "type": "frame",  "t": 12400, "cars": { ... } }
  { "type": "status", "state": "playing"|"paused"|"ended", "t": 12400 }
  { "type": "error",  "message": "..." }

The consumer streams frames at FRAME_INTERVAL_MS * (1/speed) wall-clock intervals.
MongoDB reads are async via motor; no thread-pool needed.
"""

import asyncio
import json
import logging
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer
from pymongo import ASCENDING

from api.db import get_motor_db

log = logging.getLogger(__name__)

# Must match engine/timeline.py FRAME_INTERVAL_MS
FRAME_INTERVAL_MS = 200

# How many frames to pre-fetch per batch (reduces round-trips)
BATCH_SIZE = 50


class ReplayConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.accept()
        self._state      = "idle"     # idle | playing | paused | ended
        self._session_id = None
        self._t_current  = 0          # current playback position in ms
        self._speed      = 1.0        # playback speed multiplier
        self._play_task: asyncio.Task | None = None
        log.info(f"WS connected: {self.channel_name}")

    async def disconnect(self, close_code):
        self._cancel_play()
        log.info(f"WS disconnected: {self.channel_name}")

    async def receive(self, text_data: str):
        try:
            msg = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error("invalid JSON")
            return

        action = msg.get("action")

        if action == "play":
            session_id = msg.get("session_id")
            if not session_id:
                await self._send_error("session_id required")
                return
            t_start = int(msg.get("t_start", 0))
            speed   = float(msg.get("speed", 1.0))
            await self._start_playback(session_id, t_start, speed)

        elif action == "pause":
            await self._pause()

        elif action == "seek":
            t = int(msg.get("t", self._t_current))
            await self._seek(t)

        elif action == "speed":
            speed = float(msg.get("speed", 1.0))
            await self._set_speed(speed)

        elif action == "resume":
            await self._resume()

        else:
            await self._send_error(f"unknown action: {action}")

    # ── Playback control ──────────────────────────────────────────────────────

    async def _start_playback(self, session_id: str, t_start: int, speed: float):
        self._cancel_play()
        self._session_id = session_id
        self._t_current  = t_start
        self._speed      = max(speed, 0.1)
        self._state      = "playing"
        self._play_task  = asyncio.create_task(self._stream_loop())
        await self._send_status()

    async def _pause(self):
        if self._state == "playing":
            self._cancel_play()
            self._state = "paused"
            await self._send_status()

    async def _resume(self):
        if self._state == "paused" and self._session_id:
            self._state     = "playing"
            self._play_task = asyncio.create_task(self._stream_loop())
            await self._send_status()

    async def _seek(self, t: int):
        was_playing = self._state == "playing"
        self._cancel_play()
        self._t_current = t
        self._state     = "paused"

        # Send the nearest frame immediately so the client can render it
        frame = await self._fetch_frame_at(t)
        if frame:
            await self._send_frame(frame)

        await self._send_status()

        if was_playing:
            self._state     = "playing"
            self._play_task = asyncio.create_task(self._stream_loop())

    async def _set_speed(self, speed: float):
        self._speed = max(speed, 0.1)
        if self._state == "playing":
            # Restart loop so new interval takes effect immediately
            self._cancel_play()
            self._play_task = asyncio.create_task(self._stream_loop())
        await self._send_status()

    def _cancel_play(self):
        if self._play_task and not self._play_task.done():
            self._play_task.cancel()
        self._play_task = None

    # ── Streaming loop ────────────────────────────────────────────────────────

    async def _stream_loop(self):
        """
        Main loop: fetch frames in BATCH_SIZE chunks, send at wall-clock
        intervals determined by FRAME_INTERVAL_MS / speed.
        """
        interval = FRAME_INTERVAL_MS / 1000.0 / self._speed

        try:
            while True:
                batch = await self._fetch_frames_batch(self._t_current, BATCH_SIZE)
                if not batch:
                    self._state = "ended"
                    await self._send_status()
                    return

                for frame in batch:
                    self._t_current = frame["t"]
                    await self._send_frame(frame)
                    await asyncio.sleep(interval)
                    # Re-check speed in case it changed
                    interval = FRAME_INTERVAL_MS / 1000.0 / self._speed

        except asyncio.CancelledError:
            pass  # clean shutdown — _state managed by caller
        except Exception as exc:
            log.exception("Stream error")
            await self._send_error(str(exc))

    # ── MongoDB helpers (async motor) ─────────────────────────────────────────

    async def _fetch_frames_batch(self, t_from: int, limit: int) -> list[dict]:
        db = get_motor_db()
        cursor = db.frames.find(
            {"session_id": self._session_id, "t": {"$gte": t_from}},
            {"_id": 0},
        ).sort("t", ASCENDING).limit(limit)
        return await cursor.to_list(length=limit)

    async def _fetch_frame_at(self, t: int) -> dict | None:
        db = get_motor_db()
        return await db.frames.find_one(
            {"session_id": self._session_id, "t": {"$lte": t}},
            {"_id": 0},
            sort=[("t", -1)],
        )

    # ── Message helpers ───────────────────────────────────────────────────────

    async def _send_frame(self, frame: dict):
        await self.send(json.dumps({"type": "frame", **frame}))

    async def _send_status(self):
        await self.send(json.dumps({
            "type":  "status",
            "state": self._state,
            "t":     self._t_current,
            "speed": self._speed,
        }))

    async def _send_error(self, message: str):
        await self.send(json.dumps({"type": "error", "message": message}))
