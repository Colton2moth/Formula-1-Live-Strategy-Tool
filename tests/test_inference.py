"""Tests for live feature-row inference and missing-value alignment."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from formula1_strategy_tool import inference


class _FakeBooster:
    feature_names = [
        "season",
        "current_compound",
        "gap_to_leader",
        "interval_ahead",
    ]


class _FakePitModel:
    def __init__(self) -> None:
        self.last_X: pd.DataFrame | None = None

    def get_booster(self) -> _FakeBooster:
        return _FakeBooster()

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        self.last_X = X
        return np.full((len(X), 2), 0.5)


class _FakeCompoundModel:
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return np.full((len(X), 3), 1.0 / 3.0)


def _patch_models(monkeypatch, pit: _FakePitModel) -> None:
    def fake_load_models(model_dir):
        return (
            {
                "pit_within_3_laps": pit,
                "pit_within_5_laps": pit,
                "pit_within_7_laps": pit,
                "next_compound": _FakeCompoundModel(),
            },
            ["SOFT", "MEDIUM", "HARD"],
        )

    monkeypatch.setattr(inference, "load_models", fake_load_models)


def test_missing_interval_columns_are_aligned_as_nan(monkeypatch):
    pit = _FakePitModel()
    _patch_models(monkeypatch, pit)

    feat = pd.DataFrame(
        {
            "season": [2026],
            "current_compound": ["SOFT"],
            "driver_number": [4],
            "lap_number": [10],
        }
    )

    results = inference.predict_feature_rows(feat, Path("unused"))

    assert pit.last_X is not None
    assert list(pit.last_X.columns) == [
        "season",
        "current_compound",
        "gap_to_leader",
        "interval_ahead",
    ]
    # Missing interval features stay NaN — never invented zeros.
    assert pit.last_X["gap_to_leader"].isna().all()
    assert pit.last_X["interval_ahead"].isna().all()
    assert not pit.last_X["season"].isna().any()

    assert len(results) == 1
    assert results[0]["driver_number"] == 4
    assert results[0]["lap_number"] == 10
