"""
F1 Race Replay — MongoDB Storage

Collections:
  sessions   — one doc per race session (metadata + driver list)
  frames     — one doc per timeline frame (bulk-inserted in chunks)
  track_maps — one doc per circuit (normalized GPS path for SVG rendering)

Uses pymongo (sync) for the loader/ingest scripts.
Django views use motor (async) — see motor_db() below.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection

log = logging.getLogger(__name__)

MONGO_URI  = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME    = os.getenv("F1_DB_NAME", "f1_replay")

# Chunk size for bulk frame inserts — keeps memory stable
CHUNK_SIZE = 500


def get_db():
    """Sync pymongo client — use in scripts and management commands."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client[DB_NAME]


def ensure_indexes(db):
    """Create indexes once — idempotent."""
    db.sessions.create_index(
        [("year", ASCENDING), ("event", ASCENDING), ("session_type", ASCENDING)],
        unique=True,
        name="session_unique",
    )
    db.frames.create_index(
        [("session_id", ASCENDING), ("t", ASCENDING)],
        name="session_time",
    )
    db.frames.create_index(
        [("session_id", ASCENDING)],
        name="session_id_only",
    )
    db.track_maps.create_index(
        [("event", ASCENDING), ("year", ASCENDING)],
        unique=True,
        name="track_unique",
    )
    log.info("Indexes OK")


# ── Session ───────────────────────────────────────────────────────────────────

def upsert_session(db, race_session, track_bounds) -> str:
    """
    Insert or update a session document.
    Returns the session_id (str of _id).
    """
    drivers_data = [
        {
            "code":      d.code,
            "full_name": d.full_name,
            "team":      d.team,
            "color":     d.color,
            "number":    d.number,
        }
        for d in race_session.drivers
    ]

    doc = {
        "year":           race_session.year,
        "event":          race_session.event,
        "session_type":   race_session.session_type,
        "total_laps":     race_session.total_laps,
        "session_start_ms": race_session.session_start_ms,
        "drivers":        drivers_data,
        "track_bounds":   {
            "x_min": track_bounds.x_min,
            "x_max": track_bounds.x_max,
            "y_min": track_bounds.y_min,
            "y_max": track_bounds.y_max,
        },
        "loaded_at": datetime.now(timezone.utc).isoformat(),
    }

    result = db.sessions.find_one_and_update(
        {
            "year":         race_session.year,
            "event":        race_session.event,
            "session_type": race_session.session_type,
        },
        {"$set": doc},
        upsert=True,
        return_document=True,
    )
    session_id = str(result["_id"])
    log.info(f"Session upserted → {session_id}")
    return session_id


def get_session(db, year: int, event: str, session_type: str = "Race") -> dict | None:
    return db.sessions.find_one({
        "year": year, "event": event, "session_type": session_type
    })


def list_sessions(db) -> list[dict]:
    return list(db.sessions.find({}, {"drivers": 0}).sort("year", -1))


# ── Frames ────────────────────────────────────────────────────────────────────

def insert_frames(db, session_id: str, frames: list[dict]):
    """
    Bulk-insert timeline frames in chunks.
    Deletes existing frames for this session first (clean re-load).
    """
    col: Collection = db.frames
    log.info(f"Deleting old frames for session {session_id} ...")
    col.delete_many({"session_id": session_id})

    total = len(frames)
    inserted = 0
    for i in range(0, total, CHUNK_SIZE):
        chunk = frames[i : i + CHUNK_SIZE]
        docs  = [{"session_id": session_id, **f} for f in chunk]
        col.insert_many(docs, ordered=False)
        inserted += len(chunk)
        pct = inserted / total * 100
        if inserted % 5000 == 0 or inserted == total:
            log.info(f"  Frames inserted: {inserted}/{total}  ({pct:.0f}%)")

    log.info(f"Frames done: {inserted} total")


def get_frames_range(db, session_id: str, t_start: int, t_end: int) -> list[dict]:
    """Fetch frames in a time range (ms). Used by WebSocket consumer."""
    return list(db.frames.find(
        {"session_id": session_id, "t": {"$gte": t_start, "$lte": t_end}},
        {"_id": 0},
    ).sort("t", ASCENDING))


def get_frame_at(db, session_id: str, t: int) -> dict | None:
    """Get the single closest frame at or before timestamp t."""
    return db.frames.find_one(
        {"session_id": session_id, "t": {"$lte": t}},
        {"_id": 0},
        sort=[("t", -1)],
    )


# ── Track map ─────────────────────────────────────────────────────────────────

def _extract_track_path(race_session, track_bounds) -> list[dict]:
    """
    Extract the track centre-line from the fastest qualifier's flying lap.
    Returns a list of {x, y} normalized points for SVG <polyline>.
    """
    from engine.timeline import _telemetry_for_driver
    session = race_session._session_ref

    best_driver = None
    best_len    = 0

    for d in race_session.drivers:
        try:
            laps = session.laps.pick_driver(d.code)
            fastest = laps.pick_fastest()
            tel = fastest.get_telemetry()
            if tel is not None and len(tel) > best_len:
                best_len    = len(tel)
                best_driver = (d.code, fastest)
        except Exception:
            continue

    if not best_driver:
        return []

    code, lap = best_driver
    tel = lap.get_telemetry()[["X", "Y"]].dropna()

    # Smooth the path with a rolling mean
    tel["X"] = tel["X"].rolling(5, center=True, min_periods=1).mean()
    tel["Y"] = tel["Y"].rolling(5, center=True, min_periods=1).mean()

    points = []
    prev = None
    for _, row in tel.iterrows():
        nx, ny = track_bounds.normalize(row["X"], row["Y"])
        pt = {"x": nx, "y": ny}
        # Deduplicate nearly-identical consecutive points
        if prev and abs(nx - prev["x"]) < 0.001 and abs(ny - prev["y"]) < 0.001:
            continue
        points.append(pt)
        prev = pt

    return points


def upsert_track_map(db, race_session, track_bounds):
    """Save the track SVG path points to MongoDB."""
    log.info("Extracting track map path ...")
    points = _extract_track_path(race_session, track_bounds)
    if not points:
        log.warning("No track path extracted")
        return

    doc = {
        "event":    race_session.event,
        "year":     race_session.year,
        "points":   points,
        "n_points": len(points),
    }
    db.track_maps.find_one_and_update(
        {"event": race_session.event, "year": race_session.year},
        {"$set": doc},
        upsert=True,
    )
    log.info(f"Track map saved: {len(points)} points")


def get_track_map(db, event: str, year: int = None) -> dict | None:
    query = {"event": event}
    if year:
        query["year"] = year
    return db.track_maps.find_one(query, {"_id": 0}, sort=[("year", -1)])
