"""
OpenF1 OAuth2 helper + authenticated REST GET for paid / live access.

Input:  OPENF1_USERNAME / OPENF1_PASSWORD from .env
Output: Bearer token (cached) and JSON arrays from /v1 endpoints

Flow:
    fetch_access_token()  →  one-shot password grant
    get_valid_access_token()  →  reuse token until near expiry
    openf1_get(endpoint, params)  →  Authorization: Bearer … GET

Tokens last ~1 hour. We refresh a few minutes early so a long live session
does not suddenly start getting 401s.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

# Token endpoint is outside /v1 (unlike meetings/laps/etc.).
_TOKEN_URL = "https://api.openf1.org/token"

# Refresh this many seconds before expires_in so we never ride the edge.
_REFRESH_MARGIN_SECONDS = 300

# Cached token state for this process (None = not fetched yet).
_cached_token: str | None = None
_cached_token_expires_at: float = 0.0


def fetch_access_token() -> dict[str, Any]:
    """
    Exchange OpenF1 username/password for a short-lived access token.

    Returns:
        Dict with at least access_token, expires_in, and token_type
        (matches OpenF1's JSON response).

    Raises:
        RuntimeError: Missing env vars or non-200 token response.
    """
    # Ensure .env is loaded when this runs as a CLI or before FastAPI starts.
    load_dotenv()

    username = os.getenv("OPENF1_USERNAME", "").strip()
    password = os.getenv("OPENF1_PASSWORD", "").strip()
    if not username or not password:
        raise RuntimeError(
            "OPENF1_USERNAME and OPENF1_PASSWORD must be set in .env"
        )

    # application/x-www-form-urlencoded — requests sets this when data=dict.
    response = requests.post(
        _TOKEN_URL,
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if response.status_code != 200:
        # Do not echo password; body may still help debug bad credentials.
        raise RuntimeError(
            f"OpenF1 token request failed: {response.status_code} {response.text}"
        )

    payload = response.json()
    if not payload.get("access_token"):
        raise RuntimeError(f"OpenF1 token response missing access_token: {payload}")
    return payload


def get_valid_access_token() -> str:
    """
    Return a usable Bearer token, refreshing if missing or near expiry.

    Side effect: updates the module-level token cache.
    """
    global _cached_token, _cached_token_expires_at

    # Still fresh enough — skip another /token round-trip.
    now = time.time()
    if _cached_token and now < _cached_token_expires_at - _REFRESH_MARGIN_SECONDS:
        return _cached_token

    payload = fetch_access_token()
    _cached_token = str(payload["access_token"])
    # expires_in may arrive as int or string depending on OpenF1.
    expires_in = int(payload.get("expires_in", 3600))
    _cached_token_expires_at = now + expires_in
    return _cached_token


def openf1_get(
    endpoint: str, params: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Authenticated GET against one OpenF1 /v1 endpoint.

    Parameters:
        endpoint: Path segment only, e.g. "sessions", "laps", "drivers".
        params: Optional query filters, e.g. {"session_key": "latest"}.

    Returns:
        Parsed JSON array (OpenF1's standard list-of-dicts shape).

    Raises:
        RuntimeError: Non-200 response or unexpected JSON type.
    """
    load_dotenv()
    # Same base URL override as the historical client.
    base = os.getenv("OPENF1_BASE_URL", "https://api.openf1.org/v1").rstrip("/")
    url = f"{base}/{endpoint.lstrip('/')}"

    token = get_valid_access_token()
    response = requests.get(
        url,
        params=params or {},
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "formula-1-live-strategy-tool/0.1.0",
        },
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"OpenF1 GET {endpoint} failed: {response.status_code} {response.text[:300]}"
        )

    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Expected list from {endpoint}, got {type(data)}")
    return data


def main() -> None:
    """CLI smoke test: cached token + openf1_get for latest session."""
    token = get_valid_access_token()
    print(f"token ok (len={len(token)})")

    rows = openf1_get("sessions", {"session_key": "latest"})
    print(f"GET sessions?session_key=latest -> rows={len(rows)}")
    if rows:
        row = rows[0]
        print(
            "latest session:",
            {
                "session_key": row.get("session_key"),
                "session_name": row.get("session_name"),
                "session_type": row.get("session_type"),
                "location": row.get("location"),
                "date_start": row.get("date_start"),
            },
        )


if __name__ == "__main__":
    main()
