"""Tests for the replay harness timeline builder and location thinning."""

import threading
import time

from formula1_strategy_tool.acquisition import cache_replays
from formula1_strategy_tool.acquisition import replay as replay_mod
from formula1_strategy_tool.acquisition.client import atomic_write_json, load_json
from formula1_strategy_tool.acquisition.live_state import LiveState
from formula1_strategy_tool.acquisition.replay import (
    _thin_location,
    build_checkpoints,
    build_timeline,
    download_replay_data,
    load_checkpoint_index,
    load_checkpoint_state,
    load_timeline,
    location_window_count,
    nearest_checkpoint_by_lap,
    nearest_checkpoint_by_time,
    restore_checkpoint,
    save_checkpoints,
    save_timeline,
)


def _data():
    session = {
        "session_key": 1,
        "session_name": "Race",
        "circuit_key": 4,
        "date_start": "2026-07-26T13:00:00+00:00",
        "date_end": "2026-07-26T15:00:00+00:00",
    }
    laps = [
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
    ]
    return {
        "session": session,
        "meetings": [{"meeting_key": 1, "meeting_name": "Test GP"}],
        "drivers": [{"driver_number": 4, "full_name": "Test Driver"}],
        "laps": laps,
        "stints": [
            {
                "driver_number": 4,
                "stint_number": 1,
                "compound": "MEDIUM",
                "lap_start": 1,
                "lap_end": 20,
                "tyre_age_at_start": 0,
            }
        ],
        "pit": [
            {"driver_number": 4, "lap_number": 20, "date": "2026-07-26T13:30:00+00:00"}
        ],
        "position": [
            {"driver_number": 4, "position": 1, "date": "2026-07-26T13:00:00+00:00"}
        ],
        "intervals": [],
        "weather": [],
        "race_control": [],
        "location": [],
    }


def test_timeline_is_chronological():
    events = build_timeline(_data())
    offsets = [offset for offset, _, _ in events]
    assert offsets == sorted(offsets)


def test_timeline_schedules_lap_at_date_end():
    events = build_timeline(_data())
    lap_events = [
        (offset, payload)
        for offset, topic, payload in events
        if topic == "v1/laps"
    ]
    # Lap 1 finishes at 13:01:30 → 90s after the 13:00:00 clock start.
    assert lap_events[0][0] == 90.0
    assert lap_events[0][1]["lap_number"] == 1


def test_stint_opens_with_null_lap_end():
    events = build_timeline(_data())
    stint_payloads = [payload for _, topic, payload in events if topic == "v1/stints"]
    assert len(stint_payloads) == 1
    assert "lap_end" in stint_payloads[0]
    assert stint_payloads[0]["lap_end"] is None
    assert stint_payloads[0]["compound"] == "MEDIUM"


def test_stint_scheduled_at_start_lap():
    events = build_timeline(_data())
    stint_events = [offset for offset, topic, _ in events if topic == "v1/stints"]
    # Stint 1 starts at lap 1 → race clock offset 0.
    assert stint_events == [0.0]


def test_previous_stint_closes_when_next_starts():
    data = _data()
    data["stints"] = [
        {
            "driver_number": 4,
            "stint_number": 1,
            "compound": "MEDIUM",
            "lap_start": 1,
            "lap_end": 20,
            "tyre_age_at_start": 0,
        },
        {
            "driver_number": 4,
            "stint_number": 2,
            "compound": "HARD",
            "lap_start": 21,
            "lap_end": 40,
            "tyre_age_at_start": 0,
        },
    ]
    events = build_timeline(data)
    stints = [
        (offset, payload)
        for offset, topic, payload in events
        if topic == "v1/stints"
    ]
    # Three events: stint 1 opens (None), stint 1 closes (20), stint 2 opens (None).
    assert len(stints) == 3
    stint1_open = [
        p for o, p in stints if p["stint_number"] == 1 and p["lap_end"] is None
    ]
    stint1_closed = [
        p for o, p in stints if p["stint_number"] == 1 and p["lap_end"] == 20
    ]
    stint2_open = [
        p for o, p in stints if p["stint_number"] == 2 and p["lap_end"] is None
    ]
    assert len(stint1_open) == 1
    assert len(stint1_closed) == 1
    assert len(stint2_open) == 1


