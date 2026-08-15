"""
Seed LIVE_STATE from OpenF1 REST so the API has data before MQTT traffic.

Input:  session_key (default "latest") via authenticated openf1_get
Output: rows written into LiveState; returns the resolved session_key

MQTT only pushes changes. At startup we pull a REST snapshot so /api/drivers
and live model features have something to work with. Laps/weather/race_control
are kept in full (needed for pace + flags). Position/intervals are reduced to
the latest row per driver to limit payload size between sessions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from formula1_strategy_tool.acquisition.auth import openf1_get
from formula1_strategy_tool.acquisition.live_drivers import _latest_by_driver
from formula1_strategy_tool.acquisition.live_state import LIVE_STATE, LiveState

# Same families the MQTT listener cares about, plus session context.
_SEED_ENDPOINTS = (
    "drivers",
    "laps",
    "stints",
    "pit",
    "position",
    "intervals",
    "weather",
    "race_control",
)

# Location is high-frequency (the full-session endpoint returns 422), so a
# small window anchored to the session's actual end is pulled and reduced to
# the latest sample per driver. Fallback windows widen if the tail is empty
# (e.g. a red-flagged session whose location data ended early).
_LOCATION_WINDOW_MINUTES = 2
_LOCATION_FALLBACK_WINDOWS_MINUTES = (30, 180)


def _reference_time(buffer: LiveState, session: dict) -> datetime:
    """
    Best guess for the moment the session's on-track activity last happened.

    Prefers the newest lap timestamp already in the buffer (a completed race's
    location data can end well before its scheduled ``date_end``), then the
    session's ``date_end``/``date_start``, then now for a live session.
    """
    latest: str | None = None
    for row in buffer.docs.get("v1/laps", {}).values():
        for field in ("date_end", "date_start"):
            value = row.get(field)
            if isinstance(value, str) and (latest is None or value > latest):
                latest = value

    for candidate in (latest, session.get("date_end"), session.get("date_start")):
        if candidate:
            return datetime.fromisoformat(str(candidate).replace("Z", "+00:00"))
    return datetime.now(timezone.utc)


def bootstrap_live_state(
    state: LiveState | None = None,
    session_key: str | int = "latest",
) -> int:
    """
    Pull a REST snapshot into the live buffer.

    Returns:
        Resolved numeric session_key that was seeded.
    """
    buffer = state if state is not None else LIVE_STATE

    sessions = openf1_get("sessions", {"session_key": session_key})
    if not sessions:
        raise RuntimeError(f"no sessions for session_key={session_key!r}")
    session = sessions[0]
    resolved = int(session["session_key"])
    params = {"session_key": resolved}

    # Store session + meeting name for /api/session.
    buffer.update("v1/sessions", session)
    meeting_key = session.get("meeting_key")
    if meeting_key is not None:
        meetings = openf1_get("meetings", {"meeting_key": meeting_key})
        for row in meetings:
            buffer.update("v1/meetings", row)

    for endpoint in _SEED_ENDPOINTS:
        rows = openf1_get(endpoint, params)
        # Position/intervals streams are huge — one row per driver is enough to
        # score the *current* lap after merge_asof.
        if endpoint in {"position", "intervals"}:
            rows = list(_latest_by_driver(rows).values())

        topic = f"v1/{endpoint}"
        for row in rows:
            if isinstance(row, dict):
                buffer.update(topic, row)

        print(f"bootstrap {topic}: stored={len(buffer.docs.get(topic, {}))}")

    # Location is fetched separately: the unfiltered endpoint rejects
    # whole-session requests, so anchor a small window to the last known
    # activity and keep only the latest sample per car.
    reference = _reference_time(buffer, session)
    location_rows: list[dict] = []
    windows = (_LOCATION_WINDOW_MINUTES,) + _LOCATION_FALLBACK_WINDOWS_MINUTES
    for window_minutes in windows:
        since = (reference - timedelta(minutes=window_minutes)).isoformat()
        try:
            location_rows = openf1_get("location", {**params, "date>": since})
        except Exception as exc:  # noqa: BLE001 — location is optional polish
            print(f"bootstrap v1/location window {window_minutes}m failed: {exc}")
            location_rows = []
        if location_rows:
            break

    for row in _latest_by_driver(location_rows).values():
        buffer.update("v1/location", row)

    print(f"bootstrap v1/location: stored={len(buffer.docs.get('v1/location', {}))}")

    return resolved
