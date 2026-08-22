"""Tests for automatic OpenF1 session-change monitoring and transition.

The backend must keep running across a session change (e.g. Practice -> Race)
without a restart. The transition is transactional: the new session is
bootstrapped into a staging buffer and only atomically swapped into
``LIVE_STATE`` on success. A failed bootstrap leaves the old session (state,
key, broadcaster, clients, MQTT) completely untouched and is retried on the
next monitor tick. Exactly one MQTT worker exists after a successful
transition, and a worker that fails to stop never allows a duplicate.
"""

import asyncio
import os
import threading
import time

# Disable network-backed background tasks before importing the app.
os.environ["LIVE_BOOTSTRAP"] = "0"
os.environ["LIVE_MQTT"] = "0"

import pytest

from formula1_strategy_tool import main as main_mod
from formula1_strategy_tool.acquisition import auth, live_bootstrap
from formula1_strategy_tool.acquisition.live_state import LIVE_STATE


@pytest.fixture(autouse=True)
def reset_state():
    LIVE_STATE.clear()
    main_mod._live_session_key = None
    yield
    main_mod._stop_mqtt()
    LIVE_STATE.clear()
    main_mod._live_session_key = None


def _seed_session_a():
    LIVE_STATE.update(
        "v1/sessions",
        {
            "session_key": 1,
            "circuit_key": 4,
            "session_name": "Race",
            "date_start": "2026-07-26T13:00:00+00:00",
            "date_end": "2026-07-26T15:00:00+00:00",
            "is_cancelled": False,
        },
    )
    LIVE_STATE.update(
        "v1/laps", {"driver_number": 1, "lap_number": 10, "lap_duration": 90.0}
    )
    LIVE_STATE.update(
        "v1/drivers",
        {"driver_number": 1, "full_name": "Driver A", "team_name": "Team A"},
    )
    LIVE_STATE.update(
        "v1/weather",
        {
            "track_temperature": 30.0,
            "air_temperature": 20.0,
            "date": "2026-07-26T14:00:00",
        },
    )


def _seed_session_b(state=None, session_key="latest"):
    """Write session B into the supplied (staging) buffer."""
    state.update(
        "v1/sessions",
        {"session_key": 2, "circuit_key": 23, "session_name": "Race"},
    )
    state.update(
        "v1/laps", {"driver_number": 44, "lap_number": 3, "lap_duration": 88.0}
    )
    state.update(
        "v1/drivers",
        {"driver_number": 44, "full_name": "Driver B", "team_name": "Team B"},
    )
    return int(session_key)


def _patch_ws_observers(monkeypatch):
    from formula1_strategy_tool.api import websocket as ws_mod

    resets: list[int] = []
    monkeypatch.setattr(ws_mod.broadcaster, "reset", lambda: resets.append(1))
    closed: list[int] = []

    async def fake_close_all():
        closed.append(1)

    monkeypatch.setattr(ws_mod.manager, "close_all", fake_close_all)
    return resets, closed


def test_latest_session_key_returns_none_when_openf1_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("OpenF1 down")

    monkeypatch.setattr(auth, "openf1_get", boom)

    assert main_mod._latest_session_key() is None


def test_latest_session_key_parses_session(monkeypatch):
    monkeypatch.setattr(auth, "openf1_get", lambda *a, **k: [{"session_key": 9988}])

    assert main_mod._latest_session_key() == 9988


def test_perform_session_transition_swaps_session(monkeypatch):
    _seed_session_a()
    main_mod._live_session_key = 1

    monkeypatch.setattr(live_bootstrap, "bootstrap_live_state", _seed_session_b)
    resets, closed = _patch_ws_observers(monkeypatch)

    asyncio.run(main_mod._perform_session_transition(2))

    # Active session is now B.
    assert main_mod._live_session_key == 2
    sessions = LIVE_STATE.docs_for("v1/sessions")
    assert len(sessions) == 1
    assert sessions[0]["session_key"] == 2

    # Session A laps, weather, and drivers do not survive; only B remains.
    laps = LIVE_STATE.docs_for("v1/laps")
    assert [lap["driver_number"] for lap in laps] == [44]
    assert LIVE_STATE.docs_for("v1/weather") == []
    drivers = LIVE_STATE.docs_for("v1/drivers")
    assert [driver["driver_number"] for driver in drivers] == [44]

    # Broadcaster diff state was reset and live clients were closed to resync.
    assert resets == [1]
    assert closed == [1]


