"""
In-memory buffer for live OpenF1 MQTT messages.

Input:  topic string + parsed JSON dict from a push message
Output: latest document per (topic, key), plus message counts

Rows are keyed by *domain identity* (driver_number, plus stint/pit/lap number
when present) so the same underlying row always maps to the same store key no
matter where it came from. This matters because rows arrive from two sources:
the REST bootstrap (no ``_key`` field) and MQTT pushes (which carry ``_key``).
Keying on ``_key`` first duplicated every bootstrap-seeded row the moment its
MQTT twin arrived — one car became two on the leaderboard and track map.
``_key`` is only used for topics without a driver identity (e.g. race control),
with "last" as the final fallback.

``v1/location`` is a special case: it is a high-frequency time series, so only
the latest sample per driver is retained (never one entry per message).

The store is guarded by a lock because the MQTT callback writes from a
background thread while FastAPI reads it to serve responses.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any

_LOCATION_TOPIC = "v1/location"
_MAX_PENDING_LOCATIONS = 4096


def location_xy(payload: dict[str, Any]) -> tuple[float | None, float | None]:
    """
    Extract a useful x/y from one v1/location payload.

    Returns (None, None) when the sample is missing or carries OpenF1's
    "no position" sentinel (0, 0) — a car in the garage / with no telemetry.
    """
    raw_x = payload.get("x")
    raw_y = payload.get("y")
    if raw_x is None or raw_y is None:
        return None, None
    x = float(raw_x)
    y = float(raw_y)
    if x == 0 and y == 0:
        return None, None
    return x, y


class LiveState:
    """
    Process-local store of the newest MQTT documents, with bounded retention
    and lock-guarded access for concurrent readers/writers.
    """

    def __init__(self) -> None:
        # topic -> document_key -> latest payload dict
        self.docs: dict[str, dict[str, dict[str, Any]]] = {}
        # topic -> how many messages received (including replacements)
        self.counts: dict[str, int] = {}
        # Topics changed since the last drain (drives the WS broadcaster).
        self._dirty: set[str] = set()
        # Short-lived samples awaiting projection by the WebSocket broadcaster.
        self._pending_locations: deque[dict[str, Any]] = deque(
            maxlen=_MAX_PENDING_LOCATIONS
        )
        # Guards docs/counts/_dirty: MQTT writes in a thread, API reads in others.
        self._lock = threading.RLock()

    @staticmethod
    def _key_for(topic: str, payload: dict[str, Any]) -> str:
        """Return the store key for one payload (see module docstring)."""
        # Location is a time series — always keep only the latest per driver.
        if topic == _LOCATION_TOPIC:
            number = payload.get("driver_number")
            return f"driver:{number}" if number is not None else "last"

        # Domain identity FIRST, before MQTT's _key: REST bootstrap rows have no
        # _key, so keying MQTT rows by _key stored the same underlying row twice
        # (once per source) and duplicated cars during live sessions. Deriving
        # the key from driver/stint/pit/lap identity makes an MQTT update
        # *replace* its bootstrap-seeded twin instead of sitting next to it.
        # It also collapses per-update-_key streams (position/intervals) to one
        # row per driver, keeping the buffer bounded over a full race.
        if payload.get("driver_number") is not None:
            number = payload["driver_number"]
            if payload.get("stint_number") is not None:
                return f"stint:{number}:{payload['stint_number']}"
            if payload.get("lap_number") is not None and "pit_duration" in payload:
                return f"pit:{number}:{payload['lap_number']}"
            if payload.get("lap_number") is not None and "lap_duration" in payload:
                # Keep every lap — pace features need a short history per driver.
                return f"lap:{number}:{payload['lap_number']}"
            return f"driver:{number}"

        # No driver identity (weather, race control, session context): _key is
        # the only stable row id MQTT gives us, so use it when present.
        key = payload.get("_key")
        if key is not None:
            return str(key)

        if payload.get("meeting_name") is not None:
            return f"meeting:{payload.get('meeting_key', 'last')}"
        if payload.get("session_name") is not None:
            return f"session:{payload.get('session_key', 'last')}"
        if "track_temperature" in payload:
            return f"weather:{payload.get('date', 'last')}"
        if payload.get("message") is not None:
            return f"rc:{payload.get('date', 'last')}:{payload.get('_id', id(payload))}"
        return "last"

    def update(self, topic: str, payload: dict[str, Any]) -> None:
        """Store or replace one live document (thread-safe)."""
        key = self._key_for(topic, payload)
        with self._lock:
            bucket = self.docs.setdefault(topic, {})
            bucket[key] = payload
            self.counts[topic] = self.counts.get(topic, 0) + 1
            self._dirty.add(topic)
            if topic == _LOCATION_TOPIC:
                self._pending_locations.append(payload)

    def drain_dirty(self) -> set[str]:
        """Return and clear the set of topics changed since the last drain."""
        with self._lock:
            dirty = self._dirty
            self._dirty = set()
            return dirty

    def clear(self) -> None:
        """Reset all stored documents, counts, and dirty flags."""
        with self._lock:
            self.docs.clear()
            self.counts.clear()
            self._dirty.clear()
            self._pending_locations.clear()

    def snapshot_docs(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Copy the store (topic -> key -> payload) for checkpoint persistence."""
        with self._lock:
            return {topic: dict(bucket) for topic, bucket in self.docs.items()}

    def replace_docs(self, docs: dict[str, dict[str, dict[str, Any]]]) -> None:
        """Replace the whole store with a restored snapshot (thread-safe)."""
        with self._lock:
            self.docs = {topic: dict(bucket) for topic, bucket in docs.items()}
            self.counts = {topic: len(bucket) for topic, bucket in self.docs.items()}
            self._dirty = set(self.docs)
            self._pending_locations.clear()
            self._pending_locations.extend(self.docs.get(_LOCATION_TOPIC, {}).values())

    def docs_for(self, topic: str) -> list[dict[str, Any]]:
        """Return a snapshot list of stored payloads for one topic."""
        with self._lock:
            return list(self.docs.get(topic, {}).values())

    def latest_locations(self) -> dict[int, dict[str, Any]]:
        """
        Newest useful location per driver, keyed by driver_number.

        Each entry is the compact streaming shape
        ``{driver_number, x, y, date}``; x/y are null for the no-position
        sentinel. Memory is bounded to one entry per driver.
        """
        out: dict[int, dict[str, Any]] = {}
        with self._lock:
            for payload in self.docs.get(_LOCATION_TOPIC, {}).values():
                number = payload.get("driver_number")
                if number is None:
                    continue
                x, y = location_xy(payload)
                out[int(number)] = {
                    "driver_number": int(number),
                    "x": x,
                    "y": y,
                    "date": payload.get("date"),
                }
        return out

    def drain_location_updates(self) -> list[dict[str, Any]]:
        """Return queued location samples in arrival order, then clear them."""
        with self._lock:
            pending = list(self._pending_locations)
            self._pending_locations.clear()
        return pending

    def summary(self) -> dict[str, dict[str, int]]:
        """Return per-topic message count and how many unique keys we hold."""
        out: dict[str, dict[str, int]] = {}
        with self._lock:
            for topic, bucket in self.docs.items():
                out[topic] = {
                    "messages": self.counts.get(topic, 0),
                    "unique_keys": len(bucket),
                }
            # Topics that got counts but somehow empty docs still show up.
            for topic, count in self.counts.items():
                out.setdefault(topic, {"messages": count, "unique_keys": 0})
        return out


# Shared default instance — MQTT listener and the API can import this.
LIVE_STATE = LiveState()
