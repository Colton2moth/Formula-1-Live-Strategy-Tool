# Replay Mode

Replay Mode replays one completed historical race through the same live pipeline
the app uses during a real race, so the whole stack can be tested without
waiting for a Grand Prix.

## What it is

During a live race the backend is filled by the OpenF1 MQTT listener. Between
races there is no traffic, so there is no way to exercise the WebSocket
broadcaster, parsing, rendering, animation, and prediction path end to end.
Replay Mode closes that gap by treating a completed session as a script of
events and replaying it chronologically.

```text
OpenF1 historical REST
    → replay cache
    → chronological timeline
    → replay controller's private LiveState
    → /api/replay/* + /ws/replay
    → normal frontend dashboard (replay page)
```

The key idea: replay does **not** build a separate fake frontend. It feeds the
same `LiveState` topics that MQTT feeds during a real race, but into the replay
controller's own state, so the dashboard advances exactly as it would live. No
frontend component knows about replay beyond selecting the replay data source.

## Where do I go?

| I want to…                    | Read                                        |
| ----------------------------- | ------------------------------------------- |
| Understand how replay works   | [ARCHITECTURE.md](./ARCHITECTURE.md)        |
| Run a replay                  | [USAGE.md](./USAGE.md)                      |
| Prepare/cache races           | [CACHE.md](./CACHE.md)                      |
| Find terminal commands        | [COMMANDS.md](./COMMANDS.md)                |
| Understand replay endpoints   | [API.md](./API.md)                          |
| Diagnose a problem            | [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)  |
| Check environment variables   | [CONFIGURATION.md](./CONFIGURATION.md)      |
