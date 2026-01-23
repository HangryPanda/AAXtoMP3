"""Unit tests for MetadataExtractor."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from services.metadata_extractor import MetadataExtractor

@pytest.fixture
def ffprobe_mock_data():
    return {
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": "3600.5",
            "size": "50000000",
            "bit_rate": "128000",
            "tags": {
                "title": "Test Audiobook",
                "artist": "John Doe",
                "composer": "Jane Narrator",
                "album": "The Great Test Series",
                "date": "2024",
                "genre": "Fiction",
                "comment": "A test summary",
                "language": "eng"
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
                "end_time": "300.0",
                "tags": {"title": "Chapter 1"}
            },
            {
                "id": 1,
                "start_time": "300.0",
                "end_time": "600.0",
                "tags": {"title": "Chapter 2"}
            }
        ]
    }

@pytest.mark.asyncio
async def test_parse_ffprobe_output(ffprobe_mock_data):
    extractor = MetadataExtractor()
    metadata = extractor._parse_ffprobe_output(ffprobe_mock_data, Path("test.m4b"))
    
    assert metadata.title == "Test Audiobook"
    assert "John Doe" in metadata.authors
    assert "Jane Narrator" in metadata.narrators
    assert metadata.release_date == "2024"
    assert metadata.description == "A test summary"
    assert len(metadata.chapters) == 2
    assert metadata.chapters[0].title == "Chapter 1"
    assert metadata.chapters[0].start_offset_ms == 0
    assert metadata.chapters[0].length_ms == 300000
    assert metadata.technical.sample_rate == 44100
    assert metadata.technical.duration_ms == 3600500

@pytest.mark.asyncio
async def test_parse_ffprobe_output_implicit_chapters():
    extractor = MetadataExtractor()
    data = {
        "format": {"duration": "100.0"},
        "chapters": []
    }
    metadata = extractor._parse_ffprobe_output(data, Path("test.m4b"))
    assert len(metadata.chapters) == 1
    assert metadata.chapters[0].title == "Full Book"
    assert metadata.chapters[0].length_ms == 100000

def test_split_list():
    extractor = MetadataExtractor()
    assert extractor._split_list("Author A; Author B") == ["Author A", "Author B"]
    assert extractor._split_list("Author A, Author B") == ["Author A", "Author B"]
    assert extractor._split_list("Author A & Author B") == ["Author A", "Author B"]
    assert extractor._split_list(None) == []
    assert extractor._split_list("") == []
