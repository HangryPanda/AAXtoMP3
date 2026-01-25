"""Integration tests for playback workflow (details, chapters, progress)."""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Book, BookStatus, Chapter, BookTechnical, BookAsset, BookAuthor, Person


class TestPlaybackWorkflow:
    """Tests for playback-related workflows."""

    @pytest.mark.asyncio
    async def test_get_book_details_with_chapters(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        sample_book_data: dict[str, Any],
    ) -> None:
        """Test fetching book details including chapters and technical info."""
        asin = sample_book_data["asin"]
        
        # 1. Create Book
        book = Book(**sample_book_data)
        test_session.add(book)
        await test_session.commit()

        # 2. Create Chapters
        chapters = [
            Chapter(
                book_asin=asin,
                index=0,
                title="Chapter 1",
                start_offset_ms=0,
                length_ms=60000,
                end_offset_ms=60000,
            ),
            Chapter(
                book_asin=asin,
                index=1,
                title="Chapter 2",
                start_offset_ms=60000,
                length_ms=120000,
                end_offset_ms=180000,
            ),
        ]
        test_session.add_all(chapters)

        # 3. Create Technical Info
        tech = BookTechnical(
            book_asin=asin,
            format="m4b",
            bitrate=64000,  # Fixed: using integer
            sample_rate=44100,
            channels=2,
            duration_ms=180000,
            file_size=1024000,
        )
        test_session.add(tech)

        # 4. Create Cover Asset
        cover = BookAsset(
            book_asin=asin,
            asset_type="cover",
            path="/tmp/cover.jpg",
            mime_type="image/jpeg",
        )
        test_session.add(cover)
        
        await test_session.commit()

        # 5. Call API
        response = await client.get(f"/library/{asin}/details")

        assert response.status_code == 200
        data = response.json()

        # Assert Basic Info
        assert data["asin"] == asin
        assert data["title"] == sample_book_data["title"]

        # Assert Chapters
        assert len(data["chapters"]) == 2
        assert data["chapters"][0]["title"] == "Chapter 1"
        assert data["chapters"][0]["start_offset_ms"] == 0
        assert data["chapters"][1]["title"] == "Chapter 2"
        assert data["chapters"][1]["end_offset_ms"] == 180000

        # Assert Technical
        assert data["technical"]["duration_ms"] == 180000
        assert data["duration_total_ms"] == 180000
        assert data["technical"]["format"] == "m4b"

        # Assert Cover
        assert data["cover_url"] == f"/api/library/{asin}/cover"

    @pytest.mark.asyncio
    async def test_playback_progress_workflow(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        sample_book_data: dict[str, Any],
    ) -> None:
        """Test the full playback progress lifecycle."""
        asin = sample_book_data["asin"]
        
        # 1. Create Book
        book = Book(**sample_book_data)
        test_session.add(book)
        
        # 2. Create a Chapter (needed for FK constraint)
        chapter_id = uuid4()
        chapter = Chapter(
            id=chapter_id,
            book_asin=asin,
            index=0,
            title="Chapter 1",
            start_offset_ms=0,
            length_ms=60000,
            end_offset_ms=60000,
        )
        test_session.add(chapter)
        
        await test_session.commit()

        # 3. Check initial progress (should be None or empty)
        response = await client.get(f"/library/{asin}/progress")
        assert response.status_code == 200
        assert response.json() is None

        # 4. Start playback (Update Progress)
        progress_update = {
            "position_ms": 5000,
            "playback_speed": 1.0,
            "chapter_id": str(chapter_id), # Valid UUID string
            "is_finished": False
        }
        response = await client.patch(f"/library/{asin}/progress", json=progress_update)
        assert response.status_code == 200
        data = response.json()
        assert data["position_ms"] == 5000
        assert data["is_finished"] is False
        assert data["last_chapter_id"] == str(chapter_id)
        assert data["last_played_at"] is not None

        # 5. Fetch details to verify progress inclusion
        response = await client.get(f"/library/{asin}/details")
        assert response.status_code == 200
        data = response.json()
        assert data["playback_progress"]["position_ms"] == 5000

        # 6. Finish book
        finish_update = {
            "position_ms": 60000,
            "playback_speed": 1.2,
            "chapter_id": str(chapter_id),
            "is_finished": True
        }
        response = await client.patch(f"/library/{asin}/progress", json=finish_update)
        assert response.status_code == 200
        data = response.json()
        assert data["is_finished"] is True
        assert data["completed_at"] is not None
        assert data["playback_speed"] == 1.2

        # 7. Verify persistence
        response = await client.get(f"/library/{asin}/progress")
        assert response.status_code == 200
        data = response.json()
        assert data["is_finished"] is True