"""
WebSocket live-update endpoints and broadcasters.

The browser connects to ``/ws/live`` to receive incremental JSON events as the
live ``LIVE_STATE`` buffer changes, or to ``/ws/replays/{replay_id}`` to receive
the same event types as one replay runtime's ``LiveState`` changes. REST stays
the source of full snapshots; the WebSockets only push deltas.

Event types match docs/api/CONTRACT.md: ``location_update``,
``driver_update``, ``weather_update``, ``race_control_update``, and
``prediction_update``.

A background async loop drains each state's dirty-topic flags every ~50 ms and
broadcasts only the values that actually changed, so obsolete location samples
are never queued and unrelated UI is not re-rendered. Live and replay keep
separate connection managers and broadcasters so their events never cross.
Each replay runtime gets its own broadcaster (and diff state) so one user's
events never reach another user's socket.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from formula1_strategy_tool.acquisition.live_drivers import drivers_from_live
from formula1_strategy_tool.acquisition.live_session import latest_session_doc
from formula1_strategy_tool.acquisition.live_state import LIVE_STATE, LiveState
from formula1_strategy_tool.track.models import load_layout
from formula1_strategy_tool.track.projection import LocationProjector

LOCATION_TOPIC = "v1/location"
DRIVER_TOPICS = frozenset(
    {"v1/drivers", "v1/position", "v1/laps", "v1/stints", "v1/pit", "v1/intervals"}
)
PREDICTION_TOPICS = frozenset({"v1/laps", "v1/stints", "v1/pit"})
WEATHER_TOPIC = "v1/weather"
RACE_CONTROL_TOPIC = "v1/race_control"

BROADCAST_INTERVAL_SECONDS = 0.05
PREDICTION_INTERVAL_SECONDS = 10.0


class ConnectionManager:
    """Tracks connected WebSocket clients and fans JSON events out to them."""

    def __init__(self) -> None:
        self.active: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in list(self.active):
            try:
                await websocket.send_json(message)
            except Exception:  # noqa: BLE001 — drop dead clients
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)

    async def close_all(self) -> None:
        """Close every connected client (used when a replay runtime ends)."""
        for websocket in list(self.active):
            try:
                await websocket.close()
            except Exception:  # noqa: BLE001 — client may already be gone
                pass
        self.active.clear()


def _rainfall_flag(value: Any) -> bool:
    if value is None:
        return False
    return bool(value) and value not in (0, "0", 0.0)


def _latest_weather(state: LiveState) -> dict[str, Any] | None:
    rows = state.docs_for(WEATHER_TOPIC)
    if not rows:
        return None
    latest = max(rows, key=lambda r: str(r.get("date") or ""))
    return {
        "track_temperature": latest.get("track_temperature"),
        "air_temperature": latest.get("air_temperature"),
        "rainfall": _rainfall_flag(latest.get("rainfall")),
    }


def _latest_race_control(state: LiveState) -> dict[str, Any] | None:
    rows = state.docs_for(RACE_CONTROL_TOPIC)
    if not rows:
        return None
    latest = max(rows, key=lambda r: str(r.get("date") or ""))
    flag = latest.get("flag")
    return {
        "status": str(flag).upper() if flag else "GREEN",
        "message": str(latest.get("message") or ""),
    }


def _driver_event(driver: Any) -> dict[str, Any]:
    return {
        "type": "driver_update",
        "driver_number": driver.driver_number,
        "position": driver.position,
        "current_lap": driver.current_lap,
        "compound": driver.compound,
        "tyre_age": driver.tyre_age,
        "last_lap_time": driver.last_lap_time,
        "gap_to_leader": driver.gap_to_leader,
        "interval_ahead": driver.interval_ahead,
        "interval_behind": driver.interval_behind,
        "pit_stops": driver.pit_stops,
    }


def _prediction_event(prediction: Any) -> dict[str, Any]:
    probabilities = None
    if prediction.compound_probabilities is not None:
        probabilities = prediction.compound_probabilities.model_dump()
    return {
        "type": "prediction_update",
        "driver_number": prediction.driver_number,
        "lap_number": prediction.lap_number,
        "pit_within_3_laps": prediction.pit_within_3_laps,
        "pit_within_5_laps": prediction.pit_within_5_laps,
        "pit_within_7_laps": prediction.pit_within_7_laps,
        "predicted_next_compound": prediction.predicted_next_compound,
        "compound_probabilities": probabilities,
    }


class Broadcaster:
    """Diff one LiveState against last-sent values and push only the changes."""

    def __init__(
        self,
        manager: ConnectionManager,
        state: LiveState = LIVE_STATE,
        prediction_source: Callable[[], list[Any]] | None = None,
    ) -> None:
        self.manager = manager
        self.state = state
        self._prediction_source = prediction_source
        self._last_locations: dict[int, tuple] = {}
        self._last_drivers: dict[int, tuple] = {}
        self._last_weather: dict[str, Any] | None = None
        self._last_race_control: dict[str, Any] | None = None
        self._last_predictions: dict[int, tuple] = {}
        self._last_prediction_run = 0.0
        self._projector: LocationProjector | None = None
        self._projector_circuit: int | None = None

    def reset(self) -> None:
        """Forget all last-sent state (used by tests)."""
        self._last_locations.clear()
        self._last_drivers.clear()
        self._last_weather = None
        self._last_race_control = None
        self._last_predictions.clear()
        self._last_prediction_run = 0.0
        self._projector = None
        self._projector_circuit = None

    def _projector_for_state(self) -> LocationProjector | None:
        session = latest_session_doc(self.state)
        if session is None:
            return None
        key = session.get("circuit_key")
        circuit_key = int(key) if key is not None else None
        if circuit_key is None:
            return None
        if self._projector_circuit != circuit_key:
            layout = load_layout(circuit_key)
            self._projector = LocationProjector(layout) if layout is not None else None
            self._projector_circuit = circuit_key
        return self._projector

    async def flush(self) -> None:
        dirty = self.state.drain_dirty()
        if not dirty:
            return
        if LOCATION_TOPIC in dirty:
            await self._flush_locations()
        if dirty & DRIVER_TOPICS:
            await self._flush_drivers()
        if WEATHER_TOPIC in dirty:
            await self._flush_weather()
        if RACE_CONTROL_TOPIC in dirty:
            await self._flush_race_control()
        if dirty & PREDICTION_TOPICS:
            await self._flush_predictions()

    async def _flush_locations(self) -> None:
        projector = self._projector_for_state()
        for number, location in self.state.latest_locations().items():
            key = (location["x"], location["y"])
            if self._last_locations.get(number) == key:
                continue
            self._last_locations[number] = key
            map_x = map_y = None
            x = location.get("x")
            y = location.get("y")
            if projector is not None and x is not None and y is not None:
                result = projector.project_location(number, float(x), float(y))
                if result is not None:
                    _, _, display = result
                    map_x, map_y = display
            await self.manager.broadcast(
                {
                    "type": "location_update",
                    "driver_number": number,
                    "x": location["x"],
                    "y": location["y"],
                    "map_x": map_x,
                    "map_y": map_y,
                    "timestamp": location["date"],
                }
            )

    async def _flush_drivers(self) -> None:
        drivers = drivers_from_live(self.state) or []
        for driver in drivers:
            key = (
                driver.position,
                driver.current_lap,
                driver.compound,
                driver.tyre_age,
                driver.last_lap_time,
                driver.gap_to_leader,
                driver.interval_ahead,
                driver.interval_behind,
                driver.pit_stops,
            )
            if self._last_drivers.get(driver.driver_number) == key:
                continue
            self._last_drivers[driver.driver_number] = key
            await self.manager.broadcast(_driver_event(driver))

    async def _flush_weather(self) -> None:
        weather = _latest_weather(self.state)
        if weather is None or weather == self._last_weather:
            return
        self._last_weather = weather
        await self.manager.broadcast({"type": "weather_update", **weather})

    async def _flush_race_control(self) -> None:
        race_control = _latest_race_control(self.state)
        if race_control is None or race_control == self._last_race_control:
            return
        self._last_race_control = race_control
        await self.manager.broadcast(
            {"type": "race_control_update", **race_control}
        )

    async def _flush_predictions(self) -> None:
        if self._prediction_source is None:
            return
        now = time.monotonic()
        if now - self._last_prediction_run < PREDICTION_INTERVAL_SECONDS:
            return
        self._last_prediction_run = now
        # Model inference is expensive and must not run on the event loop, so
        # it is dispatched to a worker thread below.
        try:
            predictions = await asyncio.to_thread(self._prediction_source)
        except Exception:  # noqa: BLE001 — keep other events flowing
            return
        for prediction in predictions:
            key = (
                prediction.lap_number,
                prediction.pit_within_3_laps,
                prediction.pit_within_5_laps,
                prediction.pit_within_7_laps,
                prediction.predicted_next_compound,
            )
            if self._last_predictions.get(prediction.driver_number) == key:
                continue
            self._last_predictions[prediction.driver_number] = key
            await self.manager.broadcast(_prediction_event(prediction))


async def broadcaster_loop(broadcaster: Broadcaster) -> None:
    """Flush changed values every BROADCAST_INTERVAL_SECONDS."""
    while True:
        await asyncio.sleep(BROADCAST_INTERVAL_SECONDS)
        try:
            await broadcaster.flush()
        except Exception as exc:  # noqa: BLE001 — a bad tick must not kill the loop
            print(f"broadcast tick failed: {exc}")


def _live_prediction_source() -> list[Any]:
    from formula1_strategy_tool.api.routes import _model_predictions

    return _model_predictions()


def _replay_prediction_source(controller: Any) -> Callable[[], list[Any]]:
    def source() -> list[Any]:
        from formula1_strategy_tool.api.routes import replay_predictions

        return replay_predictions(controller.state)

    return source


manager = ConnectionManager()
broadcaster = Broadcaster(manager, prediction_source=_live_prediction_source)


class ReplayChannel:
    """One replay runtime's connection manager and diff broadcaster."""

    def __init__(self, replay_id: str, controller: Any) -> None:
        self.replay_id = replay_id
        self.manager = ConnectionManager()
        self.broadcaster = Broadcaster(
            self.manager,
            state=controller.state,
            prediction_source=_replay_prediction_source(controller),
        )
        # A seek reseeds the runtime's state from scratch; reset this channel's
        # diff state so clients receive the fresh data instead of stale diffs.
        controller.on_reset = self.broadcaster.reset


