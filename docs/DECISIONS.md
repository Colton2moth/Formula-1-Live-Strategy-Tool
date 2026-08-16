# Design Decisions

Record important choices here so they are not silently changed.

Full modelling plan: [models/README.md](models/README.md).

## D001 — Backend owns OpenF1 access

The frontend communicates only with our backend.

Reason:

- protects OpenF1 credentials;
- avoids duplicate OpenF1 connections;
- keeps feature generation and state management centralized.

## D002 — Lap-level baseline

The modelling table uses one row per driver per completed lap.

Reason:

- strategy decisions are naturally lap-based;
- endpoint data is easier to align at lap boundaries;
- it is simpler than high-frequency telemetry modelling.

## D003 — Multi-horizon pit-window targets

Each driver-lap row carries three binary labels:

```text
pit_within_3_laps
pit_within_5_laps
pit_within_7_laps
```

Windows: `PIT_WINDOWS = (3, 5, 7)`.

Reason:

- short / medium / longer warning horizons for the UI;
- nested labels (if within 3, then also within 5 and 7) are easy to reason about;
- still simpler than exact pit-lap regression.

Previously the docs used a single 5-lap then single 3-lap target; v1 now uses all three.

## D004 — No historical location data

Location data is used only for live visualization initially.

Reason:

- it is not required for the first strategy models;
- excluding it reduces download and storage volume.

## D005 — No historical car telemetry initially

`car_data` is deferred for the first baselines.

Reason:

- large dataset;
- uncertain value for the first baseline;
- lap, stint, pit, interval, weather, and race-control data are more directly relevant.

Telemetry *summary* features remain a later option (see models/DATA_AND_FEATURES.md). Do not invent them without downloading `car_data`.

## D006 — Raw JSON first

Historical API responses are stored unchanged as JSON.

Reason:

- easy to inspect;
- easy to reproduce processing;
- avoids another API download when processing changes.

## D007 — Simplicity before production architecture

No database, Redis, Docker, message queue, or microservices initially.

Reason:

- none are required to understand or build the first models.

## D008 — Four XGBoost models (three pit + one compound)

Train models that share one processed driver-lap feature matrix:

1. **Pit-within-3** — XGBoost binary (`binary:logistic`)
2. **Pit-within-5** — XGBoost binary (`binary:logistic`)
3. **Pit-within-7** — XGBoost binary (`binary:logistic`)
4. **Next-compound** — XGBoost multiclass (`multi:softprob`)

Pit models use (almost) identical features and differ only by label column.

Compound classes: `SOFT`, `MEDIUM`, `HARD`, `INTERMEDIATE`, `WET`.

Reason:

- multi-horizon pit probabilities for the UI;
- separate small binary models are easy to understand and debug;
- compound stays a focused multiclass task.

## D009 — Compound model trains on imminent pit rows

Initially train the next-compound model on rows where:

```text
pit_within_3_laps == 1
```

Reason:

- matches live usage (compound prediction when a stop is likely);
- increases focus on strategically relevant rows;
- alternatives (final pre-stop lap only, wider window) can be tested later.

## D010 — Race-based splits, not random row splits

Train / validation / test by complete races (or walk-forward), never by shuffling individual driver-lap rows.

Reason:

- rows in the same race are highly correlated;
- random splits leak race-specific information.

## D011 — Regulation-era feature from the start

Include `season` and `is_2026_regulations` (season >= 2026) in the shared feature table.

Reason:

- 2026 regulations change tyre and strategy patterns;
- allows mixed-era training with optional 2026 sample weighting.

## D012 — Skip cancelled / empty races in training

Do not train on races with no usable timing data, including:

- 2023 Emilia-Romagna (Italy) — cancelled (flooding)
- 2026 Bahrain — cancelled
- 2026 Saudi Arabia — cancelled

Reason:

- OpenF1 may retain session metadata but return 404 / empty for laps and related endpoints.

## D013 — Wide driver-lap table, select features later

Build one wide processed table with all agreed columns in [data/DRIVER_LAP_SCHEMA.md](data/DRIVER_LAP_SCHEMA.md), then pick feature subsets per model (and ablate later).

Reason:

- avoids premature feature guessing;
- one processing pipeline serves three pit models + compound;
- matches the two-model architecture “broad then ablate” philosophy.

Exclude telemetry and unavailable track scores until we have real sources.
