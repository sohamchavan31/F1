"""
F1 Bulk Replay Loader — loads every session into MongoDB.

Resume-safe: sessions already in MongoDB are skipped automatically.
FastF1 telemetry is reliable from 2018 onwards.

Usage:
    python bulk_load.py                          # 2018 → current year, all sessions
    python bulk_load.py --from-year 2018         # explicit start year
    python bulk_load.py --to-year 2023           # stop at 2023
    python bulk_load.py --year 2023              # single year only
    python bulk_load.py --session Race           # Race only (skip Qualifying/Sprint)
    python bulk_load.py --dry-run                # show what would load, touch nothing
    python bulk_load.py --status                 # show what's already loaded
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

import fastf1

from engine.loader   import load_session
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

# ── Constants ─────────────────────────────────────────────────────────────────
CURRENT_YEAR       = datetime.now(timezone.utc).year
TELEMETRY_MIN_YEAR = 2018   # FastF1 telemetry reliable from here

# Session types tried per event (sprint only added when event supports it)
BASE_SESSIONS = ["Race", "Qualifying"]


# ── Schedule helpers ──────────────────────────────────────────────────────────

def get_year_schedule(year: int) -> list[tuple[str, list[str]]]:
    """
    Return [(event_name, [session_types]), ...] for the given year.
    Skips testing events.
    """
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
    except Exception as e:
        log.warning(f"  Could not fetch schedule for {year}: {e}")
        return []

    events = []
    for _, row in schedule.iterrows():
        fmt   = str(row.get("EventFormat", "conventional")).lower()
        name  = row.get("EventName") or row.get("OfficialEventName") or str(row.get("RoundNumber"))
        sessions = list(BASE_SESSIONS)
        if "sprint" in fmt:
            sessions.append("Sprint")
        events.append((name, sessions))
    return events


def is_loaded(db, year: int, event: str, session_type: str) -> bool:
    """True if the session already has frames in MongoDB."""
    sess = db.sessions.find_one(
        {"year": year, "event": event, "session_type": session_type},
        {"_id": 1}
    )
    if not sess:
        return False
    count = db.frames.count_documents({"session_id": str(sess["_id"])}, limit=1)
    return count > 0


# ── Load one session ──────────────────────────────────────────────────────────

def load_one(db, year: int, event: str, session_type: str) -> bool:
    """
    Load a single session. Returns True on success, False on failure.
    """
    t0 = time.time()
    try:
        race_session = load_session(year, event, session_type)
        frames, track_bounds = build_timeline(race_session)
        session_id = upsert_session(db, race_session, track_bounds)
        insert_frames(db, session_id, frames)
        upsert_track_map(db, race_session, track_bounds)
        elapsed = time.time() - t0
        log.info(f"  DONE  {year} {event} {session_type}  "
                 f"({len(frames)} frames, {elapsed:.0f}s)")
        return True
    except Exception as exc:
        log.error(f"  FAIL  {year} {event} {session_type}: {exc}")
        return False


# ── Status report ─────────────────────────────────────────────────────────────

def print_status(db, from_year: int, to_year: int, session_filter: str | None):
    log.info("=== Load Status ===")
    total = loaded = 0
    for year in range(from_year, to_year + 1):
        events = get_year_schedule(year)
        for event, sessions in events:
            for stype in sessions:
                if session_filter and stype != session_filter:
                    continue
                total += 1
                if is_loaded(db, year, event, stype):
                    loaded += 1
                    log.info(f"  [OK]   {year}  {event}  {stype}")
                else:
                    log.info(f"  [    ] {year}  {event}  {stype}")
    log.info(f"=== {loaded}/{total} sessions loaded ===")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Bulk-load all F1 sessions into MongoDB")
    ap.add_argument("--year",       type=int, help="Load a single year only")
    ap.add_argument("--from-year",  type=int, default=TELEMETRY_MIN_YEAR,
                    help=f"Start year (default {TELEMETRY_MIN_YEAR})")
    ap.add_argument("--to-year",    type=int, default=CURRENT_YEAR,
                    help=f"End year (default {CURRENT_YEAR})")
    ap.add_argument("--session",    type=str, choices=["Race","Qualifying","Sprint"],
                    help="Only load this session type")
    ap.add_argument("--dry-run",    action="store_true",
                    help="Show what would be loaded without doing anything")
    ap.add_argument("--status",     action="store_true",
                    help="Show which sessions are already loaded")
    ap.add_argument("--force",      action="store_true",
                    help="Re-load sessions that are already in MongoDB")
    args = ap.parse_args()

    from_year = args.year or args.from_year
    to_year   = args.year or args.to_year

    if from_year < TELEMETRY_MIN_YEAR:
        log.warning(f"FastF1 telemetry is unreliable before {TELEMETRY_MIN_YEAR}. "
                    f"Sessions before that year may have no position data.")

    db = get_db()
    ensure_indexes(db)

    if args.status:
        print_status(db, from_year, to_year, args.session)
        return

    # Build full work list
    work = []
    for year in range(from_year, to_year + 1):
        log.info(f"Fetching {year} schedule ...")
        events = get_year_schedule(year)
        if not events:
            log.warning(f"  No events found for {year}")
            continue
        for event, sessions in events:
            for stype in sessions:
                if args.session and stype != args.session:
                    continue
                if not args.force and is_loaded(db, year, event, stype):
                    log.info(f"  SKIP  {year} {event} {stype}  (already loaded)")
                    continue
                work.append((year, event, stype))

    total   = len(work)
    log.info(f"\n{'DRY RUN — ' if args.dry_run else ''}"
             f"{total} sessions to load\n")

    if args.dry_run:
        for year, event, stype in work:
            print(f"  {year}  {event}  {stype}")
        return

    success = failure = 0
    for i, (year, event, stype) in enumerate(work, 1):
        log.info(f"[{i}/{total}]  Loading {year} {event} {stype} ...")
        if load_one(db, year, event, stype):
            success += 1
        else:
            failure += 1
        # Brief pause between sessions to avoid hammering the FastF1 API
        if i < total:
            time.sleep(2)

    log.info(f"\n=== Bulk load complete ===")
    log.info(f"  Success : {success}")
    log.info(f"  Failed  : {failure}")
    log.info(f"  Total   : {total}")


if __name__ == "__main__":
    main()
