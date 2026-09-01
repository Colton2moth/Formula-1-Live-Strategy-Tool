"""
Developer replay harness: replay one completed session into a LiveState.

Input:  session_key (required), replay speed (default 10x)
Output: fills the supplied LiveState chronologically so a replay-aware
        frontend advances exactly as it would during a live race.

This reuses the real OpenF1 REST acquisition, the shared LiveState store, and
the prediction path. The only new code is the replay producer itself — nothing
in TrackMap, Leaderboard, RaceHeader, or StrategyPanel changes.

The user-facing ReplayController owns a private LiveState and always passes it
to this engine, so replay never clears or seeds the live-only module-level
``LIVE_STATE``. The CLI harness may still rely on the ``state`` default.

No-future-leakage rule:
    A completed race contains data that was not known at an earlier lap, so the
    producer only exposes a row once the replay clock reaches its timestamp.
    Stints are reconstructed live-like: the historical ``lap_end`` is dropped
    so the model only ever sees the current, open-ended stint.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from formula1_strategy_tool.acquisition.client import (
    OpenF1Client,
    atomic_write_json,
    get_or_download,
    load_json,
)
from formula1_strategy_tool.acquisition.downloader import parse_openf1_datetime
from formula1_strategy_tool.acquisition.live_state import LIVE_STATE, LiveState

# Same families the MQTT listener uses, plus session context.
_ENDPOINTS = (
    "drivers",
    "laps",
    "stints",
    "pit",
    "position",
    "intervals",
    "weather",
    "race_control",
)

# Location is high-frequency; replay thins it to ~4 samples/driver/second so a
# full session stays memory-friendly while the map still moves smoothly.
_LOCATION_THIN_SECONDS = 0.25
# Bump when the prepared timeline's shape changes (new topics, ordering rules,
# thinning intervals, or payload edits) or the checkpoint layout changes.
# Older prepared files are rebuilt from the raw cache instead of being trusted.
_TIMELINE_FORMAT_VERSION = 4
_TIMELINE_CHUNK_SECONDS = 300.0
_SUPPORTED_SPEEDS = frozenset({1.0, 2.0, 5.0, 10.0})
# Download window for the paginated location endpoint (whole-session returns 422).
_LOCATION_WINDOW_SECONDS = 300

# Races that never took place. OpenF1 still returns session metadata for these
# but no usable timing data, so they must never be replayed. They are marked
# explicitly rather than inferred from 404s because some legitimate historical
# races also have incomplete endpoint coverage (e.g. missing ``pit``).
#   9086  — 2023 Emilia-Romagna (Italy), cancelled due to flooding
#   11261 — 2026 Bahrain, cancelled
#   11269 — 2026 Saudi Arabia, cancelled
CANCELLED_SESSION_KEYS = frozenset({9086, 11261, 11269})


def replay_dir(session_key: int) -> Path:
    """Cache directory for one session's replay data (separate from data/raw)."""
    return Path("data/replay") / str(session_key)


_SESSION_LIST_START_YEAR = 2023


def fetch_replay_sessions(
    client: OpenF1Client,
    years: Sequence[int] | None = None,
) -> list[dict[str, Any]]:
    """
    Download completed Race sessions from OpenF1 for the given years.

    Defaults to 2023 → current year. Returns one dict per finished race with
    the fields the frontend needs to build a year → country picker.
    """
    now = datetime.now(timezone.utc)
    if years is None:
        years = range(_SESSION_LIST_START_YEAR, now.year + 1)
    out: list[dict[str, Any]] = []
    for year in years:
        for row in client.get("sessions", {"year": year, "session_name": "Race"}):
            end = parse_openf1_datetime(row.get("date_end"))
            if end is None or end > now:
                continue
            out.append(
                {
                    "session_key": row.get("session_key"),
                    "year": year,
                    "country_name": row.get("country_name"),
                    "location": row.get("location"),
                    "circuit_short_name": row.get("circuit_short_name"),
                    "date_start": row.get("date_start"),
                }
            )
    return out


_sessions_cache: list[dict[str, Any]] | None = None
_sessions_cache_at: float | None = None
# Refresh periodically so newly completed races appear without a server restart.
_SESSIONS_CACHE_TTL_SECONDS = 3600.0


def list_replay_sessions() -> list[dict[str, Any]]:
    """Return completed Race sessions, fetching (and caching) on first call."""
    global _sessions_cache, _sessions_cache_at
    now = time.monotonic()
    stale = (
        _sessions_cache is None
        or _sessions_cache_at is None
        or now - _sessions_cache_at > _SESSIONS_CACHE_TTL_SECONDS
    )
    if stale:
        _sessions_cache = fetch_replay_sessions(OpenF1Client())
        _sessions_cache_at = now
    return _sessions_cache


def download_replay_data(
    client: OpenF1Client, session_key: int, cache: Path | None = None
) -> dict[str, Any]:
    """Fetch (or load from cache) every endpoint needed for one replay."""
    cache = cache or replay_dir(session_key)
    cache.mkdir(parents=True, exist_ok=True)

    sessions = get_or_download(
        client, "sessions", {"session_key": session_key}, cache / "sessions.json"
    )
    if not sessions:
        raise RuntimeError(f"no session for session_key={session_key}")
    session = sessions[0]

    meeting_key = session.get("meeting_key")
    meetings: list[dict[str, Any]] = []
    if meeting_key is not None:
        meetings = get_or_download(
            client, "meetings", {"meeting_key": meeting_key}, cache / "meetings.json"
        )

    data: dict[str, Any] = {"session": session, "meetings": meetings}
    for endpoint in _ENDPOINTS:
        data[endpoint] = get_or_download(
            client, endpoint, {"session_key": session_key}, cache / f"{endpoint}.json"
        )

    data["location"] = _download_location(
        client, session_key, session, data["laps"], cache
    )
    return data


