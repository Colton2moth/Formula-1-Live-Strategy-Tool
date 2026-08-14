# Backend Architecture

See also: [TWO_MODEL_ARCHITECTURE.md](TWO_MODEL_ARCHITECTURE.md) for full modelling detail.

## 1. Historical data acquisition

Downloads completed sessions from the free OpenF1 REST API.

```text
OpenF1
→ one endpoint for one session
→ raw JSON file
```

Raw files are stored unchanged so they can be processed again without another API request.

Skip cancelled / data-less races when building training sets (e.g. 2023 Emilia-Romagna, 2026 Bahrain, 2026 Saudi Arabia).

## 2. Historical processing

Combines separate endpoint data into a lap-level feature table.

One processed row represents:

```text
one driver
at the end of one completed lap
```

Example feature groups:

- race state (lap, position, pit count)
- tyre / stint (compound, tyre age)
- pace (trailing rolling windows only)
- gaps / traffic
- weather
- race control
- season / regulation era (`is_2026_regulations`)

Identifiers (`session_key`, `driver_number`, etc.) are kept for joins and splits but are not model features.

## 3. Labels (two models)

Both models share the same processed driver-lap table, then use different labels / row filters.

### Model 1 — Pit-window (binary)

```text
pit_within_3_laps = 1 if the driver pits within the next 3 laps, else 0
```

Initial window: `N = 3` (see D003 / D008).

### Model 2 — Next compound (multiclass)

```text
SOFT | MEDIUM | HARD | INTERMEDIATE | WET
```

Trained primarily on rows where `pit_within_3_laps == 1` (a stop is imminent).

Features must only use information available at the current lap. Labels may use future pit / compound outcomes.

## 4. Model training

```text
processed driver-lap rows
→ race-based train / validation / test split
→ XGBoost pit-window classifier
→ XGBoost next-compound classifier
→ evaluation
→ saved models + feature lists
```

```text
Raw OpenF1 data
→ driver-lap feature table
→ model-specific labels
→ Pit-window model    Next-compound model
```

Live inference pipeline:

```text
driver-lap features
→ pit-window model → pit probability
→ if above threshold → compound model → next compound (+ probabilities)
```

## 5. Live race state

During a live session, the backend receives OpenF1 updates and maintains the latest state for each driver.

```text
live messages
→ RaceState
→ DriverState
```

Location data is used for the frontend map, not the initial models.

## 6. Shared feature generation

Historical training and live inference must call the same feature-building code.

```text
historical state ┐
                 ├→ feature builder → model columns
live state       ┘
```

This prevents training-serving mismatch. Both models start from the same broad leakage-safe feature set; feature subsets can be refined later via ablation.

## 7. Application API

FastAPI will provide:

- REST endpoints for initial state
- WebSocket updates for live changes
- prediction results (pit probability + next compound)
- race data for the frontend

The frontend communicates only with this backend.
