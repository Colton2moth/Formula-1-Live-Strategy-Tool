"""Tests for the replay harness timeline builder and location thinning."""

from formula1_strategy_tool.acquisition.replay import (
    _thin_location,
    build_timeline,
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


def test_stint_drops_future_lap_end():
    events = build_timeline(_data())
    stint_payloads = [payload for _, topic, payload in events if topic == "v1/stints"]
    assert len(stint_payloads) == 1
    assert "lap_end" not in stint_payloads[0]
    assert stint_payloads[0]["compound"] == "MEDIUM"


def test_stint_scheduled_at_start_lap():
    events = build_timeline(_data())
    stint_events = [offset for offset, topic, _ in events if topic == "v1/stints"]
    # Stint 1 starts at lap 1 → race clock offset 0.
    assert stint_events == [0.0]


def test_thin_location_keeps_one_per_driver_per_second():
    rows = [
        {"driver_number": 4, "date": "2026-07-26T13:00:00+00:00"},
        {"driver_number": 4, "date": "2026-07-26T13:00:00.400+00:00"},
        {"driver_number": 4, "date": "2026-07-26T13:00:01+00:00"},
        {"driver_number": 44, "date": "2026-07-26T13:00:00+00:00"},
    ]
    kept = _thin_location(rows)
    assert len(kept) == 3
    assert [row["date"] for row in kept] == [
        "2026-07-26T13:00:00+00:00",
        "2026-07-26T13:00:01+00:00",
        "2026-07-26T13:00:00+00:00",
    ]
