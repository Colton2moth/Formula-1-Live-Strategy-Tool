"""
In-memory buffer for live OpenF1 MQTT messages.

Input:  topic string + parsed JSON dict from a push message
Output: latest document per (topic, key), plus message counts

OpenF1 includes `_key` on streamed messages so updates to the same underlying
row (e.g. one driver's current lap) replace the previous version. We key the
store on `_key` when present, otherwise fall back to driver_number / "last".
"""

from __future__ import annotations

from typing import Any


class LiveState:
    """
    Process-local store of the newest MQTT documents.

    Not thread-safe beyond "MQTT callback writes, main thread reads after
    listen stops" — enough for this first version.
    """

    def __init__(self) -> None:
        # topic -> document_key -> latest payload dict
        self.docs: dict[str, dict[str, dict[str, Any]]] = {}
        # topic -> how many messages received (including replacements)
        self.counts: dict[str, int] = {}

    def update(self, topic: str, payload: dict[str, Any]) -> None:
        """
        Store or replace one live document.

        Parameters:
            topic: MQTT topic, e.g. "v1/laps".
            payload: Parsed JSON object from the broker.
        """
        # Prefer OpenF1's stable document id when streaming.
        key = payload.get("_key")
        if key is None and payload.get("driver_number") is not None:
            # REST rows often lack _key — build a stable id so stints/pits
            # for the same car do not overwrite each other.
            if payload.get("stint_number") is not None:
                key = f"stint:{payload['driver_number']}:{payload['stint_number']}"
            elif payload.get("lap_number") is not None and "pit_duration" in payload:
                key = f"pit:{payload['driver_number']}:{payload['lap_number']}"
            elif payload.get("lap_number") is not None and "lap_duration" in payload:
                # Keep every lap — pace features need a short history per driver.
                key = f"lap:{payload['driver_number']}:{payload['lap_number']}"
            else:
                key = f"driver:{payload['driver_number']}"
        if key is None and payload.get("meeting_name") is not None:
            key = f"meeting:{payload.get('meeting_key', 'last')}"
        if key is None and payload.get("session_name") is not None:
            key = f"session:{payload.get('session_key', 'last')}"
        if key is None and "track_temperature" in payload:
            key = f"weather:{payload.get('date', 'last')}"
        if key is None and payload.get("message") is not None:
            key = f"rc:{payload.get('date', 'last')}:{payload.get('_id', id(payload))}"
        if key is None:
            key = "last"
        key_str = str(key)

        bucket = self.docs.setdefault(topic, {})
        bucket[key_str] = payload
        self.counts[topic] = self.counts.get(topic, 0) + 1

    def summary(self) -> dict[str, dict[str, int]]:
        """Return per-topic message count and how many unique keys we hold."""
        out: dict[str, dict[str, int]] = {}
        for topic, bucket in self.docs.items():
            out[topic] = {
                "messages": self.counts.get(topic, 0),
                "unique_keys": len(bucket),
            }
        # Topics that got counts but somehow empty docs still show up.
        for topic, n in self.counts.items():
            out.setdefault(topic, {"messages": n, "unique_keys": 0})
        return out


# Shared default instance — MQTT listener and (later) the API can import this.
LIVE_STATE = LiveState()