def test_thin_location_keeps_one_per_driver_per_quarter_second():
    rows = [
        {"driver_number": 4, "date": "2026-07-26T13:00:00+00:00"},
        {"driver_number": 4, "date": "2026-07-26T13:00:00.100+00:00"},
        {"driver_number": 4, "date": "2026-07-26T13:00:00.250+00:00"},
        {"driver_number": 4, "date": "2026-07-26T13:00:00.500+00:00"},
        {"driver_number": 44, "date": "2026-07-26T13:00:00+00:00"},
    ]
    kept = _thin_location(rows)
    assert len(kept) == 4
    assert [row["date"] for row in kept] == [
        "2026-07-26T13:00:00+00:00",
        "2026-07-26T13:00:00.250+00:00",
        "2026-07-26T13:00:00.500+00:00",
        "2026-07-26T13:00:00+00:00",
    ]


def test_timeline_format_version_invalidates_old_thinning(tmp_path):
    # A prepared timeline from the previous 1-second thinning (older format
    # version) must be rejected and rebuilt from the raw cache.
    data = _data()
    save_timeline(tmp_path, build_timeline(data), data)
    path = replay_mod._timeline_path(tmp_path)
    blob = load_json(path)
    blob["format_version"] = replay_mod._TIMELINE_FORMAT_VERSION - 1
    atomic_write_json(path, blob)
    assert load_timeline(tmp_path, data["session"]["session_key"]) is None


def test_replay_controller_start_stop(monkeypatch):
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

    controller = replay_mod.ReplayController()
    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)

    controller.start(9979, speed=20)
    assert started.wait(timeout=1.0)
    snapshot = controller.snapshot()
    assert snapshot["status"] == "running"
    assert snapshot["running"] is True
    assert snapshot["session_key"] == 9979
    assert snapshot["speed"] == 20

    controller.stop()
    deadline = time.time() + 2.0
    while controller.snapshot()["running"] and time.time() < deadline:
        time.sleep(0.01)
    assert controller.snapshot()["status"] == "idle"
    assert controller.snapshot()["running"] is False


def test_replay_controller_pause_resume(monkeypatch):
    captured_pause: threading.Event | None = None
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
        nonlocal captured_pause
        captured_pause = pause_event
        if on_seeded is not None:
            on_seeded()
        seeded.set()
        if stop_event is not None:
            stop_event.wait(timeout=2.0)

    controller = replay_mod.ReplayController()
    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)

    controller.start(9979, speed=5)
    assert seeded.wait(timeout=1.0)
    assert controller.snapshot()["status"] == "running"

    controller.pause()
    assert controller.snapshot()["status"] == "paused"
    assert captured_pause is not None and captured_pause.is_set()

    controller.resume()
    assert controller.snapshot()["status"] == "running"
    assert captured_pause is not None and not captured_pause.is_set()

    controller.stop()


def test_replay_controller_stop_fires_restore_hook(monkeypatch):
    restored = threading.Event()

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
        if stop_event is not None:
            stop_event.wait(timeout=2.0)

    controller = replay_mod.ReplayController()
    controller.on_after_stop = restored.set
    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)

    controller.start(9979, speed=10)
    controller.stop()
    assert restored.wait(timeout=1.0)


def test_replay_controller_uses_private_state(monkeypatch):
    captured_state: dict[str, object] = {}
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
        captured_state["state"] = state
        if state is not None:
            state.update("v1/sessions", {"session_key": session_key})
        if on_seeded is not None:
            on_seeded()
        seeded.set()
        if stop_event is not None:
            stop_event.wait(timeout=2.0)

    controller = replay_mod.ReplayController()
    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)

    controller.start(9979, speed=10)
    assert seeded.wait(timeout=1.0)

    state = captured_state["state"]
    assert state is controller.state
    assert state is not replay_mod.LIVE_STATE

    # Advancing the replay filled the controller's own state, not the live one.
    assert state.docs_for("v1/sessions")
    assert replay_mod.LIVE_STATE.docs_for("v1/sessions") == []

    controller.stop()


