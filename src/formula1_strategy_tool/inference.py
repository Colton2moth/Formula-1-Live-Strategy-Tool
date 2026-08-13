"""
Score a historical driver-lap snapshot with the trained strategy models.

Input:  master CSV + model JSON files under data/models/
Output: list of prediction dicts (same fields as API PredictionState)

Used as a smoke-test before wiring FastAPI. Feature prep deliberately reuses
training._prepare_features on the *full* CSV so categorical codes match what
the pit models saw at train time.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from xgboost import XGBClassifier

from formula1_strategy_tool.training import PIT_LABELS, _prepare_features

# Default paths match training CLI defaults.
_DEFAULT_CSV = Path("data/processed/driver_laps_all.csv")
_DEFAULT_MODEL_DIR = Path("data/models")

# CompoundProbabilities schema keys (fixed order for the API contract).
_COMPOUND_KEYS = ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")


def load_models(model_dir: Path) -> tuple[dict[str, XGBClassifier], list[str]]:
    """
    Load the three pit-window boosters plus next_compound and its class list.

    Parameters:
        model_dir: Directory containing the *.json model files from training.

    Returns:
        (pit_models_by_label, compound_class_names). Compound class index i in
        predict_proba maps to compound_class_names[i].
    """
    # Pit models: one binary classifier per horizon label.
    pit_models: dict[str, XGBClassifier] = {}
    for label in PIT_LABELS:
        model = XGBClassifier()
        model.load_model(model_dir / f"{label}.json")
        pit_models[label] = model

    # Multiclass compound model + sidecar class order written at train time.
    compound_model = XGBClassifier()
    compound_model.load_model(model_dir / "next_compound.json")
    classes = json.loads((model_dir / "next_compound_classes.json").read_text())[
        "classes"
    ]
    # Store compound under a reserved key so callers get one models dict + classes.
    pit_models["next_compound"] = compound_model
    return pit_models, list(classes)


def predict_snapshot(
    csv_path: Path,
    model_dir: Path,
    session_key: int,
    lap_number: int,
) -> list[dict[str, Any]]:
    """
    Score every driver present at (session_key, lap_number) in the master CSV.

    Parameters:
        csv_path: Path to driver_laps_all.csv (or compatible).
        model_dir: Directory with trained model JSON files.
        session_key: OpenF1 session_key to filter.
        lap_number: Lap to take as the "as of now" snapshot.

    Returns:
        One prediction dict per driver (API PredictionState field names).
    """
    models, compound_classes = load_models(model_dir)

    # Load once; encode features on the full frame so cat.codes match training.
    df = pd.read_csv(csv_path)
    X_all = _prepare_features(df)

    # Keep meta columns from the raw frame; they were excluded from X.
    mask = (df["session_key"] == session_key) & (df["lap_number"] == lap_number)
    if not mask.any():
        raise ValueError(
            f"no rows for session_key={session_key} lap_number={lap_number}"
        )

    X = X_all.loc[mask]
    meta = df.loc[mask, ["driver_number", "lap_number"]]
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Binary pit-window probabilities (column 1 = positive class).
    pit_proba = {
        label: models[label].predict_proba(X)[:, 1] for label in PIT_LABELS
    }

    # Multiclass compound: always score for the smoke test (API may null later).
    compound_proba = models["next_compound"].predict_proba(X)
    pred_idx = compound_proba.argmax(axis=1)

    results: list[dict[str, Any]] = []
    for i, (_, row) in enumerate(meta.iterrows()):
        # Map class index → name; fill all five contract keys (0.0 if absent).
        probs = {name: 0.0 for name in _COMPOUND_KEYS}
        for j, name in enumerate(compound_classes):
            probs[name] = float(compound_proba[i, j])
        predicted = compound_classes[int(pred_idx[i])]

        results.append(
            {
                "driver_number": int(row["driver_number"]),
                "lap_number": int(row["lap_number"]),
                "pit_within_3_laps": float(pit_proba["pit_within_3_laps"][i]),
                "pit_within_5_laps": float(pit_proba["pit_within_5_laps"][i]),
                "pit_within_7_laps": float(pit_proba["pit_within_7_laps"][i]),
                "predicted_next_compound": predicted,
                "compound_probabilities": probs,
                "updated_at": updated_at,
            }
        )
    return results


def predict_feature_rows(
    feature_df: pd.DataFrame,
    model_dir: Path,
) -> list[dict[str, Any]]:
    """
    Score an already-built feature frame (e.g. from live_features).

    Expects columns compatible with training (driver_number, lap_number, and
    the model feature set). Uses fixed compound category codes via
    training._prepare_features.
    """
    if feature_df.empty:
        return []

    models, compound_classes = load_models(model_dir)
    X = _prepare_features(feature_df)
    # Align to the booster's feature order when available.
    booster_names = models[PIT_LABELS[0]].get_booster().feature_names
    if booster_names:
        for name in booster_names:
            if name not in X.columns:
                X[name] = pd.NA
        X = X[list(booster_names)]

    meta = feature_df[["driver_number", "lap_number"]].reset_index(drop=True)
    X = X.reset_index(drop=True)
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    pit_proba = {
        label: models[label].predict_proba(X)[:, 1] for label in PIT_LABELS
    }
    compound_proba = models["next_compound"].predict_proba(X)
    pred_idx = compound_proba.argmax(axis=1)

    results: list[dict[str, Any]] = []
    for i, row in meta.iterrows():
        probs = {name: 0.0 for name in _COMPOUND_KEYS}
        for j, name in enumerate(compound_classes):
            probs[name] = float(compound_proba[i, j])
        results.append(
            {
                "driver_number": int(row["driver_number"]),
                "lap_number": int(row["lap_number"]),
                "pit_within_3_laps": float(pit_proba["pit_within_3_laps"][i]),
                "pit_within_5_laps": float(pit_proba["pit_within_5_laps"][i]),
                "pit_within_7_laps": float(pit_proba["pit_within_7_laps"][i]),
                "predicted_next_compound": compound_classes[int(pred_idx[i])],
                "compound_probabilities": probs,
                "updated_at": updated_at,
            }
        )
    return results


def main(argv: list[str] | None = None) -> None:
    """CLI: print model predictions for one historical race-lap snapshot."""
    parser = argparse.ArgumentParser(description="Score one CSV race-lap snapshot.")
    parser.add_argument("--csv", type=Path, default=_DEFAULT_CSV)
    parser.add_argument("--model-dir", type=Path, default=_DEFAULT_MODEL_DIR)
    parser.add_argument("--session-key", type=int, required=True)
    parser.add_argument("--lap", type=int, required=True, dest="lap_number")
    args = parser.parse_args(argv)

    preds = predict_snapshot(
        args.csv, args.model_dir, args.session_key, args.lap_number
    )
    # Compact table so we can eyeball that probs are in [0, 1] and drivers exist.
    print(f"session_key={args.session_key} lap={args.lap_number} n={len(preds)}")
    for p in sorted(preds, key=lambda d: d["driver_number"]):
        print(
            f"  #{p['driver_number']:2d}  "
            f"pit3={p['pit_within_3_laps']:.3f}  "
            f"pit5={p['pit_within_5_laps']:.3f}  "
            f"pit7={p['pit_within_7_laps']:.3f}  "
            f"next={p['predicted_next_compound']}"
        )


if __name__ == "__main__":
    main()
