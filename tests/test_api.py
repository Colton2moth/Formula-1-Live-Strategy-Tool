"""Tests for the live-data REST API endpoints."""

import pytest
from fastapi.testclient import TestClient

from formula1_strategy_tool.acquisition.live_state import LIVE_STATE
from formula1_strategy_tool.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_live_state():
    LIVE_STATE.clear()
    yield


def seed_hungarian_session() -> None:
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
    LIVE_STATE.update(
        "v1/meetings", {"meeting_key": 1291, "meeting_name": "Hungarian Grand Prix"}
    )


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "OpenF1 backend is running"


def test_session_503_without_live_data():
    response = client.get("/api/session")
    assert response.status_code == 503


def test_drivers_empty_without_live_data():
    response = client.get("/api/drivers")
    assert response.status_code == 200
    assert response.json() == []


def test_driver_not_found_without_live_data():
    response = client.get("/api/drivers/999")
    assert response.status_code == 404


def test_race_state_503_without_live_data():
    response = client.get("/api/race-state")
    assert response.status_code == 503


def test_track_503_without_live_data():
    response = client.get("/api/track")
    assert response.status_code == 503


def test_session_from_live_data():
    seed_hungarian_session()
    response = client.get("/api/session")
    assert response.status_code == 200
    data = response.json()
    assert data["meeting_name"] == "Hungarian Grand Prix"
    assert data["session_name"] == "Race"


def test_track_resolves_hungaroring():
    seed_hungarian_session()
    response = client.get("/api/track")
    assert response.status_code == 200
    data = response.json()
    assert data["circuit_name"] == "Hungaroring"
    assert data["circuit_key"] == 4
    assert len(data["path"]) > 2
    assert data["path"][0] == data["path"][-1]


def test_track_404_unknown_circuit():
    LIVE_STATE.update(
        "v1/sessions", {"circuit_key": 999, "session_name": "Race"}
    )
    response = client.get("/api/track")
    assert response.status_code == 404


def seed_montreal_session() -> None:
    LIVE_STATE.update(
        "v1/sessions",
        {"circuit_key": 23, "circuit_short_name": "Montreal", "session_name": "Race"},
    )


def test_track_includes_pit_lane_for_montreal():
    seed_montreal_session()
    response = client.get("/api/track")
    assert response.status_code == 200
    data = response.json()
    assert data["circuit_key"] == 23
    assert data["pit_lane"] is not None
    assert len(data["pit_lane"]) > 2


def seed_interlagos_session() -> None:
    LIVE_STATE.update(
        "v1/sessions",
        {"circuit_key": 14, "circuit_short_name": "Interlagos", "session_name": "Race"},
    )


def test_track_no_pit_lane_for_interlagos():
    seed_interlagos_session()
    response = client.get("/api/track")
    assert response.status_code == 200
    assert response.json().get("pit_lane") is None


def test_tracks_lists_every_circuit_with_pit_lanes():
    from formula1_strategy_tool.api.circuits import CIRCUITS
    from formula1_strategy_tool.api.pit_lanes import PIT_LANES

    response = client.get("/api/tracks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(CIRCUITS)

    by_key = {track["circuit_key"]: track for track in data}
    assert set(by_key) == set(CIRCUITS)

    for key, track in by_key.items():
        assert len(track["path"]) > 2
        assert track["path"][0] == track["path"][-1]
        assert track["country_name"]
        if key in PIT_LANES:
            assert track["pit_lane"] is not None
            assert len(track["pit_lane"]) > 2
        else:
            assert track["pit_lane"] is None


def test_replay_sessions_include_readiness(monkeypatch):
    from formula1_strategy_tool.acquisition import cache_replays
    from formula1_strategy_tool.acquisition import replay as replay_mod

    monkeypatch.setattr(
        replay_mod,
        "list_replay_sessions",
        lambda: [
            {
                "session_key": 9963,
                "year": 2025,
                "country_name": "Canada",
                "location": "Montreal",
                "circuit_short_name": "Montreal",
                "date_start": "2025-06-15T18:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(cache_replays, "replay_readiness", lambda key: "ready")

    response = client.get("/api/replay/sessions")
    assert response.status_code == 200
    assert response.json()[0]["readiness"] == "ready"


def test_replay_speed_requires_running_runtime(monkeypatch):
    from formula1_strategy_tool.acquisition import replay as replay_mod
    from formula1_strategy_tool.acquisition import replay_registry

    monkeypatch.setattr(
        replay_mod.ReplayController, "start", lambda self, *a, **k: None
    )
    runtime = replay_registry.registry.create(100, speed=10)
    try:
        response = client.post(
            f"/api/replays/{runtime.replay_id}/speed", json={"speed": 50.0}
        )
        assert response.status_code == 409
    finally:
        replay_registry.registry.stop(runtime.replay_id)


def test_replay_speed_validates_range():
    response = client.post("/api/replays/unknown/speed", json={"speed": 0.1})
    assert response.status_code == 422


def test_replay_seek_accepts_exactly_one_lap_or_time(monkeypatch):
    from formula1_strategy_tool.acquisition import replay as replay_mod
    from formula1_strategy_tool.acquisition import replay_registry

    monkeypatch.setattr(
        replay_mod.ReplayController, "start", lambda self, *a, **k: None
    )
    runtime = replay_registry.registry.create(100, speed=10)
    try:
        laps: list[object] = []
        monkeypatch.setattr(runtime.controller, "seek_lap", laps.append)

        assert (
            client.post(
                f"/api/replays/{runtime.replay_id}/seek", json={"lap": 12}
            ).status_code
            == 200
        )
        assert laps == [12]
        assert (
            client.post(f"/api/replays/{runtime.replay_id}/seek", json={}).status_code
            == 422
        )
        assert (
            client.post(
                f"/api/replays/{runtime.replay_id}/seek",
                json={"lap": 12, "time": 50},
            ).status_code
            == 422
        )
    finally:
        replay_registry.registry.stop(runtime.replay_id)


def test_locations_endpoint_compact_shape():
    LIVE_STATE.update(
        "v1/location",
        {"driver_number": 4, "x": 100, "y": 200, "date": "2026-07-26T14:00:00"},
    )
    LIVE_STATE.update(
        "v1/location",
        {"driver_number": 1, "x": 0, "y": 0, "date": "2026-07-26T14:00:00"},
    )
    response = client.get("/api/locations")
    assert response.status_code == 200
    data = response.json()
    by_number = {row["driver_number"]: row for row in data}
    assert by_number[4]["x"] == 100.0
    assert by_number[4]["y"] == 200.0
    assert by_number[1]["x"] is None
