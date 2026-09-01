# Using Replay Mode

Normal developer/user workflows. For the terminal command cheat sheet, see
[COMMANDS.md](./COMMANDS.md). For preparing race data before replaying, see
[CACHE.md](./CACHE.md).

## Replay page

1. Start the backend (see [CONFIGURATION.md](./CONFIGURATION.md)), then run the
   frontend.
2. Open the **Race Replay** link in the header to navigate to `/replay`.
3. Pick a **year**, then a **race** (by country / Grand Prix) from the
   dropdowns. The dropdowns are backed by `GET /api/replay/sessions`, which
   lists completed Race sessions from 2023 onward.
4. Check the race's **readiness** (see [CACHE.md](./CACHE.md#readiness-states)).
   A race must be `ready` or `partial` before Play is enabled; `cancelled`,
   `not_ready`, and `failed` races cannot be played.
5. Choose a **Replay Speed** and press **Play**.

The page shows a `REPLAY — <year> <Grand Prix>` banner so historical data is
never mistaken for the live race, plus the same race header, track map,
leaderboard, and strategy panel used by the live dashboard. A read-only
progress bar reports replay time and lap progress from the replay controller's
authoritative clock.

Playback controls map to the runtime API:

| Control | Behaviour |
| ------- | --------- |
| Play    | start (or restart a finished replay) |
| Pause   | suspend the replay clock |
| Resume  | continue from the paused position |
| Stop    | halt the replay and restore the live MQTT listener |

Seek is available through the progress panel: a seekable timeline accepts a
replay-clock time, and an editable lap readout accepts a completed lap number
(see [API.md](./API.md#post-apireplayseek)).

Pressing **Play** runs a historical race in the replay controller's own state;
the live MQTT listener and live REST endpoints are unaffected. **Stop** (or
leaving the page while a replay is active) halts only the replay, so Live mode
continues uninterrupted.

Optionally prefill the replay speed with `frontend/.env`:

```
VITE_REPLAY_SPEED=10
```

## Startup replay using environment variables

Add to `.env`:

```
REPLAY_SESSION_KEY=<key>
REPLAY_SPEED=10
```

Then start the backend normally. When `REPLAY_SESSION_KEY` is set, the backend
also starts the replay controller's private state at startup, alongside live
bootstrap and MQTT (used for automated end-to-end checks):

```powershell
.\.venv\Scripts\python.exe -m uvicorn formula1_strategy_tool.main:app --host 127.0.0.1 --port 8000
```

## Standalone replay CLI

Replay without the API server (useful for checking the producer):

```powershell
.\.venv\Scripts\python.exe -m formula1_strategy_tool.acquisition.replay --session-key <key> --speed 10
```

## Finding session keys

Replay needs an explicit `session_key`. List completed races (uses the OpenF1
credentials in `.env`):

```powershell
.\.venv\Scripts\python.exe -c "from formula1_strategy_tool.acquisition.auth import openf1_get; [print(s['session_key'], s.get('country_name'), s.get('date_start')) for s in openf1_get('sessions', {'year': 2025, 'session_name': 'Race'})]"
```

You can also list races and their readiness through the API — see
[COMMANDS.md](./COMMANDS.md#inspect-race-readiness).

[Back to Replay overview](./README.md)
