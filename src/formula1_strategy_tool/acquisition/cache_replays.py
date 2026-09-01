"""
Bulk-cache completed Race sessions for the replay system.

Run repeatedly to warm (or repair) the replay cache without re-downloading
anything already stored:

    python -m formula1_strategy_tool.acquisition.cache_replays --years 2025 2026

Resumability comes entirely from the existing replay cache: `download_replay_data`
uses `get_or_download`, which loads endpoint files and 5-minute location windows
already on disk instead of hitting OpenF1 again. One race failing does not stop
the rest; failures are appended to `data/replay/cache_failures.txt`.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from formula1_strategy_tool.acquisition.client import OpenF1Client, load_json
from formula1_strategy_tool.acquisition.replay import (
    _ENDPOINTS,
    CANCELLED_SESSION_KEYS,
    cached_location_windows,
    classify_location_gaps,
    download_replay_data,
    fetch_replay_sessions,
    load_checkpoint_index,
    load_timeline,
    location_window_count,
    prepare_timeline,
    replay_dir,
)

FAILURES_PATH = Path("data/replay/cache_failures.txt")


def replay_readiness(session_key: int) -> str:
    """
    Return the replay readiness state for one session.

    - ``cancelled``: the race never took place (see ``CANCELLED_SESSION_KEYS``).
    - ``ready``: the prepared timeline and checkpoint/index data load and
      location data is complete or only has a harmless trailing gap.
    - ``partial``: timeline/checkpoints load but location has an internal gap
      (or is entirely absent), so the map is incomplete while replay works.
    - ``failed``: not ready and a recorded preparation failure exists.
    - ``not_ready``: not ready and no recorded failure (not prepared yet).
    """
    if session_key in CANCELLED_SESSION_KEYS:
        return "cancelled"
    cache = replay_dir(session_key)
    if load_timeline(cache, session_key, validate_chunks=True) is not None and (
        load_checkpoint_index(cache, session_key, validate_states=True) is not None
    ):
        gap = _location_gap_status(cache)
        return "partial" if gap in ("internal", "absent") else "ready"
    if _session_in_failures(session_key):
        return "failed"
    return "not_ready"


def _location_gap_status(cache: Path) -> str:
    """Classify one cached session's location windows from its stored data."""
    sessions_path = cache / "sessions.json"
    if not sessions_path.exists():
        # Without session metadata the expected window count is unknowable;
        # location is optional polish, so treat this as complete rather than
        # penalising an otherwise playable replay.
        return "complete"
    sessions = load_json(sessions_path)
    session = sessions[0] if sessions else {}
    laps_path = cache / "laps.json"
    laps = load_json(laps_path) if laps_path.exists() else []
    return classify_location_gaps(
        location_window_count(session, laps), cached_location_windows(cache)
    )


def _session_in_failures(session_key: int) -> bool:
    if not FAILURES_PATH.exists():
        return False
    needle = f"| {session_key} |"
    return any(
        needle in line
        for line in FAILURES_PATH.read_text(encoding="utf-8").splitlines()
    )


def _local_sessions() -> list[dict[str, Any]]:
    """Discover already-cached sessions from ``data/replay`` without OpenF1."""
    sessions: list[dict[str, Any]] = []
    for child in sorted(Path("data/replay").iterdir()):
        if not child.is_dir():
            continue
        path = child / "sessions.json"
        if not path.exists():
            continue
        for row in load_json(path):
            sessions.append(row)
    return sessions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Bulk-cache completed Race sessions for replay. Safe to re-run — "
            "skips any endpoint file or location window already on disk."
        ),
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        help="Season years to cache, e.g. --years 2025 2026. Required unless --local.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Reuse sessions already under data/replay/ instead of listing OpenF1.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=6,
        help="Total attempts per request (1 = no retries, 2 = retry once).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.1,
        help="Seconds between requests (OpenF1 free tier allows ~30/min).",
    )
    return parser


def _endpoint_files(cache: Path) -> dict[str, Path]:
    names = ["sessions", "meetings", *_ENDPOINTS]
    return {name: cache / f"{name}.json" for name in names}


def _label(session: dict[str, Any]) -> str:
    year = session.get("year", "?")
    country = session.get("country_name") or session.get("location") or "unknown"
    return f"{year} {country}"


def _format_windows(windows: list[int]) -> str:
    return " ".join(f"{i:04d}" for i in windows)


