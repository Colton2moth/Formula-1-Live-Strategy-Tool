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


def test_display_position_interpolates_between_points(silverstone):
    projector = Projector(silverstone)
    start = projector.display_position(0.0)
    quarter = projector.display_position(0.25)
    assert start != quarter
    assert 0.0 <= quarter[0] <= 100.0
    assert 0.0 <= quarter[1] <= 85.0


def test_display_position_wraps_to_start(silverstone):
    projector = Projector(silverstone)
    start = projector.display_position(0.0)
    wrapped = projector.display_position(0.9999)
    distance = ((wrapped[0] - start[0]) ** 2 + (wrapped[1] - start[1]) ** 2) ** 0.5
    assert distance < 1.0


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


def test_location_projector_limits_impossible_timed_jump(silverstone):
    projector = LocationProjector(silverstone)
    start = silverstone.reference_path[100]
    teleport = silverstone.reference_path[600]

    first = projector.project_location(4, start.x, start.y, 0.0)
    limited = projector.project_location(4, teleport.x, teleport.y, 1.0)

    assert first is not None
    assert limited is not None
    delta = (limited[0] - first[0]) % 1.0
    assert 0 < delta <= 0.02 + 1e-9


def test_location_projector_limits_teleport_after_long_gap(silverstone):
    projector = LocationProjector(silverstone)
    start = silverstone.reference_path[100]
    teleport = silverstone.reference_path[600]

    first = projector.project_location(4, start.x, start.y, 0.0)
    limited = projector.project_location(4, teleport.x, teleport.y, 60.0)

    assert first is not None
    assert limited is not None
    delta = (limited[0] - first[0]) % 1.0
    assert 0 < delta <= 0.02 + 1e-9


def test_location_projector_accepts_timed_lap_wrap(silverstone):
    projector = LocationProjector(silverstone)
    before_line = silverstone.reference_path[990]
    after_line = silverstone.reference_path[10]

    first = projector.project_location(4, before_line.x, before_line.y, 0.0)
    wrapped = projector.project_location(4, after_line.x, after_line.y, 1.0)

    assert first is not None
    assert wrapped is not None
    assert wrapped[0] < first[0]
