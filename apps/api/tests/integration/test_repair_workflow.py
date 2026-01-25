"""Integration tests for Repair Pipeline and Library Manager."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Book, BookStatus, Chapter, BookTechnical, BookAsset, BookScanState
from services.repair_pipeline import apply_repair, compute_preview
from services.library_manager import LibraryManager
from services.metadata_extractor import MetadataExtractor, BookMetadata, TechnicalMetadata, ChapterMetadata

# Sample Data
SAMPLE_ASIN = "B00REPAIR01"
SAMPLE_TITLE = "Repair Test Book"
SAMPLE_AAXC_PATH = "/data/downloads/B00REPAIR01_Test.aaxc"
SAMPLE_VOUCHER_PATH = "/data/downloads/B00REPAIR01_Test.voucher"
SAMPLE_COVER_PATH = "/data/downloads/B00REPAIR01_Test.jpg"
SAMPLE_OUTPUT_PATH = "/data/converted/Test Author/Repair Test Book/Repair Test Book.m4b"


@pytest.fixture
def mock_manifest_files(tmp_path):
    """Create mock manifest files."""
    manifest_dir = tmp_path / "specs"
    manifest_dir.mkdir()
    
    download_manifest = manifest_dir / "download_manifest.json"
    converted_manifest = manifest_dir / "converted_manifest.json"
    
    # Initial state: empty manifests
    download_manifest.write_text("{}", encoding="utf-8")
    converted_manifest.write_text("{}", encoding="utf-8")
    
    return manifest_dir, download_manifest, converted_manifest


@pytest.fixture
def mock_settings(tmp_path, mock_manifest_files):
    """Mock settings with temporary directories."""
    manifest_dir, _, _ = mock_manifest_files
    
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir()
    
    converted_dir = tmp_path / "converted"
    converted_dir.mkdir()
    
    completed_dir = tmp_path / "completed"
    completed_dir.mkdir()
    
    with patch("services.repair_pipeline.get_settings") as mock:
        settings = MagicMock()
        settings.manifest_dir = manifest_dir
        settings.downloads_dir = downloads_dir
        settings.converted_dir = converted_dir
        settings.completed_dir = completed_dir
        # Mock aaxtomp3_path for safety, though not used in repair directly
        settings.aaxtomp3_path = tmp_path / "AAXtoMP3"
        settings.repair_extract_metadata = True # Enable metadata extraction during repair
        mock.return_value = settings
        yield settings


@pytest.mark.asyncio
async def test_repair_updates_book_status_from_filesystem(
    test_session: AsyncSession, 
    mock_settings, 
    mock_manifest_files
):
    """
    Test that apply_repair updates a book's status and paths 
    when files exist on disk, even if manifest is initially empty.
    """
    _, download_manifest_path, _ = mock_manifest_files
    
    # 1. Setup: Book in DB as NEW
    book = Book(asin=SAMPLE_ASIN, title=SAMPLE_TITLE, status=BookStatus.NEW)
    test_session.add(book)
    await test_session.commit()
    
    # 2. Setup: Create physical files (simulate download)
    # Using the mock_settings paths directly
    aaxc_file = mock_settings.downloads_dir / f"{SAMPLE_ASIN}_Test.aaxc"
    aaxc_file.write_text("dummy content")
    voucher_file = mock_settings.downloads_dir / f"{SAMPLE_ASIN}_Test.voucher"
    voucher_file.write_text("{}")
    
    # 3. Setup: Populate download manifest with these paths
    manifest_data = {
        SAMPLE_ASIN: {
            "status": "success",
            "aaxc_path": str(aaxc_file),
            "voucher_path": str(voucher_file),
            "cover_path": None
        }
    }
    download_manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")
    
    # 4. Execute Repair
    result = await apply_repair(test_session)
    
    # 5. Verify
    await test_session.refresh(book)
    assert result["updated_books"] == 1
    assert book.status == BookStatus.DOWNLOADED
    assert book.local_path_aax == str(aaxc_file)
    assert book.local_path_voucher == str(voucher_file)


@pytest.mark.asyncio
async def test_repair_scans_m4b_and_updates_manifest(
    test_session: AsyncSession, 
    mock_settings, 
    mock_manifest_files
):
    """
    Test that apply_repair scans the converted directory for M4B files,
    matches them to books, and updates the converted manifest.
    """
    _, _, converted_manifest_path = mock_manifest_files
    
    # 1. Setup: Book in DB
    book = Book(asin=SAMPLE_ASIN, title=SAMPLE_TITLE, status=BookStatus.DOWNLOADED)
    test_session.add(book)
    await test_session.commit()
    
    # 2. Setup: Create M4B file
    m4b_path = mock_settings.converted_dir / "Test Author" / "Repair Test Book" / "Repair Test Book.m4b"
    m4b_path.parent.mkdir(parents=True)
    m4b_path.write_text("dummy audio")
    
    # 3. Mock Title Matcher to ensure successful match
    # We mock _scan_m4b_with_asin internal call or the title matcher used inside it.
    # It's easier to mock the whole _scan_m4b_with_asin function for this integration test scope
    # to avoid complex dependencies on title_matcher service.
    
    scan_result = [{
        "path": str(m4b_path),
        "asin": SAMPLE_ASIN,
        "title": SAMPLE_TITLE,
        "matched_by": "filename_match",
        "confidence": 1.0
    }]
    
    with patch("services.repair_pipeline._scan_m4b_with_asin", return_value=scan_result):
        # 4. Execute Repair
        result = await apply_repair(test_session)
    
    # 5. Verify DB updates
    await test_session.refresh(book)
    assert book.status == BookStatus.COMPLETED
    assert book.local_path_converted == str(m4b_path)
    
    # 6. Verify Manifest Updates
    manifest_content = json.loads(converted_manifest_path.read_text())
    # The key is the output path
    assert str(m4b_path) in manifest_content
    entry = manifest_content[str(m4b_path)]
    assert entry["asin"] == SAMPLE_ASIN
    assert entry["status"] == "success"


@pytest.mark.asyncio
async def test_library_manager_scan_book_populates_metadata(
    test_session: AsyncSession,
    mock_settings
):
    """
    Test that LibraryManager.scan_book correctly populates database tables 
    (Chapters, Authors, Technical) from extracted metadata.
    """
    # 1. Setup: Book in DB with converted path
    m4b_path = mock_settings.converted_dir / "book.m4b"
    m4b_path.write_text("dummy")
    
    book = Book(
        asin=SAMPLE_ASIN, 
        title="Original Title", 
        status=BookStatus.COMPLETED,
        local_path_converted=str(m4b_path)
    )
    test_session.add(book)
    await test_session.commit()
    
    # 2. Mock Metadata Extractor
    extractor = MagicMock(spec=MetadataExtractor)
    extractor.VERSION = "1.0.0"
    extractor.get_fingerprint.return_value = {"mtime": 1000, "size": 5000}
    
    mock_metadata = BookMetadata(
        title="Extracted Title",
        authors=["Author One", "Author Two"],
        narrators=["Narrator One"],
        series="Test Series",
        series_index="1",
        chapters=[
            ChapterMetadata(index=0, title="Chapter 1", start_offset_ms=0, length_ms=1000, end_offset_ms=1000),
            ChapterMetadata(index=1, title="Chapter 2", start_offset_ms=1000, length_ms=2000, end_offset_ms=3000)
        ],
        technical=TechnicalMetadata(
            format="m4b",
            bitrate=64000,
            sample_rate=44100,
            channels=2,
            duration_ms=3000,
            file_size=5000
        ),
        cover_extracted_path="/tmp/cover.jpg"
    )
    extractor.extract = AsyncMock(return_value=mock_metadata)
    
    manager = LibraryManager(extractor)
    
    # 3. Execute Scan
    success = await manager.scan_book(test_session, SAMPLE_ASIN, force=True)
    assert success is True
    
    # 4. Verify DB Population
    await test_session.refresh(book)
    
    # Title update
    assert book.title == "Extracted Title"
    
    # Scan State
    scan_state = await test_session.execute(select(BookScanState).where(BookScanState.book_asin == SAMPLE_ASIN))
    assert scan_state.scalar_one_or_none() is not None
    
    # Chapters
    chapters_res = await test_session.execute(select(Chapter).where(Chapter.book_asin == SAMPLE_ASIN))
    chapters = chapters_res.scalars().all()
    assert len(chapters) == 2
    assert chapters[0].title == "Chapter 1"
    
    # Technical
    tech_res = await test_session.execute(select(BookTechnical).where(BookTechnical.book_asin == SAMPLE_ASIN))
    tech = tech_res.scalar_one_or_none()
    assert tech is not None
    assert tech.duration_ms == 3000
    
    # Assets (Cover)
    asset_res = await test_session.execute(select(BookAsset).where(BookAsset.book_asin == SAMPLE_ASIN))
    asset = asset_res.scalar_one_or_none()
    assert asset is not None
    assert asset.asset_type == "cover"
    assert asset.path == "/tmp/cover.jpg"
