# First-Time Setup

Use this guide the first time you set up the project on a computer. It installs the backend and frontend dependencies, then starts both parts of the dashboard.

After completing this once, use [FAST_START.md](FAST_START.md) for normal startup.

## Set up the backend

Run these from the repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## Set up the frontend

Install the frontend packages from the repo root:

```powershell
cd frontend
npm install
```

## Download and process historical data

When no race is live, `/api/race-state` serves predictions from a historical
CSV snapshot. The commands differ depending on whether you only run the backend
or also train the models.

### Just run the backend (recommended for the dashboard)

Download only the season that contains the configured `INFERENCE_SESSION_KEY`
(default `9979`, the 2025 Monaco Grand Prix), then build the CSV:

```powershell
.\.venv\Scripts\Activate.ps1
f1-download-openf1 --start-year 2025 --end-year 2025
f1-process-races
```

### Train or retrain the models

The full historical dataset is required for training. Download every season
(2023 onward), process it, then train:

```powershell
.\.venv\Scripts\Activate.ps1
f1-download-openf1
f1-process-races
f1-train-pit
```

`f1-download-openf1` downloads Race sessions into `data/raw/` (a large download;
safe to re-run, it skips files already on disk). `f1-process-races` builds
`data/processed/driver_laps_all.csv`. Both folders are gitignored local data, so
run the download + process step on each new machine.

## Start the backend for the first time

Open one terminal at the repo root:

```powershell
.\.venv\Scripts\Activate.ps1
fastapi dev src/formula1_strategy_tool/main.py
```

FastAPI should be available at `http://127.0.0.1:8000`.
Useful checks:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api/race-state`

## Start the website for the first time

Open a second terminal:

```powershell
cd frontend
npm run dev
```

Vite should print a local URL, usually `http://127.0.0.1:5173/`.
In development, Vite proxies `/api` requests to the FastAPI server on port `8000`.

## View a local production build

Use this when you want to check the built version of the website locally:

```powershell
cd frontend
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run build
npm run preview
```

Keep the FastAPI terminal running while previewing the production build. Vite will print the preview URL, usually `http://127.0.0.1:4173/`.

## First-time setup issues

- If the website loads but data does not, confirm FastAPI is running and `http://127.0.0.1:8000/api/race-state` returns JSON.
- If `fastapi` is not recognized, reactivate `.venv` and rerun `pip install -r requirements.txt`.
- If `npm run dev` fails, run `npm install` inside `frontend`.
