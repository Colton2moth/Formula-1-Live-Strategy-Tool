"""Tests for truthful lap-count reporting in SessionState."""

from formula1_strategy_tool.acquisition.live_session import session_from_live
from formula1_strategy_tool.acquisition.live_state import LiveState


def _seed_session(state, *, session_key=1, circuit_key=4):
    state.update(
        "v1/sessions",
        {
            "session_key": session_key,
            "circuit_key": circuit_key,
            "circuit_short_name": "Hungaroring",
            "session_name": "Race",
            "session_type": "Race",
            "location": "Budapest",
            "date_start": "2026-07-26T13:00:00+00:00",
            "date_end": "2026-07-26T15:00:00+00:00",
            "is_cancelled": False,
        },
    )


def _seed_lap(state, driver_number, lap_number):
    state.update(
        "v1/laps",
        {
            "driver_number": driver_number,
            "lap_number": lap_number,
            "lap_duration": 90.0,
        },
    )


def test_total_laps_unknown_when_not_provided():
    state = LiveState()
    _seed_session(state)
    _seed_lap(state, 4, 14)

    session = session_from_live(state)
    assert session is not None
    assert session.current_lap == 14
    assert session.total_laps is None


def test_total_laps_known_when_provided():
    state = LiveState()
    _seed_session(state)
    _seed_lap(state, 4, 14)

    session = session_from_live(state, total_laps=72)
    assert session is not None
    assert session.current_lap == 14
    assert session.total_laps == 72


def test_early_live_race_state_lap_one_unknown_total():
    state = LiveState()
    _seed_session(state)
    _seed_lap(state, 4, 1)

    session = session_from_live(state)
    assert session is not None
    assert session.current_lap == 1
    assert session.total_laps is None


def test_latest_session_doc_prefers_highest_session_key():
    from formula1_strategy_tool.acquisition.live_session import latest_session_doc

    state = LiveState()
    _seed_session(state, session_key=100)
    state.update(
        "v1/sessions",
        {
            "session_key": 200,
            "circuit_key": 5,
            "circuit_short_name": "Monza",
            "session_name": "Race",
            "session_type": "Race",
            "location": "Monza",
            "date_start": "2026-09-06T13:00:00+00:00",
            "date_end": "2026-09-06T15:00:00+00:00",
            "is_cancelled": False,
        },
    )

    session = latest_session_doc(state)
    assert session is not None
    assert session["session_key"] == 200

    mapped = session_from_live(state)
    assert mapped is not None
    assert mapped.session_name == "Race"


def test_replay_race_state_threads_total_laps(monkeypatch):
    from fastapi.testclient import TestClient

    from formula1_strategy_tool.api import routes as routes_mod
    from formula1_strategy_tool.main import app

    state = LiveState()
    _seed_session(state, session_key=1, circuit_key=4)
    _seed_lap(state, 4, 14)

    class FakeController:
        def __init__(self):
            self.state = state
            self.progress = {"total_laps": 57}

    class FakeRuntime:
        def __init__(self):
            self.replay_id = "x"
            self.controller = FakeController()

    class FakeRegistry:
        def get(self, replay_id):
            return FakeRuntime()

    monkeypatch.setattr(routes_mod, "registry", FakeRegistry())
    monkeypatch.setattr(routes_mod, "replay_predictions", lambda s: [])

    response = TestClient(app).get("/api/replays/x/race-state")
    assert response.status_code == 200
    body = response.json()
    assert body["session"]["current_lap"] == 14
    assert body["session"]["total_laps"] == 57
