"""Tests for the live-data REST API endpoints."""

import pytest
from fastapi.testclient import TestClient

from formula1_strategy_tool.acquisition.live_state import LIVE_STATE
from formula1_strategy_tool.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_live_state():
    LIVE_STATE.docs.clear()
    LIVE_STATE.counts.clear()
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
