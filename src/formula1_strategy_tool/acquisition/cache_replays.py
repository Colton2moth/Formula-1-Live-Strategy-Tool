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

from formula1_strategy_tool.acquisition.client import OpenF1Client
from formula1_strategy_tool.acquisition.replay import (
    _ENDPOINTS,
    download_replay_data,
    fetch_replay_sessions,
    location_window_count,
    replay_dir,
)

FAILURES_PATH = Path("data/replay/cache_failures.txt")


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
        required=True,
        help="Season years to cache, e.g. --years 2025 2026.",
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


def cache_session(client: OpenF1Client, session: dict[str, Any]) -> list[str]:
    """Download (or reuse) every replay file for one session; return failures."""
    session_key = session["session_key"]
    cache = replay_dir(session_key)

    before = {name: path.exists() for name, path in _endpoint_files(cache).items()}
    location_dir = cache / "location"
    before_windows = {p.name for p in location_dir.glob("*.json")}

    try:
        data = download_replay_data(client, session_key)
    except Exception as exc:  # noqa: BLE001 — one race must not stop the bulk run
        print(f"  FAILED: {exc}", flush=True)
        return [f"download: {exc}"]

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

    failures: list[str] = []
    total = location_window_count(data["session"], data["laps"])
    if total:
        missing = [
            i for i in range(total) if not (location_dir / f"{i:04d}.json").exists()
        ]
        newly = [
            i
            for i in range(total)
            if f"{i:04d}.json" not in before_windows
            and (location_dir / f"{i:04d}.json").exists()
        ]
        reused = [i for i in range(total) if f"{i:04d}.json" in before_windows]
        status = f"  location: {len(reused)} cached, {len(newly)} downloaded"
        if missing:
            status += f", {len(missing)} missing {_format_windows(missing)}"
        print(status, flush=True)
        failures.extend(f"location window {i:04d} missing" for i in missing)
    else:
        print("  location: none required", flush=True)

    return failures


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
    client = OpenF1Client()

    years_label = ", ".join(str(year) for year in args.years)
    print(f"Loading completed races for {years_label}...", flush=True)
    sessions = fetch_replay_sessions(client, years=args.years)
    print(f"Found {len(sessions)} completed races.\n", flush=True)

    failed_sessions: list[tuple[dict[str, Any], list[str]]] = []

    try:
        for index, session in enumerate(sessions, start=1):
            session_key = session["session_key"]
            print(
                f"[{index}/{len(sessions)}] {_label(session)} ({session_key})",
                flush=True,
            )
            failures = cache_session(client, session)
            if failures:
                failed_sessions.append((session, failures))
                record_failures(session, failures)
            else:
                print("  OK", flush=True)
    except KeyboardInterrupt:
        print("\nInterrupted. Cached files are intact; re-run to resume.", flush=True)

    succeeded = len(sessions) - len(failed_sessions)
    print(
        f"\nFinished: {succeeded} succeeded, {len(failed_sessions)} had failures.",
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
