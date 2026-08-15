"""
Minimal OpenF1 MQTT listener for live push data.

Input:  OPENF1 credentials via get_valid_access_token
Output: fills LiveState / LIVE_STATE; prints each message; summary on exit

OpenF1 pushes updates on topics that mirror REST paths (e.g. v1/laps).
Auth: username = any non-empty string; password = OAuth access token.
Between race sessions you may connect successfully but receive little/no traffic.
"""

from __future__ import annotations

import argparse
import json
import ssl
import threading
import time

import paho.mqtt.client as mqtt

from formula1_strategy_tool.acquisition.auth import get_valid_access_token
from formula1_strategy_tool.acquisition.live_state import LIVE_STATE, LiveState

# TLS MQTT broker from https://openf1.org/auth.html
_MQTT_HOST = "mqtt.openf1.org"
_MQTT_PORT = 8883

# Start with strategy-relevant topics (add more later if needed).
_TOPICS = (
    "v1/drivers",
    "v1/laps",
    "v1/stints",
    "v1/pit",
    "v1/position",
    "v1/intervals",
    "v1/weather",
    "v1/race_control",
    "v1/location",
)


def _on_connect(
    client: mqtt.Client,
    userdata: object,
    flags: object,
    reason_code: object,
    properties: object = None,
) -> None:
    """Subscribe after the broker accepts our connection."""
    print(f"connected reason_code={reason_code}")
    for topic in _TOPICS:
        client.subscribe(topic)
        print(f"  subscribed {topic}")


def _on_message(
    client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage
) -> None:
    """Parse JSON, update the in-memory store, optionally print a short line."""
    # userdata is (LiveState, verbose) so the API can run quietly in a thread.
    if isinstance(userdata, tuple) and len(userdata) == 2:
        state, verbose = userdata
    else:
        state, verbose = LIVE_STATE, True

    raw = msg.payload.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        if verbose:
            print(f"{msg.topic}: (non-JSON) {raw[:240]}")
        return

    # OpenF1 may send a single object or (rarely) a list — normalize to objects.
    items = parsed if isinstance(parsed, list) else [parsed]
    for item in items:
        if isinstance(item, dict):
            state.update(msg.topic, item)

    if not verbose:
        return
    text = json.dumps(parsed, separators=(",", ":"))
    if len(text) > 240:
        text = text[:240] + "…"
    print(f"{msg.topic}: {text}")


def run_listener(
    seconds: float | None = None,
    state: LiveState | None = None,
    *,
    verbose: bool = True,
    stop_event: threading.Event | None = None,
) -> LiveState:
    """
    Connect to OpenF1 MQTT, fill `state`, return it when done.

    Parameters:
        seconds: If set, run this long then disconnect. None = until Ctrl+C.
        state: Buffer to write into (default: module LIVE_STATE).
        verbose: When False, skip per-message prints (used by FastAPI thread).
        stop_event: When set, exit the listen loop (used to stop MQTT so a
            replay can own LIVE_STATE exclusively).
    """
    buffer = state if state is not None else LIVE_STATE
    token = get_valid_access_token()

    # Pass (buffer, verbose) as userdata for the message callback.
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        userdata=(buffer, verbose),
    )
    client.username_pw_set(username="f1-strategy-tool", password=token)
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = _on_connect
    client.on_message = _on_message

    if verbose:
        print(f"connecting {_MQTT_HOST}:{_MQTT_PORT} …")
    client.connect(_MQTT_HOST, _MQTT_PORT, keepalive=60)
    client.loop_start()
    try:
        if seconds is None:
            while not (stop_event is not None and stop_event.is_set()):
                time.sleep(0.2)
        else:
            if verbose:
                print(f"listening for {seconds:g}s (Ctrl+C to stop early)…")
            time.sleep(seconds)
    except KeyboardInterrupt:
        if verbose:
            print("\nstopped by user")
    finally:
        client.loop_stop()
        client.disconnect()
        if verbose:
            print("disconnected")
            print("live state summary:", buffer.summary())
    return buffer


def main() -> None:
    """CLI: optional --seconds for a timed smoke test."""
    parser = argparse.ArgumentParser(description="Listen to OpenF1 MQTT topics.")
    parser.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="Exit after N seconds (default: run until Ctrl+C).",
    )
    args = parser.parse_args()
    run_listener(seconds=args.seconds)


if __name__ == "__main__":
    main()
