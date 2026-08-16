# Training and evaluation

Shared training methodology and commands for the strategy models.

## Data split

Splits are **season-based, not random rows**. Rows from the same race are
highly correlated, so shuffling individual rows leaks race-specific
information. The current implementation trains on seasons before a validation
season and holds out one full season:

```text
training: seasons < val_season
validation: season == val_season  (default 2025)
```

(`season_split` in `src/formula1_strategy_tool/training.py`, `--val-season`
defaults to `2025`.)

## Metrics

- Pit-window models: ROC-AUC and precision-recall AUC (average precision) on
  the validation season.
- Next-compound model: accuracy, macro F1, and a per-class classification
  report.

Race-level evaluation (alerts raised before a real stop, warning lead time,
false-alert rate) is more meaningful than per-row metrics but is not yet
automated.

## Commands

Train everything (three pit models + compound):

```powershell
.\.venv\Scripts\python.exe -m formula1_strategy_tool.training
```

Or use the console script:

```powershell
.\.venv\Scripts\Activate.ps1
f1-train-pit
```

Retrain only the compound model:

```powershell
.\.venv\Scripts\python.exe -m formula1_strategy_tool.training --model compound
```

Train a single pit horizon:

```powershell
.\.venv\Scripts\python.exe -m formula1_strategy_tool.training --model pit --label pit_within_3_laps
```

Defaults: `--csv data/processed/driver_laps_all.csv`,
`--model-dir data/models`, `--val-season 2025`.

## Model artifacts

Output under `data/models/`:

- `pit_within_3_laps.json`
- `pit_within_5_laps.json`
- `pit_within_7_laps.json`
- `next_compound.json`
- `next_compound_classes.json`

## 2026 evaluation

The `is_2026_regulations` feature lets a mixed-era model be evaluated
specifically on 2026 races. Applying larger sample weights to 2026 rows is a
planned experiment, not yet implemented — validate any weight rather than
assuming it.

## Ablation studies

After working baselines exist, run grouped ablations (remove one feature group
at a time and compare validation and race-level metrics). Run separate
ablations for the two model families — a feature may help one target but not
the other. SHAP / XGBoost feature importance can support the analysis but
should not replace ablation testing.

[Back to Model overview](./README.md)