# replay_id -> channel. Accessed only from the event loop (WS endpoints and the
# replay broadcaster loop), so no extra lock is needed.
_replay_channels: dict[str, ReplayChannel] = {}


def _get_or_create_channel(replay_id: str) -> ReplayChannel | None:
    from formula1_strategy_tool.acquisition.replay_registry import registry

    runtime = registry.get(replay_id)
    if runtime is None:
        return None
    channel = _replay_channels.get(replay_id)
    if channel is None:
        channel = ReplayChannel(replay_id, runtime.controller)
        _replay_channels[replay_id] = channel
    return channel


async def _remove_channel(replay_id: str) -> None:
    channel = _replay_channels.pop(replay_id, None)
    if channel is not None:
        await channel.manager.close_all()


async def replay_broadcaster_loop() -> None:
    """Flush every replay channel and prune channels whose runtime ended."""
    from formula1_strategy_tool.acquisition.replay_registry import registry

    while True:
        await asyncio.sleep(BROADCAST_INTERVAL_SECONDS)
        for channel in list(_replay_channels.values()):
            if not registry.exists(channel.replay_id):
                await _remove_channel(channel.replay_id)
                continue
            try:
                await channel.broadcaster.flush()
            except Exception as exc:  # noqa: BLE001 — a bad tick must not kill the loop
                print(f"replay broadcast tick failed: {exc}")


router = APIRouter()


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    """Stream incremental live events (see docs/api/CONTRACT.md)."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


@router.websocket("/ws/replays/{replay_id}")
async def websocket_replay(websocket: WebSocket, replay_id: str) -> None:
    """Stream incremental replay events for exactly one replay runtime."""
    channel = _get_or_create_channel(replay_id)
    if channel is None:
        await websocket.close(code=1008)
        return
    await channel.manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        channel.manager.disconnect(websocket)
