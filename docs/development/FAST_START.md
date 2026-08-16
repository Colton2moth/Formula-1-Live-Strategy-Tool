# Fast Start

Quick reference for daily development after [first-time setup](./SETUP.md) is
complete. Everything here assumes `.venv` exists and `frontend/node_modules` is
installed.

## Start the backend

Terminal 1, repo root:

```powershell
.\.venv\Scripts\Activate.ps1
fastapi dev src/formula1_strategy_tool/main.py
```

Backend runs at `http://127.0.0.1:8000`.

## Start the frontend

Terminal 2, after the backend is up:

```powershell
cd frontend
npm run dev
```

Vite runs at `http://127.0.0.1:5173/` and proxies `/api` to port `8000`.

## Verify

- `http://127.0.0.1:8000/api/race-state` returns JSON.
- The dashboard loads live or shows the historical snapshot.

## Quick fixes

- Website loads without data: confirm FastAPI is running and `/api/race-state`
  returns JSON.
- `FileNotFoundError: data/processed/driver_laps_all.csv`: run
  `f1-download-openf1` then `f1-process-races`.
- `fastapi` not recognized: reactivate `.venv` and rerun
  `pip install -r requirements.txt`.
- `npm run dev` fails: run `npm install` inside `frontend`.
