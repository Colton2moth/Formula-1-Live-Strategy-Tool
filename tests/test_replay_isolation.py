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
from formula1_strategy_tool.acquisition import replay_registry
from formula1_strategy_tool.acquisition.live_state import LIVE_STATE
from formula1_strategy_tool.api.websocket import (
    broadcaster,
    manager,
)
from formula1_strategy_tool.main import app


@pytest.fixture(autouse=True)
def reset_state():
    from formula1_strategy_tool.api import websocket as websocket_mod

    LIVE_STATE.clear()
    replay_registry.registry.stop_all()
    websocket_mod._replay_channels.clear()
    broadcaster.reset()
    manager.active.clear()
    yield


def _make_runtime(monkeypatch, *, session_key=9999, circuit_key=23):
    """Create a registry runtime whose worker seeds one replay session."""
    seeded = threading.Event()

    def fake_replay(session_key, speed=10.0, state=None, **kwargs):
        if state is not None:
            state.update(
                "v1/sessions",
                {
                    "session_key": session_key,
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
        if kwargs.get("on_seeded") is not None:
            kwargs["on_seeded"]()
        seeded.set()
        stop = kwargs.get("stop_event")
        if stop is not None:
            stop.wait(timeout=2.0)

    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)
    runtime = replay_registry.registry.create(session_key, speed=10)
    assert seeded.wait(timeout=1.0)
    return runtime


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


def test_location_update_projects_progress():
    from formula1_strategy_tool.track.models import load_layout

    layout = load_layout(2)
    assert layout is not None
    ref = layout.reference_path[100]
    LIVE_STATE.update(
        "v1/sessions",
        {"circuit_key": 2, "circuit_short_name": "Silverstone", "session_name": "Race"},
    )
    LIVE_STATE.update(
        "v1/location",
        {"driver_number": 4, "x": ref.x, "y": ref.y, "date": "2025-07-06T14:00:00"},
    )
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            time.sleep(1.0)
            event = websocket.receive_json()
            assert event["type"] == "location_update"
            assert event["progress"] is not None
            assert 0.0 <= event["progress"] < 1.0


def test_replay_race_state_reads_replay_state_not_live(monkeypatch):
    _seed_live_session()
    runtime = _make_runtime(monkeypatch, circuit_key=23)
    with TestClient(app) as client:
        live = client.get("/api/race-state").json()
        replay = client.get(f"/api/replays/{runtime.replay_id}/race-state").json()
    assert live["session"]["meeting_name"] == "Hungaroring"
    assert replay["session"]["meeting_name"] == "Montreal"


def test_replay_track_differs_from_live_track(monkeypatch):
    _seed_live_session()
    runtime = _make_runtime(monkeypatch, circuit_key=23)
    with TestClient(app) as client:
        live = client.get("/api/track").json()
        replay = client.get(f"/api/replays/{runtime.replay_id}/track").json()
    assert live["circuit_key"] == 4
    assert replay["circuit_key"] == 23


def test_replay_race_state_404_unknown_id():
    with TestClient(app) as client:
        assert client.get("/api/replays/unknown/race-state").status_code == 404


def test_replay_track_404_unknown_id():
    with TestClient(app) as client:
        assert client.get("/api/replays/unknown/track").status_code == 404


def test_replay_create_does_not_modify_live_state(monkeypatch):
    runtime = _make_runtime(monkeypatch, session_key=9999, circuit_key=23)
    assert LIVE_STATE.docs_for("v1/sessions") == []
    assert runtime.controller.state.docs_for("v1/sessions")


def test_websocket_replay_receives_replay_updates(monkeypatch):
    runtime = _make_runtime(monkeypatch)
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/replays/{runtime.replay_id}") as websocket:
            runtime.controller.state.update(
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


def test_websocket_live_ignores_replay_updates(monkeypatch):
    runtime = _make_runtime(monkeypatch)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            runtime.controller.state.update(
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


def test_websocket_replay_ignores_live_updates(monkeypatch):
    runtime = _make_runtime(monkeypatch)
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/replays/{runtime.replay_id}") as websocket:
            LIVE_STATE.update(
                "v1/weather",
                {
                    "track_temperature": 20.0,
                    "air_temperature": 15.0,
                    "rainfall": False,
                    "date": "2026-07-26T14:00:00",
                },
            )
            time.sleep(1.0)

            runtime.controller.state.update(
                "v1/weather",
                {
                    "track_temperature": 30.0,
                    "air_temperature": 25.0,
                    "rainfall": True,
                    "date": "2025-06-15T18:30:00",
                },
            )
            time.sleep(1.0)

            event = websocket.receive_json()
            assert event["type"] == "weather_update"
            assert event["track_temperature"] == 30.0


def test_live_predictions_use_live_state(monkeypatch):
    from formula1_strategy_tool.api import routes as routes_mod

    supplied: list[object] = []
    monkeypatch.setattr(
        routes_mod, "features_from_live", lambda state: supplied.append(state) or None
    )
    monkeypatch.setattr(routes_mod, "_csv_predictions", lambda: [])

    routes_mod._model_predictions()

    assert supplied == [LIVE_STATE]


def test_replay_predictions_use_replay_state_not_live(monkeypatch):
    from formula1_strategy_tool.api import routes as routes_mod

    supplied: list[object] = []
    monkeypatch.setattr(
        routes_mod, "features_from_live", lambda state: supplied.append(state) or None
    )
    runtime = _make_runtime(monkeypatch, circuit_key=23)

    result = routes_mod.replay_predictions(runtime.controller.state)

    assert result == []
    assert supplied == [runtime.controller.state]
    assert LIVE_STATE not in supplied


def test_race_state_endpoints_score_their_own_state(monkeypatch):
    from formula1_strategy_tool.api import routes as routes_mod

    supplied: list[object] = []
    monkeypatch.setattr(
        routes_mod, "features_from_live", lambda state: supplied.append(state) or None
    )
    monkeypatch.setattr(routes_mod, "_csv_predictions", lambda: [])

    _seed_live_session()
    runtime = _make_runtime(monkeypatch, circuit_key=23)

    with TestClient(app) as client:
        client.get("/api/race-state")
        client.get(f"/api/replays/{runtime.replay_id}/race-state")

    assert supplied == [LIVE_STATE, runtime.controller.state]


def _mqtt_lifecycle_guard(monkeypatch) -> list[str]:
    """Patch the live MQTT entry points and return a recorder for any calls."""
    from formula1_strategy_tool import main as main_mod
    from formula1_strategy_tool.acquisition import live_mqtt

    calls: list[str] = []
    monkeypatch.setattr(
        live_mqtt, "run_listener", lambda *a, **k: calls.append("run_listener")
    )
    monkeypatch.setattr(main_mod, "_start_mqtt", lambda: calls.append("_start_mqtt"))
    return calls


def test_replay_controls_do_not_control_live_mqtt(monkeypatch):
    calls = _mqtt_lifecycle_guard(monkeypatch)

    started = threading.Event()

    def fake_replay(
        session_key,
        speed=10.0,
        state=None,
        *,
        stop_event=None,
        pause_event=None,
        progress=None,
        on_seeded=None,
        seek_time=None,
        seek_lap=None,
        speed_holder=None,
    ):
        if on_seeded is not None:
            on_seeded()
        started.set()
        if stop_event is not None:
            stop_event.wait(timeout=2.0)

    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)
    controller = replay_mod.ReplayController()

    controller.start(9979, speed=10)
    assert started.wait(timeout=1.0)
    controller.pause()
    controller.resume()

    started.clear()
    controller.seek(50.0)
    assert started.wait(timeout=1.0)

    started.clear()
    controller.seek_lap(12)
    assert started.wait(timeout=1.0)

    assert controller.set_speed(2.0) is True
    controller.stop()

    assert calls == []


def test_replay_completion_does_not_control_live_mqtt(monkeypatch):
    calls = _mqtt_lifecycle_guard(monkeypatch)
    finished = threading.Event()

    def fake_replay(
        session_key,
        speed=10.0,
        state=None,
        *,
        stop_event=None,
        pause_event=None,
        progress=None,
        on_seeded=None,
        seek_time=None,
        seek_lap=None,
        speed_holder=None,
    ):
        if on_seeded is not None:
            on_seeded()
        finished.set()

    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)
    controller = replay_mod.ReplayController()

    controller.start(9979, speed=10)
    assert finished.wait(timeout=1.0)
    deadline = time.time() + 2.0
    while controller.snapshot()["status"] != "finished" and time.time() < deadline:
        time.sleep(0.01)
    assert controller.snapshot()["status"] == "finished"

    assert calls == []


def test_live_and_replay_state_hold_distinct_data(monkeypatch):
    _seed_live_session()
    LIVE_STATE.update(
        "v1/weather",
        {
            "track_temperature": 20.0,
            "air_temperature": 15.0,
            "rainfall": False,
            "date": "2026-07-26T14:00:00",
        },
    )
    LIVE_STATE.update("v1/drivers", {"driver_number": 4, "full_name": "Live Driver"})

    seeded = threading.Event()

    def fake_replay(
        session_key,
        speed=10.0,
        state=None,
        *,
        stop_event=None,
        pause_event=None,
        progress=None,
        on_seeded=None,
        seek_time=None,
        seek_lap=None,
        speed_holder=None,
    ):
        assert state is not None
        state.update(
            "v1/sessions",
            {
                "session_key": session_key,
                "circuit_key": 23,
                "circuit_short_name": "Montreal",
                "session_name": "Race",
                "session_type": "Race",
                "location": "Montreal",
                "date_start": "2025-06-15T18:00:00+00:00",
                "date_end": "2025-06-15T20:00:00+00:00",
                "is_cancelled": False,
            },
        )
        state.update(
            "v1/weather",
            {
                "track_temperature": 30.0,
                "air_temperature": 25.0,
                "rainfall": True,
                "date": "2025-06-15T18:30:00",
            },
        )
        state.update("v1/drivers", {"driver_number": 44, "full_name": "Replay Driver"})
        if on_seeded is not None:
            on_seeded()
        seeded.set()
        if stop_event is not None:
            stop_event.wait(timeout=2.0)

    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)
    controller = replay_mod.ReplayController()
    controller.start(9999, speed=10)
    assert seeded.wait(timeout=1.0)

    # Both states hold their own session, weather, and driver data.
    assert LIVE_STATE.docs_for("v1/sessions")[0]["circuit_key"] == 4
    assert controller.state.docs_for("v1/sessions")[0]["circuit_key"] == 23
    assert LIVE_STATE.docs_for("v1/weather")[0]["track_temperature"] == 20.0
    assert controller.state.docs_for("v1/weather")[0]["track_temperature"] == 30.0
    assert LIVE_STATE.docs_for("v1/drivers")[0]["full_name"] == "Live Driver"
    assert controller.state.docs_for("v1/drivers")[0]["full_name"] == "Replay Driver"

    # A live update must not overwrite or clear the replay state.
    LIVE_STATE.update(
        "v1/weather",
        {
            "track_temperature": 21.0,
            "air_temperature": 16.0,
            "rainfall": False,
            "date": "2026-07-26T14:00:00",
        },
    )
    assert controller.state.docs_for("v1/weather")[0]["track_temperature"] == 30.0

    # A replay update must not overwrite or clear the live state.
    controller.state.update(
        "v1/weather",
        {
            "track_temperature": 31.0,
            "air_temperature": 26.0,
            "rainfall": True,
            "date": "2025-06-15T18:30:00",
        },
    )
    assert LIVE_STATE.docs_for("v1/weather")[0]["track_temperature"] == 21.0

    controller.stop()
