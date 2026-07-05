"""
REST route handlers — currently backed by mock data only.

Each handler returns contract-shaped JSON from api/mocks.py. Later we swap the
data source to live RaceState + model output without changing these paths.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from formula1_strategy_tool.api.mocks import (
    MOCK_DRIVERS,
    MOCK_DRIVERS_BY_NUMBER,
    MOCK_PREDICTIONS,
    MOCK_PREDICTIONS_BY_NUMBER,
    MOCK_RACE_STATE,
    MOCK_SESSION,
    MOCK_TRACK,
)
from formula1_strategy_tool.api.schemas import (
    DriverState,
    PredictionState,
    RaceStateSnapshot,
    SessionState,
    TrackState,
)

# All contract REST paths live under /api (see docs/API_CONTRACT.md).
router = APIRouter(prefix="/api", tags=["mock-api"])


@router.get("/session", response_model=SessionState)
def get_session() -> SessionState:
    """Current session summary — weather, lap count, race-control status."""
    return MOCK_SESSION


@router.get("/drivers", response_model=list[DriverState])
def get_drivers() -> list[DriverState]:
    """All drivers' timing, tyre, and gap state."""
    return MOCK_DRIVERS


@router.get("/drivers/{driver_number}", response_model=DriverState)
def get_driver(driver_number: int) -> DriverState:
    """One driver by car number; 404 if not in the mock grid."""
    driver = MOCK_DRIVERS_BY_NUMBER.get(driver_number)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@router.get("/predictions", response_model=list[PredictionState])
def get_predictions() -> list[PredictionState]:
    """Latest strategy prediction for every driver."""
    return MOCK_PREDICTIONS


@router.get(
    "/drivers/{driver_number}/prediction",
    response_model=PredictionState,
)
def get_driver_prediction(driver_number: int) -> PredictionState:
    """One driver's prediction; 404 if driver or prediction missing."""
    prediction = MOCK_PREDICTIONS_BY_NUMBER.get(driver_number)
    if prediction is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return prediction


@router.get("/race-state", response_model=RaceStateSnapshot)
def get_race_state() -> RaceStateSnapshot:
    """
    Full bootstrap snapshot for initial page load.

    Same data as /session + /drivers + /predictions in one response.
    """
    return MOCK_RACE_STATE


@router.get("/track", response_model=TrackState)
def get_track() -> TrackState:
    """Circuit name and normalized path points for the track map."""
    return MOCK_TRACK
