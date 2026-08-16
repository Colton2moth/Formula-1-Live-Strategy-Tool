"""Tests for the offline pit-lane geometry helpers."""

from formula1_strategy_tool.pit_geometry import (
    build_centerline,
    clean_trace,
    dist_to_path,
    isolate_pit_lane,
    resample,
    simplify,
)


def test_dist_to_path():
    path = [(0.0, 0.0), (10.0, 0.0)]
    assert dist_to_path(5.0, 3.0, path) == 3.0
    assert dist_to_path(0.0, 0.0, path) == 0.0


def test_clean_trace_drops_duplicates():
    pts = [(0.0, 0.0), (0.0, 0.0), (10.0, 0.0), (10.0, 0.0), (20.0, 0.0)]
    assert clean_trace(pts) == [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]


def test_resample_preserves_endpoints_and_count():
    out = resample([(0.0, 0.0), (10.0, 0.0)], 5)
    assert len(out) == 5
    assert out[0] == (0.0, 0.0)
    assert out[-1] == (10.0, 0.0)


def test_isolate_pit_lane_trims_to_lane_segment():
    path = [(0.0, 0.0), (100.0, 0.0)]
    points = []
    for t in range(0, 5):  # on track
        points.append((float(t), float(t * 5), 0.0))
    points.append((5.0, 25.0, 4.0))  # still on track
    for t in range(6, 11):  # pit lane, far off the racing line
        points.append((float(t), float(t * 5), 20.0))
    points.append((11.0, 55.0, 4.0))  # rejoined
    for t in range(12, 16):  # back on track
        points.append((float(t), float(t * 5), 0.0))

    isolated = isolate_pit_lane(points, path, entry_time=7.0, exit_time=10.0)

    # Two-sample margin on each side of the detected entry/exit.
    assert isolated[0] == (15.0, 0.0)
    assert isolated[-1] == (65.0, 0.0)
    assert max(y for _, y in isolated) >= 19.0


def test_isolate_pit_lane_empty_when_too_short():
    path = [(0.0, 0.0), (100.0, 0.0)]
    points = [(0.0, 0.0, 0.0), (1.0, 5.0, 0.0)]
    assert isolate_pit_lane(points, path, entry_time=0.5, exit_time=1.0) == []


def test_build_centerline_median():
    a = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]
    b = [(0.0, 10.0), (10.0, 10.0), (20.0, 10.0)]
    assert build_centerline([a, b], 3) == [(0.0, 5.0), (10.0, 5.0), (20.0, 5.0)]


def test_build_centerline_empty():
    assert build_centerline([], 5) == []


def test_simplify_collinear():
    pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0), (4.0, 0.0)]
    assert simplify(pts, 0.5) == [(0.0, 0.0), (4.0, 0.0)]


def test_simplify_keeps_corner():
    pts = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)]
    assert simplify(pts, 0.1) == [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)]
