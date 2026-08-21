"""
Capture the pre-teardown circuit metadata baseline for the track-map rebuild.

Preserves the only still-valid data from the old FastF1-based system before it
is decommissioned: circuit key/name, country, reviewed orientation (rotation),
and pit-lane availability. The old 140-point reconstructed paths are
intentionally NOT preserved — git history is the rollback source.

Writes ``data/circuits/baseline_metadata.json`` and prints a cached-session
coverage summary (which cached replay session can source each circuit layout).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from formula1_strategy_tool.acquisition.replay import (
    cached_location_windows,
    classify_location_gaps,
    location_window_count,
)
from formula1_strategy_tool.api.circuits import CIRCUITS
from formula1_strategy_tool.api.countries import COUNTRY_NAMES
from formula1_strategy_tool.api.pit_lanes import PIT_LANES

OUT = Path("data/circuits/baseline_metadata.json")
REPLAY_DIR = Path("data/replay")


def _cached_sessions() -> list[tuple[int, dict]]:
    rows: list[tuple[int, dict]] = []
    if not REPLAY_DIR.exists():
        return rows
    for child in sorted(REPLAY_DIR.iterdir()):
        if not child.is_dir():
            continue
        sessions_path = child / "sessions.json"
        if not sessions_path.exists():
            continue
        for row in json.loads(sessions_path.read_text(encoding="utf-8")):
            rows.append((child.name, row))
    return rows


def main() -> None:
    baseline = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": (
            "circuits.py (circuit_key/name/rotation), countries.py (country), "
            "pit_lanes.py (pit-lane availability)"
        ),
        "circuits": {
            str(key): {
                "name": track.circuit_name,
                "country": COUNTRY_NAMES.get(key),
                "rotation": track.rotation,
                "pit_lane": key in PIT_LANES,
            }
            for key, track in sorted(CIRCUITS.items())
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(baseline['circuits'])} circuits)")

    # Coverage: which cached sessions can source each circuit's location data.
    by_circuit: dict[int, list[tuple[str, dict, str]]] = {}
    for session_key, session in _cached_sessions():
        circuit_key = session.get("circuit_key")
        if circuit_key is None:
            continue
        cache = REPLAY_DIR / str(session_key)
        laps_path = cache / "laps.json"
        laps = json.loads(laps_path.read_text(encoding="utf-8")) if laps_path.exists() else []
        expected = location_window_count(session, laps)
        gap = classify_location_gaps(expected, cached_location_windows(cache))
        by_circuit.setdefault(circuit_key, []).append((str(session_key), session, gap))

    print("\ncircuit_key  circuit_name                  sessions (complete=loc windows full)")
    for key, track in sorted(CIRCUITS.items()):
        sessions = by_circuit.get(key, [])
        ready = sum(1 for _, _, gap in sessions if gap == "complete")
        label = f"{len(sessions)} cached, {ready} complete-location"
        print(f"{key:11d}  {track.circuit_name:28s}  {label}")

    missing = [key for key in CIRCUITS if key not in by_circuit]
    print(f"\ncircuits with no cached session: {missing or 'none'}")


if __name__ == "__main__":
    main()
