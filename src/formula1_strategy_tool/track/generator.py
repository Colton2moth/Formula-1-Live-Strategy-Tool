"""
Build the canonical 1,000-point reference path from cached OpenF1 location data.

The reference path lives in the raw OpenF1 coordinate space (decimetres) so
runtime x/y projection is direct. Each accepted lap is segmented by lap timing
(``laps.json`` ``date_start``), resampled to exactly 1000 progress samples, and
combined across laps with a per-index median.

This is a build-time tool; it reads the committed replay cache under
``data/replay`` and never talks to OpenF1.
"""

from __future__ import annotations

import bisect
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from formula1_strategy_tool.acquisition.replay import replay_dir
from formula1_strategy_tool.track.models import (
    REFERENCE_POINT_COUNT,
    CircuitLayout,
    LayoutPoint,
    QualityMetrics,
    StartFinish,
)

Point = tuple[float, float]

_DM_PER_M = 10.0
_MIN_SAMPLES_PER_LAP = 40
_MIN_LAP_FRACTION = 0.65
_MAX_TELEPORT_M = 250.0

VIEW_WIDTH = 100.0
VIEW_HEIGHT = 85.0
PADDING = 6.0


def _parse(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _epoch(dt: datetime) -> float:
    return (dt - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _load_locations(
    cache: Path,
) -> dict[int, tuple[list[float], list[float], list[float]]]:
    """Return driver -> (times, xs, ys) in raw decimetres, sorted by time."""
    by_driver: dict[int, list[tuple[float, float, float]]] = {}
    loc_dir = cache / "location"
    for path in sorted(loc_dir.glob("*.json")):
        for row in _load_json(path):
            x = row.get("x")
            y = row.get("y")
            number = row.get("driver_number")
            if x is None or y is None or number is None:
                continue
            if x == 0 and y == 0:
                continue
            dt = _parse(row.get("date"))
            if dt is None:
                continue
            by_driver.setdefault(int(number), []).append(
                (_epoch(dt), float(x), float(y))
            )

    out: dict[int, tuple[list[float], list[float], list[float]]] = {}
    for number, rows in by_driver.items():
        rows.sort(key=lambda r: r[0])
        out[number] = ([r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows])
    return out


def _excluded_laps(laps: list[dict], driver: int) -> set[int]:
    """Lap numbers to skip: pit-out laps and the lap immediately before them."""
    excluded: set[int] = set()
    rows = sorted(
        (r for r in laps if r.get("driver_number") == driver),
        key=lambda r: r.get("lap_number") or 0,
    )
    for row in rows:
        if row.get("is_pit_out_lap"):
            lap = row.get("lap_number")
            if lap is not None:
                excluded.add(int(lap))
                excluded.add(int(lap) - 1)
    return excluded


def _slice_trace(
    times: list[float], xs: list[float], ys: list[float], start: float, end: float
) -> list[Point]:
    lo = bisect.bisect_left(times, start)
    hi = bisect.bisect_left(times, end)
    if hi - lo < 2:
        return []
    out: list[Point] = []
    if lo > 0 and times[lo] > times[lo - 1]:
        frac = (start - times[lo - 1]) / (times[lo] - times[lo - 1])
        frac = min(max(frac, 0.0), 1.0)
        out.append(
            (
                xs[lo - 1] + (xs[lo] - xs[lo - 1]) * frac,
                ys[lo - 1] + (ys[lo] - ys[lo - 1]) * frac,
            )
        )
    out.extend(zip(xs[lo:hi], ys[lo:hi]))
    return out


def _max_jump_metres(points: list[Point]) -> float:
    return max(
        (math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:])),
        default=0.0,
    ) / _DM_PER_M


def _cumulative_distances(points: list[Point]) -> tuple[list[float], float]:
    cum = [0.0]
    for a, b in zip(points, points[1:]):
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return cum, cum[-1]


def _resample(points: list[Point], count: int) -> list[Point] | None:
    cum, total = _cumulative_distances(points)
    if total <= 0:
        return None
    out: list[Point] = []
    seg = 0
    for i in range(count):
        target = total * i / count
        while seg < len(cum) - 2 and cum[seg + 1] < target:
            seg += 1
        a = points[seg]
        b = points[min(seg + 1, len(points) - 1)]
        span = cum[seg + 1] - cum[seg] if seg + 1 < len(cum) else 0.0
        frac = (target - cum[seg]) / span if span > 0 else 0.0
        frac = min(max(frac, 0.0), 1.0)
        out.append((a[0] + (b[0] - a[0]) * frac, a[1] + (b[1] - a[1]) * frac))
    return out


def _median_combine(samples: list[list[Point]]) -> list[Point]:
    reference: list[Point] = []
    for i in range(REFERENCE_POINT_COUNT):
        xs = [lap[i][0] for lap in samples]
        ys = [lap[i][1] for lap in samples]
        reference.append((statistics.median(xs), statistics.median(ys)))
    return reference


def _deviation(
    samples: list[list[Point]], reference: list[Point]
) -> tuple[float, float]:
    per_lap_means: list[float] = []
    max_dev = 0.0
    for lap in samples:
        dists = [
            math.hypot(lap[i][0] - reference[i][0], lap[i][1] - reference[i][1])
            for i in range(REFERENCE_POINT_COUNT)
        ]
        per_lap_means.append(statistics.median(dists))
        max_dev = max(max_dev, max(dists))
    return statistics.median(per_lap_means) / _DM_PER_M, max_dev / _DM_PER_M


