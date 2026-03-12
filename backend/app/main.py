"""
FastAPI application entry point.

Startup sequence
----------------
1. Logging is configured.
2. The lifespan context manager creates all database tables (idempotent).
3. CORS middleware is applied using ALLOWED_ORIGINS from .env.
4. API routes are mounted under /api.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.db import models  # noqa: F401 — registers ORM models with Base.metadata
from app.db.database import Base, engine

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Suppress noisy SQLAlchemy echo unless DEBUG is on
logging.getLogger("sqlalchemy.engine").setLevel(
    logging.INFO if settings.DEBUG else logging.WARNING
)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Fraud Detection API …")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified / created.")
    except Exception:
        logger.exception("Database initialisation failed — is MySQL running?")
    yield
    logger.info("Fraud Detection API shutting down.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Fraud Detection API",
    description=(
        "REST API for tracing URL redirect chains and detecting fraudulent "
        "domains using heuristic analysis. Results are persisted to MySQL."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Parse comma-separated origins from config (supports wildcard "*")
allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,          # credentials not needed for extension calls
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(router, prefix="/api", tags=["fraud-detection"])


# ---------------------------------------------------------------------------
# Dev-server convenience entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
