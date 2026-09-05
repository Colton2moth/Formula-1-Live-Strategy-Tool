# Replay terminal commands

Practical cheat sheet. All commands assume Windows PowerShell, run from the
repository root, and use the project virtualenv explicitly
(`.\.venv\Scripts\python.exe`). The backend must be running (see
[Start the backend](#start-the-backend)) before any replay API command
below works.

For endpoint details and valid ranges, see [API.md](./API.md).

## Most common commands

1. Prepare all 2023–2026 races:
   `.\.venv\Scripts\python.exe -m formula1_strategy_tool.acquisition.cache_replays --years 2023 2024 2025 2026`
2. Recheck / top up locally cached races:
   `.\.venv\Scripts\python.exe -m formula1_strategy_tool.acquisition.cache_replays --local`
3. List races and readiness:
   `Invoke-RestMethod http://127.0.0.1:8000/api/replay/sessions | Format-Table year, country_name, session_key, readiness`
4. Inspect recent cache failures:
   `Get-Content data\replay\cache_failures.txt -Tail 50`

## Cache / prepare races

### Prepare the full historical range

Downloads completed races for the supported seasons, reuses anything already
cached, and builds the replay timeline plus lap checkpoints for each race.

```powershell
.\.venv\Scripts\python.exe -m formula1_strategy_tool.acquisition.cache_replays --years 2023 2024 2025 2026
```

Use when: the Replay page shows many races as not ready. This is the command
to run normally. It continues when an individual race has a problem, and is
safe to stop and run again because cached data is reused.

### Prepare one year (or several specific years)

```powershell
.\.venv\Scripts\python.exe -m formula1_strategy_tool.acquisition.cache_replays --years 2025
```

Use when: you only need a single season. Multiple specific years can be
supplied together, e.g. `--years 2024 2025`.

### Reprocess races already on disk (`--local`)

```powershell
.\.venv\Scripts\python.exe -m formula1_strategy_tool.acquisition.cache_replays --local
```

Use when: you want to re-check / top up races already under `data/replay/`
without asking OpenF1 for the race list. `--local` discovers sessions from the
`data/replay/<session_key>/sessions.json` files, whereas `--years` asks OpenF1
for the completed race list for the given years.

### Cache retry / rate-limit options

```powershell
.\.venv\Scripts\python.exe -m formula1_strategy_tool.acquisition.cache_replays --years 2025 --max-retries 10
```

Use when: a run keeps failing on flaky requests and you want more attempts.
Options: `--max-retries` (default `6`) and `--interval` (default `2.1`, seconds
between requests). Do not lower `--interval` below the default unless you know
your OpenF1 API limits allow it.

## Start the backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn formula1_strategy_tool.main:app --host 127.0.0.1 --port 8000
```

Use when: you need the API up so the `Invoke-RestMethod` commands below (and
the Replay page) work. Live ingestion and replay run side by side; drive replay
from the page or the control endpoints below.

## Inspect race readiness

### List races and their readiness

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/replay/sessions |
  Format-Table year, country_name, session_key, readiness
```

Use when: you want to see every completed race the Replay page offers, with
its readiness state.

### Show only races that are not ready

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/replay/sessions |
  Where-Object { $_.readiness -ne "ready" } |
  Format-Table year, country_name, session_key, readiness
```

Use when: you want a short list of everything that is not a clean `ready` —
including `partial` (playable but incomplete map data), `cancelled` (never
ran), `not_ready` (not yet prepared), and `failed` (blocking preparation
failure). See [CACHE.md](./CACHE.md#readiness-states) for what each state
means.

## Inspect cache failures

```powershell
Get-Content data\replay\cache_failures.txt
```

```powershell
Get-Content data\replay\cache_failures.txt -Tail 50
```

```powershell
Select-String -Path data\replay\cache_failures.txt -Pattern "<session_key>"
```

Use when: you want to see what went wrong, or search for one session key. The
log is history only — a later successful timeline/checkpoint preparation takes
precedence when readiness is calculated, so deleting the log is **not** the way
to make a race show as `ready`.

## Manual replay API controls

Speeds are limited to `1`, `2`, `5`, or `10` (`1x` = real time). Creating a
replay returns the private `replay_id` required by every later control call.

### Start a replay

```powershell
$replay = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/replays `
  -ContentType "application/json" `
  -Body '{"session_key":9693,"speed":10}'
$replayId = $replay.replay_id
```

Use when: you want to start a replay by hand (equivalent to pressing Play on
the Replay page).

### Inspect replay status

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/replays/$replayId/status"
```

### Pause

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/replays/$replayId/pause"
```

### Resume

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/replays/$replayId/resume"
```

### Stop

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/replays/$replayId/stop"
```

Use when: you want to halt the replay and restore the live MQTT listener.

### Seek

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/replays/$replayId/seek" `
  -ContentType "application/json" `
  -Body '{"time":540.5}'
```

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/replays/$replayId/seek" `
  -ContentType "application/json" `
  -Body '{"lap":12}'
```

Use when: you want to jump to a replay-clock time or completed-lap checkpoint.
Exactly one of `time` (>= 0) or `lap` (>= 1) is required.

### Change replay speed while running

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/replays/$replayId/speed" `
  -ContentType "application/json" `
  -Body '{"speed":5}'
```

Use when: you want to change speed without restarting the replay. Only valid
while the replay is `running` or `paused` (returns 409 otherwise).

## Standalone producer

```powershell
.\.venv\Scripts\python.exe -m formula1_strategy_tool.acquisition.replay --session-key <key> --speed 10
```

Use when: you want to exercise the producer directly without the API server or
the Replay page.

[Back to Replay overview](./README.md)
