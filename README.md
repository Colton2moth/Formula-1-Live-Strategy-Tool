<p align="center">
  <img src="frontend/public/brand/pitpit-logo-badge.png" alt="PitPit logo" width="200" />
</p>

<p align="center">
<a href="https://pitpit.org">pitpit.org</a><br />
  <strong>PitPit</strong>: a live Formula 1 strategy dashboard
</p>

---

## What is PitPit?

PitPit is a live Formula 1 strategy dashboard that combines
[OpenF1](https://openf1.org) telemetry with race-state processing and
model-based pit-strategy estimates. It is for anyone following a session as it
happens who wants to see, next to the live timing, how likely each driver is
to pit and on what tyre.

The deployed site at [pitpit.org](https://pitpit.org) reflects the latest
released build. The instructions below are for running and understanding the
project locally.

## The dashboard

The dashboard is built around four primary areas:

- **Race/session header** — Grand Prix and session name, weather, flag status,
  session status, and lap count.
- **Live circuit map** — an SVG circuit with animated driver markers that
  track each car around the lap.
- **Driver leaderboard** — position, gap/interval, tyre compound, last lap, and
  pit count.
- **Strategy prediction panel** — the probability of pitting within the next
  3, 5, or 7 laps and the most likely next tyre compound.

Selecting a driver connects the map, leaderboard, and strategy panel, so all
three always describe the same car.

## How it works

```text
OpenF1 REST + MQTT
        ↓
Python live-state processing and track projection
        ↓
FastAPI REST + WebSocket APIs
        ↓
React dashboard and SVG marker animation
```

- The backend seeds state from OpenF1 REST, then stays current over OpenF1
  MQTT, maintaining one live state per driver.
- Car `x`/`y` positions are projected onto a pre-generated circuit path to lap
  progress, which the frontend animates with buffered, timestamped
  interpolation.
- REST serves full snapshots; WebSocket pushes incremental updates (weather,
  race control, gaps, locations, and predictions).

## Predictions

Pit strategy is estimated with XGBoost models trained on historical
driver-lap data:

- three binary pit-window models — `pit within 3/5/7 laps`;
- one multiclass next-compound model — `SOFT / MEDIUM / HARD / INTERMEDIATE / WET`.

At live time, the same feature builder used in training turns the current
session's data into features and the models score each driver. Predictions are
model estimates — never shown as certainties — and when a session has no
interval data (for example Qualifying), missing features are left to the
model's own missing-value handling rather than fabricated.

## Replay mode

Completed Grands Prix can be replayed from a local cache with buffered
source-time playback at 1×, 2×, 5×, and 10× speeds, pause/resume, and seeking.
Replay runs in isolation from live data, so it stays available even when no
session is live.

## Tech stack

- **Backend** — Python 3.10+, FastAPI, pandas/NumPy, XGBoost/scikit-learn,
  paho-mqtt.
- **Frontend** — React, TypeScript, Vite, Tailwind CSS.

## Running locally

First-time setup and daily startup are documented in
[docs/development/SETUP.md](docs/development/SETUP.md) and
[docs/development/FAST_START.md](docs/development/FAST_START.md).

## Documentation

See [docs/README.md](docs/README.md) for the full index — architecture, setup,
data, models, the API contract, frontend state screens, track maps, and Replay
Mode.

## Status

Core capabilities are implemented with automated coverage:

- live bootstrap and WebSocket streaming for any session type (Race,
  Qualifying, Sprint, Practice);
- the full dashboard (header, map, leaderboard, strategy panel);
- live and replay prediction scoring;
- replay mode with pause/seek/speed controls.

## Development

```bash
pytest                        # backend tests
ruff check src tests          # lint
black src tests               # format
```

Frontend build and pure-math tests:

```powershell
cd frontend
npm run build
node --experimental-strip-types --test "tests/*.test.ts"
```

## License

[MIT](LICENSE)
