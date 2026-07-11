"""
Hardcoded mock data for REST endpoints.

All values are fictional but contract-compliant. The frontend can build against
these responses until live OpenF1 ingestion and model inference replace them.

Scenario: lap 25 of 70 at the Canadian Grand Prix, eight drivers on screen.
"""

from __future__ import annotations

from formula1_strategy_tool.api.schemas import (
    DriverState,
    PredictionState,
    RaceStateSnapshot,
    SessionState,
    TrackPoint,
    TrackState,
)

# --- Session (GET /api/session) ---

MOCK_SESSION = SessionState(
    meeting_name="Canadian Grand Prix",
    session_name="Race",
    session_status="active",
    current_lap=25,
    total_laps=70,
    track_temperature=34.2,
    air_temperature=21.5,
    rainfall=False,
    race_control_status="GREEN",
)

# --- Drivers (GET /api/drivers, GET /api/drivers/{driver_number}) ---

MOCK_DRIVERS: list[DriverState] = [
    DriverState(
        driver_number=1,
        name="Max Verstappen",
        acronym="VER",
        team_name="Red Bull Racing",
        team_colour="3671C6",
        position=1,
        track_progress=0.08,
        current_lap=25,
        compound="HARD",
        tyre_age=18,
        last_lap_time=74.892,
        gap_to_leader=0.0,
        interval_ahead=None,
        interval_behind=3.8,
        pit_stops=1,
    ),
    DriverState(
        driver_number=4,
        name="Lando Norris",
        acronym="NOR",
        team_name="McLaren",
        team_colour="FF8000",
        position=2,
        track_progress=0.31,
        current_lap=25,
        compound="MEDIUM",
        tyre_age=14,
        last_lap_time=75.421,
        gap_to_leader=3.8,
        interval_ahead=3.8,
        interval_behind=1.2,
        pit_stops=1,
    ),
    DriverState(
        driver_number=16,
        name="Charles Leclerc",
        acronym="LEC",
        team_name="Ferrari",
        team_colour="E80020",
        position=3,
        track_progress=0.57,
        current_lap=25,
        compound="MEDIUM",
        tyre_age=12,
        last_lap_time=75.512,
        gap_to_leader=5.0,
        interval_ahead=1.2,
        interval_behind=4.5,
        pit_stops=1,
    ),
    DriverState(
        driver_number=44,
        name="Lewis Hamilton",
        acronym="HAM",
        team_name="Mercedes",
        team_colour="27F4D2",
        position=4,
        track_progress=0.80,
        current_lap=25,
        compound="SOFT",
        tyre_age=8,
        last_lap_time=75.698,
        gap_to_leader=9.5,
        interval_ahead=4.5,
        interval_behind=2.1,
        pit_stops=2,
    ),
    DriverState(
        driver_number=81,
        name="Oscar Piastri",
        acronym="PIA",
        team_name="McLaren",
        team_colour="FF8000",
        position=5,
        track_progress=0.94,
        current_lap=25,
        compound="MEDIUM",
        tyre_age=11,
        last_lap_time=75.734,
        gap_to_leader=11.6,
        interval_ahead=2.1,
        interval_behind=3.7,
        pit_stops=1,
    ),
    DriverState(
        driver_number=63,
        name="George Russell",
        acronym="RUS",
        team_name="Mercedes",
        team_colour="27F4D2",
        position=6,
        track_progress=0.18,
        current_lap=25,
        compound="HARD",
        tyre_age=20,
        last_lap_time=75.811,
        gap_to_leader=15.3,
        interval_ahead=3.7,
        interval_behind=2.4,
        pit_stops=1,
    ),
    DriverState(
        driver_number=14,
        name="Fernando Alonso",
        acronym="ALO",
        team_name="Aston Martin",
        team_colour="229971",
        position=7,
        track_progress=0.43,
        current_lap=25,
        compound="HARD",
        tyre_age=21,
        last_lap_time=75.946,
        gap_to_leader=17.7,
        interval_ahead=2.4,
        interval_behind=3.1,
        pit_stops=1,
    ),
    DriverState(
        driver_number=10,
        name="Pierre Gasly",
        acronym="GAS",
        team_name="Alpine",
        team_colour="00A1E8",
        position=8,
        track_progress=0.69,
        current_lap=25,
        compound="MEDIUM",
        tyre_age=13,
        last_lap_time=76.102,
        gap_to_leader=20.8,
        interval_ahead=3.1,
        interval_behind=None,
        pit_stops=1,
    ),
]

