"""Tests for mock REST API endpoints."""

from fastapi.testclient import TestClient

from formula1_strategy_tool.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "OpenF1 backend is running"


def test_get_session_matches_contract():
    response = client.get("/api/session")
    assert response.status_code == 200
    data = response.json()
    assert data["meeting_name"] == "Canadian Grand Prix"
    assert data["session_name"] == "Race"
    assert data["current_lap"] == 25
    assert "race_control_status" in data


def test_get_drivers_returns_list():
    response = client.get("/api/drivers")
    assert response.status_code == 200
    drivers = response.json()
    assert len(drivers) >= 1
    assert drivers[0]["driver_number"] == 1
    assert 0 <= drivers[0]["track_progress"] <= 1


def test_get_driver_found():
    response = client.get("/api/drivers/4")
    assert response.status_code == 200
    assert response.json()["acronym"] == "NOR"
    assert 0 <= response.json()["track_progress"] <= 1


def test_get_driver_not_found():
    response = client.get("/api/drivers/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Driver not found"


def test_get_race_state_snapshot():
    response = client.get("/api/race-state")
    assert response.status_code == 200
    data = response.json()
    assert "session" in data
    assert "drivers" in data
    assert "predictions" in data
    assert len(data["drivers"]) == len(data["predictions"])
    assert all(0 <= driver["track_progress"] <= 1 for driver in data["drivers"])


def test_get_track():
    response = client.get("/api/track")
    assert response.status_code == 200
    data = response.json()
    assert data["circuit_name"] == "Demo Switchback Circuit"
    assert data["start_finish"] == {"x": 0.6, "y": 0.88}
    assert len(data["path"]) > 2
