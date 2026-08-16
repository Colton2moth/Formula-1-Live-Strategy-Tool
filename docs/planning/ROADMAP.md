# Project Roadmap

Committed development direction and current status. Uncommitted ideas live in
[FEATURE_IDEAS.md](./FEATURE_IDEAS.md); recorded decisions in
[../DECISIONS.md](../DECISIONS.md).

## Current priority

All four v1 models are trained (`pit_within_3/5/7_laps.json`,
`next_compound.json`), the FastAPI prediction path serves real model output,
and live ingestion + the replay harness exercise the full stack.

Next, focus on model evaluation and improvement:

1. Inspect feature importances for the trained models.
2. Run grouped ablation studies (see [../models/TRAINING.md](../models/TRAINING.md)).
3. Tune thresholds, class weights, and XGBoost hyperparameters.
4. Add probability calibration before exposing calibrated values to the
   frontend.

Retrain only the compound model with:

```powershell
.\.venv\Scripts\python.exe -m formula1_strategy_tool.training --model compound
```

## Status by phase

| Phase | Goal | Status |
|-------|------|--------|
| 1. Data acquisition | Download and understand raw OpenF1 race data | Done |
| 2. One-race processing | One row per driver per completed lap | Done |
| 3. Training dataset | Process all usable races into a consistent table | Done |
| 4. Baseline models | Train and evaluate two XGBoost families | Done (3 pit + 1 compound) |
| 5. Combined inference + API | Serve predictions from saved artifacts | Done (real model output, replay first) |
| 6. Live integration | Process a live OpenF1 session | Done (MQTT listener, WebSocket, live bootstrap) |
| 7. Model improvement + frontend data | Tune models, stream live map data | In progress |

## Remaining work (Phase 7)

- threshold / class-weight / hyperparameter tuning;
- grouped ablation studies;
- 2026 sample-weighting experiments;
- probability calibration;
- feature-importance review.

Only start a phase when the previous phase works and is understood.

[Back to Documentation](../README.md)
