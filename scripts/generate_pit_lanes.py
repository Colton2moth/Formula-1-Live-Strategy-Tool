"""
Generate static pit-lane centrelines and attach them to circuit layouts.

Offline build-time tool. It reads the cached replay location traces
(``pit.json`` and ``location/*.json``), isolates each pit stop's lane trace,
builds a reviewed centreline, and writes it into the circuit's layout JSON as
``pit_lane`` (raw reference points, display points, entry/exit progress).

Run after ``generate_track_reference_paths.py`` so the reference layouts exist.

Usage:
    python scripts/generate_pit_lanes.py --session-key 9963 --write
    python scripts/generate_pit_lanes.py --all --write
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from formula1_strategy_tool.acquisition.replay import replay_dir
from formula1_strategy_tool.pit_geometry import (
    DECIMETRES_PER_METRE,
    build_centerline,
    clean_trace,
    dist_to_path,
    isolate_pit_lane,
    simplify,
    smooth,
)
from formula1_strategy_tool.track.generator import build_display_transform
from formula1_strategy_tool.track.models import (
    LayoutPoint,
    PitLane,
    layouts_dir,
    load_layout,
)
from formula1_strategy_tool.track.projection import Projector

D = DECIMETRES_PER_METRE
_WINDOW_SECONDS = 300
_BUFFER_SECONDS = 15
_MIN_LANE_SECONDS = 20.0
_MAX_LANE_SECONDS = 40.0
_CENTRELINE_SAMPLES = 120
_SIMPLIFY_TOLERANCE_M = 0.6
_MAX_CONNECT_M = 12.0


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _epoch(dt: datetime) -> float:
    return (dt - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _select_stops(pit_rows: list[dict], max_stops: int) -> list[dict]:
    chosen: list[dict] = []
    seen: set[int] = set()
    for row in sorted(pit_rows, key=lambda r: str(r.get("date") or "")):
        lane = row.get("lane_duration") or row.get("pit_duration")
        number = row.get("driver_number")
        if lane is None or number is None:
            continue
        if not (_MIN_LANE_SECONDS <= float(lane) <= _MAX_LANE_SECONDS):
            continue
        if int(number) in seen:
            continue
        seen.add(int(number))
        chosen.append(row)
        if len(chosen) >= max_stops:
            break
    return chosen


def _window_indices(
    start: datetime, end: datetime, session_start: datetime
) -> list[int]:
    lo = max(0, int((start - session_start).total_seconds() // _WINDOW_SECONDS))
    hi = max(lo, int((end - session_start).total_seconds() // _WINDOW_SECONDS))
    return list(range(lo, hi + 1))


def _extract_trace(
    cache: Path,
    driver_number: int,
    start: datetime,
    end: datetime,
    session_start: datetime,
    windows: dict[int, list[dict]],
) -> list[tuple[float, float, float]]:
    rows: list[tuple[float, float, float]] = []
    for idx in _window_indices(start, end, session_start):
        if idx not in windows:
            path = cache / "location" / f"{idx:04d}.json"
            if not path.exists():
                continue
            windows[idx] = _load_json(path)
        for r in windows[idx]:
            if r.get("driver_number") != driver_number:
                continue
            dt = _parse(r["date"])
            if start <= dt <= end:
                x = r.get("x")
                y = r.get("y")
                if x is None or y is None or (x == 0 and y == 0):
                    continue
                rows.append((_epoch(dt), float(x) / D, float(y) / D))
    rows.sort(key=lambda t: t[0])
    return rows


def _raw_centreline(
    session_key: int, circuit_key: int, max_stops: int
) -> list[tuple[float, float]] | None:
    cache = replay_dir(session_key)
    sessions = _load_json(cache / "sessions.json")
    session = sessions[0] if sessions else {}
    layout = load_layout(circuit_key)
    if layout is None:
        print(f"  circuit {circuit_key}: no reference layout, skipped")
        return None

    session_start = _parse(session["date_start"])
    pit_rows = _load_json(cache / "pit.json")
    stops = _select_stops(pit_rows, max_stops)
    if len(stops) < 2:
        print(f"  circuit {circuit_key}: only {len(stops)} usable stops, skipped")
        return None

    path_m = [(p.x / D, p.y / D) for p in layout.reference_path]
    windows: dict[int, list[dict]] = {}
    traces: list[list[tuple[float, float]]] = []

    for row in stops:
        number = int(row["driver_number"])
        lane = float(row.get("lane_duration") or row.get("pit_duration"))
        date = _parse(row["date"])
        entry = date - timedelta(seconds=lane)
        trace = _extract_trace(
            cache,
            number,
            entry - timedelta(seconds=_BUFFER_SECONDS),
            date + timedelta(seconds=_BUFFER_SECONDS),
            session_start,
            windows,
        )
        if len(trace) < 10:
            continue
        isolated = isolate_pit_lane(trace, path_m, _epoch(entry), _epoch(date))
        isolated = clean_trace(isolated)
        if len(isolated) < 10:
            continue
        traces.append(isolated)

    if len(traces) < 2:
        print(f"  circuit {circuit_key}: only {len(traces)} usable traces, skipped")
        return None

    centreline = build_centerline(traces, _CENTRELINE_SAMPLES)
    centreline = smooth(centreline, passes=2)
    centreline = simplify(centreline, _SIMPLIFY_TOLERANCE_M)

    d_entry = dist_to_path(centreline[0][0], centreline[0][1], path_m)
    d_exit = dist_to_path(centreline[-1][0], centreline[-1][1], path_m)
    if d_entry > _MAX_CONNECT_M or d_exit > _MAX_CONNECT_M:
        print(
            f"  circuit {circuit_key}: entry/exit off-track "
            f"({d_entry:.1f}m/{d_exit:.1f}m), skipped"
        )
        return None
    print(
        f"  circuit {circuit_key:>3} {layout.name:<28} "
        f"{len(centreline):>2} pts from {len(traces)} traces  "
        f"entry {d_entry:.1f}m  exit {d_exit:.1f}m"
    )
    return [(x * D, y * D) for x, y in centreline]


def _update_layout(circuit_key: int, raw_points: list[tuple[float, float]]) -> None:
    layout = load_layout(circuit_key)
    if layout is None:
        return
    reference = [(p.x, p.y) for p in layout.reference_path]
    transform = build_display_transform(reference, layout.rotation)
    display = [transform.apply(p) for p in raw_points]
    projector = Projector(layout)
    entry = projector.project(raw_points[0][0], raw_points[0][1])
    exit_ = projector.project(raw_points[-1][0], raw_points[-1][1])

    pit_lane = PitLane(
        reference=[LayoutPoint(x=x, y=y) for x, y in raw_points],
        display=[LayoutPoint(x=x, y=y) for x, y in display],
        entry_progress=entry[0] if entry else None,
        exit_progress=exit_[0] if exit_ else None,
    )
    updated = layout.model_copy(update={"pit_lane": pit_lane})
    path = layouts_dir() / f"{circuit_key}.json"
    path.write_text(updated.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"  wrote pit lane to {path}")


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-key", type=int, action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--max-stops", type=int, default=8)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    session_keys = args.session_key
    if args.all:
        session_keys = _cached_sessions()
    if not session_keys:
        parser.error("--session-key or --all is required")

    by_circuit: dict[int, int] = {}
    for key in session_keys:
        sessions = _load_json(replay_dir(key) / "sessions.json")
        if not sessions:
            continue
        ck = sessions[0].get("circuit_key")
        if ck is not None:
            by_circuit[int(ck)] = key

    results: dict[int, list[tuple[float, float]]] = {}
    for circuit_key, session_key in sorted(by_circuit.items()):
        print(f"session {session_key} circuit {circuit_key}:")
        centreline = _raw_centreline(session_key, circuit_key, args.max_stops)
        if centreline is not None:
            results[circuit_key] = centreline

    if not results:
        raise SystemExit("no pit lanes generated")

    if args.write:
        for circuit_key, raw_points in results.items():
            _update_layout(circuit_key, raw_points)


if __name__ == "__main__":
    main()
