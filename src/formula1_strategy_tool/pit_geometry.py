"""
Offline pit-lane geometry extraction from historical location traces.

Pure geometry helpers with no OpenF1 I/O, so the request path never touches
them. Coordinates are **metres** internally; ``scripts/generate_pit_lanes.py``
converts the raw decimetre cache (``÷10``) to metres on the way in and back to
decimetres on the way out, matching ``TrackState.path``.
"""

from __future__ import annotations

import math

DECIMETRES_PER_METRE = 10


def dist_to_path(x: float, y: float, path: list[tuple[float, float]]) -> float:
    """Shortest distance from ``(x, y)`` to the closed polyline ``path``."""
    best = math.inf
    for i in range(len(path) - 1):
        x1, y1 = path[i]
        x2, y2 = path[i + 1]
        dx, dy = x2 - x1, y2 - y1
        length_sq = dx * dx + dy * dy
        if length_sq == 0.0:
            px, py = x1, y1
        else:
            t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length_sq))
            px, py = x1 + t * dx, y1 + t * dy
        best = min(best, math.hypot(x - px, y - py))
    return best


def clean_trace(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop consecutive duplicate samples (zero-length steps)."""
    out: list[tuple[float, float]] = []
    for x, y in points:
        if not out or math.hypot(x - out[-1][0], y - out[-1][1]) > 0.5:
            out.append((x, y))
    return out


def isolate_pit_lane(
    points: list[tuple[float, float, float]],
    path: list[tuple[float, float]],
    entry_time: float,
    exit_time: float,
    on_track_m: float = 8.0,
) -> list[tuple[float, float]]:
    """
    Trim a chronological pit-window trace to the pit-lane segment.

    ``points`` is ``(epoch_seconds, x_m, y_m)``. ``entry_time``/``exit_time``
    are the pit record's lane bounds (``date - lane_duration`` / ``date``).
    Entry is the last on-track sample at/before ``entry_time``; exit is the
    first on-track sample at/after ``exit_time`` (the rejoin). Returns the
    trimmed ``(x, y)`` polyline with a small margin on each side so the lane
    visibly branches from and rejoins the racing surface.
    """
    if not points:
        return []
    dists = [dist_to_path(x, y, path) for _, x, y in points]

    entry_idx = 0
    for i, (t, _, _) in enumerate(points):
        if t > entry_time:
            break
        if dists[i] <= on_track_m:
            entry_idx = i

    exit_idx = len(points) - 1
    for i, (t, _, _) in enumerate(points):
        if t >= exit_time and dists[i] <= on_track_m:
            exit_idx = i
            break

    lo = max(0, entry_idx - 2)
    hi = min(len(points) - 1, exit_idx + 2)
    if hi - lo < 4:
        return []
    return [(x, y) for _, x, y in points[lo : hi + 1]]


def resample(
    points: list[tuple[float, float]], count: int
) -> list[tuple[float, float]]:
    """Resample an open polyline to exactly ``count`` arc-length-spaced points."""
    if count <= 1 or len(points) < 2:
        return list(points)
    segs = [
        math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
        for i in range(len(points) - 1)
    ]
    total = sum(segs)
    if total == 0.0:
        return [points[0]] * count
    step = total / (count - 1)
    out: list[tuple[float, float]] = [points[0]]
    acc = 0.0
    for i in range(len(segs)):
        a = points[i]
        b = points[i + 1]
        seg = segs[i]
        while acc + seg >= step and len(out) < count - 1:
            t = (step - acc) / seg if seg > 0 else 0.0
            a = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            out.append(a)
            seg -= step - acc
            acc = 0.0
        acc += seg
    while len(out) < count:
        out.append(points[-1])
    return out[:count]


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def build_centerline(
    traces: list[list[tuple[float, float]]], count: int
) -> list[tuple[float, float]]:
    """Combine traces into one centreline via per-progress median x/y."""
    if not traces:
        return []
    resampled = [resample(trace, count) for trace in traces]
    out: list[tuple[float, float]] = []
    for i in range(count):
        xs = [trace[i][0] for trace in resampled]
        ys = [trace[i][1] for trace in resampled]
        out.append((_median(xs), _median(ys)))
    return out


def smooth(
    points: list[tuple[float, float]], passes: int = 2
) -> list[tuple[float, float]]:
    """Light moving-average smoothing; endpoints stay fixed."""
    pts = list(points)
    for _ in range(passes):
        if len(pts) < 3:
            break
        out = [pts[0]]
        for i in range(1, len(pts) - 1):
            lo = max(0, i - 1)
            hi = min(len(pts), i + 2)
            out.append(
                (
                    sum(p[0] for p in pts[lo:hi]) / (hi - lo),
                    sum(p[1] for p in pts[lo:hi]) / (hi - lo),
                )
            )
        out.append(pts[-1])
        pts = out
    return pts


def _perp_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length_sq))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def simplify(
    points: list[tuple[float, float]], tolerance: float
) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker simplification with the given tolerance (metres)."""
    if len(points) < 3:
        return list(points)

    def recurse(start: int, end: int) -> list[tuple[float, float]]:
        dmax = -1.0
        index = start
        for i in range(start + 1, end):
            d = _perp_distance(points[i], points[start], points[end])
            if d > dmax:
                dmax = d
                index = i
        if dmax > tolerance:
            left = recurse(start, index)
            right = recurse(index, end)
            return left[:-1] + right
        return [points[start], points[end]]

    return recurse(0, len(points) - 1)