def test_replay_controller_seek_restarts_with_time(monkeypatch):
    seen: list[tuple[int, float, float | None, int | None]] = []
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
        seen.append((session_key, speed, seek_time, seek_lap))
        if on_seeded is not None:
            on_seeded()
        started.set()
        if stop_event is not None:
            stop_event.wait(timeout=2.0)

    controller = replay_mod.ReplayController()
    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)

    # Seek before any replay is active is a no-op.
    controller.seek(50.0)
    assert seen == []

    controller.start(9979, speed=20)
    assert started.wait(timeout=1.0)
    assert seen[0][2] is None

    started.clear()
    controller.seek(50.0)
    assert started.wait(timeout=1.0)
    assert seen[-1] == (9979, 20, 50.0, None)

    started.clear()
    controller.seek_lap(12)
    assert started.wait(timeout=1.0)
    assert seen[-1] == (9979, 20, None, 12)

    controller.stop()


def test_replay_controller_set_speed(monkeypatch):
    seeded = threading.Event()
    captured_holder: dict[str, float] | None = None

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
        nonlocal captured_holder
        captured_holder = speed_holder
        if on_seeded is not None:
            on_seeded()
        seeded.set()
        if stop_event is not None:
            stop_event.wait(timeout=2.0)

    controller = replay_mod.ReplayController()
    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)

    controller.start(9979, speed=10)
    assert seeded.wait(timeout=1.0)
    assert controller.snapshot()["speed"] == 10

    assert controller.set_speed(50.0) is True
    assert controller.snapshot()["speed"] == 50
    assert captured_holder is not None and captured_holder["value"] == 50

    controller.stop()
    # Speed can only change while running or paused.
    assert controller.set_speed(20.0) is False


def test_replay_controller_seek_preserves_pause(monkeypatch):
    captured: list[tuple[threading.Event | None, float | None, int | None]] = []
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
        captured.append((pause_event, seek_time, seek_lap))
        if on_seeded is not None:
            on_seeded()
        seeded.set()
        if stop_event is not None:
            stop_event.wait(timeout=2.0)

    controller = replay_mod.ReplayController()
    monkeypatch.setattr(replay_mod, "replay_session", fake_replay)

    controller.start(9979, speed=10)
    assert seeded.wait(timeout=1.0)
    controller.pause()
    assert controller.snapshot()["status"] == "paused"

    seeded.clear()
    controller.seek(50.0)
    assert seeded.wait(timeout=1.0)
    # The new worker is paused and seeks to the requested time.
    assert captured[-1][0] is not None and captured[-1][0].is_set()
    assert captured[-1][1] == 50.0
    assert controller.snapshot()["status"] == "paused"

    seeded.clear()
    controller.seek_lap(12)
    assert seeded.wait(timeout=1.0)
    assert captured[-1][0] is not None and captured[-1][0].is_set()
    assert captured[-1][2] == 12
    assert controller.snapshot()["status"] == "paused"

    controller.stop()


def test_fetch_replay_sessions_filters_completed():
    class FakeClient:
        def get(self, endpoint, params):
            assert endpoint == "sessions"
            return {
                2025: [
                    {
                        "session_key": 100,
                        "country_name": "Monaco",
                        "location": "Monte Carlo",
                        "circuit_short_name": "Monaco",
                        "date_end": "2025-05-25T15:00:00+00:00",
                    },
                    {
                        "session_key": 101,
                        "country_name": "Japan",
                        "location": "Suzuka",
                        "circuit_short_name": "Suzuka",
                        "date_end": "2999-01-01T00:00:00+00:00",
                    },
                ]
            }.get(params["year"], [])

    sessions = replay_mod.fetch_replay_sessions(FakeClient())
    keys = [session["session_key"] for session in sessions]
    assert 100 in keys
    assert 101 not in keys
    monaco = next(s for s in sessions if s["session_key"] == 100)
    assert monaco["year"] == 2025
    assert monaco["country_name"] == "Monaco"
    assert monaco["circuit_short_name"] == "Monaco"


def test_fetch_replay_sessions_respects_years():
    queried = []

    class FakeClient:
        def get(self, endpoint, params):
            assert endpoint == "sessions"
            queried.append(params["year"])
            return [
                {
                    "session_key": params["year"],
                    "country_name": "Test",
                    "location": "Test",
                    "circuit_short_name": "Test",
                    "date_end": "2025-01-01T00:00:00+00:00",
                }
            ]

    sessions = replay_mod.fetch_replay_sessions(FakeClient(), years=[2025, 2026])
    assert sorted(queried) == [2025, 2026]
    assert [s["session_key"] for s in sessions] == [2025, 2026]


