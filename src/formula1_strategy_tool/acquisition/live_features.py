"""
Build a driver-lap feature table from LIVE_STATE (same logic as training).

Input:  LiveState filled by REST bootstrap and/or MQTT
Output: pandas DataFrame of feature rows (plus driver_number / lap_number)

Reuses processing.add_* helpers so live inference does not drift from the
historical training pipeline. Labels are skipped — models only need features.
"""

from __future__ import annotations

import pandas as pd

from formula1_strategy_tool.acquisition.live_state import LiveState
from formula1_strategy_tool.processing import (
    add_compound_history_features,
    add_current_position,
    add_interval_features,
    add_pace_features,
    add_pit_features,
    add_race_control_features,
    add_stint_features,
    add_weather_features,
    build_spine,
)


def _topic_frame(state: LiveState, topic: str) -> pd.DataFrame:
    """Convert one MQTT/REST topic bucket into a DataFrame."""
    rows = list(state.docs.get(topic, {}).values())
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def features_from_live(state: LiveState) -> pd.DataFrame | None:
    """
    Run the shared feature pipeline on the live buffer.

    Returns:
        Full driver-lap feature frame, or None if laps are missing.
    """
    laps = _topic_frame(state, "v1/laps")
    if laps.empty:
        return None

    stints = _topic_frame(state, "v1/stints")
    pits = _topic_frame(state, "v1/pit")
    positions = _topic_frame(state, "v1/position")
    intervals = _topic_frame(state, "v1/intervals")
    weather = _topic_frame(state, "v1/weather")
    race_control = _topic_frame(state, "v1/race_control")

    # Season from session doc when present; else from lap date_start year.
    sessions = _topic_frame(state, "v1/sessions")
    if not sessions.empty and sessions.iloc[0].get("year") is not None:
        season = int(sessions.iloc[0]["year"])
    else:
        season = int(str(laps.iloc[0].get("date_start", "2026"))[:4])

    # Same sequence as process_race, without future-looking labels.
    table = build_spine(laps, season)
    if not stints.empty:
        table = add_stint_features(table, stints)
    if not pits.empty:
        table = add_pit_features(table, pits)
    if not positions.empty:
        table = add_current_position(table, positions, laps)
    if not intervals.empty and "as_of" in table.columns:
        table = add_interval_features(table, intervals)
    if not weather.empty and "as_of" in table.columns:
        table = add_weather_features(table, weather)
    if not race_control.empty and "as_of" in table.columns:
        table = add_race_control_features(table, race_control)
    if not stints.empty:
        table = add_compound_history_features(table, stints)
    table = add_pace_features(table, laps)
    return table


def latest_lap_rows(features: pd.DataFrame) -> pd.DataFrame:
    """Keep only the newest lap_number per driver (the live 'now' snapshot)."""
    idx = features.groupby("driver_number")["lap_number"].idxmax()
    return features.loc[idx].reset_index(drop=True)
