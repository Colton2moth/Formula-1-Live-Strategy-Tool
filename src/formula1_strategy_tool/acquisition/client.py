"""
HTTP client and JSON file helpers for the historical data acquisition layer.

This module is the lowest layer of the acquisition pipeline:
    OpenF1 REST API  →  OpenF1Client.get()  →  atomic_write_json()  →  data/raw/

Inputs:
    - Query parameters (e.g. {"year": 2023}, {"session_key": 9165})
    - Destination paths under data/raw/

Outputs:
    - Parsed JSON as Python lists of dicts (OpenF1 always returns JSON arrays)
    - Raw JSON files on disk, one per endpoint per session

Nothing in this module knows about races, laps, or strategy — it only fetches
and stores API responses. Higher layers (downloader, processing) build on top.
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Any

import requests

# Base URL for all OpenF1 REST requests. Override via OPENF1_BASE_URL in .env
# if you ever need a staging or proxy endpoint.
BASE_URL = os.getenv("OPENF1_BASE_URL", "https://api.openf1.org/v1").rstrip("/")

# OpenF1 community (free) tier allows 30 requests per minute sustained.
# 2.1 seconds between requests ≈ 28.6 req/min — small safety margin below the limit.
MIN_REQUEST_INTERVAL_SECONDS = 2.1

# How many times to retry a failed request before giving up entirely.
MAX_RETRIES = 6


def _describe_http_error(exc: BaseException) -> str:
    """One-line diagnostic for a failed request (status, body, or cause)."""
    response = getattr(exc, "response", None)
    if response is not None:
        body = response.text[:200] if response.text else ""
        return f"HTTP {response.status_code}: {body!r}"
    if isinstance(exc, requests.Timeout):
        return f"timeout ({type(exc).__name__})"
    if isinstance(exc, requests.ConnectionError):
        return f"connection error: {exc}"
    return f"{type(exc).__name__}: {exc}"


class OpenF1Client:
    """
    Rate-limited HTTP client for the OpenF1 REST API.

    Holds a persistent requests.Session (reuses TCP connections across calls)
    and enforces a minimum delay between requests so we stay under the
    community-tier rate limit.
    """

    def __init__(self) -> None:
        # Session object keeps the connection pool alive across multiple GETs.
        self.http = requests.Session()

        # OpenF1 asks callers to set a descriptive User-Agent.
        self.http.headers.update(
            {"User-Agent": "formula-1-live-strategy-tool/0.1.0"}
        )

        # Timestamp (monotonic clock) of when the last request *started*.
        # Used to calculate how long to wait before the next request.
        self._last_request_started = 0.0

    def get(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Fetch one OpenF1 endpoint and return the parsed JSON array.

        Args:
            endpoint: API path segment, e.g. "meetings", "laps", "stints".
            params:   Query-string filters, e.g. {"year": 2023} or
                      {"session_key": 9165}.

        Returns:
            List of dicts — one dict per row returned by the API.

        Raises:
            RuntimeError: All retry attempts exhausted.
        """
        # Build the full URL: e.g. https://api.openf1.org/v1/laps
        url = f"{BASE_URL}/{endpoint}"

        for attempt in range(MAX_RETRIES):
            # --- Rate limiting ---
            # Measure time since our last request started and sleep if needed
            # so we never exceed the community-tier request rate.
            elapsed = time.monotonic() - self._last_request_started
            wait = MIN_REQUEST_INTERVAL_SECONDS - elapsed
            if wait > 0:
                time.sleep(wait)

            # Record start time *before* the request so the interval includes
            # network latency, not just sleep time.
            self._last_request_started = time.monotonic()

            try:
                # timeout=180 because some session endpoints (laps, position)
                # return large payloads that can take a while to download.
                response = self.http.get(url, params=params, timeout=180)

                # --- HTTP 429: rate limited ---
                # OpenF1 tells us to back off. Honour Retry-After if present,
                # otherwise use exponential backoff based on attempt number.
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    delay = (
                        float(retry_after)
                        if retry_after
                        else min(60.0, 2 ** (attempt + 1))
                    )
                    # Small random jitter prevents thundering herd if we retry
                    # multiple endpoints at the same time.
                    time.sleep(delay + random.uniform(0.0, 1.0))
                    continue  # go back to top of retry loop

                # Raises HTTPError for 4xx/5xx status codes (except 429 above).
                response.raise_for_status()

                # OpenF1 always returns a JSON array at the top level.
                data = response.json()
                if not isinstance(data, list):
                    raise ValueError(f"Expected list from {endpoint}")

                return data

            except (requests.RequestException, ValueError) as exc:
                # Last attempt — wrap the underlying error so the caller sees
                # which endpoint and params failed.
                if attempt == MAX_RETRIES - 1:
                    raise RuntimeError(
                        f"Failed GET {endpoint} with {params} "
                        f"({_describe_http_error(exc)})"
                    ) from exc

                # Exponential backoff with jitter before the next attempt.
                time.sleep(min(60.0, 2 ** (attempt + 1)) + random.uniform(0.0, 1.0))

        # Should never be reached because we either return or raise above.
        raise RuntimeError("Unreachable retry state")


def atomic_write_json(path: Path, data: Any) -> None:
    """
    Write JSON to disk atomically so partial writes never corrupt existing files.

    Args:
        path: Final destination file path (e.g. data/raw/2023/.../laps.json).
        data: Any JSON-serialisable Python object (typically a list of dicts).

    Side effects:
        Creates parent directories if they do not exist.
        Writes to a .tmp sibling file first, then renames into place.
    """
    # Ensure the target directory exists (e.g. data/raw/2023/sessions/.../).
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temporary file in the same directory so the rename is atomic
    # on the same filesystem (e.g. laps.json.tmp → laps.json).
    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open("w", encoding="utf-8") as file:
        # Compact JSON (no extra whitespace) to save disk space on large endpoints.
        json.dump(data, file, ensure_ascii=False, separators=(",", ":"))

    # Atomic rename: readers never see a half-written file.
    temporary.replace(path)


def load_json(path: Path) -> Any:
    """
    Read and parse a JSON file from disk.

    Args:
        path: Path to an existing JSON file.

    Returns:
        Parsed Python object (list, dict, etc.).
    """
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_or_download(
    client: OpenF1Client,
    endpoint: str,
    params: dict[str, Any],
    destination: Path,
) -> list[dict[str, Any]]:
    """
    Return data from cache if the file exists, otherwise fetch and save it.

    This is the core resumability mechanism: re-running the downloader skips
    any endpoint/session combination that already has a JSON file on disk.

    Args:
        client:      Shared OpenF1Client instance (handles rate limiting).
        endpoint:    API path segment, e.g. "laps".
        params:      Query-string filters passed to the API.
        destination: Where to save the JSON file if a download is needed.

    Returns:
        List of dicts — either loaded from disk or freshly fetched.
    """
    # --- Cache hit: file already on disk, no API call needed ---
    if destination.exists():
        return load_json(destination)

    # --- Cache miss: fetch from API, persist, then return ---
    data = client.get(endpoint, params)
    atomic_write_json(destination, data)
    return data
