"""Tests for the runtime projection engine."""

import pytest

from formula1_strategy_tool.track.models import load_layout
from formula1_strategy_tool.track.projection import (
    LocationProjector,
    OpenPathProjector,
    Projector,
)


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


def test_open_pit_lane_progress_clamps_at_entry_middle_and_exit(silverstone):
    lane = silverstone.pit_lane
    assert lane is not None
    projector = OpenPathProjector(
        [(point.x, point.y) for point in lane.reference],
        [(point.x, point.y) for point in lane.display],
    )

    entry = projector.project(lane.reference[0].x, lane.reference[0].y)
    middle_point = lane.reference[len(lane.reference) // 2]
    middle = projector.project(middle_point.x, middle_point.y)
    exit_ = projector.project(lane.reference[-1].x, lane.reference[-1].y)

    assert entry is not None and entry[0] == pytest.approx(0.0)
    assert middle is not None and 0.25 < middle[0] < 0.75
    assert exit_ is not None and exit_[0] == pytest.approx(1.0)


def _enter_silverstone_pit(projector, silverstone):
    lane = silverstone.pit_lane
    assert lane is not None
    before_entry = silverstone.reference_path[int(lane.entry_progress * 1000) - 5]
    assert (
        projector.project_routed_location(
            4, before_entry.x, before_entry.y, timestamp=0.0
        ).route
        == "track"
    )
    first_candidate = lane.reference[7]
    assert (
        projector.project_routed_location(
            4, first_candidate.x, first_candidate.y, timestamp=1.0
        )
        is None
    )
    second_candidate = lane.reference[8]
    return projector.project_routed_location(
        4, second_candidate.x, second_candidate.y, timestamp=2.0
    )


def test_location_projector_confirms_wrap_aware_pit_entry(silverstone):
    lane = silverstone.pit_lane
    assert lane is not None and lane.entry_progress > lane.exit_progress

    routed = _enter_silverstone_pit(LocationProjector(silverstone), silverstone)

    assert routed is not None
    assert routed.route == "pit_lane"
    assert routed.pit_lane_progress is not None


def test_location_projector_handles_pit_entry_beside_backward_track_progress():
    monaco = load_layout(22)
    assert monaco is not None and monaco.pit_lane is not None
    projector = LocationProjector(monaco)
    lane = monaco.pit_lane
    before_entry = monaco.reference_path[int(lane.entry_progress * 1000) - 5]
    projector.project_routed_location(4, before_entry.x, before_entry.y, 0.0)

    first = lane.reference[2]
    second = lane.reference[3]
    held = projector.project_routed_location(4, first.x, first.y, 1.0)
    routed = projector.project_routed_location(4, second.x, second.y, 2.0)

    assert held is None
    assert routed is not None and routed.route == "pit_lane"


def test_location_projector_confirms_pit_exit_and_reseeds_track(silverstone):
    projector = LocationProjector(silverstone)
    assert _enter_silverstone_pit(projector, silverstone) is not None
    lane = silverstone.pit_lane
    assert lane is not None
    for index in (20, 25, 29):
        point = lane.reference[index]
        result = projector.project_routed_location(4, point.x, point.y, index)
        assert result is not None and result.route == "pit_lane"

    first_track = silverstone.reference_path[112]
    held = projector.project_routed_location(4, first_track.x, first_track.y, 30.0)
    second_track = silverstone.reference_path[115]
    exited = projector.project_routed_location(4, second_track.x, second_track.y, 31.0)

    assert held is not None and held.route == "pit_lane"
    assert exited is not None and exited.route == "track"
    assert exited.progress == pytest.approx(0.115, abs=0.01)


def test_location_projector_does_not_switch_on_ambiguous_track_points(silverstone):
    projector = LocationProjector(silverstone)
    lane = silverstone.pit_lane
    assert lane is not None
    for offset in range(-3, 4):
        point = silverstone.reference_path[int(lane.entry_progress * 1000) + offset]
        result = projector.project_routed_location(4, point.x, point.y)
        assert result is not None and result.route == "track"


def test_location_projector_falls_back_without_pit_geometry(silverstone):
    layout = silverstone.model_copy(update={"pit_lane": None})
    projector = LocationProjector(layout)
    point = layout.reference_path[100]

    result = projector.project_routed_location(4, point.x, point.y)

    assert result is not None
    assert result.route == "track"
    assert result.pit_lane_progress is None


def test_location_projector_reset_clears_pit_route(silverstone):
    projector = LocationProjector(silverstone)
    routed = _enter_silverstone_pit(projector, silverstone)
    assert routed is not None and routed.route == "pit_lane"

    projector.reset(4)
    point = silverstone.reference_path[300]
    after_reset = projector.project_routed_location(4, point.x, point.y)

    assert after_reset is not None and after_reset.route == "track"
