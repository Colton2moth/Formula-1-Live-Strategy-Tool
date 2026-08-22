"""Tests for the runtime projection engine."""

import pytest

from formula1_strategy_tool.track.models import load_layout
from formula1_strategy_tool.track.projection import LocationProjector, Projector


@pytest.fixture(scope="module")
def silverstone():
    layout = load_layout(2)
    assert layout is not None
    return layout


def test_project_matches_reference_start(silverstone):
    projector = Projector(silverstone)
    point = silverstone.reference_path[0]
    result = projector.project(point.x, point.y)
    assert result is not None
    progress, distance = result
    assert distance < 5.0
    assert progress < 0.01 or progress > 0.99


def test_project_matches_reference_midpoint(silverstone):
    projector = Projector(silverstone)
    point = silverstone.reference_path[500]
    result = projector.project(point.x, point.y)
    assert result is not None
    progress, _ = result
    assert abs(progress - 0.5) < 0.05


def test_project_rejects_far_point(silverstone):
    projector = Projector(silverstone)
    assert projector.project(1e7, 1e7) is None


def test_display_position_stays_in_view(silverstone):
    projector = Projector(silverstone)
    for progress in (0.0, 0.25, 0.5, 0.75, 0.999):
        x, y = projector.display_position(progress)
        assert 0.0 <= x <= 100.0
        assert 0.0 <= y <= 85.0


def test_location_projector_tracks_per_driver(silverstone):
    projector = LocationProjector(silverstone)
    point = silverstone.reference_path[100]
    result = projector.project_location(4, point.x, point.y)
    assert result is not None
    progress, distance, display = result
    assert distance < 5.0
    assert 0.0 <= display[0] <= 100.0
    # Re-projecting the same point should reuse the local window.
    again = projector.project_location(4, point.x, point.y)
    assert again is not None
    assert abs(again[0] - progress) < 1e-6
