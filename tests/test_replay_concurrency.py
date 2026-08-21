"""Multi-runtime concurrency tests: two replays run independently (Phase 10)."""

import os

os.environ["LIVE_BOOTSTRAP"] = "0"
os.environ["LIVE_MQTT"] = "0"

import threading
import time

import pytest
from fastapi.testclient import TestClient

from formula1_strategy_tool.acquisition import replay as replay_mod
from formula1_strategy_tool.acquisition import replay_registry
from formula1_strategy_tool.acquisition.live_state import LIVE_STATE, LiveState
from formula1_strategy_tool.api.websocket import broadcaster, manager
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


def _make_fake_replay(monkeypatch):
    """Install a replay_session fake; return create(session_key, circuit_key, speed)."""
    circuit_by_session: dict[int, int] = {}
    seeded_by_session: dict[int, threading.Event] = {}

    def fake_replay(session_key, speed=10.0, state=None, **kwargs):
        if state is not None:
            circuit = circuit_by_session.get(session_key, 0)
            state.update(
                "v1/sessions",
                {
                    "session_key": session_key,
                    "circuit_key": circuit,
                    "circuit_short_name": f"Circuit {circuit}",
                    "session_name": "Race",
                    "session_type": "Race",
                    "location": "Anywhere",
                    "date_start": "2025-06-15T18:00:00+00:00",
                    "date_end": "2025-06-15T20:00:00+00:00",
                    "is_cancelled": False,
                },
            )
        if kwargs.get("on_seeded") is not None:
            kwargs["on_seeded"]()
        seeded_by_session.setdefault(session_key, threading.Event()).set()
        stop = kwargs.get("stop_event")
        if stop is not None:
            stop.wait(timeout=2.0)

    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)

    def create(session_key, circuit_key, speed=10.0):
        circuit_by_session[session_key] = circuit_key
        seeded = threading.Event()
        seeded_by_session[session_key] = seeded
        runtime = replay_registry.registry.create(session_key, speed=speed)
        assert seeded.wait(timeout=1.0)
        return runtime

    return create


def test_two_runtimes_run_different_races_independently(monkeypatch):
    create = _make_fake_replay(monkeypatch)
    a = create(100, circuit_key=4, speed=10)
    b = create(200, circuit_key=23, speed=20)

    assert a.replay_id != b.replay_id
    assert a.controller.state.docs_for("v1/sessions")[0]["circuit_key"] == 4
    assert b.controller.state.docs_for("v1/sessions")[0]["circuit_key"] == 23

    a.controller.pause()
    assert a.controller.snapshot()["status"] == "paused"
    assert b.controller.snapshot()["status"] == "running"

    assert a.controller.set_speed(50.0) is True
    assert b.controller.snapshot()["speed"] == 20

    replay_registry.registry.stop(a.replay_id)
    assert replay_registry.registry.get(a.replay_id) is None
    assert replay_registry.registry.get(b.replay_id) is not None
    assert b.controller.snapshot()["status"] == "running"

    replay_registry.registry.stop(b.replay_id)


def test_two_runtimes_same_race_different_speeds(monkeypatch):
    create = _make_fake_replay(monkeypatch)
    a = create(9979, circuit_key=23, speed=10)
    b = create(9979, circuit_key=23, speed=50)

    assert a.replay_id != b.replay_id
    assert a.controller.snapshot()["session_key"] == 9979
    assert b.controller.snapshot()["session_key"] == 9979
    assert a.controller.snapshot()["speed"] == 10
    assert b.controller.snapshot()["speed"] == 50
    assert a.controller.state is not b.controller.state


def test_seek_a_does_not_affect_b(monkeypatch):
    create = _make_fake_replay(monkeypatch)
    a = create(100, circuit_key=4, speed=10)
    b = create(200, circuit_key=23, speed=20)

    b_state_before = b.controller.state.snapshot_docs()
    a.controller.seek(50.0)

    assert b.controller.state.snapshot_docs() == b_state_before
    assert b.controller.snapshot()["status"] == "running"
    assert a.controller.state.docs_for("v1/sessions")[0]["circuit_key"] == 4


def test_a_finishing_does_not_change_b_status(monkeypatch):
    seeded_b = threading.Event()
    finished_a = threading.Event()

    def fake_replay(session_key, speed=10.0, state=None, **kwargs):
        if session_key == 100:
            if kwargs.get("on_seeded") is not None:
                kwargs["on_seeded"]()
            finished_a.set()
            return
        if state is not None:
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
        if kwargs.get("on_seeded") is not None:
            kwargs["on_seeded"]()
        seeded_b.set()
        stop = kwargs.get("stop_event")
        if stop is not None:
            stop.wait(timeout=2.0)

    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)

    a = replay_registry.registry.create(100, speed=10)
    b = replay_registry.registry.create(200, speed=20)
    assert finished_a.wait(timeout=1.0)
    assert seeded_b.wait(timeout=1.0)

    deadline = time.time() + 2.0
    while a.controller.snapshot()["status"] != "finished" and time.time() < deadline:
        time.sleep(0.01)
    assert a.controller.snapshot()["status"] == "finished"

    assert b.controller.snapshot()["status"] == "running"
    assert b.controller.state.docs_for("v1/sessions")


