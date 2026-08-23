"""
Build API SessionState from the in-memory live buffer.

Input:  LiveState (v1/sessions, optional meetings/weather/race_control/laps)
Output: SessionState or None if no session document is stored yet
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from formula1_strategy_tool.acquisition.live_state import LiveState
from formula1_strategy_tool.api.schemas import SessionState


def _docs(state: LiveState, topic: str) -> list[dict[str, Any]]:
    return state.docs_for(topic)


def latest_session_doc(state: LiveState) -> dict[str, Any] | None:
    """
    Return the session document with the highest session_key.

    The buffer can briefly hold more than one session row (bootstrap seed plus
    an MQTT push for the next session before the session monitor swaps state).
    ``sessions[0]`` would then return stale metadata; max session_key is safe.
    """
    sessions = _docs(state, "v1/sessions")
    if not sessions:
        return None
    return max(sessions, key=lambda row: int(row.get("session_key") or 0))


def _latest_meeting_doc(
    state: LiveState, session: dict[str, Any]
) -> dict[str, Any] | None:
    """Pick the meeting row matching the session's meeting_key when possible."""
    meetings = _docs(state, "v1/meetings")
    if not meetings:
        return None
    meeting_key = session.get("meeting_key")
    if meeting_key is not None:
        for row in meetings:
            if row.get("meeting_key") == meeting_key:
                return row
    return max(meetings, key=lambda row: int(row.get("meeting_key") or 0))


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _session_status(session: dict[str, Any]) -> str:
    """Rough status from schedule times (good enough until live flags improve)."""
    now = datetime.now(timezone.utc)
    start = _parse_dt(session.get("date_start"))
    end = _parse_dt(session.get("date_end"))
    if session.get("is_cancelled"):
        return "cancelled"
    if start and now < start:
        return "upcoming"
    if end and now > end:
        return "completed"
    return "active"


def _race_control_status(state: LiveState) -> str:
    """Prefer the newest race_control flag; default GREEN."""
    rows = _docs(state, "v1/race_control")
    if not rows:
        return "GREEN"
    # Newest by date.
    rows = sorted(rows, key=lambda r: str(r.get("date") or ""))
    for row in reversed(rows):
        flag = row.get("flag")
        if flag:
            return str(flag).upper()
    return "GREEN"


def _current_lap(state: LiveState) -> int:
    """Max lap_number seen in stored laps (or race_control)."""
    best = 0
    for row in _docs(state, "v1/laps"):
        best = max(best, int(row.get("lap_number") or 0))
    for row in _docs(state, "v1/race_control"):
        best = max(best, int(row.get("lap_number") or 0))
    return best


def _latest_weather(state: LiveState) -> dict[str, Any] | None:
    rows = _docs(state, "v1/weather")
    if not rows:
        return None
    return max(rows, key=lambda r: str(r.get("date") or ""))


def session_from_live(
    state: LiveState, total_laps: int | None = None
) -> SessionState | None:
    """
    Map LIVE_STATE into SessionState.

    Returns None when v1/sessions has not been seeded yet.

    ``total_laps`` is the authoritative scheduled/known race distance when a
    caller has one (replay knows it from the prepared timeline). Live callers
    pass nothing because OpenF1's live session object carries no lap count, so
    the value stays null rather than inventing a denominator.
    """
    session = latest_session_doc(state)
    if session is None:
        return None

    meeting = _latest_meeting_doc(state, session)
    meeting_name = (
        session.get("circuit_short_name") or session.get("location") or "Unknown"
    )
    if meeting:
        meeting_name = str(meeting.get("meeting_name") or meeting_name)

    weather = _latest_weather(state)
    track_temp = float(weather.get("track_temperature") or 0.0) if weather else 0.0
    air_temp = float(weather.get("air_temperature") or 0.0) if weather else 0.0
    rainfall_raw = weather.get("rainfall") if weather else 0
    rainfall = bool(rainfall_raw) and rainfall_raw not in (0, "0", 0.0)

    # total_laps is not on the live session object, so it stays None unless a
    # caller supplies an authoritative value (e.g. replay from its timeline).
    current = _current_lap(state)

    return SessionState(
        meeting_name=str(meeting_name),
        session_name=str(
            session.get("session_name")
            or session.get("session_type")
            or "Session"
        ),
        session_status=_session_status(session),
        current_lap=current,
        total_laps=total_laps,
        track_temperature=track_temp,
        air_temperature=air_temp,
        rainfall=rainfall,
        race_control_status=_race_control_status(state),
    )
