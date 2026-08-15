"""
Developer replay harness: replay one completed session through LIVE_STATE.

Input:  session_key (required), replay speed (default 10x)
Output: fills LIVE_STATE chronologically so the existing /ws/live broadcaster
        and frontend advance exactly as they would during a live race.

This is the smallest useful end-to-end test: it reuses the real OpenF1 REST
acquisition, LIVE_STATE, WebSocket broadcaster, and prediction path. The only
new code is the replay producer itself — nothing in TrackMap, Leaderboard,
RaceHeader, or StrategyPanel changes.

No-future-leakage rule:
    A completed race contains data that was not known at an earlier lap, so the
    producer only exposes a row once the replay clock reaches its timestamp.
    Stints are reconstructed live-like: the historical ``lap_end`` is dropped
    so the model only ever sees the current, open-ended stint.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from formula1_strategy_tool.acquisition.client import OpenF1Client, get_or_download
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

# Location is high-frequency; replay thins it to ~1 sample/driver/second so a
# full session stays memory-friendly while the map still moves smoothly.
_LOCATION_THIN_SECONDS = 1.0
# Download window for the paginated location endpoint (whole-session returns 422).
_LOCATION_WINDOW_SECONDS = 600


def replay_dir(session_key: int) -> Path:
    """Cache directory for one session's replay data (separate from data/raw)."""
    return Path("data/replay") / str(session_key)


_SESSION_LIST_START_YEAR = 2023


def fetch_replay_sessions(client: OpenF1Client) -> list[dict[str, Any]]:
    """
    Download completed Race sessions from OpenF1 (2023 → current year).

    Returns one dict per finished race with the fields the frontend needs to
    build a year → country picker.
    """
    now = datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    for year in range(_SESSION_LIST_START_YEAR, now.year + 1):
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


def list_replay_sessions() -> list[dict[str, Any]]:
    """Return completed Race sessions, fetching (and caching) on first call."""
    global _sessions_cache
    if _sessions_cache is None:
        _sessions_cache = fetch_replay_sessions(OpenF1Client())
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
    ends = (parse_openf1_datetime(row.get("date_end")) for row in laps)
    return max((end for end in ends if end is not None), default=None)


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
    start = parse_openf1_datetime(session.get("date_start"))
    last = _last_lap_end(laps)
    end = (
        last + timedelta(minutes=5)
        if last
        else parse_openf1_datetime(session.get("date_end"))
    )
    if start is None or end is None or end <= start:
        return []

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


def build_timeline(data: dict[str, Any]) -> list[tuple[float, str, dict[str, Any]]]:
    """
    Normalize one session's rows into a chronological (offset, topic, payload)
    timeline. Identity rows (session/meetings/drivers) are not included here —
    they are seeded separately before playback starts.
    """
    t0 = _reference_time(data["session"], data["laps"])
    events: list[tuple[float, str, dict[str, Any]]] = []

    # Laps become known only when they finish (date_end) — never early.
    for row in data["laps"]:
        offset = _event_offset(row.get("date_end") or row.get("date_start"), t0)
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


def replay_session(
    session_key: int,
    speed: float = 10.0,
    state: LiveState | None = None,
    *,
    stop_event: threading.Event | None = None,
    pause_event: threading.Event | None = None,
    progress: dict[str, Any] | None = None,
    on_seeded: Callable[[], None] | None = None,
) -> None:
    """
    Download/cache one session, clear the buffer, then feed it chronologically.

    Blocks until the replay reaches race end; the final state is left visible.
    When ``stop_event`` is set, replay exits early (without clearing state if it
    has not started yet). ``pause_event`` suspends the replay clock while set.
    ``progress`` (when provided) is updated in place with the authoritative
    replay clock, total duration, and lap progress. ``on_seeded`` fires right
    after identity + the first data are written, so the API can mark the replay
    as actively running.
    """
    if speed <= 0:
        raise ValueError("speed must be positive")
    buffer = state if state is not None else LIVE_STATE

    client = OpenF1Client()
    data = download_replay_data(client, session_key)
    if stop_event is not None and stop_event.is_set():
        return
    events = build_timeline(data)

    total_duration = events[-1][0] if events else 0.0
    total_laps = max(
        (int(row.get("lap_number") or 0) for row in data["laps"]), default=0
    )
    if progress is not None:
        progress["total_duration"] = total_duration
        progress["total_laps"] = total_laps

    # Clear stale live/test data, then seed non-time-varying identity first.
    buffer.clear()
    buffer.update("v1/sessions", data["session"])
    for meeting in data["meetings"]:
        buffer.update("v1/meetings", meeting)
    for driver in data["drivers"]:
        buffer.update("v1/drivers", driver)

    if on_seeded is not None:
        on_seeded()

    print(f"replay: session_key={session_key} events={len(events)} speed={speed}x")

    start = time.monotonic()
    paused_since: float | None = None
    paused_total = 0.0
    cursor = 0
    total = len(events)
    current_lap = 0
    while cursor < total:
        if stop_event is not None and stop_event.is_set():
            print("replay: stopped early")
            return
        if pause_event is not None:
            if pause_event.is_set():
                if paused_since is None:
                    paused_since = time.monotonic()
                pause_event.wait(timeout=0.1)
                continue
            if paused_since is not None:
                paused_total += time.monotonic() - paused_since
                paused_since = None
        elapsed = (time.monotonic() - start - paused_total) * speed
        if progress is not None:
            progress["current_time"] = min(elapsed, total_duration)
            progress["current_lap"] = current_lap
        while cursor < total and events[cursor][0] <= elapsed:
            _, topic, payload = events[cursor]
            buffer.update(topic, payload)
            if topic == "v1/laps":
                current_lap = max(current_lap, int(payload.get("lap_number") or 0))
            cursor += 1
        if cursor >= total:
            break
        wait = (events[cursor][0] - elapsed) / speed
        time.sleep(max(0.0, min(wait, 0.1)))

    if progress is not None:
        progress["current_time"] = total_duration
        progress["current_lap"] = current_lap

    print("replay: reached race end; leaving final state visible")


