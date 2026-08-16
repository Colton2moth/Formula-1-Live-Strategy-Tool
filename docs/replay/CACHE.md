# Replay cache

How historical replay data is prepared and stored. For the terminal commands,
see [COMMANDS.md](./COMMANDS.md). For investigating failures, see
[TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

## Purpose

Replay data is cached under `data/replay/` so a completed race can be replayed
repeatedly without re-hitting OpenF1. This cache is **separate** from the
modelling dataset under `data/raw/`; the two are never mixed.

## Layout

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
        ├── timeline.json
        ├── checkpoints/
        │   ├── index.json
        │   └── checkpoint-0001.json, …   (one state file per completed lap)
        └── location/
            └── 0000.json, 0001.json, …   (5-minute windows)
```

## Location data

`location` is high frequency, and the whole-session endpoint returns 422, so it
is downloaded in 5-minute windows and thinned in memory to roughly 4 samples
per driver per second (0.25 s intervals). The frontend map only ever displays
the latest sample per driver, so the thinned stream still moves smoothly while
staying memory-friendly.

Windows already on disk are reused and not re-downloaded. A window that 404s
(cars parked, red flag, race ended early) leaves a gap, but location is
optional polish: a missing window does **not** block timeline/checkpoint
preparation, and a replay can still become `ready` without it.

## Preparing races

The bulk cache command prepares completed races for the supported historical
range. It discovers completed races, downloads missing replay data, reuses
files already on disk, and builds the replay timeline and lap checkpoints.

Prepare the full currently supported range:

```powershell
.\.venv\Scripts\python.exe -m formula1_strategy_tool.acquisition.cache_replays --years 2023 2024 2025 2026
```

Supported options:

- `--years 2025` — one year, or several specific years (`--years 2024 2025`).
- `--local` — discover sessions already under `data/replay/` instead of asking
  OpenF1 for the race list.
- `--max-retries` — total attempts per request. Default `6` (`1` = no retries,
  `2` = retry once).
- `--interval` — seconds between requests. Default `2.1`.

The default `--interval` exists to respect OpenF1 request limits (~30
requests/minute on the free tier).

## Resumability

The bulk cache command is safe to stop and run again: `download_replay_data`
uses `get_or_download`, which loads endpoint files and location windows already
on disk instead of hitting OpenF1 again. One race failing does not stop the
rest; failures are appended to the failure log and the run continues.

## Readiness states

Readiness describes whether a race has everything needed to play:

- `ready` — the prepared timeline and checkpoint/index data are available.
- `not_ready` — the required replay artifacts (timeline + checkpoints) do not
  yet exist and no recorded blocking failure exists.
- `failed` — not ready and a preparation failure has been recorded.
- `unknown` — readiness could not be determined (defensive fallback).

`not_ready` does **not** mean a background preparation process is running. It
is the state for a race that has simply not been prepared yet. There is no
reliable signal for whether a race is actively being prepared, so "preparing"
is not used as a readiness state. Prepare races manually with the
`cache_replays` command above.

A race with a recorded failure can still become `ready`: successful
timeline/checkpoint preparation takes precedence when readiness is calculated.

## Failure history

Failures from the bulk cache command are appended to
`data/replay/cache_failures.txt` as diagnostic history (one line per failure).
This log is history only — deleting it does not make a race `ready`. See
[TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for how to inspect it.

[Back to Replay overview](./README.md)
