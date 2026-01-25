"""Integration tests for API contracts to ensure Frontend compatibility."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from db.models import Book, BookStatus

# Define the expected structure based on apps/web/src/types/book.ts
# This acts as a contract verification.
EXPECTED_BOOK_KEYS = {
    "asin",
    "title",
    "subtitle",
    "authors",
    "narrators",
    "series",
    "chapters",
    "runtime_length_min",
    "release_date",
    "purchase_date",
    "product_images",
    "publisher",
    "language",
    "format_type",
    "content_type",
    "aax_available",
    "aaxc_available",
    "status",
    "local_path_aax",
    "local_path_voucher",
    "local_path_cover",
    "local_path_converted",
    "conversion_format",
    "error_message",
    "created_at",
    "updated_at",
}

EXPECTED_AUTHOR_KEYS = {"name", "asin"}
EXPECTED_NARRATOR_KEYS = {"name"}
EXPECTED_SERIES_KEYS = {"title", "sequence", "asin"}
EXPECTED_CHAPTER_KEYS = {"title", "length_ms", "start_offset_ms"}


@pytest.mark.asyncio
async def test_get_library_contract(client: AsyncClient, test_session: AsyncSession) -> None:
    """
    Verify that the 'GET /api/library' response matches the expected Frontend contract.
    
    This test prevents regression where backend schema changes break the frontend
    by missing keys or changing types that the frontend interface expects.
    """
    # 1. Seed data
    book = Book(
        asin="CONTRACT_TEST_001",
        title="Contract Test Book",
        subtitle="A test for types",
        authors_json='[{"name": "Test Author", "asin": "B00AUTHOR"}]',
        narrators_json='[{"name": "Test Narrator"}]',
        series_json='[{"title": "Test Series", "sequence": "1", "asin": "B00SERIES"}]',
        status=BookStatus.NEW,
        runtime_length_min=120,
        release_date="2023-01-01",
        purchase_date="2023-01-02",
        publisher="Test Publisher",
        language="en",
        format_type="audiobook",
        aax_available=True,
        aaxc_available=False,
        metadata_json={
            "chapters": [
                {"title": "Chapter 1", "length_ms": 60000, "start_offset_ms": 0}
            ],
            "content_type": "Audiobook"
        }
    )
    test_session.add(book)
    await test_session.commit()

    # 2. Request
    response = await client.get("/library")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # 3. Validation
    assert "items" in data
    assert len(data["items"]) >= 1
    
    # Find our test book
    item = next((b for b in data["items"] if b["asin"] == "CONTRACT_TEST_001"), None)
    assert item is not None, "Seeded book not found in response"

    # Check Top-Level Keys
    item_keys = set(item.keys())
    missing_keys = EXPECTED_BOOK_KEYS - item_keys
    assert not missing_keys, f"Contract violation: Missing keys in API response: {missing_keys}"

    # Check Nested Structures
    
    # Authors
    assert len(item["authors"]) == 1
    author = item["authors"][0]
    assert set(author.keys()) == EXPECTED_AUTHOR_KEYS
    assert author["name"] == "Test Author"
    assert author["asin"] == "B00AUTHOR"

    # Narrators
    assert len(item["narrators"]) == 1
    narrator = item["narrators"][0]
    assert set(narrator.keys()) == EXPECTED_NARRATOR_KEYS
    assert narrator["name"] == "Test Narrator"

    # Series
    assert item["series"] is not None
    assert len(item["series"]) == 1
    series = item["series"][0]
    assert set(series.keys()) == EXPECTED_SERIES_KEYS
    assert series["title"] == "Test Series"
    assert series["sequence"] == "1"

    # Chapters
    # Note: We just verify the contract (key exists and is a list)
    # The actual extraction logic from metadata_json is tested in unit tests.
    assert item["chapters"] is not None
    assert isinstance(item["chapters"], list)
    
    # Verify content_type (derived from metadata_json) to ensure metadata flow works
    assert item["content_type"] == "Audiobook"
