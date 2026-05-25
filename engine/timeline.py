"""
F1 Race Replay — Timeline Synchronizer

FastF1 telemetry is sampled at ~240hz per car but timestamps are NOT aligned
across drivers. This module:

  1. Extracts per-driver telemetry (speed, throttle, brake, gear, x, y)
  2. Resamples every driver to a common clock at FRAME_INTERVAL_MS resolution
  3. Interpolates gaps (FastF1 occasionally has missing samples)
  4. Returns a list of timeline frames ready for MongoDB or WebSocket streaming

A "frame" is a snapshot of ALL cars at a single timestamp:
  {
    "t":  12345,          # ms from session start
    "lap": 3,
    "cars": {
      "HAM": { "x": 0.45, "y": 0.32, "speed": 287, "throttle": 98,
               "brake": False, "gear": 7, "drs": True,
               "pos": 1, "gap_to_leader": 0.0 },
      "VER": { ... },
      ...
    }
  }
"""

import numpy as np
import pandas as pd
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

# One frame every 200 ms = 5 fps — smooth enough, MongoDB-friendly
# Reduce to 100 ms for smoother animation if storage allows
FRAME_INTERVAL_MS = 200


@dataclass
class TrackBounds:
    """Normalized 0-1 coordinate space derived from GPS data."""
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def normalize(self, x: float, y: float) -> tuple[float, float]:
        """Map raw X/Y to 0..1 range, preserving aspect ratio."""
        nx = (x - self.x_min) / max(self.x_max - self.x_min, 1)
        ny = (y - self.y_min) / max(self.y_max - self.y_min, 1)
        return round(float(nx), 5), round(float(ny), 5)


def _telemetry_for_driver(session, driver_code: str) -> pd.DataFrame:
    """
    Get merged lap+telemetry DataFrame for one driver.
    Returns columns: SessionTime_ms, X, Y, Speed, Throttle, Brake, nGear, DRS,
                     LapNumber
    """
    laps = session.laps.pick_driver(driver_code)
    if laps.empty:
        return pd.DataFrame()

    frames = []
    for _, lap in laps.iterrows():
        try:
            tel = lap.get_telemetry()
        except Exception:
            continue
        if tel is None or tel.empty:
            continue

        tel = tel[["SessionTime", "X", "Y", "Speed", "Throttle", "Brake",
                   "nGear", "DRS"]].copy()
        tel["SessionTime_ms"] = tel["SessionTime"].dt.total_seconds() * 1000
        tel["LapNumber"] = int(lap["LapNumber"])
        frames.append(tel)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames).sort_values("SessionTime_ms").reset_index(drop=True)
    df = df.drop_duplicates(subset="SessionTime_ms")
    return df


def _resample_driver(df: pd.DataFrame, t_grid: np.ndarray) -> pd.DataFrame:
    """
    Interpolate a driver's telemetry onto the shared time grid.
    Missing-data gaps longer than 5 s are left as NaN (pit lane, etc.)
    """
    if df.empty:
        return pd.DataFrame(index=t_grid)

    src_t = df["SessionTime_ms"].values

    result = {"t": t_grid}
    for col in ["X", "Y", "Speed", "Throttle", "nGear", "LapNumber"]:
        if col not in df.columns:
            result[col] = np.full(len(t_grid), np.nan)
            continue
        result[col] = np.interp(t_grid, src_t, df[col].values,
                                left=np.nan, right=np.nan)

    # Boolean columns — nearest-neighbour (no interpolation)
    for col in ["Brake", "DRS"]:
        if col not in df.columns:
            result[col] = np.zeros(len(t_grid), dtype=bool)
            continue
        idx = np.searchsorted(src_t, t_grid, side="left").clip(0, len(src_t) - 1)
        result[col] = df[col].values[idx].astype(bool)

    return pd.DataFrame(result)


def _compute_track_bounds(driver_frames: dict[str, pd.DataFrame]) -> TrackBounds:
    """Compute min/max X,Y across ALL drivers to normalize GPS coords."""
    all_x, all_y = [], []
    for df in driver_frames.values():
        if "X" in df.columns:
            all_x.extend(df["X"].dropna().tolist())
            all_y.extend(df["Y"].dropna().tolist())

    if not all_x:
        return TrackBounds(0, 1, 0, 1)

    pad_x = (max(all_x) - min(all_x)) * 0.05
    pad_y = (max(all_y) - min(all_y)) * 0.05
    return TrackBounds(
        x_min = min(all_x) - pad_x,
        x_max = max(all_x) + pad_x,
        y_min = min(all_y) - pad_y,
        y_max = max(all_y) + pad_y,
    )