def _per_lap_median_deviation(
    samples: list[list[Point]], reference: list[Point]
) -> list[float]:
    out: list[float] = []
    for lap in samples:
        dists = [
            math.hypot(lap[i][0] - reference[i][0], lap[i][1] - reference[i][1])
            for i in range(REFERENCE_POINT_COUNT)
        ]
        out.append(statistics.median(dists))
    return out


def build_reference_path(
    cache: Path,
) -> tuple[list[Point], QualityMetrics] | None:
    """Build the median 1,000-point reference path for one cached session."""
    sessions = _load_json(cache / "sessions.json")
    if not sessions:
        return None
    laps = _load_json(cache / "laps.json")
    locations = _load_locations(cache)
    if not locations or not laps:
        return None

    drivers: set[int] = set()
    collected: list[tuple[list[Point], float]] = []
    for driver, (times, xs, ys) in locations.items():
        excluded = _excluded_laps(laps, driver)
        driver_laps = sorted(
            (r for r in laps if r.get("driver_number") == driver),
            key=lambda r: r.get("lap_number") or 0,
        )
        for idx in range(len(driver_laps) - 1):
            lap = driver_laps[idx]
            number = lap.get("lap_number")
            if number is not None and int(number) in excluded:
                continue
            start_dt = _parse(lap.get("date_start"))
            end_dt = _parse(driver_laps[idx + 1].get("date_start"))
            if start_dt is None or end_dt is None:
                continue
            trace = _slice_trace(times, xs, ys, _epoch(start_dt), _epoch(end_dt))
            if len(trace) < _MIN_SAMPLES_PER_LAP:
                continue
            if _max_jump_metres(trace) > _MAX_TELEPORT_M:
                continue
            _, total = _cumulative_distances(trace)
            if total <= 0:
                continue
            resampled = _resample(trace, REFERENCE_POINT_COUNT)
            if resampled is None:
                continue
            collected.append((resampled, total))
            drivers.add(driver)

    if len(collected) < 4:
        return None

    median_total = statistics.median(total for _, total in collected)
    samples = [
        resampled
        for resampled, total in collected
        if total >= _MIN_LAP_FRACTION * median_total
    ]
    if len(samples) < 4:
        return None

    reference = _median_combine(samples)
    per_lap_dev = _per_lap_median_deviation(samples, reference)
    threshold = max(50.0 * _DM_PER_M, 3.0 * statistics.median(per_lap_dev))
    clean = [lap for lap, dev in zip(samples, per_lap_dev) if dev <= threshold]
    if len(clean) < 4:
        clean = samples
    reference = _median_combine(clean)
    median_dev, max_dev = _deviation(clean, reference)

    _, total = _cumulative_distances(reference)
    jumps = [
        math.hypot(
            reference[i + 1][0] - reference[i][0],
            reference[i + 1][1] - reference[i][1],
        )
        for i in range(REFERENCE_POINT_COUNT - 1)
    ]
    jumps.append(
        math.hypot(
            reference[0][0] - reference[-1][0],
            reference[0][1] - reference[-1][1],
        )
    )

    quality = QualityMetrics(
        accepted_laps=len(clean),
        accepted_drivers=len(drivers),
        loop_length_m=total / _DM_PER_M,
        closure_distance_m=jumps[-1] / _DM_PER_M,
        median_deviation_m=median_dev,
        max_deviation_m=max_dev,
        max_adjacent_jump_m=max(jumps) / _DM_PER_M,
    )
    return reference, quality


def _orient(point: Point, rotation_deg: float) -> Point:
    radians = math.radians(rotation_deg)
    cos = math.cos(radians)
    sin = math.sin(radians)
    return (
        point[0] * cos - point[1] * sin,
        -(point[0] * sin + point[1] * cos),
    )


def build_display_path(
    reference: list[Point], rotation_deg: float
) -> tuple[list[Point], float]:
    """Rotate + Y-flip, then uniformly scale and centre into the SVG view."""
    oriented = [_orient(p, rotation_deg) for p in reference]
    xs = [p[0] for p in oriented]
    ys = [p[1] for p in oriented]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    scale = min(
        (VIEW_WIDTH - 2 * PADDING) / width,
        (VIEW_HEIGHT - 2 * PADDING) / height,
    )
    offset_x = (VIEW_WIDTH - width * scale) / 2 - min_x * scale
    offset_y = (VIEW_HEIGHT - height * scale) / 2 - min_y * scale
    display = [(x * scale + offset_x, y * scale + offset_y) for x, y in oriented]

    span = min(10, len(display) - 1)
    dx = display[span][0] - display[0][0]
    dy = display[span][1] - display[0][1]
    angle = math.degrees(math.atan2(dy, dx))
    return display, angle


def build_layout(
    session_key: int,
    circuit_key: int,
    name: str,
    country: str | None,
    rotation: float,
) -> CircuitLayout | None:
    """Build one full CircuitLayout from a cached session, or None."""
    built = build_reference_path(replay_dir(session_key))
    if built is None:
        return None
    reference, quality = built
    display, angle = build_display_path(reference, rotation)

    return CircuitLayout(
        circuit_key=circuit_key,
        name=name,
        country=country,
        rotation=rotation,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_sessions=[session_key],
        quality=quality,
        reference_path=[LayoutPoint(x=x, y=y) for x, y in reference],
        display_path=[LayoutPoint(x=x, y=y) for x, y in display],
        start_finish=StartFinish(
            progress=0.0,
            display=LayoutPoint(x=display[0][0], y=display[0][1]),
            angle_deg=angle,
        ),
        pit_lane=None,
    )
