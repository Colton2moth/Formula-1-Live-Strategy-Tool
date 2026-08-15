"""
Build API DriverState list from the in-memory MQTT LiveState buffer.

Input:  LiveState (topics: drivers, position, laps, stints, intervals, pit)
Output: list[DriverState] or None if there is not enough live data yet

When None, routes serve an empty list. During a live session, MQTT fills the
buffer and /api/drivers switches over automatically.
"""

from __future__ import annotations

from typing import Any

from formula1_strategy_tool.acquisition.live_state import LiveState
from formula1_strategy_tool.api.schemas import DriverState


def _docs(state: LiveState, topic: str) -> list[dict[str, Any]]:
    """All stored payloads for one MQTT topic."""
    return list(state.docs.get(topic, {}).values())


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
    raw_x = location_row.get("x")
    raw_y = location_row.get("y")
    if raw_x is None or raw_y is None:
        return None, None
    x = float(raw_x)
    y = float(raw_y)
    if x == 0 and y == 0:
        return None, None
    return x, y


def drivers_from_live(state: LiveState) -> list[DriverState] | None:
    """
    Map LIVE_STATE into contract DriverState rows.

    Returns None when the drivers topic is empty (not live yet / not seeded).
    Missing timing fields fall back to safe zeros/defaults so the FE still gets
    a full object per driver.
    """
    driver_rows = _docs(state, "v1/drivers")
    if not driver_rows:
        return None

    positions = _latest_by_driver(_docs(state, "v1/position"))
    intervals = _latest_by_driver(_docs(state, "v1/intervals"))
    locations = _latest_by_driver(_docs(state, "v1/location"))
    laps = _docs(state, "v1/laps")
    stints = _docs(state, "v1/stints")
    pits = _docs(state, "v1/pit")

    # Latest completed lap per driver (max lap_number).
    latest_lap: dict[int, dict[str, Any]] = {}
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

    results: list[DriverState] = []
    for d in driver_rows:
        num = int(d["driver_number"])
        lap_row = latest_lap.get(num)
        current_lap = int(lap_row.get("lap_number") or 0) if lap_row else 0
        last_lap_time = float(lap_row.get("lap_duration") or 0.0) if lap_row else 0.0

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
        gap = int_row.get("gap_to_leader") if int_row else None
        interval = int_row.get("interval") if int_row else None
        # OpenF1 uses None / "+1 LAP" style strings sometimes — coerce gently.
        try:
            gap_f = float(gap) if gap is not None else 0.0
        except (TypeError, ValueError):
            gap_f = 0.0
        try:
            interval_f = float(interval) if interval is not None else None
        except (TypeError, ValueError):
            interval_f = None

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
                gap_to_leader=gap_f,
                interval_ahead=interval_f,
                interval_behind=None,  # derived later if we sort the grid
                pit_stops=pit_stops,
            )
        )

    # Sort by position when known so the FE gets leaderboard order.
    results.sort(key=lambda r: (r.position == 0, r.position, r.driver_number))
    return results