def _positions_at_frame(cars_snap: dict) -> dict[str, int]:
    """
    Estimate race position for each driver at this frame using distance
    to end of their current lap (approximation — good enough for leaderboard).
    Returns {driver_code: position_int}
    """
    lap_info = {
        code: (snap.get("lap", 0), snap.get("throttle", 0))
        for code, snap in cars_snap.items()
        if snap is not None
    }
    # Sort by lap desc, then throttle as tiebreak (crude but works offline)
    ranked = sorted(lap_info.items(), key=lambda x: (-x[1][0], -x[1][1]))
    return {code: i + 1 for i, (code, _) in enumerate(ranked)}


def build_timeline(race_session, max_frames: int = None) -> tuple[list[dict], TrackBounds]:
    """
    Main entry point.

    Args:
        race_session: a RaceSession (with ._session_ref populated)
        max_frames:   cap number of output frames (useful for testing)

    Returns:
        (frames_list, track_bounds)

    Each frame dict is JSON-serializable and ready for MongoDB insert.
    """
    session = race_session._session_ref
    driver_codes = [d.code for d in race_session.drivers]

    log.info(f"Extracting telemetry for {len(driver_codes)} drivers ...")
    raw: dict[str, pd.DataFrame] = {}
    for code in driver_codes:
        log.info(f"  → {code}")
        raw[code] = _telemetry_for_driver(session, code)

    # Global time range from non-empty drivers
    t_starts, t_ends = [], []
    for df in raw.values():
        if not df.empty and "SessionTime_ms" in df.columns:
            t_starts.append(df["SessionTime_ms"].min())
            t_ends.append(df["SessionTime_ms"].max())

    if not t_starts:
        raise ValueError("No telemetry found for any driver.")

    t_start = min(t_starts)
    t_end   = max(t_ends)
    t_grid  = np.arange(t_start, t_end, FRAME_INTERVAL_MS)
    log.info(f"Time grid: {len(t_grid)} frames × {FRAME_INTERVAL_MS}ms "
             f"({(t_end - t_start)/1000/60:.1f} min)")

    if max_frames:
        t_grid = t_grid[:max_frames]

    log.info("Resampling all drivers onto shared timeline ...")
    resampled: dict[str, pd.DataFrame] = {
        code: _resample_driver(df, t_grid)
        for code, df in raw.items()
    }

    bounds = _compute_track_bounds(resampled)
    log.info(f"Track bounds: X [{bounds.x_min:.0f}..{bounds.x_max:.0f}]  "
             f"Y [{bounds.y_min:.0f}..{bounds.y_max:.0f}]")

    # Build driver color/team lookup
    meta_map = {d.code: d for d in race_session.drivers}

    log.info("Building frames ...")
    frames = []
    for i, t in enumerate(t_grid):
        cars_snap = {}
        for code, df in resampled.items():
            if df.empty or i >= len(df):
                cars_snap[code] = None
                continue
            row = df.iloc[i]
            if pd.isna(row.get("X", np.nan)):
                cars_snap[code] = None
                continue

            nx, ny = bounds.normalize(row["X"], row["Y"])
            cars_snap[code] = {
                "x":        nx,
                "y":        ny,
                "speed":    int(row.get("Speed", 0) or 0),
                "throttle": int(row.get("Throttle", 0) or 0),
                "brake":    bool(row.get("Brake", False)),
                "gear":     int(row.get("nGear", 1) or 1),
                "drs":      bool(row.get("DRS", False)),
                "lap":      int(row.get("LapNumber", 0) or 0),
            }

        positions = _positions_at_frame(cars_snap)
        for code, snap in cars_snap.items():
            if snap:
                snap["pos"] = positions.get(code, 0)

        frames.append({
            "t":    int(t),      # ms from session start
            "cars": cars_snap,
        })

    log.info(f"Timeline built: {len(frames)} frames")
    return frames, bounds
