# Replay configuration

Environment variables and known limits for Replay Mode.

## Environment variables

| Variable                | Scope    | Default | Purpose                              |
| ----------------------- | -------- | ------- | ------------------------------------ |
| `REPLAY_SESSION_KEY`    | backend  | unset   | session to replay at startup         |
| `REPLAY_SPEED`          | backend  | `10`    | replay speed multiplier (1x = real)  |
| `VITE_REPLAY_SPEED`     | frontend | `10`    | prefill the Replay Speed control     |

### `REPLAY_SESSION_KEY`

When set, the backend also starts the replay controller's private state at
startup (running the given historical session alongside live bootstrap and
MQTT). Set it in `.env` and start the backend normally. See
[USAGE.md](./USAGE.md#startup-replay-using-environment-variables).

### `REPLAY_SPEED`

Replay speed multiplier used when starting replay via `REPLAY_SESSION_KEY`.

### `VITE_REPLAY_SPEED`

Prefills the Replay Speed control on the Replay page. Set it in `frontend/.env`.
Year and race are chosen in the UI; there is no `VITE_REPLAY_SESSION_KEY`.

## Current limitations

- Location is thinned to ~4 samples/driver/second to bound memory.
- The race picker is a flat year → country list; there is no search or
  meeting-name grouping.
- Predictions require `data/models` to exist; otherwise they fall back to the
  configured CSV snapshot (pre-existing behaviour, not replay-specific).

[Back to Replay overview](./README.md)
