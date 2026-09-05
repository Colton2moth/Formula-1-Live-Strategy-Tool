# Replay architecture

How Replay Mode works under the hood. For how to run it, see
[USAGE.md](./USAGE.md). For the REST surface, see [API.md](./API.md).

## System flow

```text
OpenF1 historical REST → cache → chronological timeline → replay_controller.state
    → /api/replay/* + /ws/replay → frontend replay state → header / map / table / strategy
```

Replay and live run from separate mutable state. Live uses the module-level
`LIVE_STATE` (REST bootstrap + MQTT) and `/api/*` + `/ws/live`; replay uses the
`ReplayController`'s private `LiveState` and `/api/replay/*` + `/ws/replay`.
They share the presentation components and the state/feature/event-building
logic, but replay never clears or seeds `LIVE_STATE` and live ingestion never
stops while a replay is running.

## Acquisition

One module, `src/formula1_strategy_tool/acquisition/replay.py`, reuses the
existing `OpenF1Client` and `get_or_download` helpers. It fetches only the
endpoints needed for the selected session and caches them under
`data/replay/<session_key>/` (see [CACHE.md](./CACHE.md) for the full layout).

Identity data (`sessions`, `meetings`, `drivers`) is kept small and loaded
separately, so a prepared-timeline hit can skip the heavy endpoint files
(`laps`, `location`, `position`, …) entirely.

## Timeline

Rows are normalized into a chronological `(offset, topic, payload)` list where
`offset` is seconds after the race clock starts. Identity data (session,
meeting, drivers) is seeded first; time-varying rows are scheduled from their
timestamps:

| Endpoint      | Topic               | Schedule key                                  |
| ------------- | ------------------- | --------------------------------------------- |
| drivers       | `v1/drivers`        | seeded at start (identity)                    |
| sessions      | `v1/sessions`       | seeded at start                               |
| meetings      | `v1/meetings`       | seeded at start                               |
| laps          | `v1/laps`           | `date_end` (a lap is known only when it ends) |
| pit           | `v1/pit`            | `date`                                        |
| position      | `v1/position`       | `date`                                        |
| intervals     | `v1/intervals`      | `date`                                        |
| weather       | `v1/weather`        | `date`                                        |
| race_control  | `v1/race_control`   | `date`                                        |
| location      | `v1/location`       | `date`                                        |
| stints        | `v1/stints`         | the `date_start` of the stint's first lap     |

The prepared timeline is persisted under `timeline/`: `index.json` contains
only format/session totals and chunk ranges, while each `chunk-*.json` holds up
to five minutes of race-clock events. When the format version, session key, or
referenced chunks no longer validate, the timeline is rebuilt from the raw
cache instead of being trusted.

## No future leakage

A completed race contains information that was not known at an earlier lap. The
producer only exposes a row once the replay clock reaches its timestamp, so
later laps, pits, positions, intervals, race-control events, and predictions
are never visible early.

Stints need special handling: the historical REST row describes a *completed*
stint range (`lap_start` → `lap_end`). Replay reconstructs a live-like stream
instead — each stint opens at its `lap_start` with `lap_end = null` (still
unknown), and the previous stint is closed with its true `lap_end` at the same
moment the next stint starts. This keeps the current stint open-ended while
never leaking a future stint boundary to the model. The shared feature pipeline
(`add_stint_features`) treats an open stint as covering through the latest lap.

## Playback

Before replaying, the controller's private `LiveState` is cleared so stale
replay/test data cannot mix with the new historical race. Live `LIVE_STATE` is
never touched. Identity rows are seeded, then the worker advances a race clock
scaled by the replay speed, emitting every event whose offset is due and
sleeping until the next event. Its reader holds the current chunk and
prefetches the next; after a boundary it releases the prior chunk before
loading another.

A `pause_event` suspends the clock: the paused wall-clock time is excluded from
the scaled elapsed time, so resume continues from the same position. The
authoritative clock is written back to a shared progress dict so
`/api/replays/{replay_id}/status` can report `current_time`, `total_duration`,
`current_lap`, and `total_laps` — the frontend never estimates progress on its
own.

At race end the final state is left visible rather than cleared.

### Checkpoints and seek

`build_checkpoints` replays the prepared events through a `LiveState` and
snapshots the buffer at each completed lap (immediately after the lap-completing
event, so no future state leaks in). Each checkpoint stores the lap number, its
race-clock time, the global event cursor, and the snapshot. A lightweight
`index.json` records lap / time / cursor / file per checkpoint.

Seek restores the nearest checkpoint at or before the requested target, uses
the timeline index to open the chunk containing that cursor, then fast-forwards
by applying only the events up to the target. This makes a
replay jump to an arbitrary timeline time or lap without replaying earlier laps
and without exposing future events. See [API.md](./API.md) for the seek
endpoint and [USAGE.md](./USAGE.md) for the Replay page's seekable timeline and
lap readout.

[Back to Replay overview](./README.md)
