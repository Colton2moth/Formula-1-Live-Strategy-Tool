"""Tests for the versioned circuit-layout data model."""

import pytest
from pydantic import ValidationError

from formula1_strategy_tool.track.models import (
    REFERENCE_POINT_COUNT,
    CircuitLayout,
)


def _layout(n_ref: int = 1000, n_display: int = 1000) -> dict:
    return {
        "circuit_key": 2,
        "name": "Silverstone Circuit",
        "rotation": 92.0,
        "generated_at": "2026-08-21T00:00:00Z",
        "source_sessions": [9947],
        "quality": {},
        "reference_path": [{"x": float(i), "y": 0.0} for i in range(n_ref)],
        "display_path": [{"x": float(i), "y": 0.0} for i in range(n_display)],
        "start_finish": {"display": {"x": 0.0, "y": 0.0}},
    }


def test_layout_accepts_1000_points():
    layout = CircuitLayout.model_validate(_layout())
    assert len(layout.reference_path) == REFERENCE_POINT_COUNT
    assert len(layout.display_path) == REFERENCE_POINT_COUNT


def test_layout_rejects_wrong_reference_count():
    with pytest.raises(ValidationError):
        CircuitLayout.model_validate(_layout(n_ref=999))


def test_layout_rejects_wrong_display_count():
    with pytest.raises(ValidationError):
        CircuitLayout.model_validate(_layout(n_display=1001))
