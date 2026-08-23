"""
REST route handlers for the strategy API contract.

Session and drivers are served from the live OpenF1 buffer. Live predictions
are scored from the trained models against the current live session's features
only — never silently from a historical CSV snapshot (see inference.py).
Circuit-map endpoints are temporarily unavailable while track geometry is
rebuilt from cached OpenF1 location data.
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
from formula1_strategy_tool.acquisition.live_session import (
    latest_session_doc,
    session_from_live,
)
from formula1_strategy_tool.acquisition.live_state import LIVE_STATE, LiveState
from formula1_strategy_tool.acquisition.replay_registry import ReplayRuntime, registry
from formula1_strategy_tool.api.schemas import (
    DisplayPitLane,
    DriverState,
    LiveStatus,
    LiveTopicStats,
    LocationState,
    PredictionState,
    RaceStateSnapshot,
    ReplayCreated,
    ReplayCreateRequest,
    ReplaySeekRequest,
    ReplaySessionOption,
    ReplaySpeedRequest,
    ReplayStatus,
    SessionState,
    StartFinishState,
    TrackPoint,
    TrackState,
)
from formula1_strategy_tool.inference import predict_feature_rows, predict_snapshot
from formula1_strategy_tool.track.models import CircuitLayout, layouts_dir, load_layout

# Load .env from the project root when the API process starts.
load_dotenv()

# All contract REST paths live under /api (see docs/api/CONTRACT.md).
router = APIRouter(prefix="/api", tags=["strategy-api"])

# CSV fallback cache; used only by the opt-in dev fallback (off by default).
_prediction_cache: list[PredictionState] | None = None


def _drivers(state: LiveState) -> list[DriverState]:
    """DriverState rows from a state; empty list when no data yet."""
    try:
        rows = drivers_from_live(state)
    except Exception:  # noqa: BLE001 — partial buffer must not 500 the API
        rows = None
    return rows if rows is not None else []


def _session(state: LiveState) -> SessionState:
    """SessionState from a state; 503 when no session has been ingested yet."""
    try:
        live = session_from_live(state)
    except Exception:  # noqa: BLE001 — treat partial buffer as "not ready"
        live = None
    if live is None:
        raise HTTPException(status_code=503, detail="No live session available")
    return live


def _circuit_key(state: LiveState) -> int | None:
    """circuit_key of the ingested session, or None before data arrives."""
    session = latest_session_doc(state)
    if session is None:
        return None
    key = session.get("circuit_key")
    return int(key) if key is not None else None


def _active_drivers() -> list[DriverState]:
    """Live MQTT-derived drivers; empty list when no live data yet."""
    return _drivers(LIVE_STATE)


def _active_session() -> SessionState:
    """Live/bootstrap session; 503 when no session has been ingested yet."""
    return _session(LIVE_STATE)


def _live_circuit_key() -> int | None:
    """circuit_key of the ingested live session, or None before data arrives."""
    return _circuit_key(LIVE_STATE)


def _drivers_by_number() -> dict[int, DriverState]:
    """Index current driver list by car number for single-driver routes."""
    return {d.driver_number: d for d in _active_drivers()}


def _csv_predictions() -> list[PredictionState]:
    """
    Predictions from the configured historical CSV snapshot.

    Not used by the normal live path: a live prediction must come from the
    current live session. This is consulted only when the opt-in
    ``INFERENCE_CSV_FALLBACK`` dev flag is enabled (see ``_csv_fallback_enabled``).
    """
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


def _predictions_from_state(state: LiveState) -> list[PredictionState] | None:
    """
    Score the latest lap features from ``state``; None when unusable.

    Shared scoring path for live and replay: both build features from a
    supplied LiveState so replay never reads live data.
    """
    model_dir = Path(os.getenv("INFERENCE_MODEL_DIR", "data/models"))
    try:
        feat = features_from_live(state)
        if feat is not None and not feat.empty:
            latest = latest_lap_rows(feat)
            raw = predict_feature_rows(latest, model_dir)
            if raw:
                return [PredictionState.model_validate(row) for row in raw]
    except Exception as exc:  # noqa: BLE001 — keep API up; caller decides fallback
        print(f"predictions from state failed: {exc}")
    return None


def _csv_fallback_enabled() -> bool:
    """True only when the explicit dev fallback flag is set (default OFF)."""
    flag = os.getenv("INFERENCE_CSV_FALLBACK", "0").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _model_predictions() -> list[PredictionState]:
    """
    Live predictions for the current live session.

    A prediction shown as live must come from the current live session. When
    live feature generation/inference cannot produce one, return no prediction
    (the frontend then shows its unavailable state) rather than silently
    substituting a historical CSV snapshot. The CSV path is only consulted when
    ``INFERENCE_CSV_FALLBACK`` is explicitly enabled for development.
    """
    from_state = _predictions_from_state(LIVE_STATE)
    if from_state:
        return from_state
    if _csv_fallback_enabled():
        return _csv_predictions()
    return []


def replay_predictions(state: LiveState) -> list[PredictionState]:
    """
    Score the latest lap features from a replay runtime's state.

    Deliberately no CSV fallback (that snapshot is unrelated to the replay
    session) and no live-feature read.
    """
    return _predictions_from_state(state) or []


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
    """Latest live strategy prediction for every driver; empty when unavailable."""
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

    Session and drivers come from the live buffer; predictions from the live
    session's features (empty when live inference is unavailable).
    """
    return RaceStateSnapshot(
        session=_active_session(),
        drivers=_active_drivers(),
        predictions=_model_predictions(),
    )


