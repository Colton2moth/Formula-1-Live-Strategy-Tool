import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from formula1_strategy_tool.api.routes import router as api_router


# Single app instance — uvicorn / fastapi dev import this object.
app = FastAPI(
    title="Formula 1 Live Strategy Tool",
    description="Mock REST API for frontend development. See docs/API_CONTRACT.md.",
    version="0.1.0",
)

frontend_url = os.getenv("FRONTEND_URL")

if frontend_url:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[frontend_url],
        allow_methods=["*"],
        allow_headers=["*"],
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
