# OpenF1 Strategy Backend

A learning-first backend project that uses historical OpenF1 data to train Formula 1 strategy models and live OpenF1 data to serve race information and predictions to a frontend.

## Initial goal

Build a baseline model that predicts whether a driver will pit within the next five laps.

## System flow

Historical:

```text
OpenF1 REST API
→ raw JSON
→ processed driver-lap rows
→ training dataset
→ trained model
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

## Development order

1. Download historical race data.
2. Inspect one race manually.
3. Define one processed row: one driver at one completed lap.
4. Build the processing pipeline for one race.
5. Create labels for pit-within-five-laps.
6. Train a simple baseline model.
7. Add a minimal FastAPI prediction endpoint.
8. Add live ingestion only after the historical pipeline works.

## Current scope

Include:

- Race sessions from 2023 onward
- Laps
- Stints
- Pit stops
- Position
- Intervals
- Weather
- Race control
- Session and driver metadata

Exclude for now:

- Historical location data
- Historical car telemetry
- Databases
- Redis
- Docker
- Microservices
- Cloud deployment
- Advanced strategy simulation

## Core principle

Keep the project simple enough that every file, function, and design decision is understood before moving forward.

## Requirements

- Python 3.10+
- pip

## Setup

```bash
# Clone and enter the repo
cd Formula-1-Live-Strategy-Tool

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Optional: dev tools (testing, linting, formatting)
pip install -r requirements-dev.txt

# Optional: install package in editable mode
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` if you need local configuration.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Data acquisition](docs/DATA_ACQUISITION.md)
- [Development workflow](docs/DEVELOPMENT_WORKFLOW.md)
- [Roadmap](docs/ROADMAP.md)
- [Design decisions](docs/DECISIONS.md)
- [Next step](docs/NEXT_STEP.md)
- [Agent instructions](AGENTS.md)

## Usage

### Historical data download (run once)

Downloads all completed Race sessions from 2023 through the current year into `data/raw/`. Re-running skips files already on disk.

```bash
source .venv/bin/activate
pip install -e .

# Foreground (watch progress in terminal)
f1-download-openf1

# Background — survives closing the terminal (good for a work-day run)
nohup f1-download-openf1 > download.log 2>&1 &

# Watch progress
tail -f download.log
```

Options:

```bash
f1-download-openf1 --start-year 2023 --end-year 2025
```

Expect roughly 1–3 hours for all races at the API rate limit (~2s per request). Failures are logged to `data/raw/download_errors.jsonl`; re-run the same command to retry only what failed.

### CLI stub

```bash
source .venv/bin/activate
f1-strategy --help
```

Or run directly:

```bash
python -m formula1_strategy_tool.acquisition
python -m formula1_strategy_tool
```

## Project layout

```
.
├── src/formula1_strategy_tool/   # Application package
├── docs/                         # Architecture and workflow docs
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