# Index by driver_number for single-driver lookups and 404 checks.
MOCK_DRIVERS_BY_NUMBER: dict[int, DriverState] = {
    d.driver_number: d for d in MOCK_DRIVERS
}

# --- Predictions (GET /api/predictions, GET /api/drivers/{n}/prediction) ---

MOCK_PREDICTIONS: list[PredictionState] = [
    PredictionState(
        driver_number=1,
        pit_within_5_laps=0.15,
        predicted_pit_window_start=42,
        predicted_pit_window_end=48,
        predicted_next_compound="MEDIUM",
        updated_at="2026-06-14T18:34:10Z",
    ),
    PredictionState(
        driver_number=4,
        pit_within_5_laps=0.72,
        predicted_pit_window_start=28,
        predicted_pit_window_end=31,
        predicted_next_compound="HARD",
        updated_at="2026-06-14T18:34:10Z",
    ),
    PredictionState(
        driver_number=16,
        pit_within_5_laps=0.58,
        predicted_pit_window_start=30,
        predicted_pit_window_end=34,
        predicted_next_compound="HARD",
        updated_at="2026-06-14T18:34:10Z",
    ),
    PredictionState(
        driver_number=44,
        pit_within_5_laps=0.91,
        predicted_pit_window_start=26,
        predicted_pit_window_end=28,
        predicted_next_compound="MEDIUM",
        updated_at="2026-06-14T18:34:10Z",
    ),
    PredictionState(
        driver_number=81,
        pit_within_5_laps=0.46,
        predicted_pit_window_start=31,
        predicted_pit_window_end=35,
        predicted_next_compound="HARD",
        updated_at="2026-06-14T18:34:10Z",
    ),
    PredictionState(
        driver_number=63,
        pit_within_5_laps=0.12,
        predicted_pit_window_start=43,
        predicted_pit_window_end=49,
        predicted_next_compound="MEDIUM",
        updated_at="2026-06-14T18:34:10Z",
    ),
    PredictionState(
        driver_number=14,
        pit_within_5_laps=0.09,
        predicted_pit_window_start=44,
        predicted_pit_window_end=50,
        predicted_next_compound="MEDIUM",
        updated_at="2026-06-14T18:34:10Z",
    ),
    PredictionState(
        driver_number=10,
        pit_within_5_laps=0.63,
        predicted_pit_window_start=29,
        predicted_pit_window_end=33,
        predicted_next_compound="HARD",
        updated_at="2026-06-14T18:34:10Z",
    ),
]

MOCK_PREDICTIONS_BY_NUMBER: dict[int, PredictionState] = {
    p.driver_number: p for p in MOCK_PREDICTIONS
}

# --- Bootstrap snapshot (GET /api/race-state) ---

MOCK_RACE_STATE = RaceStateSnapshot(
    session=MOCK_SESSION,
    drivers=MOCK_DRIVERS,
    predictions=MOCK_PREDICTIONS,
)

# --- Track map (GET /api/track) ---
# Normalized 0–1 coordinates forming a simple closed loop (not real GIS data).

MOCK_TRACK = TrackState(
    circuit_name="Demo Switchback Circuit",
    circuit_key=901,
    start_finish=TrackPoint(x=0.60, y=0.88),
    path=[
        TrackPoint(x=0.60, y=0.88),
        TrackPoint(x=0.87, y=0.88),
        TrackPoint(x=0.94, y=0.82),
        TrackPoint(x=0.86, y=0.58),
        TrackPoint(x=0.76, y=0.32),
        TrackPoint(x=0.67, y=0.12),
        TrackPoint(x=0.60, y=0.13),
        TrackPoint(x=0.53, y=0.31),
        TrackPoint(x=0.51, y=0.43),
        TrackPoint(x=0.63, y=0.52),
        TrackPoint(x=0.70, y=0.67),
        TrackPoint(x=0.28, y=0.67),
        TrackPoint(x=0.20, y=0.65),
        TrackPoint(x=0.25, y=0.56),
        TrackPoint(x=0.48, y=0.59),
        TrackPoint(x=0.39, y=0.49),
        TrackPoint(x=0.33, y=0.40),
        TrackPoint(x=0.39, y=0.26),
        TrackPoint(x=0.31, y=0.20),
        TrackPoint(x=0.18, y=0.04),
        TrackPoint(x=0.14, y=0.07),
        TrackPoint(x=0.11, y=0.62),
        TrackPoint(x=0.14, y=0.78),
        TrackPoint(x=0.09, y=0.88),
        TrackPoint(x=0.60, y=0.88),
    ]
)
