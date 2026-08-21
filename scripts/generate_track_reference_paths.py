"""
Generate 1,000-point reference/display circuit layouts from cached location data.

Reads the committed replay cache (``data/replay``) and the preserved metadata
baseline (``data/circuits/baseline_metadata.json``). No OpenF1 or FastF1 access.

Usage:
    python scripts/generate_track_reference_paths.py --session-key 9947 --write
    python scripts/generate_track_reference_paths.py --all --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from formula1_strategy_tool.acquisition.replay import replay_dir
from formula1_strategy_tool.track.generator import build_layout
from formula1_strategy_tool.track.models import layouts_dir

BASELINE = Path("data/circuits/baseline_metadata.json")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _baseline() -> dict[int, dict]:
    data = _load_json(BASELINE)
    return {int(k): v for k, v in data.get("circuits", {}).items()}


def _cached_sessions() -> list[int]:
    root = Path("data/replay")
    keys: list[int] = []
    for child in sorted(root.iterdir()):
        if (
            child.is_dir()
            and child.name.isdigit()
            and (child / "sessions.json").exists()
        ):
            keys.append(int(child.name))
    return keys


def _session_circuit_key(session_key: int) -> int | None:
    sessions = _load_json(replay_dir(session_key) / "sessions.json")
    if not sessions:
        return None
    value = sessions[0].get("circuit_key")
    return int(value) if value is not None else None


def _session_keys(args: argparse.Namespace) -> list[int]:
    if args.all:
        newest: dict[int, int] = {}
        for key in _cached_sessions():
            circuit_key = _session_circuit_key(key)
            if circuit_key is not None:
                newest[circuit_key] = key
        return list(newest.values())
    return args.session_key


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-key", type=int, action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    session_keys = _session_keys(args)
    if not session_keys:
        parser.error("--session-key or --all is required")

    baseline = _baseline()
    layouts = []
    for session_key in session_keys:
        circuit_key = _session_circuit_key(session_key)
        meta = baseline.get(circuit_key, {})
        if circuit_key is None:
            print(f"session {session_key}: no circuit_key, skipped")
            continue
        print(f"session {session_key} circuit {circuit_key} ({meta.get('name', '?')}):")
        layout = build_layout(
            session_key,
            circuit_key,
            meta.get("name") or f"Circuit {circuit_key}",
            meta.get("country"),
            float(meta.get("rotation", 0.0)),
        )
        if layout is None:
            print("  FAILED: not enough usable laps")
            continue
        quality = layout.quality
        print(
            f"  {quality.accepted_laps} laps / {quality.accepted_drivers} drivers  "
            f"len {quality.loop_length_m:.0f}m  "
            f"closure {quality.closure_distance_m:.1f}m  "
            f"dev {quality.median_deviation_m:.1f}m "
            f"(max {quality.max_deviation_m:.1f}m)"
        )
        layouts.append(layout)

    if not layouts:
        raise SystemExit("no layouts generated")

    if args.write:
        out = layouts_dir()
        out.mkdir(parents=True, exist_ok=True)
        for layout in layouts:
            path = out / f"{layout.circuit_key}.json"
            path.write_text(layout.model_dump_json(indent=2) + "\n", encoding="utf-8")
            print(f"  wrote {path}")


if __name__ == "__main__":
    main()
