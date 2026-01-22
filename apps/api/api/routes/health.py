"""Health check endpoints."""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings, get_settings
from db.session import get_session

router = APIRouter()


class HealthStatus(BaseModel):
    """Health check response model."""

    status: Literal["healthy", "unhealthy", "degraded"]
    database: Literal["connected", "disconnected"]
    filesystem: Literal["accessible", "inaccessible"]
    scripts: Literal["available", "missing"]
    version: str
    environment: str


class LivenessResponse(BaseModel):
    """Kubernetes liveness probe response."""

    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    """Kubernetes readiness probe response."""

    status: Literal["ready", "not_ready"]
    details: dict[str, bool]


@router.get("/health", response_model=HealthStatus)
async def health_check(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> HealthStatus:
    """Full health check endpoint."""
    # Check database
    db_status: Literal["connected", "disconnected"] = "disconnected"
    try:
        await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        pass

    # Check filesystem
    fs_status: Literal["accessible", "inaccessible"] = "inaccessible"
    try:
        if settings.downloads_dir.exists() or settings.downloads_dir.parent.exists():
            fs_status = "accessible"
    except Exception:
        pass

    # Check scripts
    scripts_status: Literal["available", "missing"] = "missing"
    try:
        if settings.aaxtomp3_path.exists():
            scripts_status = "available"
    except Exception:
        pass

    # Determine overall status
    overall: Literal["healthy", "unhealthy", "degraded"]
    if db_status == "connected" and fs_status == "accessible" and scripts_status == "available":
        overall = "healthy"
    elif db_status == "connected":
        overall = "degraded"
    else:
        overall = "unhealthy"

    return HealthStatus(
        status=overall,
        database=db_status,
        filesystem=fs_status,
        scripts=scripts_status,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/health/live", response_model=LivenessResponse)
async def liveness_probe() -> LivenessResponse:
    """Kubernetes liveness probe - checks if app is running."""
    return LivenessResponse(status="ok")


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_probe(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ReadinessResponse:
    """Kubernetes readiness probe - checks if app can serve requests."""
    checks: dict[str, bool] = {}

    # Database check
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # Filesystem check
    try:
        checks["filesystem"] = settings.downloads_dir.exists() or settings.downloads_dir.parent.exists()
    except Exception:
        checks["filesystem"] = False

    all_ready = all(checks.values())

    return ReadinessResponse(
        status="ready" if all_ready else "not_ready",
        details=checks,
    )
