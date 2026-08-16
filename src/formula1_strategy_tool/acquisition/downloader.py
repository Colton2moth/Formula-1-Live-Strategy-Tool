"""
Orchestrates bulk download of historical OpenF1 race data.

Sits above client.py in the acquisition stack:
    client.py   →  HTTP + file I/O primitives
    downloader  →  which sessions/endpoints to fetch, folder layout
    cli.py      →  command-line entry point you run tomorrow morning

For each year:
    1. Download meetings.json and sessions.json (year-level metadata)
    2. Filter to completed Race sessions only (Sprints excluded)
    3. For each session, download every strategy-relevant endpoint into
       data/raw/<year>/sessions/<meeting>_<session>_<country>_<name>/

Re-running is safe: existing JSON files are skipped (resumable).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from formula1_strategy_tool.acquisition.client import (
    OpenF1Client,
    atomic_write_json,
    get_or_download,
)

# Endpoints needed for lap-level strategy modelling (see docs/data/ACQUISITION.md).
# Deliberately excludes car_data and location — too large, not needed yet.
ENDPOINTS = [
    "drivers",
    "laps",
    "stints",
    "pit",
    "position",
    "intervals",
    "weather",
    "race_control",
    "starting_grid",
    "session_result",
    "overtakes",
]

# Do not download a session until this long after its scheduled end time.
# Avoids pulling incomplete data for sessions that just finished.
SESSION_COMPLETION_BUFFER = timedelta(hours=2)


def parse_openf1_datetime(value: str | None) -> datetime | None:
    """
    Parse an OpenF1 ISO-8601 timestamp into a timezone-aware UTC datetime.

    OpenF1 returns strings like "2024-03-02T15:00:00Z" or with +00:00 offset.
    Returns None if the value is missing or empty.
    """
    if not value:
        return None

    # Python's fromisoformat does not accept "Z"; normalise to +00:00.
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)

    # Treat naive timestamps as UTC (defensive — API should always send offset).
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def safe_name(value: str) -> str:
    """
    Turn a human-readable label into a filesystem-safe folder name segment.

    Example: "São Paulo - Race" → "s_o_paulo_-_race"
    """
    # Replace any character that is not alphanumeric, underscore, or hyphen.
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return cleaned.strip("_").lower()


def session_is_complete(session: dict[str, Any]) -> bool:
    """
    Return True if the session ended long enough ago that data should be final.

    Uses date_end from the sessions endpoint. Sessions without an end time
    (e.g. cancelled or not yet run) are excluded.
    """
    end = parse_openf1_datetime(session.get("date_end"))
    if end is None:
        return False

    # Session must have ended at least SESSION_COMPLETION_BUFFER ago.
    return end <= datetime.now(timezone.utc) - SESSION_COMPLETION_BUFFER


def append_error(path: Path, record: dict[str, Any]) -> None:
    """
    Append one JSON error record to a .jsonl log file.

    Used when a single endpoint fails so the bulk run can continue and
    failures can be retried later without re-downloading successes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def download_year(
    client: OpenF1Client,
    output_root: Path,
    year: int,
) -> None:
    """
    Download all completed Race sessions for one calendar year.

    Sprint sessions are intentionally excluded — strategy modelling targets
    full race distance only.

    Args:
        client:      Shared rate-limited HTTP client.
        output_root: Base directory, typically data/raw.
        year:        Season year (2023 onward).
    """
    year_dir = output_root / str(year)

    print(f"\nLoading {year} metadata...", flush=True)

    # Year-level metadata — one file each, cached after first fetch.
    get_or_download(
        client,
        "meetings",
        {"year": year},
        year_dir / "meetings.json",
    )

    sessions = get_or_download(
        client,
        "sessions",
        {"year": year},
        year_dir / "sessions.json",
    )

    # Only full Race sessions — no Sprints, qualifying, practice, etc.
    accepted_names = {"Race"}

    # Keep sessions that are the right type AND fully finished.
    selected_sessions = [
        session
        for session in sessions
        if session.get("session_name") in accepted_names
        and session_is_complete(session)
    ]

    print(f"Found {len(selected_sessions)} completed race sessions.", flush=True)

    for index, session in enumerate(selected_sessions, start=1):
        session_key = session["session_key"]
        meeting_key = session["meeting_key"]
        session_name = session.get("session_name", "session")
        country = session.get("country_name", "unknown")

        # Folder name encodes IDs + human labels so directories are identifiable.
        folder_name = (
            f"{meeting_key}_{session_key}_"
            f"{safe_name(country)}_{safe_name(session_name)}"
        )
        session_dir = year_dir / "sessions" / folder_name

        # Save the session metadata itself (useful when processing later).
        atomic_write_json(session_dir / "session.json", session)

        print(
            f"[{index}/{len(selected_sessions)}] "
            f"{year} {country} {session_name} ({session_key})",
            flush=True,
        )

        # Download each endpoint as a separate JSON file for this session.
        for endpoint in ENDPOINTS:
            destination = session_dir / f"{endpoint}.json"

            # Resumability: skip if we already have this file from a prior run.
            if destination.exists():
                print(f"  {endpoint}: already downloaded", flush=True)
                continue

            try:
                data = client.get(endpoint, {"session_key": session_key})
                atomic_write_json(destination, data)
                print(f"  {endpoint}: {len(data)} rows", flush=True)

            except Exception as exc:
                # Log failure and continue — one bad endpoint must not stop the rest.
                print(f"  {endpoint}: FAILED — {exc}", flush=True)
                append_error(
                    output_root / "download_errors.jsonl",
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "year": year,
                        "meeting_key": meeting_key,
                        "session_key": session_key,
                        "endpoint": endpoint,
                        "error": str(exc),
                    },
                )
