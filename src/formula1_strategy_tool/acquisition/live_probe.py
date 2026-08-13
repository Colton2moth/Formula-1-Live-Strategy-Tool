"""
Smoke-probe authenticated OpenF1 payloads for the latest session.

Input:  nothing (uses openf1_get + session_key=latest)
Output: printed counts and a few sample fields per endpoint

Purpose: inspect real paid-API shapes before we build live feature rows.
Does not write files or touch FastAPI.
"""

from __future__ import annotations

from typing import Any

from formula1_strategy_tool.acquisition.auth import openf1_get


# Endpoints we care about for strategy features (same families as historical raw/).
_ENDPOINTS = ("drivers", "laps", "stints", "position", "pit", "intervals")


def _summarize(endpoint: str, rows: list[dict[str, Any]]) -> None:
    """Print row count plus one example key set so we can see the schema."""
    print(f"\n=== {endpoint} (n={len(rows)}) ===")
    if not rows:
        print("  (empty)")
        return
    sample = rows[0]
    # Keys only — values can be huge; enough to compare with historical JSON.
    print(f"  keys: {sorted(sample.keys())}")
    # A few identity fields when present (harmless if missing).
    peek = {
        k: sample.get(k)
        for k in (
            "driver_number",
            "lap_number",
            "position",
            "compound",
            "stint_number",
            "gap_to_leader",
            "date",
            "date_start",
        )
        if k in sample
    }
    if peek:
        print(f"  sample: {peek}")


def probe_latest() -> dict[str, list[dict[str, Any]]]:
    """
    Fetch core endpoints for session_key=latest and print short summaries.

    Returns:
        Mapping endpoint name → list of row dicts (for interactive follow-up).
    """
    # Resolve which session "latest" is, then fetch the rest with that key.
    sessions = openf1_get("sessions", {"session_key": "latest"})
    if not sessions:
        raise RuntimeError("sessions?session_key=latest returned no rows")

    session = sessions[0]
    session_key = session["session_key"]
    print(
        "latest session:",
        {
            "session_key": session_key,
            "session_name": session.get("session_name"),
            "location": session.get("location"),
            "date_start": session.get("date_start"),
            "date_end": session.get("date_end"),
        },
    )

    # Use the numeric key for follow-up calls (clearer than repeating "latest").
    params = {"session_key": session_key}
    out: dict[str, list[dict[str, Any]]] = {"sessions": sessions}
    for endpoint in _ENDPOINTS:
        rows = openf1_get(endpoint, params)
        out[endpoint] = rows
        _summarize(endpoint, rows)
    return out


def main() -> None:
    """CLI entry: probe latest session endpoints."""
    probe_latest()


if __name__ == "__main__":
    main()
