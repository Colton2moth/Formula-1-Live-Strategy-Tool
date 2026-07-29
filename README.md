# Formula 1 Live Strategy Tool

Backend for an F1 strategy app: OpenF1 data, trained models, FastAPI for the frontend.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

Copy `.env.example` to `.env` if you need local config.

## Run the API (frontend)

Mock REST API — stable JSON shapes for UI work. Not live race data yet.

```bash
source .venv/bin/activate
fastapi dev src/formula1_strategy_tool/main.py
```

- API docs: http://127.0.0.1:8000/docs  
- Liveness: http://127.0.0.1:8000/  
- Routes under `/api/...` (session, drivers, predictions, race-state, track)

## Other commands

```bash
# Download historical OpenF1 race JSON → data/raw/
f1-download-openf1

# Build per-race + master driver-lap CSVs → data/processed/
python -m formula1_strategy_tool.processing

# Train pit-window + next-compound models → data/models/
python -m formula1_strategy_tool.training
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## License

MIT
