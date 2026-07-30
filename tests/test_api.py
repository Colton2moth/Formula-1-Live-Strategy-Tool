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


def test_get_driver_found():
    response = client.get("/api/drivers/4")
    assert response.status_code == 200
    assert response.json()["acronym"] == "NOR"


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


def test_get_predictions_include_all_model_outputs():
    response = client.get("/api/predictions")
    assert response.status_code == 200
    preds = response.json()
    assert len(preds) >= 1
    row = next(p for p in preds if p["driver_number"] == 4)
    # Three pit-window models + compound multiclass.
    assert row["pit_within_3_laps"] == 0.55
    assert row["pit_within_5_laps"] == 0.72
    assert row["pit_within_7_laps"] == 0.84
    assert row["predicted_next_compound"] == "HARD"
    assert row["compound_probabilities"]["HARD"] == 0.75
    assert "pit_probability" not in row


def test_get_driver_prediction_below_threshold_allows_null_compound():
    response = client.get("/api/drivers/1/prediction")
    assert response.status_code == 200
    data = response.json()
    assert data["pit_within_5_laps"] == 0.15
    assert data["predicted_next_compound"] is None
    assert data["compound_probabilities"] is not None


def test_get_track():
    response = client.get("/api/track")
    assert response.status_code == 200
    data = response.json()
    assert data["circuit_name"] == "Circuit Gilles Villeneuve"
    assert len(data["path"]) > 2
