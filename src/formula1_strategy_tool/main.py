"""
FastAPI application entry point for the Formula 1 Live Strategy Tool.

This module is the top of the "Application API" layer (see docs/ARCHITECTURE.md §7).
The frontend talks only to this backend — not directly to OpenF1.

Current scope:
    - GET /              — liveness check
    - GET /api/*         — REST contract (docs/api/CONTRACT.md)
    - GET /api/live-status — MQTT in-memory buffer summary
    - Background OpenF1 MQTT listener (LIVE_MQTT=1, default on)
    - Live predictions from the current session's features (no silent CSV fallback)
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

from formula1_strategy_tool.acquisition.live_state import LIVE_STATE
from formula1_strategy_tool.api.routes import router as api_router
from formula1_strategy_tool.api.websocket import (
    broadcaster,
    broadcaster_loop,
    manager,
    replay_broadcaster_loop,
)
from formula1_strategy_tool.api.websocket import (
    router as ws_router,
)

# Read .env before FRONTEND_URL / LIVE_MQTT checks.
load_dotenv()

# Stop event + thread for the live MQTT listener. Live ingestion is independent
# of replay and runs for the process lifetime; the session monitor stops and
# restarts it across OpenF1 session changes so old-session pushes cannot leak
# into the new session's buffer.
_mqtt_stop: threading.Event | None = None
_mqtt_thread: threading.Thread | None = None

# OpenF1 session_key the live buffer currently represents. Set by the startup
# bootstrap and updated by the session monitor on a detected session change.
_live_session_key: int | None = None

# Set once the startup bootstrap finishes (success or failure). The session
# monitor waits for it before its first check so it never races the seed.
_initial_bootstrap_done = threading.Event()

# How often the session monitor polls OpenF1 for the current session_key.
_SESSION_CHECK_INTERVAL_SECONDS = 45.0

# How long to wait for the MQTT worker to exit before failing a transition.
_MQTT_STOP_TIMEOUT_SECONDS = 5.0


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


def _start_mqtt() -> None:
    """
    Start the MQTT listener with a fresh stop event (idempotent per process).

    A no-op when MQTT is disabled or a listener is already running, so the
    session monitor can safely call it after every transition without ever
    spawning a duplicate worker.
    """
    global _mqtt_stop, _mqtt_thread
    if not _mqtt_enabled():
        print("OpenF1 MQTT listener disabled (LIVE_MQTT=0)")
        return
    if _mqtt_thread is not None and _mqtt_thread.is_alive():
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
    _mqtt_thread = thread
    print("OpenF1 MQTT listener thread started (LIVE_MQTT=1)")


def _stop_mqtt() -> bool:
    """
    Stop the current MQTT listener and wait for it to exit.

    Returns True when no listener is running or the worker fully exited, and
    False when the worker is still alive after the timeout. On False the thread
    handle is deliberately retained so ``_start_mqtt`` refuses to spawn a
    duplicate while the old worker is still alive.
    """
    global _mqtt_stop, _mqtt_thread
    stop = _mqtt_stop
    thread = _mqtt_thread
    if stop is not None:
        stop.set()
    if thread is None:
        _mqtt_stop = None
        return True
    thread.join(timeout=_MQTT_STOP_TIMEOUT_SECONDS)
    if thread.is_alive():
        print("MQTT listener did not stop in time; leaving it registered")
        return False
    _mqtt_thread = None
    _mqtt_stop = None
    return True


def _run_bootstrap() -> None:
    """Pull REST snapshot into LIVE_STATE (best-effort; API still starts on failure)."""
    global _live_session_key
    from formula1_strategy_tool.acquisition.live_bootstrap import bootstrap_live_state

    try:
        session_key = bootstrap_live_state()
        _live_session_key = session_key
        print(f"OpenF1 REST bootstrap done (session_key={session_key})")
    except Exception as exc:  # noqa: BLE001 — API stays up with empty live buffer
        print(f"OpenF1 REST bootstrap skipped: {exc}")
    finally:
        _initial_bootstrap_done.set()


def _latest_session_key() -> int | None:
    """
    Resolve OpenF1's current "latest" session_key, or None on any failure.

    A failure here must not crash the backend or clear state: callers keep the
    last valid state and simply retry on the next check.
    """
    from formula1_strategy_tool.acquisition.auth import openf1_get

    try:
        sessions = openf1_get("sessions", {"session_key": "latest"})
    except Exception as exc:  # noqa: BLE001 — an OpenF1 outage must not kill the monitor
        print(f"session check failed: {exc}")
        return None
    if not sessions:
        return None
    try:
        return int(sessions[0]["session_key"])
    except (KeyError, TypeError, ValueError):
        print("session check failed: missing/invalid session_key in response")
        return None


def _swap_to_session(new_key: int) -> int:
    """
    Blocking worker: bootstrap session B into a staging buffer, then swap it in.

    Runs in a worker thread so the slow REST bootstrap never stalls the event
    loop. MQTT is stopped first (and joined) so no old-session push can arrive
    during the transition, then the new session is bootstrapped into a private
    ``LiveState``. Only after that succeeds are the process-wide ``LIVE_STATE``
    contents atomically replaced — the existing valid state is never cleared or
    modified first. Returns the resolved session_key; raises on any failure so
    the caller keeps session A untouched and MQTT stopped.
    """
    from formula1_strategy_tool.acquisition.live_bootstrap import bootstrap_live_state
    from formula1_strategy_tool.acquisition.live_state import LiveState

    if not _stop_mqtt():
        raise RuntimeError(
            "MQTT listener did not stop in time; aborting session transition"
        )

    staging = LiveState()
    resolved = bootstrap_live_state(state=staging, session_key=new_key)

    # Validate the bootstrap resolved the expected session and produced enough
    # session context to be usable before committing anything.
    if resolved != new_key:
        raise RuntimeError(
            f"bootstrap resolved session_key={resolved}, expected {new_key}"
        )
    if not staging.docs_for("v1/sessions"):
        raise RuntimeError("bootstrap produced no session context")

    # Atomically replace the contents of the shared buffer (never the object
    # itself, which other modules hold references to).
    LIVE_STATE.replace_docs(staging.snapshot_docs())
    return resolved


async def _perform_session_transition(new_key: int) -> None:
    """
    Move the live buffer to a newly detected OpenF1 session, transactionally.

    On success: the shared buffer now holds session B, the tracked key is
    updated, the WS diff state is reset, MQTT is restarted for the new session,
    and live clients are closed so they reconnect/resync from the fresh
    /api/race-state. On failure: session A (buffer + key) is left completely
    untouched, the broadcaster is not reset, clients are not closed, and MQTT
    stays stopped so session-B pushes cannot contaminate session A. The next
    monitor tick retries the same new key.
    """
    global _live_session_key
    try:
        resolved = await asyncio.to_thread(_swap_to_session, new_key)
    except Exception as exc:  # noqa: BLE001 — keep session A; retry next check
        print(f"session transition to {new_key} failed: {exc}")
        return
    _live_session_key = resolved
    broadcaster.reset()
    _start_mqtt()
    await manager.close_all()
    print(f"live session transitioned to session_key={resolved}")


async def _session_monitor_loop() -> None:
    """Poll OpenF1 for the latest session and transition when it changes."""
    # Wait for the startup bootstrap to finish before checking, so the monitor
    # never races the initial seed of LIVE_STATE. Poll the event rather than
    # blocking a worker thread, so shutdown and disabled-bootstrap stay clean.
    while not _initial_bootstrap_done.is_set():
        await asyncio.sleep(1.0)
    while True:
        await asyncio.sleep(_SESSION_CHECK_INTERVAL_SECONDS)
        latest = await asyncio.to_thread(_latest_session_key)
        if latest is None or latest == _live_session_key:
            continue
        print(f"OpenF1 session changed {_live_session_key} -> {latest}")
        await _perform_session_transition(latest)


# How often abandoned replay runtimes are checked (TTL set by the registry).
_REPLAY_CLEANUP_INTERVAL_SECONDS = 60.0


async def _replay_cleanup_loop() -> None:
    """Periodically reap abandoned replay runtimes past the inactivity TTL."""
    from formula1_strategy_tool.acquisition.replay_registry import registry

    while True:
        await asyncio.sleep(_REPLAY_CLEANUP_INTERVAL_SECONDS)
        try:
            registry.cleanup_expired()
        except Exception as exc:  # noqa: BLE001 — a bad cleanup must not kill the loop
            print(f"replay cleanup failed: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start live bootstrap + MQTT; replay runs in per-user registry runtimes."""
    # Live ingestion is independent of replay: it starts once and stays up for
    # the process lifetime, regardless of replay start/pause/seek/stop.
    boot_flag = os.getenv("LIVE_BOOTSTRAP", "1").strip().lower()
    if boot_flag not in {"0", "false", "no", "off"}:
        # Run in a thread so slow OpenF1 calls do not block startup forever
        # without still sequencing before we serve traffic... We join briefly.
        boot = threading.Thread(
            target=_run_bootstrap, name="openf1-bootstrap", daemon=True
        )
        boot.start()
        boot.join(timeout=120.0)
    else:
        # No bootstrap: let the session monitor run without waiting on it.
        _initial_bootstrap_done.set()

    _start_mqtt()

    # WebSocket broadcasters: live, plus one channel per replay runtime.
    broadcast_task = asyncio.create_task(broadcaster_loop(broadcaster))
    print("WebSocket broadcaster started (/ws/live)")
    replay_broadcast_task = asyncio.create_task(replay_broadcaster_loop())
    print("Replay WebSocket broadcaster started (/ws/replays/{replay_id})")
    cleanup_task = asyncio.create_task(_replay_cleanup_loop())
    session_monitor_task = asyncio.create_task(_session_monitor_loop())
    yield
    broadcast_task.cancel()
    replay_broadcast_task.cancel()
    cleanup_task.cancel()
    session_monitor_task.cancel()
    # Daemon threads are abandoned on shutdown; good enough for v1.


# Single app instance — uvicorn / fastapi dev import this object.
app = FastAPI(
    title="Formula 1 Live Strategy Tool",
    description=(
        "Strategy API with optional live OpenF1 MQTT ingest; "
        "session/drivers from live data; predictions from the live session."
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
