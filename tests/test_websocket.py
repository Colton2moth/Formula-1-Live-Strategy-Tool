"""End-to-end tests for the /ws/live WebSocket incremental broadcaster."""

import os

# Disable network-backed background tasks before the app is imported, so the
# lifespan only starts the in-memory WebSocket broadcaster.
os.environ["LIVE_BOOTSTRAP"] = "0"
os.environ["LIVE_MQTT"] = "0"

import time

import pytest
from fastapi.testclient import TestClient

from formula1_strategy_tool.acquisition.live_state import LIVE_STATE
from formula1_strategy_tool.api.schemas import (
    CompoundProbabilities,
    DriverState,
    PredictionState,
)
from formula1_strategy_tool.api.websocket import (
    _driver_event,
    _prediction_event,
    broadcaster,
    manager,
)
from formula1_strategy_tool.main import app


@pytest.fixture(autouse=True)
def reset_state():
    LIVE_STATE.clear()
    broadcaster.reset()
    manager.active.clear()
    yield


def _seed_driver_and_location():
    LIVE_STATE.update(
        "v1/drivers",
        {
            "driver_number": 4,
            "full_name": "Lando Norris",
            "name_acronym": "NOR",
            "team_name": "McLaren",
            "team_colour": "FF8000",
        },
    )
    LIVE_STATE.update(
        "v1/location",
        {"driver_number": 4, "x": 100, "y": 200, "date": "2026-07-26T14:00:00"},
    )


def test_websocket_receives_location_and_driver_updates():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            _seed_driver_and_location()
            time.sleep(1.0)

            first = websocket.receive_json()
            second = websocket.receive_json()
            types = {first["type"], second["type"]}
            assert types == {"location_update", "driver_update"}

            by_type = {first["type"]: first, second["type"]: second}
            location = by_type["location_update"]
            assert location["driver_number"] == 4
            assert location["x"] == 100.0
            assert location["y"] == 200.0
            driver = by_type["driver_update"]
            assert driver["driver_number"] == 4


def test_websocket_streams_only_changed_locations():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            _seed_driver_and_location()
            time.sleep(1.0)
            websocket.receive_json()
            websocket.receive_json()

            LIVE_STATE.update(
                "v1/location",
                {"driver_number": 4, "x": 300, "y": 400, "date": "2026-07-26T14:00:05"},
            )
            time.sleep(1.0)

            event = websocket.receive_json()
            assert event["type"] == "location_update"
            assert event["driver_number"] == 4
            assert event["x"] == 300.0
            assert event["y"] == 400.0


def test_websocket_receives_weather_update():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            LIVE_STATE.update(
                "v1/weather",
                {
                    "track_temperature": 34.2,
                    "air_temperature": 21.5,
                    "rainfall": False,
                    "date": "2026-07-26T14:00:00",
                },
            )
            time.sleep(1.0)

            event = websocket.receive_json()
            assert event["type"] == "weather_update"
            assert event["track_temperature"] == 34.2
            assert event["air_temperature"] == 21.5
            assert event["rainfall"] is False


def test_websocket_receives_race_control_update():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            LIVE_STATE.update(
                "v1/race_control",
                {
                    "flag": "SAFETY CAR",
                    "message": "Safety Car deployed",
                    "date": "2026-07-26T14:00:00",
                },
            )
            time.sleep(1.0)

            event = websocket.receive_json()
            assert event["type"] == "race_control_update"
            assert event["status"] == "SAFETY CAR"
            assert event["message"] == "Safety Car deployed"


def test_driver_event_includes_timing_fields():
    driver = DriverState(
        driver_number=4,
        name="Lando Norris",
        acronym="NOR",
        team_name="McLaren",
        team_colour="FF8000",
        position=2,
        x=1245.0,
        y=-438.0,
        current_lap=25,
        compound="MEDIUM",
        tyre_age=14,
        last_lap_time=75.421,
        gap_to_leader=3.8,
        interval_ahead=1.2,
        interval_behind=2.1,
        pit_stops=1,
    )

    event = _driver_event(driver)
    assert event["type"] == "driver_update"
    assert event["driver_number"] == 4
    assert event["gap_to_leader"] == 3.8
    assert event["interval_ahead"] == 1.2
    assert event["interval_behind"] == 2.1
    assert event["pit_stops"] == 1


def test_prediction_event_shape():
    prediction = PredictionState(
        driver_number=4,
        lap_number=25,
        pit_within_3_laps=0.55,
        pit_within_5_laps=0.72,
        pit_within_7_laps=0.84,
        predicted_next_compound="HARD",
        compound_probabilities=CompoundProbabilities(
            SOFT=0.04,
            MEDIUM=0.21,
            HARD=0.75,
            INTERMEDIATE=0.0,
            WET=0.0,
        ),
        updated_at="2026-06-14T18:34:10Z",
    )

    event = _prediction_event(prediction)
    assert event["type"] == "prediction_update"
    assert event["driver_number"] == 4
    assert event["predicted_next_compound"] == "HARD"
    assert event["compound_probabilities"] == {
        "SOFT": 0.04,
        "MEDIUM": 0.21,
        "HARD": 0.75,
        "INTERMEDIATE": 0.0,
        "WET": 0.0,
    }