def cache_session(
    client: OpenF1Client, session: dict[str, Any]
) -> tuple[str, list[str]]:
    """
    Download (or reuse) every replay file for one session.

    Returns ``(readiness, failures)`` where ``readiness`` is one of ``ready``,
    ``partial``, ``cancelled``, or ``failed``, and ``failures`` holds only
    blocking preparation failures (download errors) to record.
    """
    session_key = session["session_key"]
    if session_key in CANCELLED_SESSION_KEYS:
        print("  cancelled: race never took place, skipping", flush=True)
        return "cancelled", []

    cache = replay_dir(session_key)

    before = {name: path.exists() for name, path in _endpoint_files(cache).items()}
    location_dir = cache / "location"
    before_windows = {p.name for p in location_dir.glob("*.json")}

    try:
        data = download_replay_data(client, session_key)
    except Exception as exc:  # noqa: BLE001 — one race must not stop the bulk run
        print(f"  FAILED: {exc}", flush=True)
        return "failed", [f"download: {exc}"]

    downloaded = [
        name
        for name, existed in before.items()
        if not existed and (cache / f"{name}.json").exists()
    ]
    cached = [name for name, existed in before.items() if existed]
    print(
        f"  endpoints: {len(cached)} cached, {len(downloaded)} downloaded",
        flush=True,
    )

    total = location_window_count(data["session"], data["laps"])
    existing = cached_location_windows(cache)
    gap = classify_location_gaps(total, existing)
    if total:
        newly = [
            i
            for i in range(total)
            if f"{i:04d}.json" not in before_windows
            and (location_dir / f"{i:04d}.json").exists()
        ]
        reused = [i for i in range(total) if f"{i:04d}.json" in before_windows]
        status = f"  location: {len(reused)} cached, {len(newly)} downloaded"
        missing = sorted(set(range(total)) - existing)
        if gap == "trailing":
            status += (
                f", {len(missing)} trailing window unavailable "
                f"{_format_windows(missing)}"
            )
        elif gap == "internal":
            status += f", {len(missing)} internal gap {_format_windows(missing)}"
        elif gap == "absent":
            status += ", no location data cached"
        print(status, flush=True)
    else:
        print("  location: none required", flush=True)

    # Location is optional polish: a missing window must not block preparation.
    # Build the timeline + checkpoints whenever the core endpoints downloaded
    # and they are not already current.
    if (
        load_timeline(cache, session_key, validate_chunks=True) is None
        or load_checkpoint_index(cache, session_key, validate_states=True) is None
    ):
        events, _ = prepare_timeline(cache, data)
        print(f"  timeline + checkpoints: {len(events)} events prepared", flush=True)
    else:
        print("  timeline + checkpoints: up to date", flush=True)

    return "partial" if gap in ("internal", "absent") else "ready", []


def record_failures(session: dict[str, Any], failures: list[str]) -> None:
    """Append one plain-text line per failure to the shared failure log."""
    FAILURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    key = session["session_key"]
    label = _label(session)
    with FAILURES_PATH.open("a", encoding="utf-8") as file:
        for failure in failures:
            file.write(f"{stamp} | {key} | {label} | {failure}\n")


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    client = OpenF1Client(max_retries=args.max_retries, min_interval=args.interval)

    if args.local:
        sessions = _local_sessions()
        print(f"Using {len(sessions)} locally cached sessions.\n", flush=True)
    else:
        if not args.years:
            build_parser().error("--years is required unless --local")
        years_label = ", ".join(str(year) for year in args.years)
        print(f"Loading completed races for {years_label}...", flush=True)
        sessions = fetch_replay_sessions(client, years=args.years)
        print(f"Found {len(sessions)} completed races.\n", flush=True)

    failed_sessions: list[tuple[dict[str, Any], list[str]]] = []
    counts: dict[str, int] = {"ready": 0, "partial": 0, "cancelled": 0}

    try:
        for index, session in enumerate(sessions, start=1):
            session_key = session["session_key"]
            print(
                f"[{index}/{len(sessions)}] {_label(session)} ({session_key})",
                flush=True,
            )
            readiness, failures = cache_session(client, session)
            if readiness == "failed":
                failed_sessions.append((session, failures))
                record_failures(session, failures)
            else:
                counts[readiness] += 1
                if readiness == "ready":
                    print("  READY", flush=True)
                elif readiness == "partial":
                    print("  PARTIAL", flush=True)
    except KeyboardInterrupt:
        print("\nInterrupted. Cached files are intact; re-run to resume.", flush=True)

    print(
        f"\nFinished: {counts['ready']} ready, {counts['partial']} partial, "
        f"{counts['cancelled']} cancelled, {len(failed_sessions)} failed.",
        flush=True,
    )
    if failed_sessions:
        print("\nFailures:", flush=True)
        for session, failures in failed_sessions:
            key = session["session_key"]
            for failure in failures:
                print(f"{key} | {_label(session)} | {failure}", flush=True)
        print(f"\nFailures appended to {FAILURES_PATH}", flush=True)


if __name__ == "__main__":
    main()
