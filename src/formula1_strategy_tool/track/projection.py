"""
Runtime projection engine: raw OpenF1 x/y -> lap progress -> display position.

The reference path is a closed loop of 1000 points (index 0 = start/finish,
closure 999 -> 0 implicit). ``Projector`` finds the nearest reference segment,
converts the projected segment position to cumulative progress (0.0..<1.0),
and interpolates the matching display path. A previous progress can be supplied
so close/parallel sections do not teleport the marker; implausibly distant
samples are rejected so the caller can hold the last valid position.
"""

from __future__ import annotations

import math

from formula1_strategy_tool.track.models import CircuitLayout

Point = tuple[float, float]

_DM_PER_M = 10.0
_WINDOW = 40
_LOCAL_ACCEPT_DM = 50.0 * _DM_PER_M
_MAX_DISTANCE_DM = 300.0 * _DM_PER_M


class Projector:
    """Stateless projection from raw coordinates onto one circuit layout."""

    def __init__(self, layout: CircuitLayout) -> None:
        self._reference: list[Point] = [(p.x, p.y) for p in layout.reference_path]
        self._display: list[Point] = [(p.x, p.y) for p in layout.display_path]
        self._count = len(self._reference)
        self._segments: list[tuple[float, float, float, float]] = []
        self._seg_lengths: list[float] = []
        self._cumulative = [0.0]
        for i in range(self._count):
            a = self._reference[i]
            b = self._reference[(i + 1) % self._count]
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            self._segments.append((a[0], a[1], b[0], b[1]))
            self._seg_lengths.append(length)
            self._cumulative.append(self._cumulative[-1] + length)
        self._total = self._cumulative[-1]

    def project(
        self, x: float, y: float, previous_progress: float | None = None
    ) -> tuple[float, float] | None:
        """Return (progress, distance_m) or None when the point is too far."""
        if previous_progress is not None:
            seg = int(previous_progress * self._count) % self._count
            local = self._nearest(x, y, seg - _WINDOW // 2, _WINDOW)
            if local is not None and local[0] <= _LOCAL_ACCEPT_DM:
                return local[1], local[0] / _DM_PER_M
        best = self._nearest(x, y, 0, self._count)
        if best is None or best[0] > _MAX_DISTANCE_DM:
            return None
        return best[1], best[0] / _DM_PER_M

    def display_position(self, progress: float) -> Point:
        """Interpolate the display path at a 0.0..<1.0 progress."""
        pos = progress * self._count
        index = int(pos) % self._count
        frac = pos - int(pos)
        a = self._display[index]
        b = self._display[(index + 1) % self._count]
        return (
            a[0] + (b[0] - a[0]) * frac,
            a[1] + (b[1] - a[1]) * frac,
        )

    def _nearest(
        self, x: float, y: float, start_seg: int, count: int
    ) -> tuple[float, float] | None:
        best: tuple[float, float] | None = None
        for offset in range(count):
            i = (start_seg + offset) % self._count
            ax, ay, bx, by = self._segments[i]
            dx, dy = bx - ax, by - ay
            length_sq = dx * dx + dy * dy
            if length_sq == 0:
                continue
            t = ((x - ax) * dx + (y - ay) * dy) / length_sq
            t = max(0.0, min(1.0, t))
            px, py = ax + dx * t, ay + dy * t
            distance = math.hypot(x - px, y - py)
            if best is None or distance < best[0]:
                progress = (
                    self._cumulative[i] + t * self._seg_lengths[i]
                ) / self._total
                best = (distance, progress)
        return best


class LocationProjector:
    """Per-runtime projector that keeps one previous progress per driver."""

    def __init__(self, layout: CircuitLayout) -> None:
        self._projector = Projector(layout)
        self._previous: dict[int, float] = {}

    def project_location(
        self, driver_number: int, x: float, y: float
    ) -> tuple[float, float, Point] | None:
        """Return (progress, distance_m, display point) or None to hold."""
        result = self._projector.project(x, y, self._previous.get(driver_number))
        if result is None:
            return None
        progress, distance = result
        self._previous[driver_number] = progress
        display = self._projector.display_position(progress)
        return progress, distance, display

    def reset(self, driver_number: int) -> None:
        self._previous.pop(driver_number, None)
