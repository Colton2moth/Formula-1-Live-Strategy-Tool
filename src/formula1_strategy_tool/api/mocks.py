"""
Hardcoded mock data for REST endpoints.

All values are fictional but contract-compliant. The frontend can build against
these responses until live OpenF1 ingestion and model inference replace them.

Scenario: lap 25 of 70 at the Canadian Grand Prix, three drivers on screen.
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
        current_lap=25,
        compound="SOFT",
        tyre_age=8,
        last_lap_time=75.698,
        gap_to_leader=9.5,
        interval_ahead=4.5,
        interval_behind=None,
        pit_stops=2,
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
    circuit_name="Circuit Gilles Villeneuve",
    circuit_key=23,
    path=[
        TrackPoint(x=0.12, y=0.73),
        TrackPoint(x=0.18, y=0.68),
        TrackPoint(x=0.28, y=0.62),
        TrackPoint(x=0.42, y=0.55),
        TrackPoint(x=0.58, y=0.52),
        TrackPoint(x=0.72, y=0.48),
        TrackPoint(x=0.85, y=0.42),
        TrackPoint(x=0.92, y=0.35),
        TrackPoint(x=0.88, y=0.28),
        TrackPoint(x=0.75, y=0.22),
        TrackPoint(x=0.58, y=0.18),
        TrackPoint(x=0.40, y=0.20),
        TrackPoint(x=0.25, y=0.28),
        TrackPoint(x=0.15, y=0.38),
        TrackPoint(x=0.10, y=0.52),
        TrackPoint(x=0.12, y=0.73),
    ],
)
