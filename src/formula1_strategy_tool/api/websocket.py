"""
WebSocket live-update endpoint and broadcaster.

The browser connects to ``/ws/live`` and receives incremental JSON events as
the LIVE_STATE buffer changes. REST (``/api/*``) stays the source of full
snapshots; the WebSocket only pushes deltas.

Event types match docs/API_CONTRACT.md: ``location_update``,
``driver_update``, ``weather_update``, ``race_control_update``, and
``prediction_update``.

A background async loop drains LIVE_STATE's dirty-topic flags every ~50 ms and
broadcasts only the values that actually changed, so obsolete location samples
are never queued and unrelated UI is not re-rendered.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from formula1_strategy_tool.acquisition.live_drivers import drivers_from_live
from formula1_strategy_tool.acquisition.live_state import LIVE_STATE, LiveState

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
    """Diff LIVE_STATE against last-sent values and push only the changes."""

    def __init__(
        self, manager: ConnectionManager, state: LiveState = LIVE_STATE
    ) -> None:
        self.manager = manager
        self.state = state
        self._last_locations: dict[int, tuple] = {}
        self._last_drivers: dict[int, tuple] = {}
        self._last_weather: dict[str, Any] | None = None
        self._last_race_control: dict[str, Any] | None = None
        self._last_predictions: dict[int, tuple] = {}
        self._last_prediction_run = 0.0

    def reset(self) -> None:
        """Forget all last-sent state (used by tests)."""
        self._last_locations.clear()
        self._last_drivers.clear()
        self._last_weather = None
        self._last_race_control = None
        self._last_predictions.clear()
        self._last_prediction_run = 0.0

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
        for number, location in self.state.latest_locations().items():
            key = (location["x"], location["y"])
            if self._last_locations.get(number) == key:
                continue
            self._last_locations[number] = key
            await self.manager.broadcast(
                {
                    "type": "location_update",
                    "driver_number": number,
                    "x": location["x"],
                    "y": location["y"],
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
        now = time.monotonic()
        if now - self._last_prediction_run < PREDICTION_INTERVAL_SECONDS:
            return
        self._last_prediction_run = now
        # Import lazily: model inference is expensive and must not run on the
        # event loop, so it is dispatched to a worker thread below.
        from formula1_strategy_tool.api.routes import _model_predictions

        try:
            predictions = await asyncio.to_thread(_model_predictions)
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


manager = ConnectionManager()
broadcaster = Broadcaster(manager)

router = APIRouter()


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    """Stream incremental live events (see docs/API_CONTRACT.md)."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
