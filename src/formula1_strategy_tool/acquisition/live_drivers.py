"""
Build API DriverState list from the in-memory MQTT LiveState buffer.

Input:  LiveState (topics: drivers, position, laps, stints, intervals, pit)
Output: list[DriverState] or None if there is not enough live data yet

When None, routes serve an empty list. During a live session, MQTT fills the
buffer and /api/drivers switches over automatically.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from formula1_strategy_tool.acquisition.live_state import LiveState, location_xy
from formula1_strategy_tool.api.schemas import DriverState

_UNKNOWN_GAP = "UNKNOWN"
_LAP_GAP_PATTERN = re.compile(r"^\+\s*(\d+)\s+LAPS?$", re.IGNORECASE)


def _docs(state: LiveState, topic: str) -> list[dict[str, Any]]:
    """All stored payloads for one MQTT topic."""
    return state.docs_for(topic)


def _latest_by_driver(
    rows: list[dict[str, Any]], date_field: str = "date"
) -> dict[int, dict[str, Any]]:
    """
    Keep the newest row per driver_number using an ISO date string field.

    Streaming topics often use unique _key values per update, so the buffer
    may hold many rows per driver — we pick the latest by timestamp.
    """
    best: dict[int, dict[str, Any]] = {}
    for row in rows:
        num = row.get("driver_number")
        if num is None:
            continue
        num_i = int(num)
        prev = best.get(num_i)
        if prev is None or str(row.get(date_field, "")) >= str(
            prev.get(date_field, "")
        ):
            best[num_i] = row
    return best


def _current_stint(
    stints: list[dict[str, Any]], driver_number: int, current_lap: int
) -> dict[str, Any] | None:
    """Pick the stint covering current_lap (or the highest stint_number)."""
    mine = [s for s in stints if int(s.get("driver_number", -1)) == driver_number]
    if not mine:
        return None
    covering = []
    for s in mine:
        start = int(s.get("lap_start") or 0)
        end = s.get("lap_end")
        end_i = int(end) if end is not None else current_lap
        if start <= current_lap <= end_i:
            covering.append(s)
    pool = covering or mine
    return max(pool, key=lambda s: int(s.get("stint_number") or 0))


def _car_location(
    location_row: dict[str, Any] | None,
) -> tuple[float | None, float | None]:
    """
    Extract the latest car x/y from a v1/location row.

    Returns (None, None) when the row is missing or carries OpenF1's
    "no position" sentinel (0, 0), which marks a car in the garage / with no
    telemetry rather than a real on-track location.
    """
    if location_row is None:
        return None, None
    return location_xy(location_row)


def _normalize_gap(value: Any) -> float | str | None:
    """
    Normalize one OpenF1 ``gap_to_leader`` value into the API contract shape.

    Returns a numeric gap, ``None`` for the leader, a normalized lap-count
    string (``"+1 LAP"`` / ``"+2 LAPS"``) for lapped cars, or ``"UNKNOWN"``
    when the value is missing or cannot be parsed. Never coerces missing or
    malformed data to ``0.0`` — that erases the difference between the leader,
    lapped cars, and unavailable data.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return _UNKNOWN_GAP
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return _UNKNOWN_GAP
    match = _LAP_GAP_PATTERN.match(text)
    if match:
        suffix = "LAPS" if text.upper().endswith("LAPS") else "LAP"
        return f"+{int(match.group(1))} {suffix}"
    try:
        return float(text)
    except ValueError:
        return _UNKNOWN_GAP


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an OpenF1 ISO timestamp to a timezone-aware datetime (or None)."""
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _interval_is_stale(
    int_row: dict[str, Any], lap_row: dict[str, Any] | None
) -> bool:
    """
    An interval sample is stale when it predates the driver's current lap.

    The freshness reference is the lap ``date_start`` already stored in the
    buffer (not wall-clock), so replay and test data with historical
    timestamps behave identically to a live session.
    """
    if not int_row or not lap_row:
        return False
    interval_ts = _parse_timestamp(int_row.get("date"))
    lap_start = _parse_timestamp(lap_row.get("date_start"))
    if interval_ts is None or lap_start is None:
        return False
    return interval_ts < lap_start


def drivers_from_live(state: LiveState) -> list[DriverState] | None:
    """
    Map LIVE_STATE into contract DriverState rows.

    Returns None when the drivers topic is empty (not live yet / not seeded).
    Missing timing fields fall back to safe zeros/defaults so the FE still gets
    a full object per driver.
    """
    driver_rows = _latest_by_driver(_docs(state, "v1/drivers"))
    if not driver_rows:
        return None

    positions = _latest_by_driver(_docs(state, "v1/position"))
    intervals = _latest_by_driver(_docs(state, "v1/intervals"))
    locations = _latest_by_driver(_docs(state, "v1/location"))
    laps = _docs(state, "v1/laps")
    stints = _docs(state, "v1/stints")
    pits = _docs(state, "v1/pit")

    # Track the newest observed lap separately from the newest completed lap.
    # OpenF1 creates the current lap row before lap_duration is available.
    latest_lap: dict[int, dict[str, Any]] = {}
    latest_completed_lap: dict[int, dict[str, Any]] = {}
    for row in laps:
        num = row.get("driver_number")
        if num is None:
            continue
        num_i = int(num)
        prev = latest_lap.get(num_i)
        if prev is None or int(row.get("lap_number") or 0) >= int(
            prev.get("lap_number") or 0
        ):
            latest_lap[num_i] = row
        completed = latest_completed_lap.get(num_i)
        if row.get("lap_duration") is not None and (
            completed is None
            or int(row.get("lap_number") or 0)
            >= int(completed.get("lap_number") or 0)
        ):
            latest_completed_lap[num_i] = row

    results: list[DriverState] = []
    for d in driver_rows.values():
        num = int(d["driver_number"])
        lap_row = latest_lap.get(num)
        completed_lap_row = latest_completed_lap.get(num)
        current_lap = int(lap_row.get("lap_number") or 0) if lap_row else 0
        last_lap_time = (
            float(completed_lap_row["lap_duration"])
            if completed_lap_row is not None
            else 0.0
        )

        stint = _current_stint(stints, num, max(current_lap, 1))
        compound = str(stint.get("compound") or "UNKNOWN") if stint else "UNKNOWN"
        if stint:
            # tyre_age ≈ laps on this stint + age when fitted.
            age_start = int(stint.get("tyre_age_at_start") or 0)
            lap_start = int(stint.get("lap_start") or 1)
            tyre_age = age_start + max(0, current_lap - lap_start)
        else:
            tyre_age = 0

        pos_row = positions.get(num)
        int_row = intervals.get(num)
        interval = int_row.get("interval") if int_row else None
        # OpenF1 uses None / "+1 LAP" style strings sometimes — coerce gently.
        try:
            interval_f = float(interval) if interval is not None else None
        except (TypeError, ValueError):
            interval_f = None

        # gap_to_leader keeps its semantic state: number, null (leader),
        # lap-count string, or "UNKNOWN" (missing/stale/malformed).
        if int_row is None:
            gap_value: float | str | None = _UNKNOWN_GAP
        elif _interval_is_stale(int_row, lap_row):
            gap_value = _UNKNOWN_GAP
        else:
            gap_value = _normalize_gap(int_row.get("gap_to_leader"))

        pit_stops = sum(1 for p in pits if int(p.get("driver_number", -1)) == num)

        colour = str(d.get("team_colour") or "FFFFFF").lstrip("#")
        position = int(pos_row.get("position") or 0) if pos_row else 0
        x, y = _car_location(locations.get(num))

        results.append(
            DriverState(
                driver_number=num,
                name=str(d.get("full_name") or d.get("broadcast_name") or f"#{num}"),
                acronym=str(d.get("name_acronym") or f"{num:02d}"),
                team_name=str(d.get("team_name") or "Unknown"),
                team_colour=colour,
                position=position,
                x=x,
                y=y,
                current_lap=current_lap,
                compound=compound,
                tyre_age=tyre_age,
                last_lap_time=last_lap_time,
                gap_to_leader=gap_value,
                interval_ahead=interval_f,
                interval_behind=None,  # derived later if we sort the grid
                pit_stops=pit_stops,
            )
        )

    # Sort by position when known so the FE gets leaderboard order.
    results.sort(key=lambda r: (r.position == 0, r.position, r.driver_number))
    return results