def test_location_window_count():
    session = {
        "date_start": "2026-07-26T13:00:00+00:00",
        "date_end": "2026-07-26T15:00:00+00:00",
    }
    assert location_window_count(session, []) == 24
    session["date_end"] = "2026-07-26T14:05:00+00:00"
    assert location_window_count(session, []) == 13


def test_download_replay_data_reuses_cache(tmp_path):
    session_key = 1
    cache = tmp_path / str(session_key)
    cache.mkdir(parents=True)
    atomic_write_json(
        cache / "sessions.json",
        [
            {
                "session_key": session_key,
                "meeting_key": 2,
                "date_start": "2026-07-26T13:00:00+00:00",
                "date_end": "2026-07-26T14:00:00+00:00",
            }
        ],
    )
    atomic_write_json(cache / "meetings.json", [{"meeting_key": 2}])
    for endpoint in replay_mod._ENDPOINTS:
        atomic_write_json(cache / f"{endpoint}.json", [])
    location_dir = cache / "location"
    location_dir.mkdir()
    for index in range(12):
        atomic_write_json(location_dir / f"{index:04d}.json", [])

    class ExplodingClient:
        def get(self, endpoint, params):
            raise AssertionError(f"unexpected network call to {endpoint}")

    data = download_replay_data(ExplodingClient(), session_key, cache=cache)
    assert data["session"]["session_key"] == session_key
    assert set(data) >= set(replay_mod._ENDPOINTS) | {"location", "session", "meetings"}


def test_save_and_load_timeline_roundtrip(tmp_path):
    data = _data()
    events = build_timeline(data)
    save_timeline(tmp_path, events, data)

    loaded = load_timeline(tmp_path, data["session"]["session_key"])
    assert loaded is not None
    loaded_events, meta = loaded
    assert loaded_events == events
    assert meta["format_version"] == replay_mod._TIMELINE_FORMAT_VERSION
    assert meta["session_key"] == 1
    assert meta["event_count"] == len(events)
    assert meta["total_duration"] == events[-1][0]
    assert meta["total_laps"] == 2


def test_load_timeline_missing_returns_none(tmp_path):
    assert load_timeline(tmp_path, 1) is None


def test_load_timeline_version_mismatch_returns_none(tmp_path):
    data = _data()
    save_timeline(tmp_path, build_timeline(data), data)
    path = replay_mod._timeline_path(tmp_path)
    blob = load_json(path)
    blob["format_version"] += 999
    atomic_write_json(path, blob)
    assert load_timeline(tmp_path, data["session"]["session_key"]) is None


def test_load_timeline_session_mismatch_returns_none(tmp_path):
    data = _data()
    save_timeline(tmp_path, build_timeline(data), data)
    assert load_timeline(tmp_path, 9999) is None


def _multi_driver_data():
    session = {
        "session_key": 7,
        "session_name": "Race",
        "circuit_key": 4,
        "date_start": "2026-07-26T13:00:00+00:00",
        "date_end": "2026-07-26T15:00:00+00:00",
    }
    laps = [
        {
            "driver_number": 4,
            "lap_number": 1,
            "date_start": "2026-07-26T13:00:00+00:00",
            "date_end": "2026-07-26T13:01:30+00:00",
            "lap_duration": 90.0,
        },
        {
            "driver_number": 44,
            "lap_number": 1,
            "date_start": "2026-07-26T13:00:00+00:00",
            "date_end": "2026-07-26T13:01:31+00:00",
            "lap_duration": 91.0,
        },
        {
            "driver_number": 4,
            "lap_number": 2,
            "date_start": "2026-07-26T13:01:30+00:00",
            "date_end": "2026-07-26T13:03:00+00:00",
            "lap_duration": 90.0,
        },
        {
            "driver_number": 44,
            "lap_number": 2,
            "date_start": "2026-07-26T13:01:31+00:00",
            "date_end": "2026-07-26T13:03:01+00:00",
            "lap_duration": 90.0,
        },
    ]
    return {
        "session": session,
        "meetings": [{"meeting_key": 1, "meeting_name": "Test GP"}],
        "drivers": [
            {"driver_number": 4, "full_name": "Driver Four"},
            {"driver_number": 44, "full_name": "Driver FortyFour"},
        ],
        "laps": laps,
        "stints": [],
        "pit": [],
        "position": [],
        "intervals": [],
        "weather": [],
        "race_control": [],
        "location": [],
    }


