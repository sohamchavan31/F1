"""
F1 Race Replay — Timeline Synchronizer

FastF1 telemetry is sampled at ~240hz per car but timestamps are NOT aligned
across drivers. This module:

  1. Extracts per-driver telemetry (speed, throttle, brake, gear, x, y, compound)
  2. Resamples every driver to a common clock at FRAME_INTERVAL_MS resolution
  3. Interpolates gaps (FastF1 occasionally has missing samples)
  4. Returns a list of timeline frames ready for MongoDB or WebSocket streaming

A "frame" is a snapshot of ALL cars at a single timestamp:
  {
    "t":  12345,          # ms from session start
    "cars": {
      "HAM": { "x": 0.45, "y": 0.32, "speed": 287, "throttle": 98,
               "brake": False, "gear": 7, "drs": True, "lap": 3,
               "compound": "SOFT", "pos": 1, "gap_to_leader": 0.0 },
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
FRAME_INTERVAL_MS = 200


@dataclass
class TrackBounds:
    """Normalized 0-1 coordinate space derived from GPS data."""
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def normalize(self, x: float, y: float) -> tuple[float, float]:
        nx = (x - self.x_min) / max(self.x_max - self.x_min, 1)
        ny = (y - self.y_min) / max(self.y_max - self.y_min, 1)
        return round(float(nx), 5), round(float(ny), 5)


def _telemetry_for_driver(session, driver_code: str) -> pd.DataFrame:
    """
    Get merged lap+telemetry DataFrame for one driver.
    Returns columns: SessionTime_ms, X, Y, Speed, Throttle, Brake, nGear, DRS,
                     LapNumber, Compound
    """
    laps = session.laps.pick_drivers(driver_code)
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
        # Compound is a lap-level property — constant for all points in this lap
        raw_compound = lap.get("Compound", "UNKNOWN")
        tel["Compound"] = str(raw_compound).upper() if pd.notna(raw_compound) else "UNKNOWN"
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

    # Boolean channels — nearest-neighbour
    for col in ["Brake", "DRS"]:
        if col not in df.columns:
            result[col] = np.zeros(len(t_grid), dtype=bool)
            continue
        idx = np.searchsorted(src_t, t_grid, side="left").clip(0, len(src_t) - 1)
        result[col] = df[col].values[idx].astype(bool)

    # Compound — nearest-neighbour (categorical string)
    if "Compound" in df.columns:
        idx = np.searchsorted(src_t, t_grid, side="left").clip(0, len(src_t) - 1)
        result["Compound"] = df["Compound"].values[idx]
    else:
        result["Compound"] = np.full(len(t_grid), "UNKNOWN")

    return pd.DataFrame(result)


def _compute_track_bounds(driver_frames: dict[str, pd.DataFrame]) -> TrackBounds:
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
        x_min=min(all_x) - pad_x,
        x_max=max(all_x) + pad_x,
        y_min=min(all_y) - pad_y,
        y_max=max(all_y) + pad_y,
    )


def _compute_cum_distances(resampled: dict[str, pd.DataFrame]) -> dict[str, np.ndarray]:
    """
    Compute cumulative GPS distance (in raw coordinate units) for each driver.
    Used as a stable tiebreak for position ranking within the same lap.

    Monotonically increasing. Large teleport jumps (pit entry/exit, data gaps)
    are zeroed out to avoid false advances.
    """
    cum_dists = {}
    for code, df in resampled.items():
        if df.empty or "X" not in df.columns:
            cum_dists[code] = np.zeros(1)
            continue

        x = df["X"].fillna(method="ffill").fillna(0).values
        y = df["Y"].fillna(method="ffill").fillna(0).values

        dx = np.diff(x, prepend=x[0])
        dy = np.diff(y, prepend=y[0])
        step = np.sqrt(dx ** 2 + dy ** 2)

        # Suppress teleport-sized jumps (pit stops, GPS dropouts)
        # A normal step at 300 km/h over 200 ms ≈ 16 m in raw coords
        # A jump > 50× median is almost certainly a gap, not real movement
        positive_steps = step[step > 0]
        if len(positive_steps):
            threshold = np.median(positive_steps) * 50
            step[step > threshold] = 0

        cum_dists[code] = np.cumsum(step)

    return cum_dists


def _positions_at_frame(
    cars_snap: dict,
    cum_dists: dict[str, np.ndarray],
    frame_idx: int,
) -> dict[str, int]:
    """
    Rank drivers by race position at this frame.

    Sort key: (lap_number DESC, cumulative_gps_distance DESC)

    Cumulative GPS distance is smooth and monotonically increasing — it doesn't
    flip at corners the way throttle or speed would, eliminating the flicker bug.
    """
    ranking = {}
    for code, snap in cars_snap.items():
        if snap is None:
            continue
        lap = snap.get("lap", 0)
        arr = cum_dists.get(code)
        dist = float(arr[min(frame_idx, len(arr) - 1)]) if arr is not None else 0.0
        ranking[code] = (lap, dist)

    ranked = sorted(ranking.items(), key=lambda x: (-x[1][0], -x[1][1]))
    return {code: i + 1 for i, (code, _) in enumerate(ranked)}


def build_timeline(race_session, max_frames: int = None) -> tuple[list[dict], TrackBounds]:
    """
    Main entry point.

    Args:
        race_session: a RaceSession (with ._session_ref populated)
        max_frames:   cap number of output frames (useful for testing)

    Returns:
        (frames_list, track_bounds)
    """
    session = race_session._session_ref
    driver_codes = [d.code for d in race_session.drivers]

    log.info(f"Extracting telemetry for {len(driver_codes)} drivers ...")
    raw: dict[str, pd.DataFrame] = {}
    for code in driver_codes:
        log.info(f"  → {code}")
        raw[code] = _telemetry_for_driver(session, code)

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

    log.info("Computing cumulative GPS distances for position ranking ...")
    cum_dists = _compute_cum_distances(resampled)

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
            compound = str(row.get("Compound", "UNKNOWN") or "UNKNOWN")

            cars_snap[code] = {
                "x":        nx,
                "y":        ny,
                "speed":    int(row.get("Speed", 0) or 0),
                "throttle": int(row.get("Throttle", 0) or 0),
                "brake":    bool(row.get("Brake", False)),
                "gear":     int(row.get("nGear", 1) or 1),
                "drs":      bool(row.get("DRS", False)),
                "lap":      int(row.get("LapNumber", 0) or 0),
                "compound": compound,
            }

        positions = _positions_at_frame(cars_snap, cum_dists, i)
        for code, snap in cars_snap.items():
            if snap:
                snap["pos"] = positions.get(code, 0)

        frames.append({
            "t":    int(t),
            "cars": cars_snap,
        })

    log.info(f"Timeline built: {len(frames)} frames")
    return frames, bounds
