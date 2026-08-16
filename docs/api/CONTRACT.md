# API Contract

Contract between the backend and frontend. Replay control endpoints are
documented separately in [../replay/API.md](../replay/API.md).

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

`x` / `y` are raw OpenF1/FastF1 track coordinates and `null` when the car has
no live telemetry.

### GET `/api/drivers/{driver_number}`

Returns the current state of one driver (same shape as `/api/drivers`).
Returns `404` if the car is not in the current grid.

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
    "predicted_pit_window_start": 26,
    "predicted_pit_window_end": 30,
    "updated_at": "2026-06-14T18:34:10Z"
  }
]
```

`predicted_next_compound` is a string and defaults to `"UNKNOWN"` (never
`null`). `compound_probabilities` may be `null` when no prediction is
available. `predicted_pit_window_start` / `predicted_pit_window_end` are a
placeholder window for the strategy panel (not from a dedicated model yet).

### GET `/api/drivers/{driver_number}/prediction`

Returns the latest prediction for one driver (same shape as one element of
`/api/predictions`). Returns `404` if that car is not in the snapshot.

### GET `/api/race-state`

Returns a full snapshot for initial frontend loading.

```json
{
  "session": {},
  "drivers": [],
  "predictions": []
}
```

The fields use the same schemas as `/api/session`, `/api/drivers`, and
`/api/predictions`.

### GET `/api/track`

Returns track metadata and the points used to draw the circuit. The circuit is
resolved from the live session's `circuit_key` against a static circuit
library (see `src/formula1_strategy_tool/api/circuits.py`).

```json
{
  "circuit_name": "Hungaroring",
  "circuit_key": 4,
  "country_name": "Hungary",
  "start_finish": {"x": -1470.9, "y": -123.3},
  "path": [
    {"x": -1710.5, "y": 76.6},
    {"x": -1950.7, "y": 275.8}
  ],
  "pit_lane": null
}
```

`path` is a closed loop in the raw FastF1 coordinate system (first point repeats
last). This is the same coordinate space as OpenF1 `v1/location` `x`/`y` on
`/api/drivers`, so the frontend applies one shared display transform to both.

`pit_lane` is an optional pit-lane centreline in the same raw coordinate space,
generated offline from historical location traces (see
`scripts/generate_pit_lanes.py`). It is `null` for circuits without reviewed pit
geometry, so the frontend must treat it as optional and only draw it when present.

Returns `503` before any live session is ingested and `404` when the session's
`circuit_key` is not yet in the circuit library.

### GET `/api/tracks`

Returns every circuit in the static library, sorted by `circuit_key`, so the
developer track-map preview page can render them all without a live session.

```json
[
  {
    "circuit_name": "Silverstone Circuit",
    "circuit_key": 2,
    "country_name": "United Kingdom",
    "start_finish": {"x": -1756.0, "y": 1208.0},
    "path": [{"x": -1535.7, "y": 1556.3}],
    "pit_lane": null
  }
]
```

Each entry uses the same `TrackState` schema as `/api/track`, including the
optional `pit_lane` and the `country_name` resolved from a static
circuit-key → country mapping. Unlike `/api/track`, this endpoint does not
require a live session and returns all known circuits rather than only the
current one.

### GET `/api/locations`

Returns the newest live location per driver, for high-frequency map updates.

```json
[
  {
    "driver_number": 4,
    "x": 1245,
    "y": -438,
    "date": "2026-06-14T18:34:10Z"
  }
]
```

`x` / `y` are `null` for cars without useful telemetry.

### GET `/api/live-status`

Returns an in-memory MQTT buffer summary, useful for confirming the live
listener is receiving OpenF1 pushes.

```json
{
  "mqtt_enabled": true,
  "topics": {
    "v1/laps": {"messages": 120, "unique_keys": 20},
    "v1/location": {"messages": 4000, "unique_keys": 20}
  }
}
```

Empty topics mean no push traffic yet (normal between sessions).

### Replay endpoints

Replay control endpoints (`/api/replay/...`) are documented in
[../replay/API.md](../replay/API.md).

---

## WebSocket Events

Connect to:

```text
/ws/live
```

Every event contains a `type` field. Events are pushed only when the relevant
value changes.

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
  "last_lap_time": 75.421,
  "gap_to_leader": 3.8,
  "interval_ahead": 1.2,
  "interval_behind": 2.1,
  "pit_stops": 1
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
503 Service Unavailable
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

[Back to Documentation](../README.md)