def _seed(state, data):
    state.update("v1/sessions", data["session"])
    for meeting in data["meetings"]:
        state.update("v1/meetings", meeting)
    for driver in data["drivers"]:
        state.update("v1/drivers", driver)


def test_build_checkpoints_one_per_completed_lap():
    data = _multi_driver_data()
    events = build_timeline(data)
    checkpoints = build_checkpoints(
        events, data["session"], data["meetings"], data["drivers"]
    )
    assert [cp["lap"] for cp in checkpoints] == [1, 2]
    # The lap-1 checkpoint is taken at the first lap-1 completion (offset 90).
    assert checkpoints[0]["time"] == 90.0
    assert checkpoints[1]["time"] == 180.0


def test_checkpoint_state_has_no_future_laps():
    data = _multi_driver_data()
    events = build_timeline(data)
    checkpoints = build_checkpoints(
        events, data["session"], data["meetings"], data["drivers"]
    )
    lap1 = checkpoints[0]
    laps = [
        row["lap_number"] for row in lap1["state"].get("v1/laps", {}).values()
    ]
    # Only the first driver's lap 1 has completed at offset 90 — nothing later.
    assert laps == [1]

    lap2 = checkpoints[1]
    laps = [
        row["lap_number"] for row in lap2["state"].get("v1/laps", {}).values()
    ]
    assert set(laps) == {1, 2}


def test_checkpoint_cursor_matches_replay_up_to_that_point():
    data = _multi_driver_data()
    events = build_timeline(data)
    checkpoints = build_checkpoints(
        events, data["session"], data["meetings"], data["drivers"]
    )
    for checkpoint in checkpoints:
        replay = LiveState()
        _seed(replay, data)
        for _, topic, payload in events[: checkpoint["cursor"]]:
            replay.update(topic, payload)
        assert replay.snapshot_docs() == checkpoint["state"]


def test_save_and_load_checkpoints_roundtrip(tmp_path):
    data = _multi_driver_data()
    events = build_timeline(data)
    checkpoints = build_checkpoints(
        events, data["session"], data["meetings"], data["drivers"]
    )
    save_checkpoints(tmp_path, checkpoints, data["session"]["session_key"])

    index = load_checkpoint_index(tmp_path, data["session"]["session_key"])
    assert index is not None
    assert [entry["lap"] for entry in index] == [1, 2]

    state_entry = load_checkpoint_state(tmp_path, index[1])
    assert state_entry is not None
    restored = LiveState()
    cursor = restore_checkpoint(restored, state_entry)
    assert cursor == checkpoints[1]["cursor"]
    assert restored.snapshot_docs() == checkpoints[1]["state"]


def test_nearest_checkpoint_by_time():
    checkpoints = [
        {"time": 90.0, "cursor": 10},
        {"time": 180.0, "cursor": 50},
        {"time": 270.0, "cursor": 100},
    ]
    assert nearest_checkpoint_by_time(checkpoints, 120.0)["cursor"] == 10
    assert nearest_checkpoint_by_time(checkpoints, 90.0)["cursor"] == 10
    assert nearest_checkpoint_by_time(checkpoints, 89.9) is None
    assert nearest_checkpoint_by_time(checkpoints, 270.0)["cursor"] == 100


def test_nearest_checkpoint_by_lap():
    checkpoints = [
        {"lap": 1, "cursor": 10},
        {"lap": 2, "cursor": 50},
        {"lap": 3, "cursor": 100},
    ]
    assert nearest_checkpoint_by_lap(checkpoints, 2)["cursor"] == 50
    assert nearest_checkpoint_by_lap(checkpoints, 4)["cursor"] == 100
    assert nearest_checkpoint_by_lap(checkpoints, 0) is None


def test_load_checkpoint_index_missing_returns_none(tmp_path):
    assert load_checkpoint_index(tmp_path, 7) is None


def test_load_checkpoint_index_version_mismatch_returns_none(tmp_path):
    data = _multi_driver_data()
    events = build_timeline(data)
    checkpoints = build_checkpoints(
        events, data["session"], data["meetings"], data["drivers"]
    )
    save_checkpoints(tmp_path, checkpoints, data["session"]["session_key"])

    index_path = replay_mod._checkpoint_index_path(tmp_path)
    blob = load_json(index_path)
    blob["format_version"] += 999
    atomic_write_json(index_path, blob)
    assert load_checkpoint_index(tmp_path, data["session"]["session_key"]) is None


