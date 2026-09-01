# Replay troubleshooting

Operational diagnosis and verification. Commands below assume Windows
PowerShell from the repository root. See [COMMANDS.md](./COMMANDS.md) for the
full cheat sheet and [CACHE.md](./CACHE.md) for how preparation works.

## Race is not ready

A race shows `not_ready` when the required replay artifacts (timeline +
checkpoints) do not yet exist and no failure has been recorded.

What to do:

1. Check the race's readiness with the sessions list (see
   [COMMANDS.md](./COMMANDS.md#inspect-race-readiness)).
2. Prepare it with the bulk cache command (see
   [CACHE.md](./CACHE.md#preparing-races)).

`not_ready` does **not** mean a background preparation process is running — it
simply means the race has not been prepared yet.

## Race preparation failed

A race shows `failed` when a preparation failure has been recorded in the
failure log. Inspect the log:

```powershell
Get-Content data\replay\cache_failures.txt -Tail 50
```

Search for one session:

```powershell
Select-String -Path data\replay\cache_failures.txt -Pattern "<session_key>"
```

The log is diagnostic history only. Re-running the cache command will retry the
race, and a successful timeline/checkpoint preparation takes precedence when
readiness is calculated — so a race can move from `failed` back to `ready`
after a successful re-run. Do not delete the log to force a state change.

## Missing location windows

`location` is downloaded in 5-minute windows, and a window can be missing when
OpenF1 returns nothing for it (cars parked, red flag, race ended early).
Missing location windows are report-only: they do **not** prevent
timeline/checkpoint preparation. The map simply has no samples for that
stretch.

Whether a missing window affects readiness depends on where it is:

- **Trailing gap** — only the final windows are missing (e.g. the session
  ended before the last few windows). This is harmless end-of-race truncation
  and the replay stays `ready`.
- **Internal gap** — a window is missing before a later window exists, so map
  data disappears and then resumes. The replay stays playable but becomes
  `partial`, with the picker showing `Partial location data`.

Readiness is calculated from the actual window files on disk, not from old
`location window XXXX missing` lines in `cache_failures.txt`. A race with valid
timeline/checkpoints and only a trailing gap stays `ready` even if an earlier
run recorded those location 404s.

## Cancelled races

A handful of sessions never actually ran (for example 2023 Emilia-Romagna,
which was cancelled due to flooding, and the cancelled 2026 Bahrain and Saudi
Arabia races). These are marked `cancelled` explicitly, shown in the picker
with a `(cancelled)` suffix and a muted `Cancelled` chip, and cannot be played.
Cancellation is **not** inferred from a 404 on `drivers`, `laps`, `pit`, or any
other endpoint, because some legitimate historical races have incomplete
endpoint coverage.

## Verify a replay

- Backend logs `replay: session_key=... events=N speed=...x`, then
  `replay: reached race end; leaving final state visible`.
- The first run downloads and caches data (about a minute, rate-limited at
  2.1s/request); later runs start instantly.
- The dashboard advances on its own: lap counter ticks up, cars move on the
  map, leaderboard/compound/tyre-age update, flags and weather change.
- `GET /api/replays/{replay_id}/race-state` returns the replay snapshot and
  `GET /api/replays/{replay_id}/track` its circuit, while `GET /api/race-state` keeps
  serving live data (replay never mixes into the live endpoints).

## Common status meanings

`GET /api/replays/{replay_id}/status` reports the replay controller's runtime state:

| Status        | Meaning                                                       |
| ------------- | ------------------------------------------------------------ |
| `idle`        | no replay active (default)                                   |
| `downloading` | replay started; historical data is being fetched/cached      |
| `running`     | replay is actively advancing the race clock                  |
| `paused`      | replay clock suspended; resume continues from the same point |
| `finished`    | replay reached race end; final state left visible            |
| `error`       | the replay worker exited with an error (see `error` field)   |

Note: `downloading` here refers to the runtime download after pressing Play, not
to bulk cache preparation. Readiness (`ready` / `partial` / `cancelled` /
`not_ready` / `failed` / `unknown`) is a separate concept about whether the
race has been prepared — see
[CACHE.md](./CACHE.md#readiness-states).

[Back to Replay overview](./README.md)
