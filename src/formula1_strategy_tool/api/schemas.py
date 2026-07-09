"""
Pydantic response models for the REST API.

These shapes match docs/API_CONTRACT.md exactly. FastAPI uses them to:
    - Validate outgoing JSON field names and types
    - Generate OpenAPI docs at /docs for the frontend developer

Replace the mock data sources later; keep these schemas stable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SessionState(BaseModel):
    """Race-level context returned by GET /api/session."""

    meeting_name: str
    session_name: str
    session_status: str
    current_lap: int
    total_laps: int
    track_temperature: float
    air_temperature: float
    rainfall: bool
    race_control_status: str


class DriverState(BaseModel):
    """One driver's live timing and tyre snapshot."""

    driver_number: int
    name: str
    acronym: str
    team_name: str
    team_colour: str  # hex without '#', e.g. "FF8000"
    position: int
    current_lap: int
    compound: str
    tyre_age: int
    last_lap_time: float
    gap_to_leader: float
    interval_ahead: float | None  # null when leading or no car ahead
    interval_behind: float | None
    pit_stops: int


class PredictionState(BaseModel):
    """Model output for one driver (pit-within-5-laps baseline + window)."""

    driver_number: int
    pit_within_5_laps: float = Field(ge=0.0, le=1.0)
    predicted_pit_window_start: int
    predicted_pit_window_end: int
    predicted_next_compound: str
    updated_at: str  # ISO-8601 UTC, e.g. "2026-06-14T18:34:10Z"


class RaceStateSnapshot(BaseModel):
    """Combined bootstrap payload for GET /api/race-state."""

    session: SessionState
    drivers: list[DriverState]
    predictions: list[PredictionState]


class TrackPoint(BaseModel):
    """One normalized coordinate on the circuit outline (0.0–1.0)."""

    x: float
    y: float


class TrackState(BaseModel):
    """Circuit metadata and drawable path for the track map."""

    circuit_name: str
    circuit_key: int
    start_finish: TrackPoint
    path: list[TrackPoint]
