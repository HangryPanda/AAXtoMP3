"""Integration tests for library endpoints."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Book, BookStatus


class TestLibraryEndpoints:
    """Tests for library management endpoints."""

    @pytest.mark.asyncio
    async def test_get_books_empty(self, client: AsyncClient) -> None:
        """Test getting books when library is empty."""
        response = await client.get("/library")

        assert response.status_code == 200
        data = response.json()

        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_get_books_with_data(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        sample_book_data: dict[str, Any],
    ) -> None:
        """Test getting books with data in database."""
        # Create a book
        book = Book(**sample_book_data)
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/library")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["asin"] == "B00TEST123"
        assert data["items"][0]["title"] == "Test Audiobook"

    @pytest.mark.asyncio
    async def test_get_books_pagination(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test books pagination."""
        # Create multiple books
        for i in range(15):
            book = Book(
                asin=f"B00TEST{i:03d}",
                title=f"Test Book {i}",
            )
            test_session.add(book)
        await test_session.commit()

        # Get first page
        response = await client.get("/library?page=1&page_size=10")
        data = response.json()

        assert data["total"] == 15
        assert len(data["items"]) == 10
        assert data["page"] == 1
        assert data["total_pages"] == 2

        # Get second page
        response = await client.get("/library?page=2&page_size=10")
        data = response.json()

        assert len(data["items"]) == 5
        assert data["page"] == 2

    @pytest.mark.asyncio
    async def test_get_books_filter_by_status(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test filtering books by status."""
        # Create books with different statuses
        book1 = Book(asin="B001", title="Book 1", status=BookStatus.NEW)
        book2 = Book(asin="B002", title="Book 2", status=BookStatus.COMPLETED)
        book3 = Book(asin="B003", title="Book 3", status=BookStatus.COMPLETED)
        test_session.add_all([book1, book2, book3])
        await test_session.commit()

        # Filter by COMPLETED
        response = await client.get("/library?status=COMPLETED")
        data = response.json()

        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_get_books_filter_by_content_type(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test filtering books by content type (audiobook vs podcast)."""
        podcast = Book(
            asin="P001",
            title="Podcast 1",
            metadata_json={"content_type": "Podcast"},
        )
        audiobook = Book(
            asin="A001",
            title="Audiobook 1",
            metadata_json={"content_type": "Product"},
        )
        unknown = Book(
            asin="U001",
            title="Unknown 1",
            metadata_json=None,
        )
        test_session.add_all([podcast, audiobook, unknown])
        await test_session.commit()

        response = await client.get("/library?content_type=podcast")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["asin"] == "P001"
        assert data["items"][0]["content_type"] == "Podcast"

        response = await client.get("/library?content_type=audiobook")
        data = response.json()
        asins = {it["asin"] for it in data["items"]}
        assert "P001" not in asins
        assert {"A001", "U001"}.issubset(asins)

    @pytest.mark.asyncio
    async def test_get_books_search(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """Test searching books."""
        book1 = Book(asin="B001", title="Python Programming")
        book2 = Book(asin="B002", title="JavaScript Guide")
        book3 = Book(asin="B003", title="Python Web Development")
        test_session.add_all([book1, book2, book3])
        await test_session.commit()

        response = await client.get("/library?search=Python")
        data = response.json()

        assert data["total"] == 2
        titles = [item["title"] for item in data["items"]]
        assert "Python Programming" in titles
        assert "Python Web Development" in titles

    @pytest.mark.asyncio
    async def test_get_single_book(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        sample_book_data: dict[str, Any],
    ) -> None:
        """Test getting a single book by ASIN."""
        book = Book(**sample_book_data)
        test_session.add(book)
        await test_session.commit()

        response = await client.get("/library/B00TEST123")

        assert response.status_code == 200
        data = response.json()

        assert data["asin"] == "B00TEST123"
        assert data["title"] == "Test Audiobook"
        assert data["runtime_length_min"] == 360

    @pytest.mark.asyncio
    async def test_get_single_book_not_found(self, client: AsyncClient) -> None:
        """Test getting a non-existent book."""
        response = await client.get("/library/NONEXISTENT")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_book(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        sample_book_data: dict[str, Any],
    ) -> None:
        """Test updating a book."""
        book = Book(**sample_book_data)
        test_session.add(book)
        await test_session.commit()

        response = await client.patch(
            "/library/B00TEST123",
            json={
                "status": "DOWNLOADED",
                "local_path_aax": "/downloads/test.aaxc",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "DOWNLOADED"
        assert data["local_path_aax"] == "/downloads/test.aaxc"

    @pytest.mark.asyncio
    async def test_update_book_not_found(self, client: AsyncClient) -> None:
        """Test updating a non-existent book."""
        response = await client.patch(
            "/library/NONEXISTENT",
            json={"status": "DOWNLOADED"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_sync_library(self, client: AsyncClient) -> None:
        """Test triggering library sync."""
        with patch("api.routes.jobs.job_manager") as mock_manager:
            mock_manager.queue_sync = AsyncMock()

            response = await client.post("/library/sync")

            assert response.status_code == 202
            data = response.json()

            assert "job_id" in data
            assert data["status"] == "QUEUED"
            assert "queued" in data["message"].lower()
            mock_manager.queue_sync.assert_called_once()
