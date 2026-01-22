"""Integration tests for settings endpoints."""

import pytest
from httpx import AsyncClient


class TestSettingsEndpoints:
    """Tests for settings management endpoints."""

    @pytest.mark.asyncio
    async def test_get_settings_returns_defaults(self, client: AsyncClient) -> None:
        """Test getting settings returns default values."""
        response = await client.get("/settings")

        assert response.status_code == 200
        data = response.json()

        # Check default values
        assert data["output_format"] == "m4b"
        assert data["single_file"] is True
        assert data["compression_mp3"] == 4
        assert data["compression_flac"] == 5
        assert data["compression_opus"] == 5
        assert data["cover_size"] == "1215"
        assert data["no_clobber"] is False
        assert data["move_after_complete"] is False
        assert data["auto_retry"] is True
        assert data["max_retries"] == 3

    @pytest.mark.asyncio
    async def test_update_settings_partial(self, client: AsyncClient) -> None:
        """Test partial settings update."""
        response = await client.patch(
            "/settings",
            json={"output_format": "mp3", "compression_mp3": 6},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["output_format"] == "mp3"
        assert data["compression_mp3"] == 6
        # Other values should remain default
        assert data["single_file"] is True
        assert data["compression_flac"] == 5

    @pytest.mark.asyncio
    async def test_update_settings_naming_scheme(self, client: AsyncClient) -> None:
        """Test updating naming schemes."""
        response = await client.patch(
            "/settings",
            json={
                "dir_naming_scheme": "$artist/$title",
                "file_naming_scheme": "$title - $narrator",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["dir_naming_scheme"] == "$artist/$title"
        assert data["file_naming_scheme"] == "$title - $narrator"

    @pytest.mark.asyncio
    async def test_update_settings_invalid_compression(self, client: AsyncClient) -> None:
        """Test invalid compression values are rejected."""
        response = await client.patch(
            "/settings",
            json={"compression_mp3": 15},  # Invalid: max is 9
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_get_naming_variables(self, client: AsyncClient) -> None:
        """Test getting available naming variables."""
        response = await client.get("/settings/naming-variables")

        assert response.status_code == 200
        data = response.json()

        assert "directory" in data
        assert "file" in data
        assert "chapter" in data

        # Check common variables exist
        assert "$title" in data["directory"]
        assert "$artist" in data["directory"]
        assert "$chapter" in data["chapter"]
        assert "$chapternum" in data["chapter"]

    @pytest.mark.asyncio
    async def test_settings_persistence(self, client: AsyncClient) -> None:
        """Test settings are persisted across requests."""
        # Update a setting
        await client.patch(
            "/settings",
            json={"output_format": "flac"},
        )

        # Fetch settings again
        response = await client.get("/settings")
        data = response.json()

        assert data["output_format"] == "flac"
