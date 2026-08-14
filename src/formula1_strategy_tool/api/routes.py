"""
REST route handlers for the strategy API contract.

Session and drivers are served from the live OpenF1 buffer. The track map is
resolved from a static circuit library keyed by the live session's
circuit_key. Predictions are scored from the trained models against a
historical CSV snapshot (see inference.py).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

from formula1_strategy_tool.acquisition.live_drivers import drivers_from_live
from formula1_strategy_tool.acquisition.live_features import (
    features_from_live,
    latest_lap_rows,
)
from formula1_strategy_tool.acquisition.live_session import session_from_live
from formula1_strategy_tool.acquisition.live_state import LIVE_STATE
from formula1_strategy_tool.api.circuits import track_for_circuit
from formula1_strategy_tool.api.schemas import (
    DriverState,
    LiveStatus,
    LiveTopicStats,
    PredictionState,
    RaceStateSnapshot,
    SessionState,
    TrackState,
)
from formula1_strategy_tool.inference import predict_feature_rows, predict_snapshot

# Load .env from the project root when the API process starts.
load_dotenv()

# All contract REST paths live under /api (see docs/API_CONTRACT.md).
router = APIRouter(prefix="/api", tags=["strategy-api"])

# CSV fallback cache; live predictions are recomputed from LIVE_STATE.
_prediction_cache: list[PredictionState] | None = None


def _active_drivers() -> list[DriverState]:
    """Live MQTT-derived drivers; empty list when no live data yet."""
    live = drivers_from_live(LIVE_STATE)
    return live if live is not None else []


def _active_session() -> SessionState:
    """Live/bootstrap session; 503 when no session has been ingested yet."""
    live = session_from_live(LIVE_STATE)
    if live is None:
        raise HTTPException(status_code=503, detail="No live session available")
    return live


def _live_circuit_key() -> int | None:
    """circuit_key of the ingested session, or None before data arrives."""
    sessions = list(LIVE_STATE.docs.get("v1/sessions", {}).values())
    if not sessions:
        return None
    key = sessions[0].get("circuit_key")
    return int(key) if key is not None else None


def _drivers_by_number() -> dict[int, DriverState]:
    """Index current driver list by car number for single-driver routes."""
    return {d.driver_number: d for d in _active_drivers()}


def _csv_predictions() -> list[PredictionState]:
    """Cached predictions from the configured historical CSV snapshot."""
    global _prediction_cache
    if _prediction_cache is not None:
        return _prediction_cache

    csv_path = Path(os.getenv("INFERENCE_CSV", "data/processed/driver_laps_all.csv"))
    model_dir = Path(os.getenv("INFERENCE_MODEL_DIR", "data/models"))
    session_key = int(os.getenv("INFERENCE_SESSION_KEY", "9979"))
    lap_number = int(os.getenv("INFERENCE_LAP", "20"))

    if not csv_path.exists():
        return []

    try:
        raw = predict_snapshot(csv_path, model_dir, session_key, lap_number)
    except Exception as exc:  # noqa: BLE001 — keep API up without a snapshot
        print(f"CSV predictions unavailable: {exc}")
        return []

    _prediction_cache = [PredictionState.model_validate(row) for row in raw]
    return _prediction_cache


def _model_predictions() -> list[PredictionState]:
    """
    Prefer live-buffer features + models; fall back to CSV snapshot.

    Live path rebuilds features from LIVE_STATE on each call (buffer is small
    enough for now). CSV path stays cached.
    """
    model_dir = Path(os.getenv("INFERENCE_MODEL_DIR", "data/models"))
    try:
        feat = features_from_live(LIVE_STATE)
        if feat is not None and not feat.empty:
            latest = latest_lap_rows(feat)
            raw = predict_feature_rows(latest, model_dir)
            if raw:
                return [PredictionState.model_validate(row) for row in raw]
    except Exception as exc:  # noqa: BLE001 — keep API up; log and fall back
        print(f"live predictions failed, using CSV fallback: {exc}")

    return _csv_predictions()


@router.get("/session", response_model=SessionState)
def get_session() -> SessionState:
    """Current session summary — weather, lap count, race-control status."""
    return _active_session()


@router.get("/drivers", response_model=list[DriverState])
def get_drivers() -> list[DriverState]:
    """All drivers' timing, tyre, and gap state from the live buffer."""
    return _active_drivers()


@router.get("/drivers/{driver_number}", response_model=DriverState)
def get_driver(driver_number: int) -> DriverState:
    """One driver by car number; 404 if not in the current grid."""
    driver = _drivers_by_number().get(driver_number)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@router.get("/predictions", response_model=list[PredictionState])
def get_predictions() -> list[PredictionState]:
    """Latest strategy prediction for every driver (trained models on CSV)."""
    return _model_predictions()


@router.get(
    "/drivers/{driver_number}/prediction",
    response_model=PredictionState,
)
def get_driver_prediction(driver_number: int) -> PredictionState:
    """One driver's model prediction; 404 if that car is not in the snapshot."""
    for prediction in _model_predictions():
        if prediction.driver_number == driver_number:
            return prediction
    raise HTTPException(status_code=404, detail="Driver not found")


@router.get("/race-state", response_model=RaceStateSnapshot)
def get_race_state() -> RaceStateSnapshot:
    """
    Full bootstrap snapshot for initial page load.

    Session and drivers come from the live buffer; predictions from the models.
    """
    return RaceStateSnapshot(
        session=_active_session(),
        drivers=_active_drivers(),
        predictions=_model_predictions(),
    )


@router.get("/track", response_model=TrackState)
def get_track() -> TrackState:
    """Static circuit path for the live session's circuit_key."""
    circuit_key = _live_circuit_key()
    if circuit_key is None:
        raise HTTPException(status_code=503, detail="No live session available")
    track = track_for_circuit(circuit_key)
    if track is None:
        raise HTTPException(
            status_code=404, detail=f"No circuit map for circuit_key {circuit_key}"
        )
    return track


@router.get("/live-status", response_model=LiveStatus)
def get_live_status() -> LiveStatus:
    """
    In-memory MQTT buffer summary (not full race-state yet).

    Use this to confirm the live listener is receiving OpenF1 pushes.
    """
    # mqtt_enabled mirrors main.py lifespan (env LIVE_MQTT, default on).
    mqtt_flag = os.getenv("LIVE_MQTT", "1").strip().lower()
    mqtt_enabled = mqtt_flag not in {"0", "false", "no", "off"}
    raw = LIVE_STATE.summary()
    topics = {
        name: LiveTopicStats(
            messages=stats["messages"], unique_keys=stats["unique_keys"]
        )
        for name, stats in raw.items()
    }
    return LiveStatus(mqtt_enabled=mqtt_enabled, topics=topics)
