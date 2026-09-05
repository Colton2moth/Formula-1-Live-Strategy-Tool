"""Tests for session-aware OpenF1 live-state bootstrap."""

import pytest

from formula1_strategy_tool.acquisition import live_bootstrap
from formula1_strategy_tool.acquisition.live_state import LiveState


@pytest.mark.parametrize(
    ("session_type", "expects_intervals"),
    [("Race", True), ("Qualifying", False)],
)
def test_intervals_are_requested_only_for_races(
    monkeypatch, session_type, expects_intervals
):
    requested: list[str] = []

    def fake_get(endpoint, params):
        requested.append(endpoint)
        if endpoint == "sessions":
            return [
                {
                    "session_key": 123,
                    "session_type": session_type,
                    "date_start": "2026-09-05T12:00:00+00:00",
                }
            ]
        return []

    monkeypatch.setattr(live_bootstrap, "openf1_get", fake_get)

    resolved = live_bootstrap.bootstrap_live_state(state=LiveState(), session_key=123)

    assert resolved == 123
    assert ("intervals" in requested) is expects_intervals
    assert "laps" in requested
    assert "location" in requested
