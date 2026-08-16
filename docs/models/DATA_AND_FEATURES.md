# Data and features

Shared feature-engineering concerns for both model families. The full column
list lives in [../data/DRIVER_LAP_SCHEMA.md](../data/DRIVER_LAP_SCHEMA.md);
this file records the rules the pipeline must follow.

## Grain

One row = one driver at the end of one completed lap. Each row represents the
state of one driver's race immediately after completing a lap.

## Shared feature generation

Historical training and live inference call the same feature-building code
(`_prepare_features` in `src/formula1_strategy_tool/training.py`). Both model
families start from the same broad leakage-safe feature set; model-specific
feature subsets are refined later, not guessed up front.

## Feature categories

- race state (lap, position, pit count, laps since last pit)
- tyre / stint (compound, tyre age, stint length, compounds used so far)
- pace (trailing rolling windows only)
- gaps / traffic
- weather
- race control
- season / regulation era (`season`, `is_2026_regulations`)

## Identifiers vs model features

Identifiers (`session_key`, `meeting_key`, `driver_number`, `date_start`,
`as_of`, …) are kept for joins, grouping, and splitting, but are excluded from
the model feature matrix. `training._EXCLUDE` lists the columns that are
never model inputs.

## Leakage rules

Mandatory:

- A row at lap N may only use information available at or before lap N.
- Never use future outcomes as features: eventual finishing position, the
  actual next compound, the actual next pit lap, future lap times, full-race
  summary statistics, final weather, or future Safety Car periods.
- All rolling features must be **trailing** (never centred).
- Track/team-level historical features must only use races before the race
  represented by the row.

## Trailing rolling windows

Rolling pace features (`rolling_mean_lap_time_3`, `rolling_median_lap_time_5`,
etc.) are computed with a trailing window per driver, for example:

```python
df["rolling_mean_lap_time_3"] = (
    df.groupby(["session_key", "driver_number"])["lap_duration"]
      .transform(lambda s: s.rolling(3, min_periods=1).mean())
)
```

Be consistent about whether the just-completed lap is included: for live
inference immediately after a lap completes, including it is valid.

## Race-control and weather data

Race-control and weather features are joined as-of the current lap, so a lap
only sees conditions known at that point in the race.

## Regulation-era features

`season` and `is_2026_regulations` (`season >= 2026`) are included from the
start so mixed-era training is possible and 2026 behaviour can be evaluated
separately.

## Unavailable features

Do not invent features that have no real source:

- telemetry summaries (requires `car_data`, not downloaded)
- track scores (pit-lane loss, overtaking difficulty)
- tyre-set availability (not reliably in OpenF1)

If a feature is unavailable, document the limitation and let the model infer
from available history instead.

[Back to Model overview](./README.md)
