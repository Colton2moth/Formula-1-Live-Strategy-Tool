# Formula 1 Live Strategy Tool — Two-Model Architecture

## 1. Project Goal

Build two machine-learning models for a live Formula 1 strategy application:

1. **Pit-Window Model**
   - Predicts whether a driver will pit within the next `N` laps.
   - Initial recommendation: use `N = 3`.

2. **Next-Compound Model**
   - Predicts which tyre compound the driver will use at their next pit stop.
   - Initial classes:
     - `SOFT`
     - `MEDIUM`
     - `HARD`
     - `INTERMEDIATE`
     - `WET`

The models should operate from the same processed driver-lap dataset, but each model may ultimately use a different subset of features.

The initial development philosophy is:

> Start with a broad, leakage-safe feature set, build working baselines, and use ablation studies later to determine which feature groups are genuinely useful.

---

## 2. Core Dataset Structure

Use **one row per driver per completed lap**.

Each row represents the state of one driver's race immediately after completing a lap.

Example:

| session_key | driver_number | lap_number | compound | tyre_age | gap_ahead | recent_pace_delta | pit_within_3_laps | next_compound |
|---|---:|---:|---|---:|---:|---:|---:|---|
| 9158 | 4 | 25 | MEDIUM | 18 | 2.4 | 0.41 | 1 | HARD |

The feature values must only contain information that would have been available live at that point in the race.

### Primary identifiers

Identifiers should be preserved for grouping, joining, debugging, and train/test splitting, but should not automatically be passed into the models.

Recommended identifiers:

- `session_key`
- `meeting_key`
- `season`
- `round_number`
- `driver_number`
- `team_name`
- `lap_number`
- `timestamp`

Avoid treating raw identifiers such as `driver_number` or `session_key` as normal predictive features.

---

## 3. Shared Processing Pipeline

Both models should use the same general data pipeline:

```text
Raw OpenF1 data
        |
        v
Session-level data joins
        |
        v
Driver-lap feature table
        |
        v
Leakage-safe rolling and historical features
        |
        v
Model-specific labels
        |
        +--------------------------+
        |                          |
        v                          v
Pit-window dataset       Next-compound dataset
        |                          |
        v                          v
Pit-window model         Compound model
```

The shared feature table should be built once. Model-specific training datasets can then select different rows, labels, and feature columns.

---

## 4. Model 1: Pit-Window Model

## 4.1 Objective

Predict whether the driver will make a pit stop within the next `N` laps.

Initial target:

```python
PIT_WINDOW_LAPS = 3
```

Binary label:

```python
pit_within_3_laps = 1
```

when the driver pits on one of the next three laps, otherwise:

```python
pit_within_3_laps = 0
```

### Example

If a driver pits on lap 28:

- Lap 25: positive
- Lap 26: positive
- Lap 27: positive
- Lap 28: normally excluded or handled separately because the stop is already occurring
- Earlier laps: negative

The exact convention must be consistent throughout label generation and evaluation.

---

## 4.2 Initial Model Type

Use an XGBoost binary classifier.

Suggested starting point:

```python
from xgboost import XGBClassifier

model = XGBClassifier(
    objective="binary:logistic",
    eval_metric="aucpr",
    n_estimators=300,
    max_depth=5,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
)
```

These are baseline values only. Hyperparameter tuning should happen after the full pipeline works.

---

## 4.3 Candidate Features

### Race-state features

- `lap_number`
- `total_laps`
- `laps_remaining`
- `race_progress`
- `current_position`
- `number_of_pit_stops`
- `laps_since_last_pit`
- `current_stint_number`

### Tyre and stint features

- `current_compound`
- `tyre_age`
- `stint_length`
- `compound_laps_remaining_estimate`
- `is_new_tyre`, if available
- `current_compound_usage_count`

### Pace features

- `current_lap_time`
- `previous_lap_time`
- `rolling_mean_lap_time_3`
- `rolling_mean_lap_time_5`
- `rolling_median_lap_time_3`
- `pace_delta_to_stint_best`
- `pace_delta_to_recent_average`
- `degradation_slope`
- `sector_1_delta`
- `sector_2_delta`
- `sector_3_delta`

Rolling features must use trailing windows only.

### Traffic and gap features

