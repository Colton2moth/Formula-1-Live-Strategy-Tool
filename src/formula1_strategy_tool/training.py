"""
Train baseline XGBoost models for pit windows and next compound.

Input:  data/processed/driver_laps_all.csv
Output: data/models/pit_within_{3,5,7}_laps.json
        data/models/next_compound.json

Pit models: binary, all rows.
Compound model: multiclass on rows where pit_within_3_laps == 1
(and next_compound is known). Season holdout for validation.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    f1_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

# All three binary pit-window targets we train in v1.
PIT_LABELS = (
    "pit_within_3_laps",
    "pit_within_5_laps",
    "pit_within_7_laps",
)

# Not model inputs: IDs, timestamps, and labels (would leak or ID-memorize).
_EXCLUDE = {
    "meeting_key",
    "session_key",
    "driver_number",
    "date_start",
    "as_of",
    "pit_within_3_laps",
    "pit_within_5_laps",
    "pit_within_7_laps",
    "next_compound",
}

# String columns encoded as integer codes for XGBoost.
_CATEGORICAL = ("current_compound", "previous_compound")

# Compound classes in a stable display order (actual set may omit rare ones).
_COMPOUND_ORDER = ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")


def _prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Shared feature matrix from a driver-lap frame (labels already excluded)."""
    work = df.copy()
    for col in ("gap_to_leader", "interval_ahead"):
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")

    feature_cols = [c for c in work.columns if c not in _EXCLUDE]
    X = work[feature_cols].copy()

    for col in _CATEGORICAL:
        if col in X.columns:
            X[col] = X[col].astype("category").cat.codes.replace(-1, pd.NA)
            X[col] = pd.to_numeric(X[col], errors="coerce")

    bool_cols = X.select_dtypes(include=["bool"]).columns
    X[bool_cols] = X[bool_cols].astype(int)
    return X


def load_xy(csv_path: Path, label: str) -> tuple[pd.DataFrame, pd.Series]:
    """Load master CSV and return (features X, label y) for one pit window."""
    if label not in PIT_LABELS:
        raise ValueError(f"unknown label {label!r}; expected one of {PIT_LABELS}")

    df = pd.read_csv(csv_path)
    y = df[label].astype(int)
    X = _prepare_features(df)
    return X, y


def load_compound_xy(csv_path: Path) -> tuple[pd.DataFrame, pd.Series]:
    """
    Features + next_compound for imminent-stop rows only.

    Training filter (architecture): pit_within_3_laps == 1 and next_compound known.
    """
    df = pd.read_csv(csv_path)
    mask = (df["pit_within_3_laps"] == 1) & df["next_compound"].notna()
    subset = df.loc[mask].copy()
    y = subset["next_compound"].astype(str)
    X = _prepare_features(subset)
    return X, y


def season_split(
    X: pd.DataFrame, y: pd.Series, seasons: pd.Series, val_season: int = 2025
) -> tuple:
    """Train on seasons < val_season, validate on val_season."""
    train_mask = seasons < val_season
    val_mask = seasons == val_season
    return X.loc[train_mask], X.loc[val_mask], y.loc[train_mask], y.loc[val_mask]


def train_pit_window(
    csv_path: Path,
    model_dir: Path,
    label: str,
    val_season: int = 2025,
) -> XGBClassifier:
    """Fit one XGBClassifier for the given pit_within_* label and save it."""
    X, y = load_xy(csv_path, label)
    seasons = X["season"]
    X_train, X_val, y_train, y_val = season_split(X, y, seasons, val_season)

    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="auc",
        tree_method="hist",
        random_state=42,
    )
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_val)[:, 1]
    auc = roc_auc_score(y_val, proba)
    ap = average_precision_score(y_val, proba)
    print(f"\n=== {label} ===")
    print(f"train rows={len(X_train)}  val rows={len(X_val)} (season {val_season})")
    print(f"val positive rate={y_val.mean():.3f}")
    print(f"val ROC-AUC={auc:.3f}  PR-AUC={ap:.3f}")

    model_dir.mkdir(parents=True, exist_ok=True)
    out = model_dir / f"{label}.json"
    model.save_model(out)
    print(f"saved {out}")
    return model


def train_next_compound(
    csv_path: Path,
    model_dir: Path,
    val_season: int = 2025,
) -> XGBClassifier:
    """
    Fit multiclass next_compound on imminent-pit rows; save model + class list.
    """
    X, y = load_compound_xy(csv_path)
    seasons = X["season"]
    X_train, X_val, y_train, y_val = season_split(X, y, seasons, val_season)

    # Integer codes 0..K-1 in a stable order for classes present in training.
    present = [c for c in _COMPOUND_ORDER if c in set(y_train)]
    for c in sorted(set(y_train) - set(present)):
        present.append(c)
    class_to_code = {name: i for i, name in enumerate(present)}
    y_train_code = y_train.map(class_to_code)
    y_val_code = y_val.map(class_to_code)
    # Drop val rows whose class never appeared in train (can't evaluate fairly).
    val_ok = y_val_code.notna()
    X_val = X_val.loc[val_ok]
    y_val = y_val.loc[val_ok]
    y_val_code = y_val_code.loc[val_ok].astype(int)

    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="multi:softprob",
        num_class=len(present),
        eval_metric="mlogloss",
        tree_method="hist",
        random_state=42,
    )
    model.fit(X_train, y_train_code)

    pred_code = model.predict(X_val)
    code_to_class = {i: n for n, i in class_to_code.items()}
    pred = pd.Series(pred_code).map(code_to_class)
    acc = accuracy_score(y_val, pred)
    macro_f1 = f1_score(y_val, pred, average="macro", zero_division=0)

    print("\n=== next_compound ===")
    print("filter: pit_within_3_laps==1 & next_compound not null")
    print(f"train rows={len(X_train)}  val rows={len(X_val)} (season {val_season})")
    print(f"classes={present}")
    print(f"val accuracy={acc:.3f}  macro-F1={macro_f1:.3f}")
    print(classification_report(y_val, pred, zero_division=0))

    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "next_compound.json"
    model.save_model(model_path)
    # Sidecar so inference can map class index → compound name.
    classes_path = model_dir / "next_compound_classes.json"
    classes_path.write_text(json.dumps({"classes": present}, indent=2) + "\n")
    print(f"saved {model_path}")
    print(f"saved {classes_path}")
    return model


def main(argv: Sequence[str] | None = None) -> None:
    """CLI: train pit-window and/or next_compound baselines."""
    parser = argparse.ArgumentParser(description="Train strategy XGBoost baselines.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/processed/driver_laps_all.csv"),
        help="Master driver-lap CSV.",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("data/models"),
        help="Directory for saved model files.",
    )
    parser.add_argument(
        "--val-season",
        type=int,
        default=2025,
        help="Hold out this season for validation (default: 2025).",
    )
    parser.add_argument(
        "--model",
        choices=["pit", "compound", "all"],
        default="all",
        help="Which family to train (default: all).",
    )
    parser.add_argument(
        "--label",
        choices=[*PIT_LABELS, "all"],
        default="all",
        help="Pit window label(s) when --model includes pit (default: all).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.model in ("pit", "all"):
        labels = PIT_LABELS if args.label == "all" else (args.label,)
        for label in labels:
            train_pit_window(args.csv, args.model_dir, label, args.val_season)

    if args.model in ("compound", "all"):
        train_next_compound(args.csv, args.model_dir, args.val_season)


if __name__ == "__main__":
    main()
