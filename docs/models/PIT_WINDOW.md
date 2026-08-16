# Pit-window models

Predict whether a driver will make a pit stop within the next `N` laps.

## Objective

Three binary classifiers share the same features and differ only by label
horizon (see decision D003 / D008):

| Label | Meaning |
|-------|---------|
| `pit_within_3_laps` | 1 if the driver pits within the next 3 laps, else 0 |
| `pit_within_5_laps` | 1 if the driver pits within the next 5 laps, else 0 |
| `pit_within_7_laps` | 1 if the driver pits within the next 7 laps, else 0 |

The labels are nested (within 3 ⇒ within 5 ⇒ within 7), which gives the UI
short/medium/long warning horizons. `PIT_WINDOWS = (3, 5, 7)` in
`src/formula1_strategy_tool/training.py`.

## Model type

One XGBoost binary classifier per horizon (`objective="binary:logistic"`).
Current baseline hyperparameters:

```python
XGBClassifier(
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
```

These are baseline values; hyperparameter tuning comes after the full pipeline
is stable.

## Class imbalance

Most driver-lap rows are not within a few laps of a stop, so the positive
class is rare. Do not judge the pit models by accuracy alone. Possible
treatments (not yet applied): `scale_pos_weight`, per-row sample weights,
negative downsampling, and probability-threshold tuning.

## Features

The pit models start from the full leakage-safe feature set; see
[DATA_AND_FEATURES.md](./DATA_AND_FEATURES.md). Pit-relevant groups include
race state, tyre/stint state, pace, and race control.

## Evaluation

Reported per horizon at train time:

- ROC-AUC
- Precision-recall AUC (average precision)

Race-level evaluation is more meaningful than per-row metrics: whether the
model raised an alert before the actual stop, how many laps of warning it gave,
and how many false alerts it produced.

## Output

Each model emits a probability in `[0, 1]`. The API exposes all three as
`pit_within_3_laps`, `pit_within_5_laps`, and `pit_within_7_laps` (see
[../api/CONTRACT.md](../api/CONTRACT.md)).

[Back to Model overview](./README.md)
