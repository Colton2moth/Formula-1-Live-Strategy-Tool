# Backend Architecture

High-level view of the whole system. Modelling detail lives in
[models/README.md](models/README.md); Replay Mode detail lives in
[replay/README.md](replay/README.md).

## 1. Historical data acquisition

Downloads completed Race sessions from the free OpenF1 REST API.

```text
OpenF1
→ one endpoint for one session
→ raw JSON file
```

Raw files are stored unchanged under `data/raw/` so they can be processed again
without another API request. See [data/ACQUISITION.md](data/ACQUISITION.md).

Skip cancelled / data-less races when building training sets (e.g. 2023
Emilia-Romagna, 2026 Bahrain, 2026 Saudi Arabia).

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

Identifiers (`session_key`, `driver_number`, etc.) are kept for joins and
splits but are not model features. See
[models/DATA_AND_FEATURES.md](models/DATA_AND_FEATURES.md) and
[data/DRIVER_LAP_SCHEMA.md](data/DRIVER_LAP_SCHEMA.md).

## 3. Models

Four XGBoost models share the same processed driver-lap table and differ only
by label / row filter:

- **Pit-window (binary, ×3)** — `pit_within_3_laps`, `pit_within_5_laps`,
  `pit_within_7_laps` (see [models/PIT_WINDOW.md](models/PIT_WINDOW.md)).
- **Next compound (multiclass)** — `SOFT | MEDIUM | HARD | INTERMEDIATE | WET`,
  trained on rows where a stop is imminent (see
  [models/NEXT_COMPOUND.md](models/NEXT_COMPOUND.md)).

Features must only use information available at the current lap; labels may use
future pit / compound outcomes.

```text
processed driver-lap rows
→ season-based train / validation split
→ XGBoost pit-window classifiers (×3)
→ XGBoost next-compound classifier
→ saved models + feature lists
```

Live inference:

```text
driver-lap features
→ pit-window models → pit probabilities (3 / 5 / 7 laps)
→ next-compound model → next compound (+ probabilities)
```

## 4. Live race state

During a live session the backend receives OpenF1 MQTT updates (with a REST
bootstrap fallback) and maintains the latest state for each driver in
`LIVE_STATE`.

```text
live messages
→ LIVE_STATE
→ DriverState / SessionState
```

Location data is used for the frontend map, not the strategy models.

A session monitor polls OpenF1 every ~45 seconds for the current
`session_key`. When it changes (e.g. Practice → Race), the backend stops the
MQTT listener, bootstraps the new session over REST into a temporary staging
`LiveState`, then atomically swaps it into the process-wide `LIVE_STATE`. On a
failed bootstrap the old session is left completely intact and MQTT stays
stopped until the next tick retries. On success it restarts MQTT, resets the
WebSocket diff state, and closes live clients so they reconnect and resync —
the process never needs a restart. Live predictions are scored only from the
current session's features (no silent historical fallback).

## 5. Shared feature generation

Historical training and live inference call the same feature-building code
(`_prepare_features`), so the live feature rows match the training columns.

```text
historical state ┐
                 ├→ feature builder → model columns
live state       ┘
```

This prevents training-serving mismatch. Both model families start from the
same broad leakage-safe feature set; subsets are refined later via ablation.

## 6. Application API

The backend provides:

- REST endpoints for initial state (`/api/*`, see
  [api/CONTRACT.md](api/CONTRACT.md));
- WebSocket updates for live changes (`/ws/live`);
- prediction results (pit probability + next compound);
- race data and track geometry for the frontend.

The frontend communicates only with this backend.

## 7. Track map

Circuit geometry is generated offline from cached OpenF1 location traces into
versioned layouts under `data/circuits/layouts/`:

```text
cached location traces
→ 1,000-point raw reference path (OpenF1 coordinates)
→ 1,000-point display path (rotated, scaled, centred)
```

The reference path is backend-internal: live/replay x/y are projected onto it
to lap progress, then mapped to a display position. The frontend receives only
the display path and projected `map_x`/`map_y` positions, so it never
reconstructs geometry. See `scripts/generate_track_reference_paths.py` and
`src/formula1_strategy_tool/track/`.

[Back to Documentation](README.md)
