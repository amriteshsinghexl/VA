"""
VA Actuarial Engine â€” FastAPI backend.

Start with:  python start_backend.py
API docs at: http://localhost:8001/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.routes import health, model, outputs


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    import logging
    logging.getLogger(__name__).info(
        "VA backend started â€” base_dir=%s  port=%s", settings.base_dir, settings.port
    )
    yield


app = FastAPI(
    title="VA Actuarial Engine API",
    description=(
        "FastAPI backend for the Abc_corp VA Python Valuation Model. "
        "Supports async job submission, SSE-compatible status polling, "
        "and output file browsing."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(model.router)
app.include_router(outputs.router)
