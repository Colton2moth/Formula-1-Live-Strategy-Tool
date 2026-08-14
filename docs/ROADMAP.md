# Project Roadmap

## Phase 1: Data acquisition

Goal: download and understand raw OpenF1 race data.

Tasks:

- create project structure;
- download one race;
- inspect each endpoint;
- make the downloader resumable;
- download completed races from 2023 onward;
- document cancelled / empty races to skip in training.

Status: largely done (see data audit). Mock REST API exists for frontend work.

## Phase 2: One-race processing

Goal: create one row per driver per completed lap.

Tasks:

- load raw files;
- establish timeline and joins;
- determine current stint and tyre age;
- add position, intervals, weather, and race-control state;
- add season / `is_2026_regulations`;
- verify several rows manually.

## Phase 3: Training dataset

Goal: process all usable races consistently.

Tasks:

- reuse the one-race logic;
- create `pit_within_3_laps` labels;
- create `next_compound` labels;
- prevent future-data leakage (trailing windows only);
- skip cancelled races (D012);
- save the processed table (CSV or Parquet).

## Phase 4: Baseline models

Goal: train and evaluate two XGBoost baselines.

Tasks:

- split by race / season (not random rows);
- train pit-window binary classifier;
- train next-compound multiclass classifier (on imminent-pit rows);
- evaluate with PR-AUC / recall / calibration (pit) and macro F1 / confusion matrix (compound);
- save both models and their feature lists.

## Phase 5: Combined inference + API

Goal: serve predictions from saved model artifacts.

Tasks:

- `predict_strategy(row)` — pit probability, then compound if above threshold;
- create / extend FastAPI prediction endpoints;
- validate input features;
- replace mock prediction payloads with model output (replay first).

## Phase 6: Live integration

Goal: process a live OpenF1 session.

Tasks:

- connect to paid OpenF1 stream;
- maintain race and driver state;
- reuse the feature builder;
- run both models after important updates;
- serve live state through REST and WebSocket.

## Phase 7: Model improvement + frontend data

Goal: improve models and support the GUI.

Tasks:

- threshold / class-weight / hyperparameter tuning;
- grouped ablation studies;
- 2026 sample weighting experiments;
- stream live locations and track-map data;
- expose calibrated probabilities to the frontend.

Only start a phase when the previous phase works and is understood.

Immediate next task (from TWO_MODEL_ARCHITECTURE.md):

> Inspect the acquired dataset, identify the tables and columns needed to construct one row per driver per lap, and propose the first version of the driver-lap schema before writing the full feature pipeline.
