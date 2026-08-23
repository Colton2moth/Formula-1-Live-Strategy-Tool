"""Tests for LiveState retention, thread-safe accessors, and location helpers."""

from formula1_strategy_tool.acquisition.live_state import LiveState, location_xy
from formula1_strategy_tool.acquisition.live_drivers import drivers_from_live


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


def test_driver_rows_deduplicate_bootstrap_and_mqtt_versions():
    state = LiveState()
    state.update(
        "v1/drivers",
        {"driver_number": 1, "full_name": "Bootstrap Driver"},
    )
    state.update(
        "v1/drivers",
        {"_key": "mqtt:1", "driver_number": 1, "full_name": "MQTT Driver"},
    )

    drivers = drivers_from_live(state)

    assert drivers is not None
    assert len(drivers) == 1
    assert drivers[0].name == "MQTT Driver"


def test_snapshot_and_replace_docs_roundtrip():
    state = LiveState()
    state.update("v1/laps", {"driver_number": 1, "lap_number": 1, "lap_duration": 90.0})
    state.update("v1/location", _location(44, 12, 34))

    snapshot = state.snapshot_docs()
    assert snapshot["v1/laps"] == state.docs["v1/laps"]
    assert snapshot["v1/location"] == state.docs["v1/location"]

    restored = LiveState()
    restored.replace_docs(snapshot)
    assert restored.docs_for("v1/laps") == state.docs_for("v1/laps")
    assert restored.latest_locations()[44]["x"] == 12.0
    assert set(restored.counts) == {"v1/laps", "v1/location"}


def test_replace_docs_marks_all_topics_dirty():
    state = LiveState()
    state.update("v1/laps", {"driver_number": 1, "lap_number": 1, "lap_duration": 90.0})
    assert state.drain_dirty() == {"v1/laps"}
    assert state.drain_dirty() == set()

    state.replace_docs({"v1/laps": state.docs["v1/laps"]})
    assert state.drain_dirty() == {"v1/laps"}
