"""FastAPI application entrypoint for Audible Library Manager API."""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health, jobs, library, settings, stream
from core.config import get_settings
from db.session import create_db_and_tables
from services.job_recovery import mark_inflight_jobs_interrupted

# Configure logging to show INFO level and above
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

# Also configure uvicorn's logger to avoid duplicates
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# Global shutdown event for coordinating graceful shutdown
shutdown_event: asyncio.Event | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup/shutdown events."""
    global shutdown_event

    # Startup
    logger.info("Starting Audible Library Manager API...")
    config = get_settings()
    config.ensure_directories()
    await create_db_and_tables()
    await mark_inflight_jobs_interrupted()

    # Initialize shutdown event
    shutdown_event = asyncio.Event()

    # Store in app state for access from routes/services
    app.state.shutdown_event = shutdown_event

    logger.info("API startup complete")
    yield

    # Shutdown - graceful cleanup
    logger.info("Initiating graceful shutdown...")

    # Signal shutdown to all components
    if shutdown_event:
        shutdown_event.set()

    # Import job_manager here to avoid circular imports
    try:
        from api.routes.jobs import get_job_manager
        job_manager = get_job_manager()
        if job_manager:
            logger.info("Waiting for running jobs to complete graceful shutdown...")
            await job_manager.shutdown(timeout=25.0)  # Leave 5s buffer for docker
    except Exception as e:
        logger.warning("Error during job manager shutdown: %s", e)

    # Close any open file handles or connections
    logger.info("Closing database connections...")
    # SQLAlchemy async engine cleanup is handled by the session context

    logger.info("Graceful shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_settings()

    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        description="REST API for managing Audible audiobook library, downloads, and conversions",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins_list,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(library.router, prefix="/library", tags=["Library"])
    app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
    app.include_router(settings.router, prefix="/settings", tags=["Settings"])
    app.include_router(stream.router, prefix="/stream", tags=["Stream"])

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = get_settings()
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        workers=config.workers if not config.debug else 1,
    )
