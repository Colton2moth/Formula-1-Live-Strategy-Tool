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

    return resolved
