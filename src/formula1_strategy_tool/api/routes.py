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
from formula1_strategy_tool.acquisition.replay import replay_controller
from formula1_strategy_tool.api.circuits import track_for_circuit
from formula1_strategy_tool.api.schemas import (
    DriverState,
    LiveStatus,
    LiveTopicStats,
    LocationState,
    PredictionState,
    RaceStateSnapshot,
    ReplaySeekRequest,
    ReplaySessionOption,
    ReplayStartRequest,
    ReplayStatus,
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
    try:
        live = drivers_from_live(LIVE_STATE)
    except Exception:  # noqa: BLE001 — partial buffer must not 500 the API
        live = None
    return live if live is not None else []


def _active_session() -> SessionState:
    """Live/bootstrap session; 503 when no session has been ingested yet."""
    try:
        live = session_from_live(LIVE_STATE)
    except Exception:  # noqa: BLE001 — treat partial buffer as "not ready"
        live = None
    if live is None:
        raise HTTPException(status_code=503, detail="No live session available")
    return live


def _live_circuit_key() -> int | None:
    """circuit_key of the ingested session, or None before data arrives."""
    sessions = LIVE_STATE.docs_for("v1/sessions")
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
        _prediction_cache = [PredictionState.model_validate(row) for row in raw]
    except Exception as exc:  # noqa: BLE001 — keep API up without a snapshot
        print(f"CSV predictions unavailable: {exc}")
        return []

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


@router.get("/locations", response_model=list[LocationState])
def get_locations() -> list[LocationState]:
    """
    Compact newest live location per driver (for high-frequency polling/stream).

    Keyed by driver_number; x/y are null for cars without useful telemetry.
    Memory is bounded to one entry per driver.
    """
    locations = LIVE_STATE.latest_locations()
    return [
        LocationState(**locations[number])
        for number in sorted(locations)
    ]


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


def _replay_status() -> ReplayStatus:
    """Map the replay controller snapshot into the response model."""
    return ReplayStatus(**replay_controller.snapshot())


@router.get("/replay/status", response_model=ReplayStatus)
def get_replay_status() -> ReplayStatus:
    """Current replay controller state (idle/running/finished/error)."""
    return _replay_status()


@router.get("/replay/sessions", response_model=list[ReplaySessionOption])
def get_replay_sessions() -> list[ReplaySessionOption]:
    """Completed Race sessions, for the year → country replay picker."""
    from formula1_strategy_tool.acquisition.cache_replays import replay_readiness
    from formula1_strategy_tool.acquisition.replay import list_replay_sessions

    try:
        sessions = list_replay_sessions()
    except Exception as exc:  # noqa: BLE001 — surface OpenF1 failures cleanly
        raise HTTPException(
            status_code=503, detail=f"Could not list sessions: {exc}"
        ) from exc
    return [
        ReplaySessionOption(**row, readiness=replay_readiness(row["session_key"]))
        for row in sessions
    ]


@router.post("/replay/start", response_model=ReplayStatus)
def start_replay(request: ReplayStartRequest) -> ReplayStatus:
    """
    Start replaying a completed session through LIVE_STATE.

    ``session_key`` defaults to REPLAY_SESSION_KEY, then INFERENCE_SESSION_KEY.
    Starting a replay stops the live MQTT listener so live pushes cannot mix.
    """
    session_key = request.session_key
    if session_key is None:
        env_key = os.getenv("REPLAY_SESSION_KEY") or os.getenv(
            "INFERENCE_SESSION_KEY"
        )
        if env_key:
            session_key = int(env_key)
        else:
            raise HTTPException(
                status_code=400, detail="session_key is required"
            )
    replay_controller.start(session_key, request.speed)
    return _replay_status()


@router.post("/replay/pause", response_model=ReplayStatus)
def pause_replay() -> ReplayStatus:
    """Suspend the running replay clock; resume from the same position."""
    replay_controller.pause()
    return _replay_status()


@router.post("/replay/seek", response_model=ReplayStatus)
def seek_replay(request: ReplaySeekRequest) -> ReplayStatus:
    """
    Jump the active replay to the nearest checkpoint at or before ``lap``.

    The producer restores that checkpoint's buffer state and applies only the
    events between the checkpoint cursor and the target, instead of replaying
    from lap 1.
    """
    replay_controller.seek(request.lap)
    return _replay_status()


@router.post("/replay/resume", response_model=ReplayStatus)
def resume_replay() -> ReplayStatus:
    """Continue a paused replay from where it left off."""
    replay_controller.resume()
    return _replay_status()


@router.post("/replay/stop", response_model=ReplayStatus)
def stop_replay() -> ReplayStatus:
    """Stop the running replay and restore the live MQTT listener."""
    replay_controller.stop()
    return _replay_status()