def test_failed_bootstrap_preserves_session_a_state_and_key(monkeypatch):
    _seed_session_a()
    main_mod._live_session_key = 1

    def boom(state=None, session_key="latest"):
        raise RuntimeError("OpenF1 timeout")

    monkeypatch.setattr(live_bootstrap, "bootstrap_live_state", boom)

    asyncio.run(main_mod._perform_session_transition(2))

    # Session A is completely intact.
    assert main_mod._live_session_key == 1
    assert LIVE_STATE.docs_for("v1/sessions")[0]["session_key"] == 1
    assert LIVE_STATE.docs_for("v1/laps")[0]["driver_number"] == 1
    assert LIVE_STATE.docs_for("v1/weather")[0]["track_temperature"] == 30.0
    assert LIVE_STATE.docs_for("v1/drivers")[0]["full_name"] == "Driver A"


def test_failed_bootstrap_does_not_reset_broadcaster_or_close_clients(monkeypatch):
    _seed_session_a()
    main_mod._live_session_key = 1

    def boom(state=None, session_key="latest"):
        raise RuntimeError("OpenF1 timeout")

    monkeypatch.setattr(live_bootstrap, "bootstrap_live_state", boom)
    resets, closed = _patch_ws_observers(monkeypatch)

    asyncio.run(main_mod._perform_session_transition(2))

    assert resets == []
    assert closed == []


def test_failed_bootstrap_does_not_restart_mqtt(monkeypatch):
    from formula1_strategy_tool.acquisition import live_mqtt

    _seed_session_a()
    main_mod._live_session_key = 1

    def boom(state=None, session_key="latest"):
        raise RuntimeError("OpenF1 timeout")

    monkeypatch.setattr(live_bootstrap, "bootstrap_live_state", boom)

    calls: list[str] = []

    def contaminating_run_listener(*args, **kwargs):
        # If MQTT were restarted against session-A state, it would write B data.
        calls.append("started")
        LIVE_STATE.update(
            "v1/laps", {"driver_number": 99, "lap_number": 1, "lap_duration": 1.0}
        )
        stop = kwargs.get("stop_event")
        while not (stop is not None and stop.is_set()):
            time.sleep(0.02)

    monkeypatch.setattr(live_mqtt, "run_listener", contaminating_run_listener)
    monkeypatch.setenv("LIVE_MQTT", "1")

    asyncio.run(main_mod._perform_session_transition(2))

    # MQTT was not restarted, so no session-B data entered session-A state.
    assert calls == []
    assert [lap["driver_number"] for lap in LIVE_STATE.docs_for("v1/laps")] == [1]


def test_retry_after_failure_can_transition(monkeypatch):
    _seed_session_a()
    main_mod._live_session_key = 1

    attempts = {"count": 0}

    def flaky_bootstrap(state=None, session_key="latest"):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("OpenF1 timeout")
        _seed_session_b(state, session_key=session_key)
        return int(session_key)

    monkeypatch.setattr(live_bootstrap, "bootstrap_live_state", flaky_bootstrap)

    asyncio.run(main_mod._perform_session_transition(2))
    assert main_mod._live_session_key == 1
    assert LIVE_STATE.docs_for("v1/sessions")[0]["session_key"] == 1

    asyncio.run(main_mod._perform_session_transition(2))
    assert main_mod._live_session_key == 2
    assert LIVE_STATE.docs_for("v1/sessions")[0]["session_key"] == 2


