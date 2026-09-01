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
from dataclasses import dataclass
from typing import Literal

from formula1_strategy_tool.track.models import CircuitLayout

Point = tuple[float, float]

_DM_PER_M = 10.0
_WINDOW = 40
_LOCAL_ACCEPT_DM = 50.0 * _DM_PER_M
_MAX_DISTANCE_DM = 300.0 * _DM_PER_M
# Generous physical envelope; the per-update cap prevents large visual jumps.
_MAX_FORWARD_SPEED_MPS = 150.0
_CONTINUITY_SLACK_M = 75.0
_MAX_BACKWARD_PROGRESS = 0.005
_MAX_PROGRESS_STEP = 0.02

_PIT_MAX_DISTANCE_M = 50.0
_PIT_ROUTE_ADVANTAGE_M = 4.0
_PIT_COMMIT_DISTANCE_M = 18.0
_PIT_TRACK_DISTANCE_SLACK_M = 12.0
_PIT_FALLBACK_MIN_TRACK_DISTANCE_M = 1.0
_PIT_ENTRY_PROGRESS_LIMIT = 0.5
_PIT_ENTRY_TRACK_WINDOW = 0.08
_PIT_EXIT_PROGRESS_START = 0.85
_PIT_EXIT_TRACK_WINDOW = 0.08
_PIT_BACKWARD_TOLERANCE = 0.03
_ROUTE_CONFIRM_SAMPLES = 2


@dataclass(frozen=True)
class RoutedLocation:
    """One trustworthy route-specific projection for a driver sample."""

    progress: float
    distance_m: float
    display: Point
    route: Literal["track", "pit_lane"]
    pit_lane_progress: float | None = None


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

    @property
    def lap_length_m(self) -> float:
        return self._total / _DM_PER_M

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


class OpenPathProjector:
    """Project onto an entry-to-exit path whose progress clamps at both ends."""

    def __init__(self, reference: list[Point], display: list[Point]) -> None:
        if len(reference) < 2 or len(reference) != len(display):
            raise ValueError("open reference/display paths must have equal length >= 2")
        self._reference = reference
        self._display = display
        self._segments: list[tuple[float, float, float, float]] = []
        self._lengths: list[float] = []
        self._cumulative = [0.0]
        for a, b in zip(reference, reference[1:]):
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            self._segments.append((a[0], a[1], b[0], b[1]))
            self._lengths.append(length)
            self._cumulative.append(self._cumulative[-1] + length)
        self._total = self._cumulative[-1]
        if self._total <= 0:
            raise ValueError("open path must have positive length")

    def project(self, x: float, y: float) -> tuple[float, float] | None:
        best: tuple[float, float] | None = None
        for i, (ax, ay, bx, by) in enumerate(self._segments):
            dx, dy = bx - ax, by - ay
            length_sq = dx * dx + dy * dy
            if length_sq == 0:
                continue
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length_sq))
            px, py = ax + dx * t, ay + dy * t
            distance = math.hypot(x - px, y - py)
            progress = (self._cumulative[i] + t * self._lengths[i]) / self._total
            if best is None or distance < best[1]:
                best = progress, distance
        if best is None or best[1] / _DM_PER_M > _PIT_MAX_DISTANCE_M:
            return None
        return best[0], best[1] / _DM_PER_M

    def display_position(self, progress: float) -> Point:
        distance = max(0.0, min(1.0, progress)) * self._total
        index = len(self._lengths) - 1
        for i, end in enumerate(self._cumulative[1:]):
            if distance <= end:
                index = i
                break
        length = self._lengths[index]
        fraction = 0.0 if length == 0 else (distance - self._cumulative[index]) / length
        a, b = self._display[index], self._display[index + 1]
        return a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction


@dataclass
class _DriverRouteState:
    route: Literal["track", "pit_lane"] = "track"
    pit_progress: float | None = None
    entry_votes: int = 0
    exit_votes: int = 0


