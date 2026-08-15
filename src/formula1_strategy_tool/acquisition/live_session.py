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


def session_from_live(state: LiveState) -> SessionState | None:
    """
    Map LIVE_STATE into SessionState.

    Returns None when v1/sessions has not been seeded yet.
    """
    sessions = _docs(state, "v1/sessions")
    if not sessions:
        return None
    session = sessions[0]

    meetings = _docs(state, "v1/meetings")
    meeting_name = (
        session.get("circuit_short_name") or session.get("location") or "Unknown"
    )
    if meetings:
        meeting_name = str(
            meetings[0].get("meeting_name") or meeting_name
        )

    weather = _latest_weather(state)
    track_temp = float(weather.get("track_temperature") or 0.0) if weather else 0.0
    air_temp = float(weather.get("air_temperature") or 0.0) if weather else 0.0
    rainfall_raw = weather.get("rainfall") if weather else 0
    rainfall = bool(rainfall_raw) and rainfall_raw not in (0, "0", 0.0)

    # total_laps is not on the session object — use current lap as a floor;
    # FE can treat 0 as unknown. Race weekends often know this from elsewhere later.
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
        total_laps=current,  # unknown true distance; avoid guessing a lap count
        track_temperature=track_temp,
        air_temperature=air_temp,
        rainfall=rainfall,
        race_control_status=_race_control_status(state),
    )
