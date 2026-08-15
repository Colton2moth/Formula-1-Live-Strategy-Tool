"""Tests for LiveState retention, thread-safe accessors, and location helpers."""

from formula1_strategy_tool.acquisition.live_state import LiveState, location_xy


def _location(driver_number, x, y, date="2026-01-01T00:00:00", key=None):
    payload = {"driver_number": driver_number, "x": x, "y": y, "date": date}
    if key is not None:
        payload["_key"] = key
    return payload


def test_location_retention_keeps_latest_per_driver():
    state = LiveState()
    # Each MQTT location message can carry a unique _key; retention must still
    # collapse to a single entry per driver rather than accumulate.
    for i, (x, y) in enumerate([(100, 200), (110, 210), (120, 220)]):
        state.update("v1/location", _location(1, x, y, key=f"loc:{i}"))
    state.update("v1/location", _location(44, 5, 6, key="loc:44"))

    assert len(state.docs_for("v1/location")) == 2

    locations = state.latest_locations()
    assert locations[1]["x"] == 120.0
    assert locations[1]["y"] == 220.0
    assert locations[44]["x"] == 5.0
    assert locations[44]["y"] == 6.0


def test_latest_locations_nulls_no_position_sentinel():
    state = LiveState()
    state.update("v1/location", _location(1, 0, 0))
    state.update("v1/location", _location(44, 12, 34))

    locations = state.latest_locations()
    assert locations[1]["x"] is None
    assert locations[1]["y"] is None
    assert locations[44]["x"] == 12.0
    assert locations[44]["y"] == 34.0


def test_location_xy():
    assert location_xy({"x": 0, "y": 0}) == (None, None)
    assert location_xy({"x": 489, "y": 3934}) == (489.0, 3934.0)
    assert location_xy({}) == (None, None)


def test_other_topics_still_use_key():
    state = LiveState()
    state.update(
        "v1/laps",
        {"_key": "a", "driver_number": 1, "lap_number": 1, "lap_duration": 90.0},
    )
    state.update(
        "v1/laps",
        {"_key": "b", "driver_number": 1, "lap_number": 2, "lap_duration": 89.0},
    )
    assert len(state.docs_for("v1/laps")) == 2