- `gap_to_driver_ahead`
- `gap_to_driver_behind`
- `interval_to_driver_ahead`
- `interval_to_driver_behind`
- `estimated_clean_air_after_pit`
- `cars_within_pit_window`
- `position_change_recent`
- `traffic_density_near_driver`

### Race-control features

- `safety_car_active`
- `virtual_safety_car_active`
- `yellow_flag_active`
- `red_flag_recent`
- `race_control_phase`

### Weather features

- `rainfall`
- `air_temperature`
- `track_temperature`
- `humidity`
- `wind_speed`
- `weather_change_recent`
- `track_temperature_trend`

### Telemetry summary features

Raw telemetry should generally be aggregated to driver-lap summaries.

Possible features:

- `mean_speed`
- `max_speed`
- `mean_throttle`
- `full_throttle_percentage`
- `braking_percentage`
- `mean_rpm`
- `drs_usage_percentage`
- `energy_deployment_summary`, if derivable
- `telemetry_missing_percentage`

### Regulation and season features

- `season`
- `regulation_era`
- `is_2026_regulations`
- `race_number_within_season`

Example encoding:

```python
is_2026_regulations = int(season >= 2026)
```

A categorical alternative is:

```text
GROUND_EFFECT_2022_2025
REGULATIONS_2026_PLUS
```

For the first implementation, a binary flag is sufficient.

### Track-context features

- `circuit_key`
- `pit_lane_loss_estimate`
- `historical_stop_count_at_track`
- `track_overtaking_difficulty`
- `track_degradation_category`

Track-level features must be derived only from prior races or static circuit information. Do not calculate them using the result of the race currently being predicted.

---

## 4.4 Class Imbalance

Most driver-lap rows will not be within three laps of a pit stop, so the target will be imbalanced.

Possible treatments:

- XGBoost `scale_pos_weight`
- Per-row sample weights
- Negative downsampling
- Probability threshold tuning
- Precision-recall-focused evaluation

Example:

```python
positive_count = y_train.sum()
negative_count = len(y_train) - positive_count
scale_pos_weight = negative_count / positive_count
```

Do not judge this model using accuracy alone.

---

## 4.5 Pit-Window Evaluation

Recommended metrics:

- Precision-recall AUC
- ROC AUC
- Precision
- Recall
- F1 score
- Brier score
- Calibration curve
- False alerts per driver-race
- Percentage of actual stops detected
- Average warning time before a stop

Race-level evaluation is particularly important.

Example race-level questions:

- Did the model raise an alert before the actual stop?
- How many laps before the stop did the first valid alert occur?
- How many false alerts were produced during the race?
- Were probabilities well calibrated?

---

## 5. Model 2: Next-Compound Model

## 5.1 Objective

Predict the tyre compound used at the driver's next pit stop.

Multiclass target:

```text
SOFT
MEDIUM
HARD
INTERMEDIATE
WET
```

The model should predict the next compound only when a future pit stop exists.

---

## 5.2 Training Row Selection

Unlike the pit-window model, the compound model should not necessarily be trained on every driver-lap row.

Recommended initial approach:

Train it only on rows where:

```python
pit_within_3_laps == 1
```

This makes the task:

> Given that a pit stop is likely soon, which compound will be fitted?

This also matches how the models will be connected during live inference.

Alternative approaches can be tested later:

- Use only the final lap before each pit stop
- Use all rows within the pit window
- Weight rows more heavily as the stop approaches
- Train on a larger window such as five laps before a stop

Begin with all positive pit-window rows because this provides more training examples.

---

## 5.3 Initial Model Type

Use an XGBoost multiclass classifier.

```python
from xgboost import XGBClassifier

model = XGBClassifier(
    objective="multi:softprob",
    eval_metric="mlogloss",
    n_estimators=300,
    max_depth=5,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
)
```

Encode compound labels using a stable label mapping.

Example:

```python
COMPOUND_TO_CLASS = {
    "SOFT": 0,
    "MEDIUM": 1,
    "HARD": 2,
    "INTERMEDIATE": 3,
    "WET": 4,
}
```

---

## 5.4 Candidate Features

The compound model can begin with the same broad feature table as the pit-window model.

However, the following features are expected to be especially important.

### Remaining-distance features

- `laps_remaining`
- `race_progress`
- `expected_next_stint_length`
- `estimated_laps_to_finish_after_stop`

### Tyre-history features