def _display_track(layout: CircuitLayout) -> TrackState:
    """Map a CircuitLayout to the display-ready TrackState contract."""
    pit_lane = None
    if layout.pit_lane is not None and layout.pit_lane.display:
        pit_lane = DisplayPitLane(
            path=[TrackPoint(x=p.x, y=p.y) for p in layout.pit_lane.display],
            entry_progress=layout.pit_lane.entry_progress,
            exit_progress=layout.pit_lane.exit_progress,
        )
    start = layout.start_finish.display
    return TrackState(
        circuit_name=layout.name,
        circuit_key=layout.circuit_key,
        rotation=layout.rotation,
        country_name=layout.country,
        display_path=[TrackPoint(x=p.x, y=p.y) for p in layout.display_path],
        start_finish=StartFinishState(
            x=start.x, y=start.y, angle_deg=layout.start_finish.angle_deg
        ),
        pit_lane=pit_lane,
    )


@router.get("/track", response_model=TrackState)
def get_track() -> TrackState:
    """Display-ready circuit map for the live session's circuit_key."""
    circuit_key = _live_circuit_key()
    if circuit_key is None:
        raise HTTPException(status_code=503, detail="No live session available")
    layout = load_layout(circuit_key)
    if layout is None:
        raise HTTPException(
            status_code=404, detail=f"No circuit map for circuit_key {circuit_key}"
        )
    return _display_track(layout)


@router.get("/tracks", response_model=list[TrackState])
def get_tracks() -> list[TrackState]:
    """Every generated circuit map (display-ready)."""
    tracks: list[TrackState] = []
    for path in sorted(layouts_dir().glob("*.json")):
        try:
            layout = CircuitLayout.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except Exception:  # noqa: BLE001 — skip malformed layouts
            continue
        tracks.append(_display_track(layout))
    return tracks


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


def _replay_status(runtime: ReplayRuntime) -> ReplayStatus:
    """Map a runtime's controller snapshot into the response model."""
    return ReplayStatus(**runtime.controller.snapshot())


