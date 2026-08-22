"""Tests for automatic OpenF1 session-change monitoring and transition.

The backend must keep running across a session change (e.g. Practice -> Race)
without a restart: old-session data is cleared, the new session is bootstrapped,
the WS diff state is reset, live clients reconnect/resync, and exactly one MQTT
worker exists afterward.
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
        "v1/weather",
        {
            "track_temperature": 30.0,
            "air_temperature": 20.0,
            "date": "2026-07-26T14:00:00",
        },
    )


def test_latest_session_key_returns_none_when_openf1_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("OpenF1 down")

    monkeypatch.setattr(auth, "openf1_get", boom)

    assert main_mod._latest_session_key() is None


def test_latest_session_key_parses_session(monkeypatch):
    monkeypatch.setattr(auth, "openf1_get", lambda *a, **k: [{"session_key": 9988}])

    assert main_mod._latest_session_key() == 9988


def test_perform_session_transition_swaps_session(monkeypatch):
    from formula1_strategy_tool.api import websocket as ws_mod

    _seed_session_a()
    main_mod._live_session_key = 1

    def fake_bootstrap(state=None, session_key="latest"):
        LIVE_STATE.update(
            "v1/sessions",
            {"session_key": 2, "circuit_key": 23, "session_name": "Race"},
        )
        LIVE_STATE.update(
            "v1/laps", {"driver_number": 44, "lap_number": 3, "lap_duration": 88.0}
        )
        return 2

    monkeypatch.setattr(live_bootstrap, "bootstrap_live_state", fake_bootstrap)

    resets: list[int] = []
    monkeypatch.setattr(ws_mod.broadcaster, "reset", lambda: resets.append(1))

    closed: list[int] = []

    async def fake_close_all():
        closed.append(1)

    monkeypatch.setattr(ws_mod.manager, "close_all", fake_close_all)

    asyncio.run(main_mod._perform_session_transition(2))

    # Active session is now B.
    assert main_mod._live_session_key == 2
    sessions = LIVE_STATE.docs_for("v1/sessions")
    assert len(sessions) == 1
    assert sessions[0]["session_key"] == 2

    # Session A laps and weather are gone; only B data remains.
    laps = LIVE_STATE.docs_for("v1/laps")
    assert [lap["driver_number"] for lap in laps] == [44]
    assert LIVE_STATE.docs_for("v1/weather") == []

    # Broadcaster diff state was reset and live clients were closed to resync.
    assert resets == [1]
    assert closed == [1]


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
