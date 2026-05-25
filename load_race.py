"""
F1 Race Replay — Race Loader Pipeline

Usage:
    python load_race.py --year 2024 --event Monaco --session Race
    python load_race.py --year 2024 --event Monza  --session Race --test

--test flag loads only the first 300 frames (~1 min of race) for quick testing.
"""

import argparse
import logging
import time

from engine.loader  import load_session
from engine.timeline import build_timeline
from engine.storage  import (
    get_db, ensure_indexes,
    upsert_session, insert_frames, upsert_track_map,
)

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt = "%H:%M:%S",
)
log = logging.getLogger(__name__)


def run(year: int, event: str, session_type: str, test_mode: bool):
    t0 = time.time()

    # 1. Download + parse via FastF1
    race_session = load_session(year, event, session_type)

    # 2. Build unified timeline
    max_frames = 300 if test_mode else None
    frames, track_bounds = build_timeline(race_session, max_frames=max_frames)

    # 3. Save to MongoDB
    db = get_db()
    ensure_indexes(db)
    session_id = upsert_session(db, race_session, track_bounds)
    insert_frames(db, session_id, frames)
    upsert_track_map(db, race_session, track_bounds)

    elapsed = time.time() - t0
    log.info(f"✓ Pipeline complete in {elapsed:.1f}s")
    log.info(f"  Session ID : {session_id}")
    log.info(f"  Frames     : {len(frames)}")
    log.info(f"  Drivers    : {[d.code for d in race_session.drivers]}")
    if test_mode:
        log.info("  (test mode — first 300 frames only)")

    return session_id


def main():
    ap = argparse.ArgumentParser(description="Load an F1 race into MongoDB")
    ap.add_argument("--year",    type=int, default=2024,   help="Season year")
    ap.add_argument("--event",   type=str, default="Monaco", help="Event name e.g. Monaco")
    ap.add_argument("--session", type=str, default="Race",  help="Race | Qualifying | Sprint")
    ap.add_argument("--test",    action="store_true",       help="Load only 300 frames")
    args = ap.parse_args()

    run(args.year, args.event, args.session, args.test)


if __name__ == "__main__":
    main()