def test_restore_seek_returns_checkpoint_cursor(tmp_path):
    data = _multi_driver_data()
    events = build_timeline(data)
    checkpoints = build_checkpoints(
        events, data["session"], data["meetings"], data["drivers"]
    )
    save_checkpoints(tmp_path, checkpoints, data["session"]["session_key"])

    buffer = LiveState()
    cursor, lap = replay_mod._restore_seek(
        tmp_path,
        data["session"]["session_key"],
        events,
        data["session"],
        data["meetings"],
        data["drivers"],
        seek_time=180.0,
        buffer=buffer,
    )
    assert lap == 2
    assert cursor == checkpoints[1]["cursor"]
    assert buffer.snapshot_docs() == checkpoints[1]["state"]


def test_restore_seek_fast_forwards_between_checkpoints(tmp_path):
    data = _multi_driver_data()
    events = build_timeline(data)
    checkpoints = build_checkpoints(
        events, data["session"], data["meetings"], data["drivers"]
    )
    save_checkpoints(tmp_path, checkpoints, data["session"]["session_key"])

    buffer = LiveState()
    # 91.0 is after the lap-1 checkpoint (90.0) but before lap 2 (180.0).
    cursor, lap = replay_mod._restore_seek(
        tmp_path,
        data["session"]["session_key"],
        events,
        data["session"],
        data["meetings"],
        data["drivers"],
        seek_time=91.0,
        buffer=buffer,
    )
    assert lap == 1
    assert cursor == checkpoints[1]["cursor"] - 1  # applied only the 91.0 event
    laps = [row["lap_number"] for row in buffer.docs_for("v1/laps")]
    assert laps == [1, 1]  # both drivers' lap 1, nothing from lap 2


def test_restore_seek_builds_checkpoints_when_missing(tmp_path):
    data = _multi_driver_data()
    events = build_timeline(data)

    buffer = LiveState()
    cursor, lap = replay_mod._restore_seek(
        tmp_path,
        data["session"]["session_key"],
        events,
        data["session"],
        data["meetings"],
        data["drivers"],
        seek_time=90.0,
        buffer=buffer,
    )
    assert lap == 1
    assert cursor > 0
    # Checkpoints were built and persisted on first seek.
    index = load_checkpoint_index(tmp_path, data["session"]["session_key"])
    assert index is not None and len(index) == 2


def test_restore_seek_before_first_lap_seeds_identity(tmp_path):
    data = _multi_driver_data()
    events = build_timeline(data)

    buffer = LiveState()
    cursor, lap = replay_mod._restore_seek(
        tmp_path,
        data["session"]["session_key"],
        events,
        data["session"],
        data["meetings"],
        data["drivers"],
        seek_time=0.0,
        buffer=buffer,
    )
    assert (cursor, lap) == (0, 0)
    assert buffer.docs_for("v1/sessions")[0]["session_key"] == 7
    assert len(buffer.docs_for("v1/drivers")) == 2


def test_replay_session_seek_reaches_same_final_state(monkeypatch, tmp_path):
    data = _multi_driver_data()
    events = build_timeline(data)
    monkeypatch.setattr(replay_mod, "replay_dir", lambda key: tmp_path)
    monkeypatch.setattr(
        replay_mod, "download_replay_data", lambda client, key, cache=None: data
    )

    buffer = LiveState()
    progress: dict = {}
    replay_mod.replay_session(
        7, speed=100000, state=buffer, progress=progress, seek_time=91.0
    )

    expected = LiveState()
    _seed(expected, data)
    for _, topic, payload in events:
        expected.update(topic, payload)
    assert buffer.snapshot_docs() == expected.snapshot_docs()
    assert progress["current_lap"] == 2
    assert progress["total_laps"] == 2


