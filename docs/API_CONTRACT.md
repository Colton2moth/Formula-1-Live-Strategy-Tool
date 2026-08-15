# API Contract

This file defines the initial contract between the backend and frontend.

Base URL:

```text
/api
```

Live WebSocket:

```text
/ws/live
```

The API uses JSON.

---

## REST Endpoints

### GET `/api/session`

Returns the current session state from the live buffer. Returns `503` before
any live session has been ingested.

```json
{
  "meeting_name": "Hungarian Grand Prix",
  "session_name": "Race",
  "session_status": "active",
  "current_lap": 25,
  "total_laps": 70,
  "track_temperature": 34.2,
  "air_temperature": 21.5,
  "rainfall": false,
  "race_control_status": "GREEN"
}
```

### GET `/api/drivers`

Returns the current state of every driver.

```json
[
  {
    "driver_number": 4,
    "name": "Lando Norris",
    "acronym": "NOR",
    "team_name": "McLaren",
    "team_colour": "FF8000",
    "position": 2,
    "x": 1245,
    "y": -438,
    "current_lap": 25,
    "compound": "MEDIUM",
    "tyre_age": 14,
    "last_lap_time": 75.421,
    "gap_to_leader": 3.8,
    "interval_ahead": 1.2,
    "interval_behind": 2.1,
    "pit_stops": 1
  }
]
```

### GET `/api/drivers/{driver_number}`

Returns the current state of one driver.

```json
{
  "driver_number": 4,
  "name": "Lando Norris",
  "acronym": "NOR",
  "team_name": "McLaren",
  "team_colour": "FF8000",
  "position": 2,
  "x": 1245,
  "y": -438,
  "current_lap": 25,
  "compound": "MEDIUM",
  "tyre_age": 14,
  "last_lap_time": 75.421,
  "gap_to_leader": 3.8,
  "interval_ahead": 1.2,
  "interval_behind": 2.1,
  "pit_stops": 1
}
```

### GET `/api/predictions`

Returns the latest strategy prediction for every driver.

Three pit-window probabilities (3 / 5 / 7 laps) plus next-compound multiclass:

```json
[
  {
    "driver_number": 4,
    "lap_number": 25,
    "pit_within_3_laps": 0.55,
    "pit_within_5_laps": 0.72,
    "pit_within_7_laps": 0.84,
    "predicted_next_compound": "HARD",
    "compound_probabilities": {
      "SOFT": 0.04,
      "MEDIUM": 0.21,
      "HARD": 0.75,
      "INTERMEDIATE": 0.00,
      "WET": 0.00
    },
    "updated_at": "2026-06-14T18:34:10Z"
  }
]
```

`predicted_next_compound` / `compound_probabilities` may be `null` when pit risk is low. Raw compound probabilities may still be exposed for debugging.

### GET `/api/drivers/{driver_number}/prediction`

Returns the latest prediction for one driver.

```json
{
  "driver_number": 4,
  "lap_number": 25,
  "pit_within_3_laps": 0.55,
  "pit_within_5_laps": 0.72,
  "pit_within_7_laps": 0.84,
  "predicted_next_compound": "HARD",
  "compound_probabilities": {
    "SOFT": 0.04,
    "MEDIUM": 0.21,
    "HARD": 0.75,
    "INTERMEDIATE": 0.00,
    "WET": 0.00
  },
  "updated_at": "2026-06-14T18:34:10Z"
}
```

### GET `/api/race-state`

Returns a full snapshot for initial frontend loading.

```json
{
  "session": {},
  "drivers": [],
  "predictions": []
}
```

The fields use the same schemas as `/api/session`, `/api/drivers`, and `/api/predictions`.

### GET `/api/track`

Returns track metadata and the points used to draw the circuit. The circuit is
resolved from the live session's `circuit_key` against a static circuit
library (see `src/formula1_strategy_tool/api/circuits.py`).

```json
{
  "circuit_name": "Hungaroring",
  "circuit_key": 4,
  "start_finish": {"x": -1470.9, "y": -123.3},
  "path": [
    {"x": -1710.5, "y": 76.6},
    {"x": -1950.7, "y": 275.8}
  ]
}
```

`path` is a closed loop in the raw FastF1 coordinate system (first point repeats
last). This is the same coordinate space as OpenF1 `v1/location` `x`/`y` on
`/api/drivers`, so the frontend applies one shared display transform to both.
Returns `503` before any live session is ingested and `404` when the session's
`circuit_key` is not yet in the circuit library.

---

## WebSocket Events

Connect to:

```text
/ws/live
```

Every event contains a `type` field.

### Location update

```json
{
  "type": "location_update",
  "driver_number": 4,
  "x": 1245,
  "y": -438,
  "timestamp": "2026-06-14T18:34:10Z"
}
```

### Driver state update

```json
{
  "type": "driver_update",
  "driver_number": 4,
  "position": 2,
  "current_lap": 25,
  "compound": "MEDIUM",
  "tyre_age": 14,
  "last_lap_time": 75.421
}
```

### Prediction update

```json
{
  "type": "prediction_update",
  "driver_number": 4,
  "lap_number": 25,
  "pit_within_3_laps": 0.55,
  "pit_within_5_laps": 0.72,
  "pit_within_7_laps": 0.84,
  "predicted_next_compound": "HARD",
  "compound_probabilities": {
    "SOFT": 0.04,
    "MEDIUM": 0.21,
    "HARD": 0.75,
    "INTERMEDIATE": 0.00,
    "WET": 0.00
  }
}
```

### Weather update

```json
{
  "type": "weather_update",
  "track_temperature": 34.2,
  "air_temperature": 21.5,
  "rainfall": false
}
```

### Race control update

```json
{
  "type": "race_control_update",
  "status": "SAFETY_CAR",
  "message": "Safety Car deployed"
}
```

---

## Error Response

```json
{
  "detail": "Driver not found"
}
```

Common status codes:

```text
200 OK
404 Not Found
422 Validation Error
500 Internal Server Error
```

---

## Initial Design Rules

- The frontend communicates only with this backend.
- REST provides full snapshots.
- WebSocket provides incremental live updates.
- Field names should remain stable once frontend development begins.
- New fields may be added without removing existing fields.
- Unknown live values should use `null`.
- `driver_number` is an identifier, not a model feature.
