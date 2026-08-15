# Replay System

The replay harness replays one completed historical race through the same live
pipeline the app uses during a real race, so the whole stack can be tested
without waiting for a Grand Prix.

```text
OpenF1 historical REST → cache → chronological timeline → LIVE_STATE.update(...)
    → /ws/live broadcaster → frontend live state → header / map / table / strategy
```

No frontend component knows about replay. The dashboard advances exactly as it
would during a live race because the replay producer feeds the same
`LIVE_STATE` topics that MQTT does.

## Why it exists

During a live race the backend is filled by the OpenF1 MQTT listener. Between
races there is no traffic, so there was no way to exercise the WebSocket
broadcaster, parsing, rendering, animation, and prediction path end to end.
Replay closes that gap by treating a completed session as a script of events.

## How it works

### 1. Acquisition and caching

One module, `src/formula1_strategy_tool/acquisition/replay.py`, reuses the
existing `OpenF1Client` and `get_or_download` helpers. It fetches only the
endpoints needed for the selected session and caches them under:

```text
data/
└── replay/
    └── <session_key>/
        ├── sessions.json
        ├── meetings.json
        ├── drivers.json
        ├── laps.json
        ├── stints.json
        ├── pit.json
        ├── position.json
        ├── intervals.json
        ├── weather.json
        ├── race_control.json
        └── location/
            └── 0000.json, 0001.json, …   (10-minute windows)
```

This cache is separate from the modelling dataset in `data/raw/`. Repeated
replays reuse the cache and do not re-hit OpenF1.

`location` is high frequency and the whole-session endpoint returns 422, so it
is downloaded in 10-minute windows and thinned in memory to roughly one sample
per driver per second (the frontend map only ever displays the latest sample
per driver anyway).

### 2. Timeline

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

### 3. No future leakage

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

### 4. Playback

Before replaying, `LIVE_STATE` is cleared so stale live/test data cannot mix
with the historical race. The worker then advances a race clock scaled by the
replay speed, emitting every event whose offset is due, and sleeping until the
next event. At race end the final state is left visible rather than cleared.

## Using it

### Pick a session key

Replay needs an explicit `session_key`. List completed races (uses the OpenF1
credentials in `.env`):

```powershell
.\.venv\Scripts\python.exe -c "from formula1_strategy_tool.acquisition.auth import openf1_get; [print(s['session_key'], s.get('country_name'), s.get('date_start')) for s in openf1_get('sessions', {'year': 2025, 'session_name': 'Race'})]"
```

### Option A — start in replay mode (env var)

Add to `.env`:

```
REPLAY_SESSION_KEY=<key>
REPLAY_SPEED=20
```

Then start the backend normally. When `REPLAY_SESSION_KEY` is set, the MQTT
listener and REST bootstrap are disabled and replay starts automatically:

```powershell
.\.venv\Scripts\python.exe -m uvicorn formula1_strategy_tool.main:app --host 127.0.0.1 --port 8000
```

### Option B — start from the website (footer button)

Start the backend without `REPLAY_SESSION_KEY`, then run the frontend. A
**Replay** control sits in the footer: pick a **year**, then a **race** (by
country) from the dropdowns, set the speed, and press **Start**. The dropdowns
are backed by `GET /api/replay/sessions`, which lists completed Race sessions
from 2023 onward. Pressing **Start** stops the live MQTT listener so live
pushes cannot mix with the replay. **Stop** halts the replay at its next
checkpoint.

Optionally prefill only the speed input with `frontend/.env`:

```
VITE_REPLAY_SPEED=10
```

(Year and race are chosen in the UI now; `VITE_REPLAY_SESSION_KEY` is no
longer used by the picker.)

### Option C — standalone CLI

Replay without the API server (useful for checking the producer):

```powershell
.\.venv\Scripts\python.exe -m formula1_strategy_tool.acquisition.replay --session-key <key> --speed 20
```

## Runtime control API

| Method | Path                  | Purpose                                   |
| ------ | --------------------- | ----------------------------------------- |
| GET    | `/api/replay/status`  | `idle` / `downloading` / `running` / `finished` / `error` |
| GET    | `/api/replay/sessions`| completed Race sessions (year + country)  |
| POST   | `/api/replay/start`   | start a replay (`{session_key, speed}`)   |
| POST   | `/api/replay/stop`    | stop the running replay                   |

`session_key` on `/api/replay/start` falls back to `REPLAY_SESSION_KEY`, then
`INFERENCE_SESSION_KEY`, and returns 400 if none are set.

## Verifying a replay

- Backend logs `replay: session_key=... events=N speed=...x`, then
  `replay: reached race end; leaving final state visible`.
- The first run downloads and caches data (about a minute, rate-limited at
  2.1s/request); later runs start instantly.
- The dashboard advances on its own: lap counter ticks up, cars move on the
  map, leaderboard/compound/tyre-age update, flags and weather change.
- `GET /api/live-status` shows the topic counters filling;
  `GET /api/race-state` returns the live snapshot.

## Configuration reference

| Variable                | Scope    | Default | Purpose                              |
| ----------------------- | -------- | ------- | ------------------------------------ |
| `REPLAY_SESSION_KEY`    | backend  | unset   | session to replay at startup         |
| `REPLAY_SPEED`          | backend  | `10`    | replay speed multiplier (1x = real)  |
| `VITE_REPLAY_SPEED`     | frontend | `10`    | prefill the footer speed input       |

## Current limitations

- Location is thinned to ~1 sample/driver/second to bound memory.
- There is no pause/resume or seek yet — only start and stop.
- The race picker is a flat year → country list; there is no search or
  meeting-name grouping.
- Stopping a replay leaves MQTT off; restart the backend to return to live
  mode.
- Predictions require `data/models` to exist; otherwise they fall back to the
  configured CSV snapshot (pre-existing behaviour, not replay-specific).