class LocationProjector:
    """Per-runtime projector that continuity-limits progress per driver."""

    def __init__(self, layout: CircuitLayout) -> None:
        self._projector = Projector(layout)
        self._previous: dict[int, tuple[float, float | None]] = {}
        self._routes: dict[int, _DriverRouteState] = {}
        self._pit_projector: OpenPathProjector | None = None
        self._pit_entry: float | None = None
        self._pit_exit: float | None = None
        pit = layout.pit_lane
        if (
            pit is not None
            and pit.entry_progress is not None
            and pit.exit_progress is not None
            and math.isfinite(pit.entry_progress)
            and math.isfinite(pit.exit_progress)
        ):
            try:
                self._pit_projector = OpenPathProjector(
                    [(point.x, point.y) for point in pit.reference],
                    [(point.x, point.y) for point in pit.display],
                )
                self._pit_entry = pit.entry_progress % 1.0
                self._pit_exit = pit.exit_progress % 1.0
            except ValueError:
                pass

    def project_location(
        self, driver_number: int, x: float, y: float, timestamp: float | None = None
    ) -> tuple[float, float, Point] | None:
        """Return (progress, distance_m, display point) or None to hold."""
        previous = self._previous.get(driver_number)
        previous_progress = previous[0] if previous is not None else None
        result = self._projector.project(x, y, previous_progress)
        if result is None:
            return None
        progress, distance = result
        if previous is not None and timestamp is not None and previous[1] is not None:
            elapsed = timestamp - previous[1]
            if elapsed <= 0:
                return None
            limit = (
                _MAX_FORWARD_SPEED_MPS * elapsed + _CONTINUITY_SLACK_M
            ) / self._projector.lap_length_m
            delta = progress - previous_progress
            if delta > 0.5:
                delta -= 1.0
            elif delta < -0.5:
                delta += 1.0
            limit = min(limit, _MAX_PROGRESS_STEP)
            if delta < -_MAX_BACKWARD_PROGRESS:
                forward_delta = (progress - previous_progress) % 1.0
                progress = (previous_progress + min(forward_delta, limit)) % 1.0
            elif delta < 0:
                self._previous[driver_number] = (previous_progress, timestamp)
                return None
            elif delta > limit:
                progress = (previous_progress + limit) % 1.0
        self._previous[driver_number] = (progress, timestamp)
        display = self._projector.display_position(progress)
        return progress, distance, display

    def project_routed_location(
        self, driver_number: int, x: float, y: float, timestamp: float | None = None
    ) -> RoutedLocation | None:
        """Project a sample onto the driver's stable main-track or pit-lane route."""
        if (
            self._pit_projector is None
            or self._pit_entry is None
            or self._pit_exit is None
        ):
            track = self.project_location(driver_number, x, y, timestamp)
            return None if track is None else RoutedLocation(*track, "track")

        state = self._routes.setdefault(driver_number, _DriverRouteState())
        main = self._projector.project(x, y)
        pit = self._pit_projector.project(x, y)
        if state.route == "pit_lane":
            return self._project_pit_route(driver_number, state, main, pit, timestamp)

        pit_candidate = False
        if main is not None and pit is not None:
            main_progress, main_distance = main
            pit_progress, pit_distance = pit
            entry_distance = min(
                (main_progress - self._pit_entry) % 1.0,
                (self._pit_entry - main_progress) % 1.0,
            )
            advances = state.pit_progress is None or (
                pit_progress + _PIT_BACKWARD_TOLERANCE >= state.pit_progress
            )
            pit_candidate = (
                entry_distance <= _PIT_ENTRY_TRACK_WINDOW
                and pit_progress <= _PIT_ENTRY_PROGRESS_LIMIT
                and (
                    pit_distance + _PIT_ROUTE_ADVANTAGE_M < main_distance
                    or (
                        pit_distance <= _PIT_COMMIT_DISTANCE_M
                        and main_distance >= _PIT_FALLBACK_MIN_TRACK_DISTANCE_M
                        and pit_distance <= main_distance + _PIT_TRACK_DISTANCE_SLACK_M
                    )
                )
                and advances
            )
        if pit_candidate and pit is not None:
            state.entry_votes += 1
            state.pit_progress = pit[0]
            if state.entry_votes >= _ROUTE_CONFIRM_SAMPLES:
                state.route = "pit_lane"
                state.exit_votes = 0
                previous = self._previous.get(driver_number)
                main_progress = previous[0] if previous is not None else main[0]
                return RoutedLocation(
                    main_progress,
                    pit[1],
                    self._pit_projector.display_position(pit[0]),
                    "pit_lane",
                    pit[0],
                )
            return None

        state.entry_votes = 0
        state.pit_progress = None
        track = self.project_location(driver_number, x, y, timestamp)
        return None if track is None else RoutedLocation(*track, "track")

    def _project_pit_route(
        self,
        driver_number: int,
        state: _DriverRouteState,
        main: tuple[float, float] | None,
        pit: tuple[float, float] | None,
        timestamp: float | None,
    ) -> RoutedLocation | None:
        pit_progress = pit[0] if pit is not None else None
        pit_advances = pit_progress is not None and (
            state.pit_progress is None
            or pit_progress + _PIT_BACKWARD_TOLERANCE >= state.pit_progress
        )
        exit_candidate = (
            main is not None
            and state.pit_progress is not None
            and state.pit_progress >= _PIT_EXIT_PROGRESS_START
            and min(
                (main[0] - self._pit_exit) % 1.0,
                (self._pit_exit - main[0]) % 1.0,
            )
            <= _PIT_EXIT_TRACK_WINDOW
            and (pit is None or main[1] + _PIT_ROUTE_ADVANTAGE_M < pit[1])
        )
        state.exit_votes = state.exit_votes + 1 if exit_candidate else 0
        if state.exit_votes >= _ROUTE_CONFIRM_SAMPLES and main is not None:
            state.route = "track"
            state.pit_progress = None
            state.entry_votes = 0
            self._previous[driver_number] = (main[0], timestamp)
            return RoutedLocation(
                main[0], main[1], self._projector.display_position(main[0]), "track"
            )
        if pit is None or not pit_advances:
            return None
        state.pit_progress = max(state.pit_progress or 0.0, pit_progress)
        previous = self._previous.get(driver_number)
        if previous is None:
            return None
        return RoutedLocation(
            previous[0],
            pit[1],
            self._pit_projector.display_position(state.pit_progress),
            "pit_lane",
            state.pit_progress,
        )

    def reset(self, driver_number: int) -> None:
        self._previous.pop(driver_number, None)
        self._routes.pop(driver_number, None)

    def route_for(self, driver_number: int) -> Literal["track", "pit_lane"]:
        """Return the driver's retained route when the latest sample is unusable."""
        state = self._routes.get(driver_number)
        return state.route if state is not None else "track"