def test_cache_session_trailing_location_gap_is_ready(monkeypatch, tmp_path):
    session = {
        "session_key": 5,
        "year": 2025,
        "country_name": "Test",
        "location": "Test",
    }
    monkeypatch.setattr(cache_replays, "replay_dir", lambda key: tmp_path / str(key))

    def fake_download(client, session_key, cache=None):
        return {
            "session": {
                "session_key": 5,
                "date_start": "2026-07-26T13:00:00+00:00",
                "date_end": "2026-07-26T14:00:00+00:00",
            },
            "meetings": [],
            "drivers": [],
            "laps": [],
            "stints": [],
            "pit": [],
            "position": [],
            "intervals": [],
            "weather": [],
            "race_control": [],
            "location": [],
        }

    monkeypatch.setattr(cache_replays, "download_replay_data", fake_download)

    location_dir = tmp_path / "5" / "location"
    location_dir.mkdir(parents=True)
    for index in range(11):  # 12 windows needed, only 11 present → trailing gap
        atomic_write_json(location_dir / f"{index:04d}.json", [])

    readiness, failures = cache_replays.cache_session(object(), session)
    assert readiness == "ready"
    assert failures == []
    # A trailing location gap is report-only: the prepared representation builds.
    assert load_timeline(tmp_path / "5", 5) is not None
    assert load_checkpoint_index(tmp_path / "5", 5) is not None


def test_last_lap_end_derives_from_lap_duration():
    laps = [
        {
            "driver_number": 4,
            "date_start": "2026-07-26T13:00:00+00:00",
            "lap_duration": 90.0,
        },
        {
            "driver_number": 4,
            "date_start": "2026-07-26T13:01:30+00:00",
            "lap_duration": 89.0,
        },
    ]
    assert replay_mod._last_lap_end(laps).isoformat() == "2026-07-26T13:02:59+00:00"


def test_last_lap_end_empty_returns_none():
    assert replay_mod._last_lap_end([]) is None


def test_replay_readiness_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_replays, "replay_dir", lambda key: tmp_path / str(key))
    cache_replays.prepare_timeline(tmp_path / "1", _data())
    assert cache_replays.replay_readiness(1) == "ready"


def test_replay_readiness_not_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_replays, "replay_dir", lambda key: tmp_path / str(key))
    monkeypatch.setattr(cache_replays, "FAILURES_PATH", tmp_path / "no-failures.txt")
    assert cache_replays.replay_readiness(99) == "not_ready"


def test_replay_readiness_failed(monkeypatch, tmp_path):
    failures = tmp_path / "cache_failures.txt"
    failures.write_text(
        "2026-01-01T00:00:00+00:00 | 42 | 2025 Test | download failed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cache_replays, "replay_dir", lambda key: tmp_path / str(key))
    monkeypatch.setattr(cache_replays, "FAILURES_PATH", failures)
    assert cache_replays.replay_readiness(42) == "failed"


def test_classify_location_gaps_complete():
    assert replay_mod.classify_location_gaps(4, [0, 1, 2, 3]) == "complete"


def test_classify_location_gaps_one_trailing_missing():
    # 21 windows expected, 20 present → the single missing window is trailing.
    assert replay_mod.classify_location_gaps(21, range(20)) == "trailing"


def test_classify_location_gaps_multiple_trailing_missing():
    # 22 windows expected, 18 present → 0018–0021 missing, all trailing.
    assert replay_mod.classify_location_gaps(22, range(18)) == "trailing"


def test_classify_location_gaps_internal():
    # 0002–0003 missing but 0004+ present → location resumes after a gap.
    assert replay_mod.classify_location_gaps(6, [0, 1, 4, 5]) == "internal"


def test_classify_location_gaps_multiple_internal():
    assert replay_mod.classify_location_gaps(8, [0, 1, 4, 7]) == "internal"


def test_classify_location_gaps_absent():
    assert replay_mod.classify_location_gaps(4, []) == "absent"


def test_classify_location_gaps_none_expected():
    assert replay_mod.classify_location_gaps(0, []) == "complete"


def _write_readiness_cache(
    tmp_path, session_key, windows, *, date_end="2026-07-26T14:00:00+00:00"
):
    cache = tmp_path / str(session_key)
    cache.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        cache / "sessions.json",
        [
            {
                "session_key": session_key,
                "date_start": "2026-07-26T13:00:00+00:00",
                "date_end": date_end,
            }
        ],
    )
    atomic_write_json(cache / "laps.json", [])
    location_dir = cache / "location"
    location_dir.mkdir(parents=True, exist_ok=True)
    for index in windows:
        atomic_write_json(location_dir / f"{index:04d}.json", [])
    atomic_write_json(cache / "timeline.json", {})
    checkpoints_dir = cache / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        checkpoints_dir / "index.json",
        {
            "format_version": replay_mod._TIMELINE_FORMAT_VERSION,
            "session_key": session_key,
            "checkpoints": [],
        },
    )
    return cache


