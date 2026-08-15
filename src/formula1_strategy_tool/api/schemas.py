"""
Pydantic response models for the REST API.

These shapes match docs/API_CONTRACT.md exactly. FastAPI uses them to:
    - Validate outgoing JSON field names and types
    - Generate OpenAPI docs at /docs for the frontend developer
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
    # Raw OpenF1/FastF1 track coordinate (same space as the circuit path).
    # Null when the car has no live telemetry (garage / no position sample).
    x: float | None = None
    y: float | None = None
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
    Combined model output for one driver.

    Three binary pit-window probabilities (same features, different horizons)
    plus next-compound multiclass output. Compound fields may be null when
    pit risk is low.
    """

    driver_number: int
    lap_number: int
    # Probabilities from pit_within_{3,5,7}_laps models (typically non-decreasing).
    pit_within_3_laps: float = Field(ge=0.0, le=1.0)
    pit_within_5_laps: float = Field(ge=0.0, le=1.0)
    pit_within_7_laps: float = Field(ge=0.0, le=1.0)
    # FE currently requires a string (calls .trim()); never send null.
    predicted_next_compound: str = "UNKNOWN"
    compound_probabilities: CompoundProbabilities | None = None
    # Placeholder window for FE strategy panel until a dedicated window model exists.
    predicted_pit_window_start: int = 0
    predicted_pit_window_end: int = 0
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
    # FE map draws a start/finish marker; default to first path point if omitted.
    start_finish: TrackPoint
    path: list[TrackPoint]


class LiveTopicStats(BaseModel):
    """Per-topic counters from the in-memory MQTT buffer."""

    messages: int
    unique_keys: int


class LiveStatus(BaseModel):
    """
    Lightweight view of LIVE_STATE for GET /api/live-status.

    Empty topics mean no push traffic yet (normal between sessions).
    """

    mqtt_enabled: bool
    topics: dict[str, LiveTopicStats]
