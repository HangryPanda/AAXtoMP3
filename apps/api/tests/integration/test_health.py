"""Integration tests for health endpoints."""

import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient) -> None:
        """Test full health check endpoint."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy", "degraded"]
        assert "database" in data
        assert "filesystem" in data
        assert "scripts" in data
        assert "version" in data
        assert "environment" in data

    @pytest.mark.asyncio
    async def test_liveness_probe(self, client: AsyncClient) -> None:
        """Test Kubernetes liveness probe."""
        response = await client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_readiness_probe(self, client: AsyncClient) -> None:
        """Test Kubernetes readiness probe."""
        response = await client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] in ["ready", "not_ready"]
        assert "details" in data
        assert isinstance(data["details"], dict)
