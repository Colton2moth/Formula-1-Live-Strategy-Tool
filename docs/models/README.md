# Models

Overview of the strategy models the application produces and serves.

## What the application predicts

Two families of supervised models, all built from the same driver-lap feature
table (see [DATA_AND_FEATURES.md](./DATA_AND_FEATURES.md)):

1. **Pit-window models** — three binary XGBoost classifiers that predict
   whether a driver will pit within 3, 5, or 7 laps. See
   [PIT_WINDOW.md](./PIT_WINDOW.md).
2. **Next-compound model** — one multiclass XGBoost classifier that predicts
   which tyre compound (`SOFT` / `MEDIUM` / `HARD` / `INTERMEDIATE` / `WET`)
   will be fitted at the next stop. See [NEXT_COMPOUND.md](./NEXT_COMPOUND.md).

## Relationship between the models

The models are trained separately but operate as a pipeline:

```text
driver-lap features
    → pit-window models → pit probabilities (3 / 5 / 7 laps)
    → next-compound model → next compound + per-class probabilities
```

The next-compound model is trained only on rows where a stop is imminent
(`pit_within_3_laps == 1`), matching how it is used at inference. The current
inference path scores both families for every driver; there is no threshold
that suppresses the compound output.

## Shared feature pipeline

Historical training and live inference call the same feature-building code
(`src/formula1_strategy_tool/training.py::_prepare_features`), which prevents
training/serving mismatch. Feature subsets per model are a later concern; both
families start from the same broad leakage-safe feature set. See
[DATA_AND_FEATURES.md](./DATA_AND_FEATURES.md).

## Model artifacts

Trained models are saved under `data/models/`:

- `pit_within_3_laps.json`
- `pit_within_5_laps.json`
- `pit_within_7_laps.json`
- `next_compound.json`
- `next_compound_classes.json` (class-index → compound-name sidecar)

Inference loads these with `src/formula1_strategy_tool/inference.py`.

## Where to look

- [Pit-window models](./PIT_WINDOW.md)
- [Next-compound model](./NEXT_COMPOUND.md)
- [Features and leakage](./DATA_AND_FEATURES.md)
- [Training and evaluation](./TRAINING.md)
- [Driver-lap schema](../data/DRIVER_LAP_SCHEMA.md)

[Back to Documentation](../README.md)