def test_runtime_states_are_disjoint(monkeypatch):
    create = _make_fake_replay(monkeypatch)
    a = create(100, circuit_key=4)
    b = create(200, circuit_key=23)

    a.controller.state.update(
        "v1/drivers", {"driver_number": 1, "full_name": "Driver A"}
    )
    b.controller.state.update(
        "v1/drivers", {"driver_number": 2, "full_name": "Driver B"}
    )

    assert [d["full_name"] for d in a.controller.state.docs_for("v1/drivers")] == [
        "Driver A"
    ]
    assert [d["full_name"] for d in b.controller.state.docs_for("v1/drivers")] == [
        "Driver B"
    ]
    assert a.controller.state.docs_for("v1/sessions")[0]["session_key"] == 100
    assert b.controller.state.docs_for("v1/sessions")[0]["session_key"] == 200
    assert LIVE_STATE.docs_for("v1/sessions") == []
    assert LIVE_STATE.docs_for("v1/drivers") == []


def test_api_race_state_returns_own_state(monkeypatch):
    create = _make_fake_replay(monkeypatch)
    a = create(100, circuit_key=4)
    b = create(200, circuit_key=23)

    with TestClient(app) as client:
        ra = client.get(f"/api/replays/{a.replay_id}/race-state").json()
        rb = client.get(f"/api/replays/{b.replay_id}/race-state").json()

    assert ra["session"]["meeting_name"] == "Circuit 4"
    assert rb["session"]["meeting_name"] == "Circuit 23"


def test_websocket_replays_are_isolated(monkeypatch):
    create = _make_fake_replay(monkeypatch)
    a = create(100, circuit_key=4)
    b = create(200, circuit_key=23)

    with TestClient(app) as client:
        with (
            client.websocket_connect(f"/ws/replays/{a.replay_id}") as ws_a,
            client.websocket_connect(f"/ws/replays/{b.replay_id}") as ws_b,
        ):
            b.controller.state.update(
                "v1/weather",
                {
                    "track_temperature": 30.0,
                    "air_temperature": 25.0,
                    "rainfall": False,
                    "date": "2025-06-15T18:30:00",
                },
            )
            time.sleep(1.0)

            a.controller.state.update(
                "v1/weather",
                {
                    "track_temperature": 25.0,
                    "air_temperature": 20.0,
                    "rainfall": False,
                    "date": "2025-06-15T18:00:00",
                },
            )
            time.sleep(1.0)

            event_a = ws_a.receive_json()
            event_b = ws_b.receive_json()
            assert event_a["type"] == "weather_update"
            assert event_a["track_temperature"] == 25.0
            assert event_b["type"] == "weather_update"
            assert event_b["track_temperature"] == 30.0


def test_invalid_id_never_falls_back(monkeypatch):
    create = _make_fake_replay(monkeypatch)
    a = create(100, circuit_key=4)

    with TestClient(app) as client:
        assert client.get("/api/replays/not-a-real-id/race-state").status_code == 404
        assert client.get(f"/api/replays/{a.replay_id}/race-state").status_code == 200


def _single_driver_data():
    return {
        "session": {
            "session_key": 7,
            "session_name": "Race",
            "circuit_key": 4,
            "date_start": "2026-07-26T13:00:00+00:00",
            "date_end": "2026-07-26T15:00:00+00:00",
        },
        "meetings": [{"meeting_key": 1, "meeting_name": "Test GP"}],
        "drivers": [{"driver_number": 4, "full_name": "Driver Four"}],
        "laps": [
            {
                "driver_number": 4,
                "lap_number": 1,
                "date_start": "2026-07-26T13:00:00+00:00",
                "date_end": "2026-07-26T13:01:30+00:00",
                "lap_duration": 90.0,
            },
            {
                "driver_number": 4,
                "lap_number": 2,
                "date_start": "2026-07-26T13:01:30+00:00",
                "date_end": "2026-07-26T13:03:00+00:00",
                "lap_duration": 89.0,
            },
        ],
        "stints": [],
        "pit": [],
        "position": [],
        "intervals": [],
        "weather": [],
        "race_control": [],
        "location": [],
    }


def test_two_runtimes_load_shared_prepared_data(monkeypatch, tmp_path):
    from formula1_strategy_tool.acquisition.client import atomic_write_json
    from formula1_strategy_tool.acquisition.replay import prepare_timeline

    data = _single_driver_data()
    prepare_timeline(tmp_path, data)
    atomic_write_json(tmp_path / "sessions.json", [data["session"]])
    atomic_write_json(tmp_path / "meetings.json", data["meetings"])
    atomic_write_json(tmp_path / "drivers.json", data["drivers"])

    monkeypatch.setattr(replay_mod, "replay_dir", lambda key: tmp_path)
    monkeypatch.setattr(
        replay_mod,
        "download_replay_data",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("prepared data must be reused, not re-downloaded")
        ),
    )

    buffer_a = LiveState()
    buffer_b = LiveState()
    replay_mod.replay_session(7, speed=100000, state=buffer_a)
    replay_mod.replay_session(7, speed=100000, state=buffer_b)

    assert buffer_a.snapshot_docs() == buffer_b.snapshot_docs()
    assert buffer_a.docs_for("v1/sessions")[0]["session_key"] == 7
