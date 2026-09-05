# Development Setup

Everything needed to install and run the backend and frontend. First-time setup
is one section; normal daily startup is another. For how changes should be
developed (commit size, complexity checks), see [WORKFLOW.md](./WORKFLOW.md).

## First-time setup

Run these from the repo root unless stated otherwise.

### Backend dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

`pip install -e .` installs the package in editable mode so the console
scripts (`f1-download-openf1`, `f1-process-races`, `f1-train-pit`) are on your
`PATH`.

### Frontend dependencies

```powershell
cd frontend
npm install
```

### Environment configuration

Copy `.env.example` to `.env` if you need local configuration (for example the
OpenF1 credentials used by the downloader and replay mode).

### Required local data

Live predictions are scored from the current live session's features using the
trained models under `data/models`. The historical driver-lap CSV is needed only
to train those models, not to serve predictions.

To run the dashboard against live data, make sure `data/models` contains the
trained model files (see [models/TRAINING.md](../models/TRAINING.md)). To train
or retrain the models from the full historical dataset:

```powershell
.\.venv\Scripts\Activate.ps1
f1-download-openf1
f1-process-races
f1-train-pit
```

`f1-download-openf1` downloads completed Race sessions into `data/raw/` (a
large download; safe to re-run — it skips files already on disk).
`f1-process-races` builds `data/processed/driver_laps_all.csv`. Both folders
are gitignored local data, so run the download + process step on each new
machine. See [data/ACQUISITION.md](../data/ACQUISITION.md) for the downloader
and [models/TRAINING.md](../models/TRAINING.md) for training.

## Normal daily startup

### Start the backend

Open one terminal at the repo root:

```powershell
.\.venv\Scripts\Activate.ps1
fastapi dev src/formula1_strategy_tool/main.py
```

The backend is available at `http://127.0.0.1:8000`. Useful checks:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api/race-state`

### Start the frontend

Wait for the backend to finish starting, then open a second terminal:

```powershell
cd frontend
npm run dev
```

Vite prints a local URL, usually `http://127.0.0.1:5173/`. In development, Vite
proxies `/api` requests to the FastAPI server on port `8000`.

## Local production preview

Use this to check the built version of the website locally:

```powershell
cd frontend
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run build
npm run preview
```

Keep the FastAPI terminal running while previewing. Vite prints the preview
URL, usually `http://127.0.0.1:4173/`.

## Common setup problems

- If the website loads without data, confirm FastAPI is running and
  `http://127.0.0.1:8000/api/race-state` returns JSON.
- If `fastapi` is not recognized, reactivate `.venv` and rerun
  `pip install -r requirements.txt`.
- If `npm run dev` fails, run `npm install` inside `frontend`.
- If a launcher still references an old project path after the repo was moved
  or renamed, recreate `.venv` from the repo root because Windows
  virtual-environment launchers store absolute paths:

  ```powershell
  Remove-Item -Recurse -Force .venv
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  pip install -e .
  ```
