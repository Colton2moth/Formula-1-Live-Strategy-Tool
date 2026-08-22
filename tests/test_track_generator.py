"""Tests for the 1,000-point reference generator's pure helpers."""

from formula1_strategy_tool.track.generator import (
    REFERENCE_POINT_COUNT,
    _orient,
    _resample,
    build_display_path,
)


def _square_loop() -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for i in range(100):
        points.append((float(i * 10), 0.0))
    for i in range(100):
        points.append((1000.0, float(i * 10)))
    for i in range(100):
        points.append((1000.0 - float(i * 10), 1000.0))
    for i in range(100):
        points.append((0.0, 1000.0 - float(i * 10)))
    return points


def test_resample_returns_exact_count():
    out = _resample(_square_loop(), REFERENCE_POINT_COUNT)
    assert out is not None
    assert len(out) == REFERENCE_POINT_COUNT


def test_display_path_fits_view():
    reference = _resample(_square_loop(), REFERENCE_POINT_COUNT)
    assert reference is not None
    display, _ = build_display_path(reference, 0.0)
    assert len(display) == REFERENCE_POINT_COUNT
    for x, y in display:
        assert 0.0 <= x <= 100.0
        assert 0.0 <= y <= 85.0


def test_orient_flips_y_for_svg():
    assert _orient((100.0, 0.0), 0.0) == (100.0, -0.0)
    assert _orient((0.0, 100.0), 0.0) == (0.0, -100.0)
