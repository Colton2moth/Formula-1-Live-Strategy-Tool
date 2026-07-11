# Fast Start

Use this after you have completed [FIRST_TIME_SETUP.md](FIRST_TIME_SETUP.md) at least once.

## Start the backend

Open a terminal at the repo root:

```powershell
.\.venv\Scripts\Activate.ps1
fastapi dev src/formula1_strategy_tool/main.py
```

The backend should be available at `http://127.0.0.1:8000`.

## Start the frontend

Open a second terminal at the repo root:

```powershell
cd frontend
npm run dev
```

Open the URL printed by Vite, usually `http://127.0.0.1:5173/`.

## Quick troubleshooting

- If the website loads without data, check `http://127.0.0.1:8000/api/race-state`.
- If `fastapi` is not recognized, reactivate `.venv` in the backend terminal.
- If frontend packages changed, run `npm install` inside `frontend` before starting Vite.
