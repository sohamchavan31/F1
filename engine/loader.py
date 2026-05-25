"""
F1 Race Replay — Telemetry Loader
Downloads and parses FastF1 data for a given race session.
"""

import fastf1
import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Any
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# FastF1 cache — avoids re-downloading (put this anywhere writable)
CACHE_DIR = Path(__file__).parent.parent / "data_cache"
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))


# ── Team colours (2026 approximate) ──────────────────────────────────────────
TEAM_COLORS = {
    "Mercedes":          "#00D2BE",
    "Ferrari":           "#E8002D",
    "Red Bull Racing":   "#3671C6",
    "McLaren":           "#FF8000",
    "Aston Martin":      "#229971",
    "Alpine":            "#0093CC",
    "Williams":          "#64C4FF",
    "Haas F1 Team":      "#B6BABD",
    "Kick Sauber":       "#52E252",
    "Racing Bulls":      "#6692FF",
    "Audi":              "#C0C0C0",
    "Cadillac":          "#D4AF37",
}


@dataclass
class DriverMeta:
    code:        str          # e.g. "HAM"
    full_name:   str
    team:        str
    color:       str          # hex
    number:      int


@dataclass
class RaceSession:
    year:             int
    event:            str          # e.g. "Monaco"
    session_type:     str         # "Race" | "Qualifying" | "Sprint"
    drivers:          list[DriverMeta]
    total_laps:       int
    session_start_ms: int         # unix ms of session t=0
    raw_laps:         Any = field(repr=False, default=None)
    raw_weather:      Any = field(repr=False, default=None)
    _session_ref:     Any = field(repr=False, default=None)


def load_session(year: int, event: str, session_type: str = "Race") -> RaceSession:
    """
    Load a FastF1 session and return a RaceSession with metadata.
    Example:
        sess = load_session(2024, "Monaco", "Race")
    """
    log.info(f"Loading {year} {event} {session_type} ...")
    session = fastf1.get_session(year, event, session_type)
    session.load(telemetry=True, weather=True, messages=True)
    log.info("Session loaded OK")

    # Build driver metadata list
    drivers: list[DriverMeta] = []
    for drv in session.drivers:
        info = session.get_driver(drv)
        team = info.get("TeamName", "Unknown")
        drivers.append(DriverMeta(
            code      = info.get("Abbreviation", drv),
            full_name = info.get("FullName", ""),
            team      = team,
            color     = TEAM_COLORS.get(team, "#AAAAAA"),
            number    = int(info.get("DriverNumber", 0)),
        ))

    # Session t=0 in unix ms
    t0 = session.session_start_time
    start_ms = int(t0.timestamp() * 1000) if hasattr(t0, "timestamp") else 0

    return RaceSession(
        year             = year,
        event            = event,
        session_type     = session_type,
        drivers          = drivers,
        total_laps       = int(session.laps["LapNumber"].max()) if len(session.laps) else 0,
        session_start_ms = start_ms,
        raw_laps         = session.laps,
        raw_weather      = session.weather_data,
        _session_ref     = session,
    )
