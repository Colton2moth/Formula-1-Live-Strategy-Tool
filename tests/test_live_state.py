"""Tests for LiveState retention, thread-safe accessors, and location helpers."""

from formula1_strategy_tool.acquisition.live_drivers import drivers_from_live
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


def test_location_updates_queue_intermediate_samples_until_drain():
    state = LiveState()
    for index, x in enumerate((100, 110, 120)):
        state.update(
            "v1/location",
            _location(1, x, 200, date=f"2026-01-01T00:00:0{index}"),
        )

    assert state.latest_locations()[1]["x"] == 120.0
    assert [row["x"] for row in state.drain_location_updates()] == [100, 110, 120]
    assert state.drain_location_updates() == []


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


def test_laps_keep_history_per_driver():
    # Distinct laps must both be retained (pace features need lap history),
    # even when each MQTT message carries its own _key.
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


def test_driver_uses_last_completed_lap_time_while_current_lap_is_running():
    state = LiveState()
    state.update("v1/drivers", {"driver_number": 1, "full_name": "Driver One"})
    state.update(
        "v1/laps",
        {"driver_number": 1, "lap_number": 10, "lap_duration": 75.421},
    )
    state.update(
        "v1/laps",
        {"driver_number": 1, "lap_number": 11, "lap_duration": None},
    )

    drivers = drivers_from_live(state)

    assert drivers is not None
    assert drivers[0].current_lap == 11
    assert drivers[0].last_lap_time == 75.421


def test_mqtt_row_replaces_bootstrap_row():
    # Regression: the REST bootstrap seeds rows without _key, then MQTT pushes
    # the same underlying rows *with* _key. Both must map to the same store key,
    # otherwise every car appears twice on the leaderboard and track map.
    state = LiveState()

    # Driver row: REST first, MQTT twin second — one entry, MQTT values win.
    state.update("v1/drivers", {"driver_number": 1, "team_name": "Old"})
    state.update(
        "v1/drivers", {"_key": "9999_1", "driver_number": 1, "team_name": "New"}
    )
    drivers = state.docs_for("v1/drivers")
    assert len(drivers) == 1
    assert drivers[0]["team_name"] == "New"

    # Pit row: same pit stop from both sources must not double the pit count.
    pit = {"driver_number": 1, "lap_number": 12, "pit_duration": 22.5}
    state.update("v1/pit", pit)
    state.update("v1/pit", {**pit, "_key": "9999_1_12"})
    assert len(state.docs_for("v1/pit")) == 1

    # Stint row: the MQTT update (lap_end filled in) must replace the seed.
    stint = {"driver_number": 1, "stint_number": 2, "lap_start": 10, "lap_end": None}
    state.update("v1/stints", stint)
    state.update("v1/stints", {**stint, "_key": "s2", "lap_end": 20})
    stints = state.docs_for("v1/stints")
    assert len(stints) == 1
    assert stints[0]["lap_end"] == 20


def test_position_stream_stays_bounded():
    # Position/intervals MQTT updates carry a unique _key per message; retention
    # must still collapse to one row per driver so the buffer cannot grow
    # unboundedly over a two-hour race.
    state = LiveState()
    for i in range(5):
        state.update(
            "v1/position",
            {"_key": f"pos:{i}", "driver_number": 1, "position": 5 - i},
        )
    rows = state.docs_for("v1/position")
    assert len(rows) == 1
    assert rows[0]["position"] == 1


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
