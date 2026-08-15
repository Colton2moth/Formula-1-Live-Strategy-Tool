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
from formula1_strategy_tool.api.websocket import broadcaster, manager
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
