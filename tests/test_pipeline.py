"""
Offline test — validates the full pipeline without MongoDB.

Uses the 2023 Monza Race (small, fast download).
Run from project root:  python tests/test_pipeline.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

from engine.loader   import load_session
from engine.timeline import build_timeline, FRAME_INTERVAL_MS

def test_pipeline():
    print("\n=== F1 Race Replay — Pipeline Test ===\n")

    # Load 2023 Monza Race (cached after first run)
    sess = load_session(2023, "Monza", "Race")

    print(f"Year        : {sess.year}")
    print(f"Event       : {sess.event}")
    print(f"Session     : {sess.session_type}")
    print(f"Total laps  : {sess.total_laps}")
    print(f"Drivers     : {[d.code for d in sess.drivers]}")
    print(f"Driver count: {len(sess.drivers)}")
    print()

    # Build timeline — first 100 frames only for speed
    frames, bounds = build_timeline(sess, max_frames=100)

    print(f"Frames built : {len(frames)}")
    print(f"Frame interval: {FRAME_INTERVAL_MS}ms")
    print(f"Track bounds : X[{bounds.x_min:.0f}..{bounds.x_max:.0f}]"
          f"  Y[{bounds.y_min:.0f}..{bounds.y_max:.0f}]")
    print()

    # --- Frame structure check ---
    first = frames[0]
    print("=== First frame ===")
    print(f"  t (ms): {first['t']}")
    active = {k: v for k, v in first["cars"].items() if v is not None}
    print(f"  Active cars: {len(active)}/{len(first['cars'])}")

    sample_driver = next(iter(active))
    snap = active[sample_driver]
    print(f"\n  Sample car ({sample_driver}):")
    for k, v in snap.items():
        print(f"    {k}: {v}")

    # --- Coordinate bounds check ---
    all_x = [v["x"] for f in frames for v in f["cars"].values() if v]
    all_y = [v["y"] for f in frames for v in f["cars"].values() if v]
    print(f"\n=== Normalized coordinate range ===")
    print(f"  X: {min(all_x):.3f} .. {max(all_x):.3f}  (should be 0..1)")
    print(f"  Y: {min(all_y):.3f} .. {max(all_y):.3f}  (should be 0..1)")

    assert 0.0 <= min(all_x) and max(all_x) <= 1.0, "X out of 0-1 range"
    assert 0.0 <= min(all_y) and max(all_y) <= 1.0, "Y out of 0-1 range"

    # --- Timeline continuity check ---
    ts = [f["t"] for f in frames]
    gaps = [ts[i+1] - ts[i] for i in range(len(ts)-1)]
    assert all(g == FRAME_INTERVAL_MS for g in gaps), \
        f"Irregular gaps: {set(gaps)}"

    # --- JSON serializable check ---
    json.dumps(frames[0])

    print("\n All checks passed")
    print(f"\nNext step: run MongoDB and load a full race:")
    print(f"  python load_race.py --year 2024 --event Monaco --session Race")
    print(f"  python load_race.py --year 2023 --event Monza  --session Race --test")


if __name__ == "__main__":
    test_pipeline()
