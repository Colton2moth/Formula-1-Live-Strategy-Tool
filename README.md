# OpenF1 Strategy Backend

A learning-first backend project that uses historical OpenF1 data to train Formula 1 strategy models and live OpenF1 data to serve race information and predictions to a frontend.

## Initial goal

Build a baseline model that predicts whether a driver will pit within the next few laps, plus a companion model for the next tyre compound.

## System flow

Historical:

```text
OpenF1 REST API
→ raw JSON
→ processed driver-lap rows
→ training dataset
→ trained models
```

Live:

```text
OpenF1 live feed
→ current race state
→ feature generation
→ model inference
→ FastAPI REST/WebSocket API
→ frontend
```

## Core principle

Keep the project simple enough that every file, function, and design decision is understood before moving forward.

## Requirements

- Python 3.10+
- pip
- Node.js (frontend)

## Documentation

See [docs/README.md](docs/README.md) for the full documentation index, covering
architecture, setup, development workflow, data, models, the API contract, the
frontend, Replay Mode, and project planning.

## Getting started

First-time setup and daily startup are documented in
[docs/development/SETUP.md](docs/development/SETUP.md).

## Project layout

```
.
├── src/formula1_strategy_tool/   # Application package
├── docs/                         # Documentation (see docs/README.md)
├── frontend/                     # React frontend
├── tests/                        # Pytest tests
├── data/                         # Local data (gitignored)
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

## Development

```bash
# Run tests
pytest

# Lint
ruff check src tests

# Format
black src tests
```

## License

MIT
