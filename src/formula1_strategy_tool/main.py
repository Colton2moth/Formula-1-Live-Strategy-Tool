"""
FastAPI application entry point for the Formula 1 Live Strategy Tool.

This module is the top of the "Application API" layer (see docs/ARCHITECTURE.md §7).
The frontend talks only to this backend — not directly to OpenF1.

Current scope:
    - GET /              — liveness check
    - GET /api/*         — REST contract (docs/API_CONTRACT.md)
    - GET /api/live-status — MQTT in-memory buffer summary
    - Background OpenF1 MQTT listener (LIVE_MQTT=1, default on)
    - Predictions from trained models on a historical CSV snapshot
    - Session / drivers from live OpenF1; track from a static circuit library
    - Optional CORS via FRONTEND_URL (needed when FE is on Render)

Run locally (from repo root so relative data/ paths resolve):
    uvicorn formula1_strategy_tool.main:app --host 0.0.0.0 --port 8000
Avoid --reload while using MQTT (reload can start duplicate listeners).
"""

from __future__ import annotations

import asyncio
import os
import threading
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from formula1_strategy_tool.acquisition.replay import replay_controller
from formula1_strategy_tool.api.routes import router as api_router
from formula1_strategy_tool.api.websocket import (
    broadcaster,
    broadcaster_loop,
)
from formula1_strategy_tool.api.websocket import (
    router as ws_router,
)

# Read .env before FRONTEND_URL / LIVE_MQTT checks.
load_dotenv()

# Stop event for the current MQTT listener thread. Replaced with a fresh event
# each time the listener is (re)started so it can resume after a replay stops.
_mqtt_stop = threading.Event()


def _mqtt_enabled() -> bool:
    """Return True unless LIVE_MQTT is explicitly disabled."""
    flag = os.getenv("LIVE_MQTT", "1").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def _mqtt_worker(stop_event: threading.Event) -> None:
    """Background thread target: fill LIVE_STATE until the process exits."""
    # Import inside the thread so app import stays light if MQTT is disabled.
    from formula1_strategy_tool.acquisition.live_mqtt import run_listener

    try:
        # verbose=False keeps uvicorn logs readable during a race.
        run_listener(seconds=None, verbose=False, stop_event=stop_event)
    except Exception as exc:  # noqa: BLE001 — keep API up if MQTT dies
        print(f"MQTT listener exited: {exc}")


def _stop_mqtt() -> None:
    """Signal the current MQTT listener to exit (used before replay starts)."""
    _mqtt_stop.set()


def _start_mqtt() -> None:
    """Start (or restart) the MQTT listener with a fresh stop event."""
    global _mqtt_stop
    if not _mqtt_enabled():
        print("OpenF1 MQTT listener disabled (LIVE_MQTT=0)")
        return
    stop_event = threading.Event()
    _mqtt_stop = stop_event
    thread = threading.Thread(
        target=_mqtt_worker,
        args=(stop_event,),
        name="openf1-mqtt",
        daemon=True,
    )
    thread.start()
    print("OpenF1 MQTT listener thread started (LIVE_MQTT=1)")


def _run_bootstrap() -> None:
    """Pull REST snapshot into LIVE_STATE (best-effort; API still starts on failure)."""
    from formula1_strategy_tool.acquisition.live_bootstrap import bootstrap_live_state

    try:
        session_key = bootstrap_live_state()
        print(f"OpenF1 REST bootstrap done (session_key={session_key})")
    except Exception as exc:  # noqa: BLE001 — API stays up with empty live buffer
        print(f"OpenF1 REST bootstrap skipped: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start replay, or bootstrap + MQTT (replay mode disables both)."""
    # A runtime replay (via the API) stops the MQTT listener first and restarts
    # it once the user deliberately stops/leaves replay mode.
    replay_controller.on_before_start = _stop_mqtt
    replay_controller.on_after_stop = _start_mqtt

    replay_key = os.getenv("REPLAY_SESSION_KEY", "").strip()

    if replay_key:
        # Replay mode: a developer-controlled historical race drives LIVE_STATE.
        speed = float(os.getenv("REPLAY_SPEED", "10").strip())
        replay_controller.start(int(replay_key), speed)
        print(
            f"Replay mode: session_key={replay_key} speed={speed}x "
            "(bootstrap + MQTT disabled)"
        )
    else:
        # LIVE_BOOTSTRAP default on — disable with LIVE_BOOTSTRAP=0 for MQTT-only.
        boot_flag = os.getenv("LIVE_BOOTSTRAP", "1").strip().lower()
        if boot_flag not in {"0", "false", "no", "off"}:
            # Run in a thread so slow OpenF1 calls do not block startup forever
            # without still sequencing before we serve traffic... We join briefly.
            boot = threading.Thread(
                target=_run_bootstrap, name="openf1-bootstrap", daemon=True
            )
            boot.start()
            boot.join(timeout=120.0)

        _start_mqtt()

    # WebSocket broadcaster: flushes changed live values to /ws/live clients.
    broadcast_task = asyncio.create_task(broadcaster_loop(broadcaster))
    print("WebSocket broadcaster started (/ws/live)")
    yield
    broadcast_task.cancel()
    # Daemon threads are abandoned on shutdown; good enough for v1.


# Single app instance — uvicorn / fastapi dev import this object.
app = FastAPI(
    title="Formula 1 Live Strategy Tool",
    description=(
        "Strategy API with optional live OpenF1 MQTT ingest; "
        "session/drivers from live data; predictions from CSV snapshot."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the deployed frontend origin to call this API from the browser.
_frontend_url = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
if _frontend_url:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/")
def root() -> dict[str, str]:
    """Root liveness check — does not reflect race or model state."""
    return {"message": "OpenF1 backend is running"}
