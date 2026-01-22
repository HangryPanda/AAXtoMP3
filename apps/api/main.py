"""FastAPI application entrypoint for Audible Library Manager API."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health, jobs, library, settings, stream
from core.config import get_settings
from db.session import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup/shutdown events."""
    # Startup
    config = get_settings()
    config.ensure_directories()
    await create_db_and_tables()
    yield
    # Shutdown - cleanup if needed


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
