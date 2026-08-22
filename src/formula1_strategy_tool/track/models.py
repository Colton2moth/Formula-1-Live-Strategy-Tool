"""
Versioned circuit-layout data model for the track-map rebuild.

A layout stores two progress-aligned paths:

- ``reference_path`` — exactly 1000 raw OpenF1-coordinate points used to
  project live/replay x/y onto lap progress. Never normalised.
- ``display_path`` — exactly 1000 display-space points (rotated, uniformly
  scaled, centred) used only for rendering.

Both paths share the same index -> progress mapping; index 0 is the
start/finish line and closure from index 999 back to 0 is implicit (no
duplicate 1001st point).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, model_validator

REFERENCE_POINT_COUNT = 1000
LAYOUT_VERSION = 1


def layouts_dir() -> Path:
    """Directory holding one versioned JSON layout per circuit_key."""
    return Path("data/circuits/layouts")


class LayoutPoint(BaseModel):
    x: float
    y: float


class QualityMetrics(BaseModel):
    accepted_laps: int = 0
    accepted_drivers: int = 0
    loop_length_m: float = 0.0
    closure_distance_m: float = 0.0
    median_deviation_m: float = 0.0
    max_deviation_m: float = 0.0
    max_adjacent_jump_m: float = 0.0


class StartFinish(BaseModel):
    progress: float = 0.0
    display: LayoutPoint
    angle_deg: float = 0.0


class PitLane(BaseModel):
    reference: list[LayoutPoint]
    display: list[LayoutPoint]
    entry_progress: float | None = None
    exit_progress: float | None = None


class CircuitLayout(BaseModel):
    """One circuit layout, validated at load time."""

    layout_version: int = LAYOUT_VERSION
    circuit_key: int
    name: str
    country: str | None = None
    rotation: float = 0.0
    generated_at: str
    source_sessions: list[int]
    quality: QualityMetrics
    reference_path: list[LayoutPoint]
    display_path: list[LayoutPoint]
    start_finish: StartFinish
    pit_lane: PitLane | None = None

    @model_validator(mode="after")
    def _check_point_counts(self) -> CircuitLayout:
        if len(self.reference_path) != REFERENCE_POINT_COUNT:
            raise ValueError(
                f"reference_path has {len(self.reference_path)} points, "
                f"expected {REFERENCE_POINT_COUNT}"
            )
        if len(self.display_path) != REFERENCE_POINT_COUNT:
            raise ValueError(
                f"display_path has {len(self.display_path)} points, "
                f"expected {REFERENCE_POINT_COUNT}"
            )
        return self


def load_layout(circuit_key: int) -> CircuitLayout | None:
    """Load and validate one layout; None when it has not been generated."""
    path = layouts_dir() / f"{circuit_key}.json"
    if not path.exists():
        return None
    return CircuitLayout.model_validate_json(path.read_text(encoding="utf-8"))
