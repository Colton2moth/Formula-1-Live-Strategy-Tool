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
  "total_laps": null,
  "track_temperature": 34.2,
  "air_temperature": 21.5,
  "rainfall": false,
  "race_control_status": "GREEN"
}
```

`total_laps` is the scheduled race distance when it is authoritatively
known, and `null` when it is not. OpenF1's live session object does not carry
a lap count, so the live endpoints return `null` rather than inventing a
denominator. A completed replay that knows the final lap count from its
prepared timeline returns a real number. The frontend shows `14` when the
total is unknown and `14 / 72` when it is known.

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

`x` / `y` are raw OpenF1 track coordinates and `null` when the car has
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

Live predictions are scored only from the current live session's features.
When live inference cannot produce a prediction, the endpoint returns `[]`
(and the single-driver endpoint returns `404`) rather than substituting a
historical CSV snapshot. A historical snapshot is used only when the backend's
opt-in `INFERENCE_CSV_FALLBACK` development flag is set.

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

Returns display-ready circuit geometry for the live session's `circuit_key`.
The geometry is generated offline from cached OpenF1 location traces into a
versioned layout (see `scripts/generate_track_reference_paths.py`).

```json
{
  "circuit_name": "Silverstone Circuit",
  "circuit_key": 2,
  "rotation": 92.0,
  "country_name": "United Kingdom",
  "display_path": [
    {"x": 67.3, "y": 64.8},
    {"x": 66.9, "y": 64.5}
  ],
  "start_finish": {"x": 67.3, "y": 64.8, "angle_deg": -144.1},
  "pit_lane": {
    "path": [{"x": 66.0, "y": 63.0}],
    "entry_progress": 0.91,
    "exit_progress": 0.11
  }
}
```

`display_path` is 1000 progress-aligned points already rotated, uniformly
scaled, and centred for the SVG view — the frontend draws it directly with no
runtime transform. `start_finish` is the marker position and angle in the same
display space. `pit_lane` is optional and `null` for circuits without reviewed
pit geometry; `entry_progress` / `exit_progress` are the pit entry/exit
positions on the main loop (0.0–1.0).

Returns `503` before any live session is ingested and `404` when the session's
`circuit_key` has no generated layout.

### GET `/api/tracks`

Returns every generated circuit layout (display-ready), sorted by
`circuit_key`, for the developer track-map preview page.

```json
[
  {
    "circuit_name": "Silverstone Circuit",
    "circuit_key": 2,
    "rotation": 92.0,
    "country_name": "United Kingdom",
    "display_path": [{"x": 67.3, "y": 64.8}],
    "start_finish": {"x": 67.3, "y": 64.8, "angle_deg": -144.1},
    "pit_lane": null
  }
]
```

Each entry uses the same `TrackState` schema as `/api/track`. Unlike
`/api/track`, this endpoint does not require a live session.

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

When OpenF1 moves to a new session, the backend resets its live buffer and
closes `/ws/live` connections. Clients should treat the close as a normal
reconnect and refetch `/api/race-state` to resync to the new session.

### Location update

```json
{
  "type": "location_update",
  "driver_number": 4,
  "x": 1245,
  "y": -438,
  "progress": 0.6274,
  "timestamp": "2026-06-14T18:34:10Z"
}
```

`x` / `y` are the raw OpenF1 coordinates, retained for debugging. `progress`
is the projected normalized position around the main circuit, from `0.0`
inclusive to `1.0` exclusive. The frontend maps `progress` onto `display_path`
to place the marker, so the backend no longer supplies display-specific
`map_x` / `map_y` coordinates. `progress` is `null` when the sample cannot be
projected reliably; the frontend should retain the last valid position.
When a timestamped sample implies physically impossible movement, the backend
advances progress by at most 2% of a lap so markers recover continuously
instead of teleporting to the raw target.

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
