"""MonsoonAI FastAPI application.

Start with:  uvicorn app.main:app --reload --port 8000   (from backend/)
Interactive API docs:  http://localhost:8000/docs
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import DEMO_MODE_BANNER
from .ml.registry import get_engine
from .routes import forecast, live, meta, predict, upload, verify

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("monsoonai")

app = FastAPI(
    title="MonsoonAI API",
    description=(
        "Regime-Aware AI Post-Processing of Monsoon Rainfall Forecasts. "
        f"{DEMO_MODE_BANNER}. Demo forecasts are synthetic and are not official "
        "weather forecasts."
    ),
    version="1.0.0",
)

# The dashboard is served by Vite on a different port, so CORS is required.
# Origins are permissive for the local prototype; restrict them for deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(forecast.router)
app.include_router(predict.router)
app.include_router(verify.router)
app.include_router(upload.router)
app.include_router(live.router)


@app.on_event("startup")
def startup() -> None:
    """Load models once at boot and log whether trained artefacts were found."""
    engine = get_engine(reload=True)
    info = engine.info()
    logger.info("MonsoonAI starting in %s mode", info["mode"])
    if not engine.trained:
        logger.warning(
            "No trained models found in %s - the API will answer with the "
            "documented heuristic fallback. Run 'python train_models.py'.",
            info["models_dir"],
        )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the traceback server-side; never leak it to the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check the backend logs for details."},
    )
