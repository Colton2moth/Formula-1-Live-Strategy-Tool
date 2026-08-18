# Replay API

REST endpoints for the replay controller. See
[Manual commands](./COMMANDS.md) for PowerShell examples.

## Summary

| Method | Path                  | Purpose                                   |
| ------ | --------------------- | ----------------------------------------- |
| GET    | `/api/replay/status`  | controller state + replay progress        |
| GET    | `/api/replay/sessions`| completed Race sessions (year + country + readiness) |
| POST   | `/api/replay/start`   | start a replay (`{session_key, speed}`)   |
| POST   | `/api/replay/pause`   | suspend the running replay clock          |
| POST   | `/api/replay/resume`  | continue a paused replay                  |
| POST   | `/api/replay/seek`    | jump by replay-clock `time` or completed `lap` |
| POST   | `/api/replay/speed`   | change the active replay speed in place   |
| POST   | `/api/replay/stop`    | stop the replay and restore live MQTT     |

## Response shape

Every replay endpoint returns the current replay status object:

| Field           | Type             | Meaning                                  |
| --------------- | ---------------- | ---------------------------------------- |
| `status`        | string           | `idle` \| `downloading` \| `running` \| `paused` \| `finished` \| `error` |
| `running`       | boolean          | whether the producer thread is alive     |
| `session_key`   | number \| null   | active session key                       |
| `speed`         | number \| null   | active replay speed                      |
| `error`         | string \| null   | last worker error, if any                |
| `current_time`  | number \| null   | race-clock seconds (owned by producer)   |
| `total_duration`| number \| null   | seconds from the last timeline event     |
| `current_lap`   | number \| null   | current completed lap                    |
| `total_laps`    | number \| null   | total laps from the full lap history     |

The frontend never estimates progress on its own; it reads the authoritative
`current_time` / `total_duration` / `current_lap` / `total_laps` owned by the
producer.

## GET `/api/replay/status`

Current replay controller state and progress. Returns the status object above.

## GET `/api/replay/sessions`

Completed Race sessions for the year → country replay picker (2023 onward).
Returns a list where each entry has:

| Field               | Type             | Meaning                        |
| ------------------- | ---------------- | ------------------------------ |
| `session_key`       | number           | session to replay              |
| `year`              | number           | season year                    |
| `country_name`      | string \| null   | Grand Prix country             |
| `location`          | string \| null   | location                       |
| `circuit_short_name`| string \| null   | short circuit name             |
| `date_start`        | string \| null   | session start (ISO-8601)       |
| `readiness`         | string           | `ready` \| `partial` \| `cancelled` \| `not_ready` \| `failed` \| `unknown` |

Readiness is documented in [CACHE.md](./CACHE.md#readiness-states). Returns
`503` when the OpenF1 session list cannot be fetched.

## POST `/api/replay/start`

Start replaying a completed session through `LIVE_STATE`.

Request body:

```json
{ "session_key": 9693, "speed": 20 }
```

- `session_key` — optional. Falls back to `REPLAY_SESSION_KEY`, then
  `INFERENCE_SESSION_KEY`. Returns `400` if none are set.
- `speed` — replay multiplier, `0.25`–`100`, default `10`.

Starting a replay stops the live MQTT listener so live pushes cannot mix.

## POST `/api/replay/pause`

Suspend the running replay clock. Resume continues from the same position.

## POST `/api/replay/resume`

Continue a paused replay from where it left off.

## POST `/api/replay/stop`

Stop the running replay and restore the live MQTT listener.

## POST `/api/replay/seek`

Jump the active replay to a replay-clock time or completed-lap checkpoint. The
producer restores the nearest checkpoint at or before the target, then resumes
without exposing future events.

Request body — exactly one of:

```json
{ "time": 540.5 }
```

```json
{ "lap": 12 }
```

- `time` — replay-clock seconds, `>= 0`.
- `lap` — completed lap number, `>= 1`.

Providing neither target, both targets, or an out-of-range value returns `422`.

## POST `/api/replay/speed`

Change the active replay speed in place, without restarting it.

Request body:

```json
{ "speed": 40 }
```

- `speed` — replay multiplier, `0.25`–`100`.

Only valid while the replay is `running` or `paused`; otherwise returns `409`.

[Back to Replay overview](./README.md)
