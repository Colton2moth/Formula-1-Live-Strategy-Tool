"""Tests for live gap_to_leader state preservation in drivers_from_live."""

from formula1_strategy_tool.acquisition.live_drivers import (
    _normalize_gap,
    drivers_from_live,
)
from formula1_strategy_tool.acquisition.live_state import LiveState


def _seed_driver(state: LiveState, number: int = 1) -> None:
    state.update(
        "v1/drivers",
        {
            "driver_number": number,
            "full_name": f"Driver {number}",
            "name_acronym": f"D{number}",
            "team_name": "Team",
            "team_colour": "FF8000",
        },
    )


def _seed_lap(
    state: LiveState,
    number: int = 1,
    lap_number: int = 10,
    date_start: str = "2026-07-26T13:00:00+00:00",
) -> None:
    state.update(
        "v1/laps",
        {
            "driver_number": number,
            "lap_number": lap_number,
            "lap_duration": 90.0,
            "date_start": date_start,
        },
    )


def _seed_interval(
    state: LiveState,
    number: int = 1,
    gap: object = None,
    date: str = "2026-07-26T13:00:05+00:00",
) -> None:
    state.update(
        "v1/intervals",
        {"driver_number": number, "gap_to_leader": gap, "interval": None, "date": date},
    )


def _gap(state: LiveState) -> float | str | None:
    drivers = drivers_from_live(state)
    assert drivers is not None
    return drivers[0].gap_to_leader


def test_gap_numeric_preserved():
    state = LiveState()
    _seed_driver(state)
    _seed_lap(state)
    _seed_interval(state, gap=3.216)

    assert _gap(state) == 3.216


def test_gap_leader_is_null():
    state = LiveState()
    _seed_driver(state)
    _seed_lap(state)
    _seed_interval(state, gap=None)

    assert _gap(state) is None


def test_gap_lapped_one_lap():
    state = LiveState()
    _seed_driver(state)
    _seed_lap(state)
    _seed_interval(state, gap="+1 LAP")

    assert _gap(state) == "+1 LAP"


def test_gap_lapped_two_laps():
    state = LiveState()
    _seed_driver(state)
    _seed_lap(state)
    _seed_interval(state, gap="+2 LAPS")

    assert _gap(state) == "+2 LAPS"


def test_gap_missing_interval_row_is_unknown():
    state = LiveState()
    _seed_driver(state)
    _seed_lap(state)

    assert _gap(state) == "UNKNOWN"


def test_gap_malformed_string_is_unknown():
    state = LiveState()
    _seed_driver(state)
    _seed_lap(state)
    _seed_interval(state, gap="gibberish")

    assert _gap(state) == "UNKNOWN"


def test_gap_stale_interval_is_unknown():
    state = LiveState()
    _seed_driver(state)
    _seed_lap(state, date_start="2026-07-26T13:00:00+00:00")
    # Interval predates the current lap start, so it is stale.
    _seed_interval(state, gap=3.216, date="2026-07-26T12:59:00+00:00")

    assert _gap(state) == "UNKNOWN"


def test_gap_zero_is_preserved_not_unknown():
    state = LiveState()
    _seed_driver(state)
    _seed_lap(state)
    _seed_interval(state, gap=0.0)

    assert _gap(state) == 0.0


def test_normalize_gap_lap_string_variants():
    assert _normalize_gap("+1 LAP") == "+1 LAP"
    assert _normalize_gap("+2 LAPS") == "+2 LAPS"
    assert _normalize_gap("+3 laps") == "+3 LAPS"
    assert _normalize_gap("+1  lap") == "+1 LAP"
    assert _normalize_gap("3.5") == 3.5
    assert _normalize_gap(7) == 7.0
    assert _normalize_gap(None) is None
    assert _normalize_gap("") == "UNKNOWN"
    assert _normalize_gap("LAP") == "UNKNOWN"