- `current_compound`
- `previous_compound`
- `compounds_used_so_far`
- `has_used_soft`
- `has_used_medium`
- `has_used_hard`
- `has_used_two_dry_compounds`
- `current_stint_length`
- `number_of_pit_stops`

### Weather features

- `rainfall`
- `rainfall_trend`
- `track_temperature`
- `air_temperature`
- `weather_change_recent`
- `wet_track_likelihood`

### Strategy-context features

- `safety_car_active`
- `virtual_safety_car_active`
- `gap_to_driver_ahead`
- `gap_to_driver_behind`
- `estimated_clean_air_after_pit`
- `expected_stint_length`
- `current_position`
- `track_degradation_category`

### Regulation features

- `season`
- `regulation_era`
- `is_2026_regulations`

The regulation feature may be especially relevant for compound prediction because regulation changes can affect tyre behaviour, stint length, overtaking, and strategy patterns.

### Tyre-set availability

Actual available tyre sets would be valuable, but this data may not be reliably available through OpenF1.

If tyre-set availability is unavailable:

- Do not invent it.
- Document the limitation.
- Allow the model to infer likely availability from stint and compound history.
- Add a future integration point for official or manually supplied tyre-set data.

---

## 5.5 Compound-Class Imbalance

Dry compounds will likely dominate the dataset, while intermediate and wet examples will be rare.

Potential treatments:

- Per-class sample weights
- Separate dry and wet models later
- Grouped two-stage prediction:
  1. Dry versus wet-weather tyre
  2. Specific compound
- Macro F1 evaluation
- Stratified reporting by weather condition

For the initial version, keep one multiclass model and measure performance before increasing complexity.

---

## 5.6 Compound Evaluation

Recommended metrics:

- Macro F1
- Weighted F1
- Per-class precision
- Per-class recall
- Multiclass log loss
- Confusion matrix
- Top-2 accuracy
- Probability calibration by class

Top-2 accuracy is useful because the model may assign strong probabilities to two strategically plausible compounds.

Example prediction:

```json
{
  "predicted_compound": "HARD",
  "compound_probabilities": {
    "SOFT": 0.03,
    "MEDIUM": 0.28,
    "HARD": 0.66,
    "INTERMEDIATE": 0.02,
    "WET": 0.01
  }
}
```

---

## 6. Relationship Between the Models

The models should initially operate as a pipeline.

```text
Current driver-lap features
            |
            v
Pit-window model
            |
            v
Probability of pitting within 3 laps
            |
            +---- below threshold ----> Do not produce an active pit prediction
            |
            +---- above threshold ----> Run compound model
                                        |
                                        v
                              Predicted next compound
```

Example live result:

```json
{
  "driver_number": 4,
  "lap_number": 31,
  "pit_window_laps": 3,
  "pit_probability": 0.72,
  "predicted_compound": "HARD",
  "compound_probabilities": {
    "SOFT": 0.04,
    "MEDIUM": 0.21,
    "HARD": 0.75
  }
}
```

The API should still be able to expose the raw compound probabilities even if the pit probability is below the display threshold. This is useful for debugging and experimentation.

---

## 7. Shared Features Versus Model-Specific Features

Start by supplying both models with the full leakage-safe feature set.

Later, define model-specific feature lists:

```python
SHARED_FEATURES = [
    # race state
    # tyre state
    # pace
    # gaps
    # race control
    # weather
    # regulation era
]

PIT_MODEL_FEATURES = SHARED_FEATURES + [
    "degradation_slope",
    "laps_since_last_pit",
    "pace_delta_to_stint_best",
]

COMPOUND_MODEL_FEATURES = SHARED_FEATURES + [
    "laps_remaining",
    "compounds_used_so_far",
    "has_used_two_dry_compounds",
    "expected_next_stint_length",
]
```

Do not optimize feature subsets before a reliable baseline exists.

---

## 8. Leakage Rules

The following rules are mandatory.

### Never use future information

A row at lap 25 cannot contain information from lap 26 or later.

Do not use:

- Eventual finishing position
- Actual next compound as a feature
- Actual next pit lap as a feature
- Future lap times
- Full-race summary statistics
- Race-level averages calculated using future laps
- Features generated using centred rolling windows
- Final weather conditions
- Future Safety Car periods

### Rolling features

All rolling features must be trailing.

Correct:

