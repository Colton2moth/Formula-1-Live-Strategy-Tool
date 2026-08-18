"""Isolation tests: live and replay run from separate mutable state."""

import os

# Disable network-backed background tasks before the app is imported.
os.environ["LIVE_BOOTSTRAP"] = "0"
os.environ["LIVE_MQTT"] = "0"

import threading
import time

import pytest
from fastapi.testclient import TestClient

from formula1_strategy_tool.acquisition import replay as replay_mod
from formula1_strategy_tool.acquisition.live_state import LIVE_STATE
from formula1_strategy_tool.acquisition.replay import replay_controller
from formula1_strategy_tool.api.websocket import (
    broadcaster,
    manager,
    replay_broadcaster,
    replay_manager,
)
from formula1_strategy_tool.main import app


@pytest.fixture(autouse=True)
def reset_state():
    LIVE_STATE.clear()
    replay_controller.state.clear()
    broadcaster.reset()
    replay_broadcaster.reset()
    manager.active.clear()
    replay_manager.active.clear()
    yield


def _seed_replay_session(circuit_key: int = 23) -> None:
    replay_controller.state.update(
        "v1/sessions",
        {
            "circuit_key": circuit_key,
            "circuit_short_name": "Montreal",
            "session_name": "Race",
            "session_type": "Race",
            "location": "Montreal",
            "date_start": "2025-06-15T18:00:00+00:00",
            "date_end": "2025-06-15T20:00:00+00:00",
            "is_cancelled": False,
        },
    )


def _seed_live_session() -> None:
    LIVE_STATE.update(
        "v1/sessions",
        {
            "circuit_key": 4,
            "circuit_short_name": "Hungaroring",
            "session_name": "Race",
            "session_type": "Race",
            "location": "Budapest",
            "date_start": "2026-07-26T13:00:00+00:00",
            "date_end": "2026-07-26T15:00:00+00:00",
            "is_cancelled": False,
        },
    )


def test_replay_race_state_reads_replay_state_not_live():
    _seed_live_session()
    _seed_replay_session(circuit_key=23)
    with TestClient(app) as client:
        live = client.get("/api/race-state").json()
        replay = client.get("/api/replay/race-state").json()
    assert live["session"]["meeting_name"] == "Hungaroring"
    assert replay["session"]["meeting_name"] == "Montreal"


def test_replay_track_differs_from_live_track():
    _seed_live_session()
    _seed_replay_session(circuit_key=23)
    with TestClient(app) as client:
        live = client.get("/api/track").json()
        replay = client.get("/api/replay/track").json()
    assert live["circuit_key"] == 4
    assert replay["circuit_key"] == 23


def test_replay_race_state_conflicts_without_replay():
    with TestClient(app) as client:
        assert client.get("/api/replay/race-state").status_code == 409


def test_replay_track_conflicts_without_replay():
    with TestClient(app) as client:
        assert client.get("/api/replay/track").status_code == 409


def test_replay_start_does_not_modify_live_state(monkeypatch):
    seeded = threading.Event()

    def fake_replay(session_key, speed=10.0, state=None, **kwargs):
        if state is not None:
            state.update(
                "v1/sessions",
                {"session_key": session_key, "circuit_key": 23},
            )
        seeded.set()

    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)

    with TestClient(app) as client:
        client.post("/api/replay/start", json={"session_key": 9999})
        assert seeded.wait(timeout=1.0)

    assert LIVE_STATE.docs_for("v1/sessions") == []
    assert replay_controller.state.docs_for("v1/sessions")


def test_websocket_replay_receives_replay_updates():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/replay") as websocket:
            replay_controller.state.update(
                "v1/weather",
                {
                    "track_temperature": 25.0,
                    "air_temperature": 20.0,
                    "rainfall": False,
                    "date": "2025-06-15T18:00:00",
                },
            )
            time.sleep(1.0)

            event = websocket.receive_json()
            assert event["type"] == "weather_update"
            assert event["track_temperature"] == 25.0


def test_websocket_live_ignores_replay_updates():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            replay_controller.state.update(
                "v1/weather",
                {
                    "track_temperature": 99.0,
                    "air_temperature": 99.0,
                    "rainfall": False,
                    "date": "2025-06-15T18:00:00",
                },
            )
            time.sleep(1.0)

            LIVE_STATE.update(
                "v1/weather",
                {
                    "track_temperature": 20.0,
                    "air_temperature": 15.0,
                    "rainfall": False,
                    "date": "2025-06-15T18:00:00",
                },
            )
            time.sleep(1.0)

            event = websocket.receive_json()
            assert event["type"] == "weather_update"
            assert event["track_temperature"] == 20.0