def _last_lap_end(laps: list[dict[str, Any]]) -> datetime | None:
    """Latest lap end time; derives from ``date_start + lap_duration`` when
    OpenF1 ``laps`` rows carry no ``date_end`` field."""
    best: datetime | None = None
    for row in laps:
        end = parse_openf1_datetime(row.get("date_end"))
        if end is None:
            start = parse_openf1_datetime(row.get("date_start"))
            duration = row.get("lap_duration")
            if start is not None and duration is not None:
                try:
                    end = start + timedelta(seconds=float(duration))
                except (TypeError, ValueError):
                    end = None
        if end is not None and (best is None or end > best):
            best = end
    return best


def _location_bounds(
    session: dict[str, Any], laps: list[dict[str, Any]]
) -> tuple[datetime, datetime] | None:
    """(start, end) range for one session's location stream, or None if absent."""
    start = parse_openf1_datetime(session.get("date_start"))
    last = _last_lap_end(laps)
    end = (
        last + timedelta(minutes=5)
        if last
        else parse_openf1_datetime(session.get("date_end"))
    )
    if start is None or end is None or end <= start:
        return None
    return start, end


def location_window_count(
    session: dict[str, Any], laps: list[dict[str, Any]]
) -> int:
    """Number of 5-minute location windows needed to cover one session."""
    bounds = _location_bounds(session, laps)
    if bounds is None:
        return 0
    start, end = bounds
    window = timedelta(seconds=_LOCATION_WINDOW_SECONDS)
    delta = end - start
    return int(delta // window) + (1 if delta % window else 0)


def classify_location_gaps(expected_count: int, existing: Sequence[int]) -> str:
    """
    Classify a session's cached location windows by their index layout.

    Returns one of:

    - ``complete`` — every expected window is present.
    - ``trailing`` — every missing window is after the last present window, i.e.
      harmless end-of-race truncation (cars parked / race ended early).
    - ``internal`` — some window is missing before a later present window, so
      map data disappears and then resumes.
    - ``absent`` — expected windows exist but none are present.

    The result is derived from window indices only, never from log strings, so
    the bulk-cache command and the API readiness calculation agree.
    """
    if expected_count <= 0:
        return "complete"
    present = {index for index in existing if 0 <= index < expected_count}
    missing = set(range(expected_count)) - present
    if not missing:
        return "complete"
    if not present:
        return "absent"
    if all(index > max(present) for index in missing):
        return "trailing"
    return "internal"


def cached_location_windows(cache: Path) -> set[int]:
    """Indices of location windows already stored under ``cache/location``."""
    location_dir = cache / "location"
    if not location_dir.exists():
        return set()
    return {
        int(path.stem) for path in location_dir.glob("*.json") if path.stem.isdigit()
    }


def _download_location(
    client: OpenF1Client,
    session_key: int,
    session: dict[str, Any],
    laps: list[dict[str, Any]],
    cache: Path,
) -> list[dict[str, Any]]:
    """
    Pull the full-session location stream in cached, paginated windows.

    OpenF1 rejects whole-session location requests (422) and the inclusive
    ``date>=`` bound errors (500), so each window uses ``date>`` / ``date<``.
    Chunks are thinned per window to keep peak memory bounded; the caller's
    timeline step thins again to close gaps at window boundaries.
    """
    bounds = _location_bounds(session, laps)
    if bounds is None:
        return []
    start, end = bounds

    location_dir = cache / "location"
    location_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    window = start
    index = 0
    while window < end:
        window_end = min(window + timedelta(seconds=_LOCATION_WINDOW_SECONDS), end)
        try:
            chunk = get_or_download(
                client,
                "location",
                {
                    "session_key": session_key,
                    "date>": window.isoformat(),
                    "date<": window_end.isoformat(),
                },
                location_dir / f"{index:04d}.json",
            )
        except Exception as exc:  # noqa: BLE001 — location is optional polish
            print(f"replay location window {index} failed: {exc}")
            index += 1
            window = window_end
            continue
        rows.extend(_thin_location(chunk))
        index += 1
        window = window_end
    return rows


def _event_offset(value: Any, t0: datetime) -> float | None:
    """Race-clock offset in seconds for one timestamp, or None if unparseable."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parse_openf1_datetime(value)
    if dt is None:
        return None
    return max(0.0, (dt - t0).total_seconds())


def _reference_time(session: dict[str, Any], laps: list[dict[str, Any]]) -> datetime:
    """Start of the race clock: earliest session/lap start, else now."""
    candidates = [parse_openf1_datetime(session.get("date_start"))]
    candidates += [parse_openf1_datetime(row.get("date_start")) for row in laps]
    valid = [candidate for candidate in candidates if candidate is not None]
    return min(valid) if valid else datetime.now(timezone.utc)


def _thin_location(
    rows: list[dict[str, Any]], interval_seconds: float = _LOCATION_THIN_SECONDS
) -> list[dict[str, Any]]:
    """Keep roughly one location sample per driver per interval_seconds."""
    keep: list[dict[str, Any]] = []
    earliest: dict[int, datetime] = {}
    for row in rows:
        number = row.get("driver_number")
        dt = parse_openf1_datetime(row.get("date"))
        if number is None or dt is None:
            continue
        key = int(number)
        if dt < earliest.get(key, dt):
            continue
        keep.append(row)
        earliest[key] = dt + timedelta(seconds=interval_seconds)
    return keep


def _lap_start_index(laps: list[dict[str, Any]]) -> dict[tuple[int, int], Any]:
    """Map (driver_number, lap_number) -> date_start for stint scheduling."""
    index: dict[tuple[int, int], Any] = {}
    for row in laps:
        number = row.get("driver_number")
        lap_number = row.get("lap_number")
        if number is None or lap_number is None:
            continue
        index[(int(number), int(lap_number))] = row.get("date_start")
    return index


def _lap_finish_time(row: dict[str, Any]) -> datetime | None:
    """
    When a lap completed, for replay scheduling.

    OpenF1 lap rows usually lack ``date_end``; derive finish from
    ``date_start + lap_duration`` so laps are not exposed at lap *start*
    (future-data leak). Falls back to ``date_start`` only when duration is
    missing.
    """
    end = parse_openf1_datetime(row.get("date_end"))
    if end is not None:
        return end
    start = parse_openf1_datetime(row.get("date_start"))
    duration = row.get("lap_duration")
    if start is not None and duration is not None:
        try:
            return start + timedelta(seconds=float(duration))
        except (TypeError, ValueError):
            pass
    return start


def build_timeline(data: dict[str, Any]) -> list[tuple[float, str, dict[str, Any]]]:
    """
    Normalize one session's rows into a chronological (offset, topic, payload)
    timeline. Identity rows (session/meetings/drivers) are not included here —
    they are seeded separately before playback starts.
    """
    t0 = _reference_time(data["session"], data["laps"])
    events: list[tuple[float, str, dict[str, Any]]] = []

    # Laps become known only when they finish — never at date_start alone.
    for row in data["laps"]:
        finish = _lap_finish_time(row)
        offset = _event_offset(finish, t0)
        if offset is not None:
            events.append((offset, "v1/laps", row))

    for row in data["pit"]:
        offset = _event_offset(row.get("date"), t0)
        if offset is not None:
            events.append((offset, "v1/pit", row))

    for endpoint in ("position", "intervals", "weather", "race_control"):
        topic = f"v1/{endpoint}"
        for row in data[endpoint]:
            offset = _event_offset(row.get("date"), t0)
            if offset is not None:
                events.append((offset, topic, row))

    for row in _thin_location(data["location"]):
        offset = _event_offset(row.get("date"), t0)
        if offset is not None:
            events.append((offset, "v1/location", row))

    # Stints: reconstruct a live-like stream. Each stint opens at its lap_start
    # with lap_end=None (still unknown); the previous stint is closed with its
    # true lap_end at the same moment the next stint starts. This keeps the
    # current stint open-ended without leaking future stint boundaries.
    lap_start = _lap_start_index(data["laps"])
    by_driver: dict[int, list[dict[str, Any]]] = {}
    for row in data["stints"]:
        number = row.get("driver_number")
        if number is not None:
            by_driver.setdefault(int(number), []).append(row)

    for rows in by_driver.values():
        rows.sort(key=lambda r: int(r.get("stint_number") or 0))
        for index, row in enumerate(rows):
            number = row.get("driver_number")
            stint_lap = row.get("lap_start")
            stamp = (
                lap_start.get((int(number), int(stint_lap)))
                if number is not None and stint_lap is not None
                else None
            )
            offset = _event_offset(stamp, t0)
            offset = offset if offset is not None else 0.0
            open_row = {k: (None if k == "lap_end" else v) for k, v in row.items()}
            events.append((offset, "v1/stints", open_row))
            if index > 0:
                closed = dict(rows[index - 1])
                events.append((offset, "v1/stints", closed))

    events.sort(key=lambda item: item[0])
    return events


def _timeline_dir(cache: Path) -> Path:
    return cache / "timeline"


def _timeline_path(cache: Path) -> Path:
    """Lightweight prepared timeline index for one replay cache."""
    return _timeline_dir(cache) / "index.json"


def _timeline_chunk_path(cache: Path, file_name: str) -> Path:
    return _timeline_dir(cache) / file_name


def _timeline_meta(
    events: list[tuple[float, str, dict[str, Any]]], data: dict[str, Any]
) -> dict[str, Any]:
    """Metadata stored alongside the prepared event list."""
    total_duration = events[-1][0] if events else 0.0
    total_laps = max(
        (int(row.get("lap_number") or 0) for row in data["laps"]), default=0
    )
    return {
        "format_version": _TIMELINE_FORMAT_VERSION,
        "session_key": data["session"].get("session_key"),
        "total_duration": total_duration,
        "total_laps": total_laps,
        "event_count": len(events),
        "chunk_duration": _TIMELINE_CHUNK_SECONDS,
    }


def save_timeline(
    cache: Path,
    events: list[tuple[float, str, dict[str, Any]]],
    data: dict[str, Any],
) -> None:
    """Persist chronological events as race-clock chunks plus a small index."""
    meta = _timeline_meta(events, data)
    timeline_dir = _timeline_dir(cache)
    timeline_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[dict[str, Any]] = []
    cursor = 0
    while cursor < len(events):
        chunk_number = int(events[cursor][0] // _TIMELINE_CHUNK_SECONDS)
        end_cursor = cursor
        while (
            end_cursor < len(events)
            and int(events[end_cursor][0] // _TIMELINE_CHUNK_SECONDS)
            == chunk_number
        ):
            end_cursor += 1
        chunk_events = events[cursor:end_cursor]
        file_name = f"chunk-{chunk_number:04d}.json"
        atomic_write_json(
            _timeline_chunk_path(cache, file_name),
            [[offset, topic, payload] for offset, topic, payload in chunk_events],
        )
        chunks.append(
            {
                "file": file_name,
                "start_time": chunk_events[0][0],
                "end_time": chunk_events[-1][0],
                "start_cursor": cursor,
                "event_count": len(chunk_events),
            }
        )
        cursor = end_cursor
    atomic_write_json(_timeline_path(cache), {**meta, "chunks": chunks})
    referenced = {chunk["file"] for chunk in chunks}
    for path in timeline_dir.glob("chunk-*.json"):
        if path.name not in referenced:
            path.unlink()
    legacy = cache / "timeline.json"
    if legacy.exists():
        legacy.unlink()


def load_timeline(
    cache: Path, session_key: int, *, validate_chunks: bool = False
) -> dict[str, Any] | None:
    """Return the lightweight chunk index, or None when it is unusable."""
    path = _timeline_path(cache)
    if not path.exists():
        return None
    try:
        blob = load_json(path)
    except (OSError, ValueError):
        return None
    if not isinstance(blob, dict):
        return None
    if blob.get("format_version") != _TIMELINE_FORMAT_VERSION:
        return None
    if blob.get("session_key") != session_key:
        return None
    if not (
        isinstance(blob.get("event_count"), int)
        and isinstance(blob.get("total_duration"), (int, float))
        and isinstance(blob.get("total_laps"), int)
        and blob.get("chunk_duration") == _TIMELINE_CHUNK_SECONDS
    ):
        return None
    chunks = blob.get("chunks")
    if not isinstance(chunks, list):
        return None
    expected_cursor = 0
    previous_end = -1.0
    for entry in chunks:
        if not (
            isinstance(entry, dict)
            and isinstance(entry.get("file"), str)
            and isinstance(entry.get("start_time"), (int, float))
            and isinstance(entry.get("end_time"), (int, float))
            and isinstance(entry.get("start_cursor"), int)
            and isinstance(entry.get("event_count"), int)
        ):
            return None
        if entry["start_cursor"] != expected_cursor or entry["event_count"] <= 0:
            return None
        if float(entry["start_time"]) < previous_end:
            return None
        expected_cursor += entry["event_count"]
        previous_end = float(entry["end_time"])
        if validate_chunks:
            events = _load_timeline_chunk(cache, entry)
            if events is None:
                return None
            if (
                events[0][0] != entry["start_time"]
                or events[-1][0] != entry["end_time"]
            ):
                return None
    if expected_cursor != blob["event_count"]:
        return None
    return blob


def _load_timeline_chunk(
    cache: Path, entry: dict[str, Any]
) -> list[tuple[float, str, dict[str, Any]]] | None:
    """Load and validate one indexed chunk without retaining other chunks."""
    path = _timeline_chunk_path(cache, entry["file"])
    if not path.exists():
        return None
    try:
        raw_events = load_json(path)
    except (OSError, ValueError):
        return None
    if not isinstance(raw_events, list) or len(raw_events) != entry["event_count"]:
        return None
    events: list[tuple[float, str, dict[str, Any]]] = []
    previous = -1.0
    for item in raw_events:
        if not (isinstance(item, list) and len(item) == 3):
            return None
        offset, topic, payload = item
        if not (
            isinstance(offset, (int, float))
            and isinstance(topic, str)
            and isinstance(payload, dict)
            and float(offset) >= previous
        ):
            return None
        previous = float(offset)
        events.append((float(offset), topic, payload))
    return events


@dataclass
class TimelineReader:
    """Cursor-based reader retaining only the current and next event chunks."""

    cache: Path
    index: dict[str, Any]

    def __post_init__(self) -> None:
        self._chunk_index = 0
        self._event_index = 0
        self._cursor = 0
        self._loaded: dict[int, list[tuple[float, str, dict[str, Any]]]] = {}

    @property
    def loaded_chunk_indices(self) -> tuple[int, ...]:
        return tuple(sorted(self._loaded))

    @property
    def cursor(self) -> int:
        return self._cursor

    def seek_cursor(self, cursor: int) -> None:
        chunks = self.index["chunks"]
        self._cursor = cursor
        if cursor >= self.index["event_count"]:
            self._chunk_index = len(chunks)
            self._event_index = 0
            self._loaded.clear()
            return
        for chunk_index, entry in enumerate(chunks):
            end = entry["start_cursor"] + entry["event_count"]
            if entry["start_cursor"] <= cursor < end:
                self._chunk_index = chunk_index
                self._event_index = cursor - entry["start_cursor"]
                self._loaded.clear()
                self._ensure_window()
                return
        raise ValueError(f"timeline cursor {cursor} is outside the index")

    def peek(self) -> tuple[float, str, dict[str, Any]] | None:
        while self._chunk_index < len(self.index["chunks"]):
            self._ensure_window()
            events = self._loaded[self._chunk_index]
            if self._event_index < len(events):
                return events[self._event_index]
            self._chunk_index += 1
            self._event_index = 0
            self._ensure_window()
        return None

    def pop(self) -> tuple[float, str, dict[str, Any]] | None:
        event = self.peek()
        if event is not None:
            self._event_index += 1
            self._cursor += 1
        return event

    def _ensure_window(self) -> None:
        chunks = self.index["chunks"]
        keep = set(range(self._chunk_index, min(self._chunk_index + 2, len(chunks))))
        self._loaded = {
            key: value for key, value in self._loaded.items() if key in keep
        }
        for chunk_index in keep:
            if chunk_index not in self._loaded:
                events = _load_timeline_chunk(self.cache, chunks[chunk_index])
                if events is None:
                    file_name = chunks[chunk_index]["file"]
                    raise ValueError(f"invalid replay chunk {file_name}")
                self._loaded[chunk_index] = events


def _load_identity(
    cache: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Load the small identity rows seeded before playback starts.

    Kept separate so a prepared-timeline hit skips the heavy endpoint files
    (laps, location, position, ...) entirely; only these three small files are
    read.
    """
    sessions = load_json(cache / "sessions.json")
    session = sessions[0] if sessions else {}
    meetings_path = cache / "meetings.json"
    meetings = load_json(meetings_path) if meetings_path.exists() else []
    drivers = load_json(cache / "drivers.json")
    return session, meetings, drivers


def prepare_timeline(
    cache: Path, data: dict[str, Any]
) -> tuple[list[tuple[float, str, dict[str, Any]]], dict[str, Any]]:
    """Build + persist the prepared timeline and lap checkpoints from raw data.

    Single preparation path used by both the bulk cache run and the lazy
    replay rebuild, so the timeline and checkpoints always come from the same
    ``build_timeline`` event stream.
    """
    events = build_timeline(data)
    save_timeline(cache, events, data)
    checkpoints = build_checkpoints(
        events, data["session"], data["meetings"], data["drivers"]
    )
    save_checkpoints(cache, checkpoints, data["session"].get("session_key"))
    index = load_timeline(cache, data["session"].get("session_key"))
    if index is None:
        raise ValueError("prepared replay timeline index is invalid")
    return events, index


def _checkpoint_dir(cache: Path) -> Path:
    """Directory holding one checkpoint state file per completed lap."""
    return cache / "checkpoints"


def _checkpoint_index_path(cache: Path) -> Path:
    return _checkpoint_dir(cache) / "index.json"


def _checkpoint_state_path(cache: Path, lap: int) -> Path:
    return _checkpoint_dir(cache) / f"checkpoint-{lap:04d}.json"


def build_checkpoints(
    events: list[tuple[float, str, dict[str, Any]]],
    session: dict[str, Any],
    meetings: list[dict[str, Any]],
    drivers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Snapshot the buffer at each completed lap by replaying the prepared events
    through a LiveState, using the same update/keying as live playback.

    A checkpoint only contains state available at its race-clock position: the
    snapshot is taken immediately after the event that completes each new lap,
    so later laps, stints, and messages are never present. Identity rows are
    seeded first, matching ``replay_session``'s start.
    """
    state = LiveState()
    state.update("v1/sessions", session)
    for meeting in meetings:
        state.update("v1/meetings", meeting)
    for driver in drivers:
        state.update("v1/drivers", driver)

    checkpoints: list[dict[str, Any]] = []
    current_lap = 0
    for cursor, (offset, topic, payload) in enumerate(events):
        state.update(topic, payload)
        if topic == "v1/laps":
            lap = int(payload.get("lap_number") or 0)
            if lap > current_lap:
                current_lap = lap
                checkpoints.append(
                    {
                        "lap": current_lap,
                        "time": offset,
                        "cursor": cursor + 1,
                        "state": state.snapshot_docs(),
                    }
                )
    return checkpoints


def save_checkpoints(
    cache: Path, checkpoints: list[dict[str, Any]], session_key: int
) -> None:
    """Persist per-lap checkpoint states plus a lightweight cursor index.

    State files are written before the index so a partially-written set is
    detected (the index points at files that must already exist).
    """
    index: list[dict[str, Any]] = []
    for checkpoint in checkpoints:
        lap = checkpoint["lap"]
        file_name = f"checkpoint-{lap:04d}.json"
        atomic_write_json(_checkpoint_state_path(cache, lap), checkpoint)
        index.append(
            {
                "lap": checkpoint["lap"],
                "time": checkpoint["time"],
                "cursor": checkpoint["cursor"],
                "file": file_name,
            }
        )
    atomic_write_json(
        _checkpoint_index_path(cache),
        {
            "format_version": _TIMELINE_FORMAT_VERSION,
            "session_key": session_key,
            "checkpoints": index,
        },
    )


def load_checkpoint_index(
    cache: Path, session_key: int, *, validate_states: bool = False
) -> list[dict[str, Any]] | None:
    """Return the lightweight checkpoint index, or None if unusable.

    Unusable means missing, wrong format version, wrong session, or malformed.
    """
    path = _checkpoint_index_path(cache)
    if not path.exists():
        return None
    try:
        blob = load_json(path)
    except (OSError, ValueError):
        return None
    if not isinstance(blob, dict):
        return None
    if blob.get("format_version") != _TIMELINE_FORMAT_VERSION:
        return None
    if blob.get("session_key") != session_key:
        return None
    entries = blob.get("checkpoints")
    if not isinstance(entries, list):
        return None
    previous_time = -1.0
    previous_lap = 0
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("lap"), int)
            or not isinstance(entry.get("time"), (int, float))
            or not isinstance(entry.get("cursor"), int)
            or not isinstance(entry.get("file"), str)
        ):
            return None
        if entry["lap"] <= previous_lap or float(entry["time"]) < previous_time:
            return None
        if validate_states and load_checkpoint_state(cache, entry) is None:
            return None
        previous_lap = entry["lap"]
        previous_time = float(entry["time"])
    return entries


def load_checkpoint_state(cache: Path, entry: dict[str, Any]) -> dict[str, Any] | None:
    """Load one checkpoint's snapshot from disk, or None if missing/malformed."""
    file_name = entry.get("file")
    if not isinstance(file_name, str):
        return None
    path = _checkpoint_dir(cache) / file_name
    if not path.exists():
        return None
    try:
        checkpoint = load_json(path)
    except (OSError, ValueError):
        return None
    if not isinstance(checkpoint, dict) or not isinstance(
        checkpoint.get("state"), dict
    ):
        return None
    if any(checkpoint.get(key) != entry.get(key) for key in ("lap", "time", "cursor")):
        return None
    return checkpoint


def nearest_checkpoint_by_time(
    checkpoints: Sequence[dict[str, Any]], time_: float
) -> dict[str, Any] | None:
    """Last checkpoint at or before ``time_`` (index is time-ascending)."""
    chosen: dict[str, Any] | None = None
    for checkpoint in checkpoints:
        if float(checkpoint["time"]) <= time_:
            chosen = checkpoint
        else:
            break
    return chosen


def nearest_checkpoint_by_lap(
    checkpoints: Sequence[dict[str, Any]], lap: int
) -> dict[str, Any] | None:
    """Last checkpoint at or before ``lap`` (index is lap-ascending)."""
    chosen: dict[str, Any] | None = None
    for checkpoint in checkpoints:
        if int(checkpoint["lap"]) <= lap:
            chosen = checkpoint
        else:
            break
    return chosen


def restore_checkpoint(state: LiveState, checkpoint: dict[str, Any]) -> int:
    """Restore ``state`` from one checkpoint; return the cursor to resume from."""
    state.replace_docs(checkpoint["state"])
    return int(checkpoint["cursor"])


def _restore_seek(
    cache: Path,
    session_key: int,
    reader: TimelineReader,
    session: dict[str, Any],
    meetings: list[dict[str, Any]],
    drivers: list[dict[str, Any]],
    seek_time: float,
    buffer: LiveState,
) -> tuple[int, int]:
    """Restore nearest checkpoint <= ``seek_time`` and fast-forward to it.

    Returns ``(cursor, current_lap)``. Builds checkpoints from the loaded
    timeline when they are missing (e.g. an older cache), then falls back to
    the identity seed when there is no checkpoint before ``seek_time``. Only
    events at or before ``seek_time`` are applied, so no future data leaks in.
    """
    index = load_checkpoint_index(cache, session_key)
    if index is None:
        raise ValueError("missing or invalid replay checkpoint index")

    entry = nearest_checkpoint_by_time(index or [], seek_time)
    checkpoint = load_checkpoint_state(cache, entry) if entry is not None else None
    if checkpoint is None:
        buffer.update("v1/sessions", session)
        for meeting in meetings:
            buffer.update("v1/meetings", meeting)
        for driver in drivers:
            buffer.update("v1/drivers", driver)
        cursor = 0
        current_lap = 0
    else:
        cursor = restore_checkpoint(buffer, checkpoint)
        current_lap = int(checkpoint["lap"])

    reader.seek_cursor(cursor)
    event = reader.peek()
    while event is not None and event[0] <= seek_time:
        _, topic, payload = reader.pop()
        buffer.update(topic, payload)
        if topic == "v1/laps":
            current_lap = max(current_lap, int(payload.get("lap_number") or 0))
        event = reader.peek()
    return reader.cursor, current_lap


def replay_session(
    session_key: int,
    speed: float = 10.0,
    state: LiveState | None = None,
    *,
    stop_event: threading.Event | None = None,
    pause_event: threading.Event | None = None,
    progress: dict[str, Any] | None = None,
    on_seeded: Callable[[], None] | None = None,
    seek_time: float | None = None,
    seek_lap: int | None = None,
    speed_holder: dict[str, float] | None = None,
) -> None:
    """
    Download/cache one session, clear the buffer, then feed it chronologically.

    ``state`` is the buffer to fill; it defaults to ``LIVE_STATE`` for the CLI
    harness, but the ``ReplayController`` always passes its own private
    ``LiveState`` so replay never clears or seeds live data.

    Blocks until the replay reaches race end; the final state is left visible.
    When ``stop_event`` is set, replay exits early (without clearing state if it
    has not started yet). ``pause_event`` suspends the replay clock while set.
    ``progress`` (when provided) is updated in place with the authoritative
    replay clock, total duration, and lap progress. ``on_seeded`` fires right
    after identity + the first data are written, so the API can mark the replay
    as actively running. ``seek_time`` or ``seek_lap`` restores the nearest
    prepared checkpoint and resumes from there. ``speed_holder`` is a mutable
    ``{"value": float}`` the clock reads each tick so the speed can change
    without restarting the worker.
    """
    if float(speed) not in _SUPPORTED_SPEEDS:
        raise ValueError("speed must be one of 1, 2, 5, or 10")
    buffer = state if state is not None else LIVE_STATE

    cache = replay_dir(session_key)
    timeline_index = load_timeline(cache, session_key)
    if timeline_index is None or load_checkpoint_index(cache, session_key) is None:
        data = download_replay_data(OpenF1Client(), session_key, cache=cache)
        if stop_event is not None and stop_event.is_set():
            return
        _, timeline_index = prepare_timeline(cache, data)
        session = data["session"]
        meetings = data["meetings"]
        drivers = data["drivers"]
    else:
        session, meetings, drivers = _load_identity(cache)
    reader = TimelineReader(cache, timeline_index)

    total_duration = timeline_index["total_duration"]
    total_laps = timeline_index["total_laps"]
    if progress is not None:
        progress["total_duration"] = total_duration
        progress["total_laps"] = total_laps

    # Clear stale live/test data, then seed identity or restore a checkpoint.
    buffer.clear()
    if seek_time is not None and seek_lap is not None:
        raise ValueError("seek_time and seek_lap are mutually exclusive")
    if seek_lap is not None:
        index = load_checkpoint_index(cache, session_key)
        checkpoint = nearest_checkpoint_by_lap(index or [], seek_lap)
        target = float(checkpoint["time"]) if checkpoint is not None else 0.0
    else:
        target = min(max(seek_time or 0.0, 0.0), total_duration)
    if seek_time is not None or seek_lap is not None:
        _, current_lap = _restore_seek(
            cache, session_key, reader, session, meetings, drivers, target, buffer
        )
        base_offset = target
    else:
        buffer.update("v1/sessions", session)
        for meeting in meetings:
            buffer.update("v1/meetings", meeting)
        for driver in drivers:
            buffer.update("v1/drivers", driver)
        current_lap, base_offset = 0, 0.0
        reader.seek_cursor(0)

    if progress is not None:
        progress["current_time"] = min(base_offset, total_duration)
        progress["current_lap"] = current_lap

    if on_seeded is not None:
        on_seeded()

    def current_speed() -> float:
        return speed_holder["value"] if speed_holder is not None else speed

    print(
        f"replay: session_key={session_key} "
        f"events={timeline_index['event_count']} speed={speed}x"
    )

    replay_time = base_offset
    last_wall = time.monotonic()
    event = reader.peek()
    while event is not None:
        if stop_event is not None and stop_event.is_set():
            print("replay: stopped early")
            return
        if pause_event is not None and pause_event.is_set():
            pause_event.wait(timeout=0.1)
            last_wall = time.monotonic()
            continue
        now = time.monotonic()
        replay_time += (now - last_wall) * current_speed()
        last_wall = now
        if replay_time > total_duration:
            replay_time = total_duration
        if progress is not None:
            progress["current_time"] = replay_time
            progress["current_lap"] = current_lap
        while event is not None and event[0] <= replay_time:
            _, topic, payload = reader.pop()
            buffer.update(topic, payload)
            if topic == "v1/laps":
                current_lap = max(current_lap, int(payload.get("lap_number") or 0))
            event = reader.peek()
        if event is None:
            break
        wait = (event[0] - replay_time) / current_speed()
        time.sleep(max(0.0, min(wait, 0.1)))

    if progress is not None:
        progress["current_time"] = total_duration
        progress["current_lap"] = current_lap

    print("replay: reached race end; leaving final state visible")


class ReplayController:
    """
    Runtime start/stop wrapper around the blocking replay producer.

    One controller is shared by the FastAPI replay endpoints and the startup
    path. The controller owns a private ``LiveState`` (``self.state``) that the
    producer fills, so replay never touches the live-only ``LIVE_STATE``.
    ``on_before_start`` / ``on_after_stop`` are optional lifecycle hooks, and
    ``on_reset`` fires when a new replay starts or seeks (wired by the replay
    broadcaster so it forgets its diff state).
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._lock = threading.Lock()
        self._transition_lock = threading.Lock()
        self.status = "idle"
        self.session_key: int | None = None
        self.speed: float | None = None
        self._speed_holder: dict[str, float] = {"value": 10.0}
        self.error: str | None = None
        # Private buffer the replay producer fills; live data stays in LIVE_STATE.
        self.state = LiveState()
        self.on_before_start: Callable[[], None] | None = None
        self.on_after_stop: Callable[[], None] | None = None
        # Fired when a new replay starts or seeks, so the replay broadcaster can
        # forget its diff state and push the fresh replay data cleanly.
        self.on_reset: Callable[[], None] | None = None
        self.progress: dict[str, Any] = {
            "current_time": 0.0,
            "total_duration": None,
            "current_lap": 0,
            "total_laps": None,
        }

    def start(self, session_key: int, speed: float = 10.0) -> None:
        """Stop any running replay, then start a new one in a daemon thread."""
        self._validate_speed(speed)
        with self._transition_lock:
            if self.on_before_start is not None:
                self.on_before_start()
            self._stop_and_join_worker()
            with self._lock:
                self._launch(session_key, speed, seek_time=None, seek_lap=None)

    def seek(self, time_: float) -> None:
        """Restart the active replay at the nearest checkpoint <= ``time_``.

        Only valid while a replay is running/paused/finished. Paused state is
        preserved across the seek.
        """
        with self._transition_lock:
            with self._lock:
                if self.status not in {"running", "paused", "finished"}:
                    return
                if self.session_key is None or self.speed is None:
                    return
                session_key, speed = self.session_key, self.speed
                was_paused = self.status == "paused"
            self._stop_and_join_worker()
            with self._lock:
                self._launch(
                    session_key,
                    speed,
                    seek_time=time_,
                    seek_lap=None,
                    paused=was_paused,
                )

    def seek_lap(self, lap: int) -> None:
        """Restart the active replay at the checkpoint for ``lap``."""
        with self._transition_lock:
            with self._lock:
                if self.status not in {"running", "paused", "finished"}:
                    return
                if self.session_key is None or self.speed is None:
                    return
                session_key, speed = self.session_key, self.speed
                was_paused = self.status == "paused"
            self._stop_and_join_worker()
            with self._lock:
                self._launch(
                    session_key,
                    speed,
                    seek_time=None,
                    seek_lap=lap,
                    paused=was_paused,
                )

    def set_speed(self, speed: float) -> bool:
        """Change the active replay speed in place; False when not runnable."""
        with self._transition_lock:
            with self._lock:
                if self.status not in {"running", "paused"}:
                    return False
                if float(speed) not in _SUPPORTED_SPEEDS:
                    return False
                self.speed = speed
                self._speed_holder["value"] = speed
                return True

    def _launch(
        self,
        session_key: int,
        speed: float,
        *,
        seek_time: float | None,
        seek_lap: int | None,
        paused: bool = False,
    ) -> None:
        """Start a fresh producer after the prior worker has been joined."""
        stop_event = threading.Event()
        self._stop = stop_event
        pause_event = threading.Event()
        if paused:
            pause_event.set()
        self._pause = pause_event
        holder = {"value": speed}
        self._speed_holder = holder
        self.status = "downloading"
        self.session_key = session_key
        self.speed = speed
        self.error = None
        self.progress = {
            "current_time": 0.0,
            "total_duration": None,
            "current_lap": 0,
            "total_laps": None,
        }
        if self.on_reset is not None:
            self.on_reset()
        self._thread = threading.Thread(
            target=self._run,
            args=(
                session_key,
                speed,
                stop_event,
                self._pause,
                self.progress,
                holder,
                seek_time,
                seek_lap,
            ),
            name="openf1-replay",
            daemon=True,
        )
        self._thread.start()

    def pause(self) -> None:
        """Suspend the replay clock; playback resumes from the same position."""
        with self._transition_lock:
            with self._lock:
                if self.status == "running":
                    self._pause.set()
                    self.status = "paused"

    def resume(self) -> None:
        """Continue a paused replay from where it left off."""
        with self._transition_lock:
            with self._lock:
                if self.status == "paused":
                    self._pause.clear()
                    self.status = "running"

    def stop(self) -> None:
        """Stop the replay; fire the optional on_after_stop hook."""
        with self._transition_lock:
            with self._lock:
                was_active = self.status in {
                    "downloading",
                    "running",
                    "paused",
                    "finished",
                }
                self.status = "idle"
            self._stop_and_join_worker()
        if was_active and self.on_after_stop is not None:
            self.on_after_stop()

    def _stop_and_join_worker(self) -> None:
        """Signal the current worker and join without holding the state lock."""
        with self._lock:
            thread = self._thread
            self._stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join()

    @staticmethod
    def _validate_speed(speed: float) -> None:
        if float(speed) not in _SUPPORTED_SPEEDS:
            raise ValueError("speed must be one of 1, 2, 5, or 10")

    def _run(
        self,
        session_key: int,
        speed: float,
        stop_event: threading.Event,
        pause_event: threading.Event,
        progress: dict[str, Any],
        speed_holder: dict[str, float],
        seek_time: float | None = None,
        seek_lap: int | None = None,
    ) -> None:
        try:
            replay_session(
                session_key,
                speed=speed,
                state=self.state,
                stop_event=stop_event,
                pause_event=pause_event,
                progress=progress,
                on_seeded=lambda: self._on_seeded(stop_event, pause_event),
                seek_time=seek_time,
                seek_lap=seek_lap,
                speed_holder=speed_holder,
            )
        except Exception as exc:  # noqa: BLE001 — keep API up if replay dies
            # A superseded worker must not clobber a newer replay's status.
            if stop_event.is_set():
                return
            with self._lock:
                if self._stop is not stop_event:
                    return
                self.error = str(exc)
                self.status = "error"
            print(f"Replay worker exited: {exc}")
            return
        if not stop_event.is_set():
            with self._lock:
                if self._stop is stop_event:
                    self.status = "finished"

    def _on_seeded(
        self, stop_event: threading.Event, pause_event: threading.Event
    ) -> None:
        """Mark the replay as running (or paused) once its own state is seeded."""
        with self._lock:
            if self._stop is stop_event and not stop_event.is_set():
                self.status = "paused" if pause_event.is_set() else "running"

    def snapshot(self) -> dict[str, Any]:
        """Current controller state for /api/replays/{replay_id}/status."""
        with self._lock:
            return {
                "status": self.status,
                "running": self._thread is not None and self._thread.is_alive(),
                "session_key": self.session_key,
                "speed": self.speed,
                "error": self.error,
                "current_time": self.progress["current_time"],
                "total_duration": self.progress["total_duration"],
                "current_lap": self.progress["current_lap"],
                "total_laps": self.progress["total_laps"],
            }


def main() -> None:
    """CLI: replay one historical session (developer-controlled, no frontend UI)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Replay one completed OpenF1 session (CLI default: LIVE_STATE)."
    )
    parser.add_argument("--session-key", type=int, required=True)
    parser.add_argument("--speed", type=float, default=10.0)
    args = parser.parse_args()
    replay_session(args.session_key, speed=args.speed)


if __name__ == "__main__":
    main()