def test_readiness_complete_location_is_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_replays, "replay_dir", lambda key: tmp_path / str(key))
    monkeypatch.setattr(cache_replays, "FAILURES_PATH", tmp_path / "no-failures.txt")
    _write_readiness_cache(tmp_path, 1, range(12))
    assert cache_replays.replay_readiness(1) == "ready"


def test_readiness_one_trailing_missing_window_is_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_replays, "replay_dir", lambda key: tmp_path / str(key))
    monkeypatch.setattr(cache_replays, "FAILURES_PATH", tmp_path / "no-failures.txt")
    _write_readiness_cache(tmp_path, 1, range(11))  # 0011 missing, trailing
    assert cache_replays.replay_readiness(1) == "ready"


def test_readiness_multiple_trailing_missing_windows_is_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_replays, "replay_dir", lambda key: tmp_path / str(key))
    monkeypatch.setattr(cache_replays, "FAILURES_PATH", tmp_path / "no-failures.txt")
    _write_readiness_cache(tmp_path, 1, range(9))  # 0009–0011 missing, trailing
    assert cache_replays.replay_readiness(1) == "ready"


def test_readiness_internal_location_gap_is_partial(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_replays, "replay_dir", lambda key: tmp_path / str(key))
    monkeypatch.setattr(cache_replays, "FAILURES_PATH", tmp_path / "no-failures.txt")
    windows = [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11]  # 0002 missing, later data
    _write_readiness_cache(tmp_path, 1, windows)
    assert cache_replays.replay_readiness(1) == "partial"


def test_readiness_multiple_internal_gaps_is_partial(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_replays, "replay_dir", lambda key: tmp_path / str(key))
    monkeypatch.setattr(cache_replays, "FAILURES_PATH", tmp_path / "no-failures.txt")
    windows = [0, 1, 4, 7, 8, 9, 10, 11]  # 0002–0003 and 0005–0006 internal
    _write_readiness_cache(tmp_path, 1, windows)
    assert cache_replays.replay_readiness(1) == "partial"


def test_readiness_absent_location_is_partial(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_replays, "replay_dir", lambda key: tmp_path / str(key))
    monkeypatch.setattr(cache_replays, "FAILURES_PATH", tmp_path / "no-failures.txt")
    _write_readiness_cache(tmp_path, 1, [])  # 12 expected, none present
    assert cache_replays.replay_readiness(1) == "partial"


def test_readiness_cancelled_sessions(monkeypatch, tmp_path):
    monkeypatch.setattr(cache_replays, "replay_dir", lambda key: tmp_path / str(key))
    monkeypatch.setattr(cache_replays, "FAILURES_PATH", tmp_path / "no-failures.txt")
    assert cache_replays.replay_readiness(9086) == "cancelled"
    assert cache_replays.replay_readiness(11261) == "cancelled"
    assert cache_replays.replay_readiness(11269) == "cancelled"


def test_cache_session_skips_cancelled_sessions():
    session = {
        "session_key": 9086,
        "year": 2023,
        "country_name": "Italy",
        "location": "Imola",
    }

    class ExplodingClient:
        def get(self, endpoint, params):
            raise AssertionError("cancelled session must not be downloaded")

    readiness, failures = cache_replays.cache_session(ExplodingClient(), session)
    assert readiness == "cancelled"
    assert failures == []


def test_readiness_stale_failure_entries_do_not_override_valid_cache(
    monkeypatch, tmp_path
):
    failures = tmp_path / "cache_failures.txt"
    failures.write_text(
        "2026-01-01T00:00:00+00:00 | 1 | 2026 Test | location window 0011 missing\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cache_replays, "replay_dir", lambda key: tmp_path / str(key))
    monkeypatch.setattr(cache_replays, "FAILURES_PATH", failures)
    _write_readiness_cache(tmp_path, 1, range(11))  # trailing gap, still ready
    assert cache_replays.replay_readiness(1) == "ready"
