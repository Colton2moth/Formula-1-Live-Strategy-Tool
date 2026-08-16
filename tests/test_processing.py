"""Tests for live/replay stint handling in the shared feature pipeline."""

import pandas as pd

from formula1_strategy_tool.processing import add_stint_features, build_spine


def _spine() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "meeting_key": [1, 1, 1],
            "session_key": [9979, 9979, 9979],
            "driver_number": [4, 4, 4],
            "lap_number": [1, 2, 3],
            "date_start": ["2025-05-25T13:00:00+00:00"] * 3,
        }
    )


def _stints(lap_end) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "meeting_key": 1,
                "session_key": 9979,
                "driver_number": 4,
                "stint_number": 1,
                "lap_start": 1,
                "lap_end": lap_end,
                "compound": "MEDIUM",
                "tyre_age_at_start": 0,
            }
        ]
    )


def test_add_stint_features_keeps_open_stint():
    spine = build_spine(_spine(), 2025)
    out = add_stint_features(spine, _stints(None))
    # An open (lap_end=None) stint must cover all laps, not drop them.
    assert len(out) == 3
    assert (out["current_compound"] == "MEDIUM").all()
    assert list(out["tyre_age"]) == [0, 1, 2]
