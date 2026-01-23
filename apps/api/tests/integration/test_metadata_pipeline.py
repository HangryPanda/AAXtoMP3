"""Integration tests for the metadata scanning pipeline."""

import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path
from sqlalchemy import select
from db.models import Book, BookStatus
from services.library_manager import LibraryManager
from services.metadata_extractor import MetadataExtractor

@pytest.fixture
def mock_ffprobe_data():
    return {
        "format": {
            "format_name": "mp4",
            "duration": "3600.0",
            "size": "50000000",
            "bit_rate": "128000",
            "tags": {
                "title": "Integration Test Book",
                "artist": "Pipeline Author",
                "composer": "Pipeline Narrator",
                "album": "Pipeline Series",
                "genre": "Sci-Fi",
                "date": "2024",
                "comment": "Description here"
            }
        },
        "streams": [
            {
                "codec_type": "audio",
                "sample_rate": "44100",
                "channels": 2
            }
        ],
        "chapters": [
            {
                "id": 0,
                "start_time": "0.0",
                "end_time": "1800.0",
                "tags": {"title": "Chapter 1"}
            },
            {
                "id": 1,
                "start_time": "1800.0",
                "end_time": "3600.0",
                "tags": {"title": "Chapter 2"}
            }
        ]
    }

@pytest.mark.asyncio
async def test_metadata_pipeline_end_to_end(
    client, test_session, mock_ffprobe_data, tmp_path
):
    """
    Test the flow: Book exists -> Scan -> Details Endpoint.
    """
    # 1. Setup: Create a book in 'COMPLETED' state with a dummy file
    asin = "B00PIPELINE"
    book = Book(
        asin=asin,
        title="Original Title", # Should be updated by scan
        status=BookStatus.COMPLETED,
        local_path_converted=str(tmp_path / "test.m4b")
    )
    test_session.add(book)
    await test_session.commit()

    # Create dummy file
    (tmp_path / "test.m4b").touch()

    # 2. Mock Extractor internals
    # We patch the instance that LibraryManager uses, or patch at the class level
    with patch("services.metadata_extractor.MetadataExtractor._run_ffprobe", new_callable=AsyncMock) as mock_run:
        with patch("services.metadata_extractor.MetadataExtractor.extract_cover", new_callable=AsyncMock) as mock_cover:
            mock_run.return_value = mock_ffprobe_data
            mock_cover.return_value = "/app/data/covers/test_cover.jpg"

            # 3. Trigger Scan via API
            response = await client.post(f"/library/{asin}/scan?force=true")
            assert response.status_code == 200
            assert response.json()["message"] == "Scan completed."

    # 4. Verify Persistence via Details Endpoint
    response = await client.get(f"/library/{asin}/details")
    assert response.status_code == 200
    data = response.json()

    # Check Book Identity
    assert data["title"] == "Integration Test Book"
    assert data["authors"][0]["name"] == "Pipeline Author"
    assert data["narrators"][0]["name"] == "Pipeline Narrator"
    
    # Check Series
    assert data["series"]["name"] == "Pipeline Series"
    
    # Check Chapters
    assert len(data["chapters"]) == 2
    assert data["chapters"][0]["title"] == "Chapter 1"
    assert data["chapters"][0]["length_ms"] == 1800000
    
    # Check Technical
    assert data["technical"]["sample_rate"] == 44100
    
    # Check Assets (Cover)
    assert data["assets"][0]["asset_type"] == "cover"
    assert data["assets"][0]["path"] == "/app/data/covers/test_cover.jpg"
    assert data["cover_url"] == f"/api/library/{asin}/cover"

@pytest.mark.asyncio
async def test_progress_update(client, test_session):
    asin = "B00PROGRESS"
    book = Book(asin=asin, title="Progress Test", status=BookStatus.COMPLETED)
    test_session.add(book)
    await test_session.commit()

    # 1. Update Progress
    payload = {
        "position_ms": 5000,
        "playback_speed": 1.5,
        "is_finished": False
    }
    response = await client.patch(f"/library/{asin}/progress", json=payload)
    if response.status_code != 200:
        raise AssertionError(f"PATCH /library/{asin}/progress failed: {response.status_code} {response.text}")
    data = response.json()
    assert data["position_ms"] == 5000
    assert data["playback_speed"] == 1.5
    assert data["is_finished"] is False

    # 2. Check Continue Listening
    response = await client.get("/library/continue-listening")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["book_asin"] == asin
    assert items[0]["position_ms"] == 5000