class ReplayController:
    """
    Runtime start/stop wrapper around the blocking replay producer.

    One controller is shared by the FastAPI replay endpoints and the startup
    path. ``on_before_start`` is an optional hook (wired by main.py) used to
    stop the live MQTT listener so its pushes cannot mix with replay data;
    ``on_after_stop`` is its counterpart, restoring live mode once the user
    deliberately leaves replay.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._lock = threading.Lock()
        self.status = "idle"
        self.session_key: int | None = None
        self.speed: float | None = None
        self.error: str | None = None
        self.on_before_start: Callable[[], None] | None = None
        self.on_after_stop: Callable[[], None] | None = None
        self.progress: dict[str, Any] = {
            "current_time": 0.0,
            "total_duration": None,
            "current_lap": 0,
            "total_laps": None,
        }

    def start(self, session_key: int, speed: float = 10.0) -> None:
        """Stop any running replay, then start a new one in a daemon thread."""
        with self._lock:
            self._stop.set()
            stop_event = threading.Event()
            self._stop = stop_event
            self._pause = threading.Event()
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
            if self.on_before_start is not None:
                self.on_before_start()
            self._thread = threading.Thread(
                target=self._run,
                args=(session_key, speed, stop_event, self._pause, self.progress),
                name="openf1-replay",
                daemon=True,
            )
            self._thread.start()

    def pause(self) -> None:
        """Suspend the replay clock; playback resumes from the same position."""
        with self._lock:
            if self.status == "running":
                self._pause.set()
                self.status = "paused"

    def resume(self) -> None:
        """Continue a paused replay from where it left off."""
        with self._lock:
            if self.status == "paused":
                self._pause.clear()
                self.status = "running"

    def stop(self) -> None:
        """Stop the replay and restore live mode via the on_after_stop hook."""
        with self._lock:
            was_active = self.status in {
                "downloading",
                "running",
                "paused",
                "finished",
            }
            self._stop.set()
            self.status = "idle"
        if was_active and self.on_after_stop is not None:
            self.on_after_stop()

    def _run(
        self,
        session_key: int,
        speed: float,
        stop_event: threading.Event,
        pause_event: threading.Event,
        progress: dict[str, Any],
    ) -> None:
        try:
            replay_session(
                session_key,
                speed=speed,
                stop_event=stop_event,
                pause_event=pause_event,
                progress=progress,
                on_seeded=self._on_seeded,
            )
        except Exception as exc:  # noqa: BLE001 — keep API up if replay dies
            self.error = str(exc)
            self.status = "error"
            print(f"Replay worker exited: {exc}")
            return
        if not stop_event.is_set():
            self.status = "finished"

    def _on_seeded(self) -> None:
        """Mark the replay as actively running once data is in LIVE_STATE."""
        with self._lock:
            self.status = "running"

    def snapshot(self) -> dict[str, Any]:
        """Current controller state for the /api/replay/status endpoint."""
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


replay_controller = ReplayController()


def main() -> None:
    """CLI: replay one historical session (developer-controlled, no frontend UI)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Replay one completed OpenF1 session through LIVE_STATE."
    )
    parser.add_argument("--session-key", type=int, required=True)
    parser.add_argument("--speed", type=float, default=10.0)
    args = parser.parse_args()
    replay_session(args.session_key, speed=args.speed)


if __name__ == "__main__":
    main()