def _runtime(replay_id: str) -> ReplayRuntime:
    """Return the runtime for ``replay_id``; generic 404 when unknown/expired."""
    runtime = registry.get(replay_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Replay not found")
    return runtime


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


@router.post("/replays", response_model=ReplayCreated)
def create_replay(request: ReplayCreateRequest) -> ReplayCreated:
    """Start a new isolated replay runtime and return its opaque replay_id."""
    runtime = registry.create(request.session_key, request.speed)
    return ReplayCreated(replay_id=runtime.replay_id, **runtime.controller.snapshot())


@router.get("/replays/{replay_id}/status", response_model=ReplayStatus)
def get_replay_status(replay_id: str) -> ReplayStatus:
    """Current state of one replay runtime (idle/running/finished/error)."""
    return _replay_status(_runtime(replay_id))


@router.get("/replays/{replay_id}/race-state", response_model=RaceStateSnapshot)
def get_replay_race_state(replay_id: str) -> RaceStateSnapshot:
    """Replay-owned bootstrap snapshot for the given replay runtime."""
    runtime = _runtime(replay_id)
    state = runtime.controller.state
    # The replay producer knows the completed race distance from the prepared
    # timeline; pass it through so a completed replay keeps a real denominator.
    total_laps = runtime.controller.progress.get("total_laps")
    try:
        session = session_from_live(state, total_laps=total_laps)
    except Exception:  # noqa: BLE001 — treat an unseeded replay as "not ready"
        session = None
    if session is None:
        raise HTTPException(status_code=409, detail="Replay has not seeded yet")
    return RaceStateSnapshot(
        session=session,
        drivers=_drivers(state),
        predictions=replay_predictions(state),
    )


@router.get("/replays/{replay_id}/track", response_model=TrackState)
def get_replay_track(replay_id: str) -> TrackState:
    """Display-ready circuit map for the replay runtime's circuit_key."""
    runtime = _runtime(replay_id)
    circuit_key = _circuit_key(runtime.controller.state)
    if circuit_key is None:
        raise HTTPException(status_code=409, detail="Replay has not seeded yet")
    layout = load_layout(circuit_key)
    if layout is None:
        raise HTTPException(
            status_code=404, detail=f"No circuit map for circuit_key {circuit_key}"
        )
    return _display_track(layout)


@router.post("/replays/{replay_id}/pause", response_model=ReplayStatus)
def pause_replay(replay_id: str) -> ReplayStatus:
    """Suspend the running replay clock; resume from the same position."""
    runtime = _runtime(replay_id)
    runtime.controller.pause()
    return _replay_status(runtime)


@router.post("/replays/{replay_id}/resume", response_model=ReplayStatus)
def resume_replay(replay_id: str) -> ReplayStatus:
    """Continue a paused replay from where it left off."""
    runtime = _runtime(replay_id)
    runtime.controller.resume()
    return _replay_status(runtime)


@router.post("/replays/{replay_id}/seek", response_model=ReplayStatus)
def seek_replay(replay_id: str, request: ReplaySeekRequest) -> ReplayStatus:
    """
    Jump the active replay to a replay-clock time or completed-lap checkpoint.

    The producer restores the nearest checkpoint at or before the requested
    target, then resumes without exposing future events.
    """
    runtime = _runtime(replay_id)
    if request.lap is not None:
        runtime.controller.seek_lap(request.lap)
    elif request.time is not None:
        runtime.controller.seek(request.time)
    return _replay_status(runtime)


@router.post("/replays/{replay_id}/speed", response_model=ReplayStatus)
def set_replay_speed(replay_id: str, request: ReplaySpeedRequest) -> ReplayStatus:
    """Change the active replay speed in place, without restarting it."""
    runtime = _runtime(replay_id)
    if not runtime.controller.set_speed(request.speed):
        raise HTTPException(
            status_code=409, detail="Replay is not running or paused"
        )
    return _replay_status(runtime)


@router.post("/replays/{replay_id}/stop", response_model=ReplayStatus)
def stop_replay(replay_id: str) -> ReplayStatus:
    """Stop and remove only the named replay runtime (live is unaffected)."""
    runtime = _runtime(replay_id)
    registry.stop(replay_id)
    return _replay_status(runtime)
