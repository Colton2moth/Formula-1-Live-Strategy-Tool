# Fast Start

Use this after you have completed [FIRST_TIME_SETUP.md](FIRST_TIME_SETUP.md) at least once.

## Start the backend

Open a terminal at the repo root and run:

```powershell
.\.venv\Scripts\Activate.ps1
fastapi dev src/formula1_strategy_tool/main.py
```

The backend should be available at `http://127.0.0.1:8000`.

## Start the frontend

Wait for fastapi to complete its set up the, open a second terminal at the repo root and run:

```powershell
cd frontend
npm run dev
```

Open the URL printed by Vite, usually `http://127.0.0.1:5173/`.

## Quick troubleshooting

- If the website loads without data, check `http://127.0.0.1:8000/api/race-state`.
- If `fastapi` is not recognized, reactivate `.venv` in the backend terminal.
- If a launcher still references an old project path after the repo was moved or
  renamed, recreate `.venv` from the repo root because Windows virtual-environment
  launchers store absolute paths:

  ```powershell
  Remove-Item -Recurse -Force .venv
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  pip install -e .
  ```

- If frontend packages changed, run `npm install` inside `frontend` before starting Vite.
