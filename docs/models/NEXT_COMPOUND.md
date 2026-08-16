# Next-compound model

Predict which tyre compound a driver will use at their next pit stop.

## Objective

Multiclass classification over five compound classes:

```text
SOFT | MEDIUM | HARD | INTERMEDIATE | WET
```

The model should only be asked to predict when a future stop exists (see
training-row selection below).

## Training-row selection

Unlike the pit-window models, the compound model is not trained on every
driver-lap row. It is trained only on rows where:

```python
pit_within_3_laps == 1   and   next_compound is known
```

This reframes the task as "given that a stop is imminent, which compound will
be fitted?", which matches live usage. Alternatives (final pre-stop lap only,
wider windows) can be explored later.

## Model type

One XGBoost multiclass classifier (`objective="multi:softprob"`). Current
baseline hyperparameters:

```python
XGBClassifier(
    n_estimators=100,
    max_depth=4,
    learning_rate=0.08,
    subsample=0.9,
    colsample_bytree=0.9,
    objective="multi:softprob",
    num_class=len(present_classes),
    eval_metric="mlogloss",
    tree_method="hist",
    random_state=42,
)
```

Compound labels are encoded to integer codes with a stable order; the mapping
is written to `next_compound_classes.json` so inference maps class index back
to a compound name.

## Class imbalance

Dry compounds dominate; `INTERMEDIATE` and `WET` are rare. The current version
keeps one multiclass model and measures performance before increasing
complexity. Possible later treatments: per-class weights, separate dry/wet
models, or a two-stage dry-vs-wet then specific-compound prediction.

## Features

The compound model starts from the same broad feature table, with a few
groups especially relevant: remaining distance, tyre history, weather, and
strategy context. See [DATA_AND_FEATURES.md](./DATA_AND_FEATURES.md). Actual
available tyre-set data is not reliably in OpenF1 — do not invent it.

## Evaluation

Reported at train time:

- accuracy
- macro F1
- per-class classification report

Top-2 accuracy is also useful because the model may assign strong probability
to two strategically plausible compounds.

## Output

The model emits a per-class probability distribution plus the argmax compound.
The API exposes `predicted_next_compound` (string) and `compound_probabilities`
(map of the five classes), which may be `null` when a stop is not imminent (see
[../api/CONTRACT.md](../api/CONTRACT.md)).

[Back to Model overview](./README.md)
