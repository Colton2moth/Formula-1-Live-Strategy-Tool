"""
FastAPI application entry point for the Formula 1 Live Strategy Tool.

This module is the top of the "Application API" layer (see docs/ARCHITECTURE.md §7).
The frontend talks only to this backend — not directly to OpenF1.

Current scope:
    - GET /              — liveness check
    - GET /api/*         — mock REST endpoints (docs/API_CONTRACT.md)
    - OpenAPI docs at /docs for frontend development

Mock data lives in api/mocks.py. Replace with live state + model output later.

Run locally:
    fastapi dev src/formula1_strategy_tool/main.py
    # or
    uvicorn formula1_strategy_tool.main:app --reload
"""

from fastapi import FastAPI

from formula1_strategy_tool.api.routes import router as api_router

# Single app instance — uvicorn / fastapi dev import this object.
app = FastAPI(
    title="Formula 1 Live Strategy Tool",
    description="Mock REST API for frontend development. See docs/API_CONTRACT.md.",
    version="0.1.0",
)

# Mount all /api/... contract routes from the mock router.
app.include_router(api_router)


@app.get("/")
def root() -> dict[str, str]:
    """
    Root liveness check.

    Returns a simple JSON message. Does not reflect race or model state.
    """
    return {"message": "OpenF1 backend is running"}
