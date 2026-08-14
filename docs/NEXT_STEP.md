# Next Step

**Done:** all four v1 models trained  
- `pit_within_3/5/7_laps.json`  
- `next_compound.json` (+ `next_compound_classes.json`)

Retrain compound only:
`python -m formula1_strategy_tool.training --model compound`

**Do only this next (pick one):**
1. Inspect feature importances, or  
2. Wire prediction mocks → real `predict_proba` on a historical race replay.