```python
df["rolling_mean_lap_time_3"] = (
    df.groupby(["session_key", "driver_number"])["lap_duration"]
      .transform(lambda s: s.rolling(3, min_periods=1).mean())
)
```

Be careful whether the current lap should be included. For live inference immediately after a lap completes, including the completed current lap is valid.

### Static historical features

Track- or team-level historical features must only use races before the race represented by the row.

---

## 9. Train, Validation, and Test Splitting

Do not randomly split individual rows.

Rows from the same race are highly correlated. Random row splitting would leak race-specific information between training and validation.

Split by complete sessions or races.

Recommended first split:

```text
Training:   2023–2024
Validation: selected 2025 races
Test:       remaining 2025 races
```

Once sufficient 2026 data exists:

```text
Training:   2023–2025 plus early 2026
Validation: held-out 2026 races
Test:       later held-out 2026 races
```

Another option is walk-forward validation:

```text
Train on races 1..K
Validate on race K+1
Repeat through the season
```

This better approximates real deployment but is more expensive.

---

## 10. Handling the 2026 Regulation Change

Include a regulation-era feature from the beginning.

```python
df["is_2026_regulations"] = (df["season"] >= 2026).astype(int)
```

Initial plan:

1. Train on all available data from 2023 onward.
2. Include `season` and `is_2026_regulations`.
3. Evaluate performance specifically on 2026 races.
4. Optionally apply moderately larger sample weights to 2026 rows.
5. Gradually reduce reliance on older data as more 2026 races become available.
6. Compare a mixed-era model against a dedicated 2026 model later.

Example weighting:

```python
df["sample_weight"] = 1.0
df.loc[df["season"] == 2026, "sample_weight"] = 2.0
```

The exact weight must be validated rather than assumed.

---

## 11. Ablation Study Plan

After working baselines exist, run grouped ablation studies.

Suggested feature groups:

1. Race state
2. Tyre and stint state
3. Pace and degradation
4. Gaps and traffic
5. Telemetry summaries
6. Weather
7. Race control
8. Track context
9. Regulation era
10. Driver or team history, if added

For each experiment:

```text
Train baseline with all features
Train again with one feature group removed
Compare validation and race-level metrics
```

Example experiment table:

| Experiment | Removed group | PR AUC | Recall | False alerts/race | Macro F1 |
|---|---|---:|---:|---:|---:|
| Baseline | None | ... | ... | ... | ... |
| A1 | Regulation era | ... | ... | ... | ... |
| A2 | Telemetry | ... | ... | ... | ... |
| A3 | Weather | ... | ... | ... | ... |
| A4 | Traffic and gaps | ... | ... | ... | ... |

Run separate ablation studies for the two models because a feature may be valuable for one target but not the other.

After grouped ablations, individual-feature ablations can be run for the most promising groups.

SHAP or XGBoost feature importance can support analysis, but they should not replace ablation testing.

---

## 12. Suggested Project Structure

```text
project/
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
│
├── models/
│   ├── pit_window/
│   └── next_compound/
│
├── notebooks/
│   ├── data_validation.ipynb
│   ├── pit_window_baseline.ipynb
│   └── compound_baseline.ipynb
│
├── src/
│   ├── data/
│   │   ├── load_data.py
│   │   ├── build_driver_laps.py
│   │   ├── build_labels.py
│   │   └── validate_data.py
│   │
│   ├── features/
│   │   ├── race_features.py
│   │   ├── tyre_features.py
│   │   ├── pace_features.py
│   │   ├── traffic_features.py
│   │   ├── weather_features.py
│   │   ├── telemetry_features.py
│   │   └── feature_pipeline.py
│   │
│   ├── training/
│   │   ├── split_data.py
│   │   ├── train_pit_window.py
│   │   ├── train_compound.py
│   │   ├── evaluate_pit_window.py
│   │   ├── evaluate_compound.py
│   │   └── ablation.py
│   │
│   ├── inference/
│   │   ├── load_models.py
│   │   ├── predict_pit_window.py
│   │   ├── predict_compound.py
│   │   └── strategy_pipeline.py
│   │
│   ├── api/
│   │   ├── main.py
│   │   ├── schemas.py
│   │   └── routes.py
│   │
│   └── config.py
│
├── tests/
│   ├── test_labels.py
│   ├── test_features.py
│   ├── test_splits.py
│   └── test_inference.py
│
├── requirements.txt
└── README.md
```