def test_mqtt_lifecycle_keeps_single_worker(monkeypatch):
    from formula1_strategy_tool.acquisition import live_mqtt

    started = threading.Event()

    def fake_run_listener(*args, **kwargs):
        started.set()
        stop = kwargs.get("stop_event")
        while not (stop is not None and stop.is_set()):
            time.sleep(0.02)

    monkeypatch.setattr(live_mqtt, "run_listener", fake_run_listener)
    monkeypatch.setenv("LIVE_MQTT", "1")

    def mqtt_threads():
        return [t for t in threading.enumerate() if t.name == "openf1-mqtt"]

    try:
        main_mod._start_mqtt()
        assert started.wait(timeout=1.0)
        first = main_mod._mqtt_thread
        assert first is not None and first.is_alive()
        assert len(mqtt_threads()) == 1

        # A second start must not spawn a duplicate worker.
        main_mod._start_mqtt()
        assert main_mod._mqtt_thread is first
        assert len(mqtt_threads()) == 1

        main_mod._stop_mqtt()
        first.join(timeout=2.0)
        assert not first.is_alive()
        assert main_mod._mqtt_thread is None
        assert len(mqtt_threads()) == 0

        # A restart yields exactly one fresh worker.
        main_mod._start_mqtt()
        assert started.wait(timeout=1.0)
        assert main_mod._mqtt_thread is not None and main_mod._mqtt_thread.is_alive()
        assert len(mqtt_threads()) == 1
        main_mod._stop_mqtt()
    finally:
        main_mod._stop_mqtt()


def test_successful_transition_leaves_single_mqtt_worker(monkeypatch):
    from formula1_strategy_tool.acquisition import live_mqtt

    _seed_session_a()
    main_mod._live_session_key = 1

    monkeypatch.setattr(live_bootstrap, "bootstrap_live_state", _seed_session_b)

    def fake_run_listener(*args, **kwargs):
        stop = kwargs.get("stop_event")
        while not (stop is not None and stop.is_set()):
            time.sleep(0.02)

    monkeypatch.setattr(live_mqtt, "run_listener", fake_run_listener)
    monkeypatch.setenv("LIVE_MQTT", "1")

    def mqtt_threads():
        return [t for t in threading.enumerate() if t.name == "openf1-mqtt"]

    try:
        # Session A ingestion is running before the transition.
        main_mod._start_mqtt()
        assert len(mqtt_threads()) == 1

        asyncio.run(main_mod._perform_session_transition(2))

        assert main_mod._live_session_key == 2
        assert len(mqtt_threads()) == 1
        assert main_mod._mqtt_thread is not None and main_mod._mqtt_thread.is_alive()
    finally:
        main_mod._stop_mqtt()


def test_worker_that_fails_to_stop_prevents_second_worker(monkeypatch):
    from formula1_strategy_tool.acquisition import live_mqtt

    release = threading.Event()

    def stubborn_run_listener(*args, **kwargs):
        # Ignores the stop event; only the test can release it.
        release.wait(10)

    monkeypatch.setattr(live_mqtt, "run_listener", stubborn_run_listener)
    monkeypatch.setenv("LIVE_MQTT", "1")
    monkeypatch.setattr(main_mod, "_MQTT_STOP_TIMEOUT_SECONDS", 0.1)

    def mqtt_threads():
        return [t for t in threading.enumerate() if t.name == "openf1-mqtt"]

    try:
        main_mod._start_mqtt()
        assert len(mqtt_threads()) == 1

        # The worker ignores the stop event, so _stop_mqtt times out and keeps
        # the thread handle registered.
        assert main_mod._stop_mqtt() is False
        assert len(mqtt_threads()) == 1

        # A start attempt must NOT spawn a second worker while one is alive.
        main_mod._start_mqtt()
        assert len(mqtt_threads()) == 1
    finally:
        release.set()
        thread = main_mod._mqtt_thread
        if thread is not None:
            thread.join(timeout=2.0)
        main_mod._mqtt_thread = None
        main_mod._mqtt_stop = None
