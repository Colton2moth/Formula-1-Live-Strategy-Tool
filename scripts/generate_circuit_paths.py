"""
Generate normalized circuit path data for the static track library.

Uses FastF1's official circuit corner / marshal-sector coordinates as anchor
points, orders them around the circuit, and smooths them into a closed loop.
Output is the 0-1 normalized ``TrackPoint`` data committed to
``src/formula1_strategy_tool/api/circuits.py``.

FastF1 is a build-time dependency only (not listed in requirements.txt). Run:

    python scripts/generate_circuit_paths.py --year 2025 --circuit-key 4

OpenF1 and FastF1 share the same ``circuit_key`` numbering.
"""

from __future__ import annotations

import argparse
import math
from collections.abc import Iterable

try:
    import fastf1.mvapi as mvapi
except ImportError as exc:  # pragma: no cover - build-time tool
    raise SystemExit("fastf1 is required: pip install fastf1") from exc

RESAMPLE = 140
SAMPLES_PER_SEGMENT = 12


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _project(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return 0.0
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_sq
    return max(0.0, min(1.0, t))


def _order_by_track_distance(
    sectors: list[tuple[float, float]], corners: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    """Order corners + sectors by arc length along the sector reference loop."""
    n = len(sectors)
    cumulative = [0.0] * n
    for i in range(1, n):
        cumulative[i] = cumulative[i - 1] + _dist(sectors[i - 1], sectors[i])

    def position(point: tuple[float, float]) -> float:
        best: tuple[float, float] | None = None
        for i in range(n):
            a = sectors[i]
            b = sectors[(i + 1) % n]
            t = _project(point, a, b)
            projected = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            d = _dist(point, projected)
            if best is None or d < best[0]:
                best = (d, cumulative[i] + t * _dist(a, b))
        return best[1] if best else 0.0

    merged = sectors + corners
    ordered = sorted(merged, key=position)
    out: list[tuple[float, float]] = []
    for point in ordered:
        if not out or _dist(point, out[-1]) > 1.0:
            out.append(point)
    if out and _dist(out[0], out[-1]) < 1.0:
        out = out[:-1]
    return out


def _catmull_rom_closed(
    points: list[tuple[float, float]], samples: int
) -> list[tuple[float, float]]:
    n = len(points)
    out: list[tuple[float, float]] = []
    for i in range(n):
        p0 = points[(i - 1) % n]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n]
        for step in range(samples):
            t = step / samples
            t2 = t * t
            t3 = t2 * t
            out.append(
                (
                    0.5
                    * (
                        2 * p1[0]
                        + (-p0[0] + p2[0]) * t
                        + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                        + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
                    ),
                    0.5
                    * (
                        2 * p1[1]
                        + (-p0[1] + p2[1]) * t
                        + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                        + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
                    ),
                )
            )
    return out


def _resample(
    points: list[tuple[float, float]], count: int
) -> list[tuple[float, float]]:
    closed = points + [points[0]]
    total = sum(
        math.hypot(closed[i + 1][0] - closed[i][0], closed[i + 1][1] - closed[i][1])
        for i in range(len(closed) - 1)
    )
    step = total / count
    out: list[tuple[float, float]] = []
    acc = 0.0
    for i in range(len(closed) - 1):
        a = closed[i]
        b = closed[i + 1]
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        while acc + seg >= step and len(out) < count:
            t = (step - acc) / seg
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            seg -= step - acc
            acc = 0.0
            a = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        acc += seg
    return out


def _normalize(
    points: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w = maxx - minx
    h = maxy - miny
    return [((p[0] - minx) / w, (p[1] - miny) / h) for p in points]


def _bounds(
    points: list[tuple[float, float]],
) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), max(xs), min(ys), max(ys)


def build_path(
    year: int, circuit_key: int
) -> tuple[list[tuple[float, float]], tuple[float, float]]:
    """Return (normalized path points, normalized start_finish point)."""
    info = mvapi.get_circuit_info(year=year, circuit_key=circuit_key)
    if info is None:
        raise ValueError(
            f"no circuit info for year={year} circuit_key={circuit_key}"
        )

    corners = list(zip(info.corners["X"], info.corners["Y"]))
    sectors = list(zip(info.marshal_sectors["X"], info.marshal_sectors["Y"]))
    start_finish_raw = sectors[0]

    anchors = _order_by_track_distance(sectors, corners)
    if len(anchors) < 4:
        raise ValueError("too few anchor points")

    splined = _catmull_rom_closed(anchors, SAMPLES_PER_SEGMENT)
    resampled = _resample(splined, RESAMPLE)
    minx, maxx, miny, maxy = _bounds(resampled)
    w = maxx - minx
    h = maxy - miny
    normalized = [((p[0] - minx) / w, (p[1] - miny) / h) for p in resampled]
    normalized.append(normalized[0])
    start_finish_norm = (
        (start_finish_raw[0] - minx) / w,
        (start_finish_raw[1] - miny) / h,
    )
    return normalized, start_finish_norm


def format_points(points: Iterable[tuple[float, float]]) -> str:
    return "\n".join(
        f'    TrackPoint(x={x:.4f}, y={y:.4f}),' for x, y in points
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--circuit-key", type=int, required=True)
    args = parser.parse_args()

    path, start_finish = build_path(args.year, args.circuit_key)
    print(f"start_finish=TrackPoint(x={start_finish[0]:.4f}, y={start_finish[1]:.4f})")
    print("path=[")
    print(format_points(path))
    print("]")


if __name__ == "__main__":
    main()
