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


class CompoundProbabilities(BaseModel):
    """Multiclass probabilities from the next-compound XGBoost model."""

    SOFT: float = Field(ge=0.0, le=1.0)
    MEDIUM: float = Field(ge=0.0, le=1.0)
    HARD: float = Field(ge=0.0, le=1.0)
    INTERMEDIATE: float = Field(ge=0.0, le=1.0)
    WET: float = Field(ge=0.0, le=1.0)


class PredictionState(BaseModel):
    """
    Combined two-model output for one driver.

    pit_probability comes from the pit-window classifier (N = pit_window_laps).
    Compound fields may be null when probability is below the display threshold;
    mocks may still include them for frontend experimentation.
    """

    driver_number: int
    lap_number: int
    pit_window_laps: int = 3
    pit_probability: float = Field(ge=0.0, le=1.0)
    predicted_next_compound: str | None
    compound_probabilities: CompoundProbabilities | None
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
    path: list[TrackPoint]
