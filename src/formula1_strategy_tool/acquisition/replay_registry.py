"""
In-process registry of active replay runtimes (multi-user replay isolation).

Each user-facing replay owns one ``ReplayController`` and therefore a private
``LiveState``, playback clock, speed, pause/stop events, progress, and error.
The prepared historical files under ``data/replay/<session_key>/`` stay shared
and read-only; only the in-memory playback runtime is per user.

Replay IDs are cryptographically random opaque tokens, never sequential. The
registry is deliberately not exposed through a public API: there is no endpoint
that lists active replays, and unknown/expired IDs return a generic not-found.

This is the single-process MVP. If the backend later runs multiple workers or
instances, an in-memory registry is no longer sufficient and replay state must
move to a shared service or sticky routing.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from formula1_strategy_tool.acquisition.replay import ReplayController

# Abandoned runtimes are reaped after this much inactivity.
DEFAULT_INACTIVITY_TTL_SECONDS = 30 * 60


@dataclass
class ReplayRuntime:
    """One user's isolated replay runtime."""

    replay_id: str
    controller: ReplayController
    created_at: float
    last_activity: float


class ReplayRegistry:
    """Owns every active replay runtime and reaps abandoned ones."""

    def __init__(
        self,
        inactivity_ttl: float = DEFAULT_INACTIVITY_TTL_SECONDS,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._runtimes: dict[str, ReplayRuntime] = {}
        self._lock = threading.Lock()
        self._inactivity_ttl = inactivity_ttl
        self._now = now

    def create(self, session_key: int, speed: float = 10.0) -> ReplayRuntime:
        """Create a new isolated runtime and start its replay worker."""
        replay_id = secrets.token_urlsafe(24)
        controller = ReplayController()
        controller.start(session_key, speed)
        runtime = ReplayRuntime(
            replay_id=replay_id,
            controller=controller,
            created_at=self._now(),
            last_activity=self._now(),
        )
        with self._lock:
            self._runtimes[replay_id] = runtime
        return runtime

    def get(self, replay_id: str) -> ReplayRuntime | None:
        """Return one runtime by ID (or None), recording the access as activity."""
        with self._lock:
            runtime = self._runtimes.get(replay_id)
            if runtime is not None:
                runtime.last_activity = self._now()
            return runtime

    def touch(self, replay_id: str) -> None:
        """Record recent activity for a runtime without reading it."""
        with self._lock:
            runtime = self._runtimes.get(replay_id)
            if runtime is not None:
                runtime.last_activity = self._now()

    def stop(self, replay_id: str) -> None:
        """Stop and remove only the named runtime."""
        with self._lock:
            runtime = self._runtimes.pop(replay_id, None)
        if runtime is not None:
            runtime.controller.stop()

    def stop_all(self) -> None:
        """Stop and remove every runtime (used by tests and shutdown)."""
        with self._lock:
            runtimes = list(self._runtimes.values())
            self._runtimes.clear()
        for runtime in runtimes:
            runtime.controller.stop()

    def exists(self, replay_id: str) -> bool:
        """True when the runtime exists, without recording activity."""
        with self._lock:
            return replay_id in self._runtimes

    def cleanup_expired(self) -> int:
        """Stop and remove runtimes idle past the inactivity TTL."""
        now = self._now()
        with self._lock:
            expired = [
                runtime
                for runtime in self._runtimes.values()
                if now - runtime.last_activity > self._inactivity_ttl
            ]
            for runtime in expired:
                self._runtimes.pop(runtime.replay_id, None)
        for runtime in expired:
            runtime.controller.stop()
        return len(expired)


def _inactivity_ttl_from_env() -> float:
    """Inactivity TTL from REPLAY_INACTIVITY_TTL_SECONDS, else the default."""
    raw = os.getenv("REPLAY_INACTIVITY_TTL_SECONDS", "").strip()
    try:
        value = float(raw)
        if value > 0:
            return value
    except ValueError:
        pass
    return DEFAULT_INACTIVITY_TTL_SECONDS


registry = ReplayRegistry(inactivity_ttl=_inactivity_ttl_from_env())