This is a target structure, not a requirement for the first commit.

For the first implementation, keep the code simple and split files only when responsibilities become clear.

---

## 13. Recommended Implementation Order

### Phase 1: Validate the acquired data

1. Confirm all required tables are present.
2. Confirm race, driver, stint, lap, weather, position, and race-control keys join correctly.
3. Check missing data rates.
4. Check timestamp and lap alignment.
5. Confirm pit stops and compound changes can be identified reliably.

### Phase 2: Build the driver-lap table

1. Create one row per driver per completed lap.
2. Add race-state features.
3. Add tyre and stint features.
4. Add trailing pace features.
5. Add gap and position features.
6. Add weather and race-control features.
7. Add telemetry summaries.
8. Add season and regulation-era features.
9. Save the processed feature table.

### Phase 3: Generate labels

1. Detect each driver's next pit lap.
2. Generate `pit_within_3_laps`.
3. Generate `next_compound`.
4. Exclude rows where no valid future stop exists from compound training.
5. Add tests for known example races.

### Phase 4: Train simple baselines

1. Train a basic pit-window XGBoost model.
2. Evaluate on held-out races.
3. Train a basic compound XGBoost model.
4. Evaluate with macro F1 and a confusion matrix.
5. Save both models and their feature lists.

### Phase 5: Build combined inference

1. Accept one processed driver-lap row.
2. Produce pit probability.
3. If above the configured threshold, produce compound probabilities.
4. Return a combined structured prediction.

### Phase 6: Improve the models

1. Tune thresholds.
2. Tune class weights.
3. Tune XGBoost parameters.
4. Run grouped ablations.
5. Add SHAP analysis.
6. Evaluate 2026 weighting.
7. Add probability calibration.
8. Add live OpenF1 integration.

---

## 14. Minimal First Milestone

The first useful milestone should be intentionally small.

Deliverables:

- One processed CSV or Parquet file with one row per driver-lap
- A working `pit_within_3_laps` label
- A working `next_compound` label
- One race-based train/validation split
- One baseline pit-window model
- One baseline compound model
- Basic evaluation output
- Saved model files
- One function that runs both models for a single row

Example interface:

```python
def predict_strategy(driver_lap_features: dict) -> dict:
    pit_probability = predict_pit_probability(driver_lap_features)

    result = {
        "pit_probability": pit_probability,
        "pit_window_laps": 3,
        "predicted_compound": None,
        "compound_probabilities": None,
    }

    if pit_probability >= PIT_THRESHOLD:
        compound_prediction = predict_next_compound(driver_lap_features)
        result.update(compound_prediction)

    return result
```

Do not begin with live API integration, complex simulation, or exact pit-lap regression. First prove that the two supervised-learning targets can be built and evaluated correctly.

---

## 15. Important Open Design Decisions

These should be made during implementation and documented.

- Should the pit target use 2, 3, or 5 laps?
- Should the compound model train on every positive pit-window row or only the final pre-stop row?
- How should laps under Safety Car be represented in pace features?
- How should missing interval and telemetry values be handled?
- Should red-flag tyre changes count as pit stops?
- How should first-lap stops and retirement-related stops be handled?
- Should intermediate and wet compounds remain in the same multiclass model?
- How should 2026 samples be weighted?
- Which threshold should trigger an active pit warning?
- Should driver and team history be added later?

Start with explicit simple rules, then revise them based on validation results.

---

## 16. Instructions for Cursor

When implementing this architecture:

1. Work one stage at a time.
2. Do not generate the entire project at once.
3. Begin by inspecting the available processed and raw data schemas.
4. Before writing label-generation code, clearly define the pit-stop conventions.
5. Keep all features leakage-safe.
6. Use complete races for train, validation, and test splits.
7. Add small tests for feature and label logic.
8. Keep feature generation separate from model training.
9. Save the exact feature list with each trained model.
10. Prefer clear, short functions over premature abstraction.
11. Do not add unnecessary edge-case handling until the baseline pipeline works.
12. Explain each implementation step before moving to the next one.

The immediate next task should be:

> Inspect the acquired dataset, identify the tables and columns needed to construct one row per driver per lap, and propose the first version of the driver-lap schema before writing the full feature pipeline.
