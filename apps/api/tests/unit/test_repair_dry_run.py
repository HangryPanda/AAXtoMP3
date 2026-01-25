"""Unit tests for Repair Pipeline dry-run logic."""

import json
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Book, BookStatus, LocalItem
from services.repair_pipeline import compute_dry_run

SAMPLE_ASIN = "B00DRYRUN01"

@pytest.fixture
def mock_settings(tmp_path):
    """Mock settings with temporary directories."""
    manifest_dir = tmp_path / "specs"
    manifest_dir.mkdir()
    
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
        mock.return_value = settings
        yield settings

@pytest.fixture
def mock_manifests(mock_settings):
    """Setup mock manifest files."""
    dl_path = mock_settings.manifest_dir / "download_manifest.json"
    cv_path = mock_settings.manifest_dir / "converted_manifest.json"
    
    dl_path.write_text("{}", encoding="utf-8")
    cv_path.write_text("{}", encoding="utf-8")
    return dl_path, cv_path

@pytest.fixture
def mock_session():
    """Mock database session."""
    return MagicMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_dry_run_no_data(mock_session, mock_settings, mock_manifests):
    """Test dry run for an ASIN with no data anywhere."""
    # Mock DB return None
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)
    
    result = await compute_dry_run(mock_session, SAMPLE_ASIN)
    
    assert result["asin"] == SAMPLE_ASIN
    assert result["in_remote_catalog"] is False
    assert result["has_download_manifest"] is False
    assert result["has_converted_manifest"] is False
    assert result["local_item_exists"] is False
    assert "no action" in result["notes"][0]

@pytest.mark.asyncio
async def test_dry_run_orphan_conversion(mock_session, mock_settings, mock_manifests):
    """Test dry run finding an orphan conversion (file exists, manifest exists, but no Book in DB)."""
    _, cv_path = mock_manifests
    
    # 1. Setup conversion manifest
    m4b_path = mock_settings.converted_dir / "book.m4b"
    m4b_path.touch()
    
    cv_data = {
        str(m4b_path): {
            "status": "success",
            "asin": SAMPLE_ASIN,
            "output_path": str(m4b_path),
            "imported_at": "2023-01-01T00:00:00"
        }
    }
    cv_path.write_text(json.dumps(cv_data))
    
    # 2. Mock DB: Book not found, LocalItem not found
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: None), # Book
        MagicMock(scalar_one_or_none=lambda: None)  # LocalItem
    ]
    
    result = await compute_dry_run(mock_session, SAMPLE_ASIN)
    
    assert result["in_remote_catalog"] is False
    assert result["has_converted_manifest"] is True
    assert result["proposed_local_item_insert"] is not None
    assert result["proposed_local_item_insert"]["output_path"] == str(m4b_path)
    assert "Would insert LocalItem" in result["notes"][0]

@pytest.mark.asyncio
async def test_dry_run_book_update_needed(mock_session, mock_settings, mock_manifests):
    """Test dry run where Book exists but paths need updating."""
    dl_path, _ = mock_manifests
    
    # 1. Setup download manifest & files
    aaxc_path = mock_settings.downloads_dir / "book.aaxc"
    aaxc_path.touch()
    
    dl_data = {
        SAMPLE_ASIN: {
            "status": "success",
            "aaxc_path": str(aaxc_path),
            "voucher_path": None,
            "cover_path": None
        }
    }
    dl_path.write_text(json.dumps(dl_data))
    
    # 2. Mock DB: Book exists but has no paths
    book = Book(asin=SAMPLE_ASIN, title="Test", status=BookStatus.NEW)
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: book), # Book
        MagicMock(scalar_one_or_none=lambda: None)  # LocalItem
    ]
    
    result = await compute_dry_run(mock_session, SAMPLE_ASIN)
    
    assert result["in_remote_catalog"] is True
    assert result["proposed_book_updates"] is not None
    
    updates = result["proposed_book_updates"]
    assert "local_path_aax" in updates
    assert updates["local_path_aax"]["to"] == str(aaxc_path)
    
    assert "status" in updates
    assert updates["status"]["to"] == BookStatus.DOWNLOADED

@pytest.mark.asyncio
async def test_dry_run_legacy_path_normalization(mock_session, mock_settings, mock_manifests):
    """Test that legacy manifest paths are normalized to current runtime paths."""
    _, cv_path = mock_manifests
    
    # 1. Manifest has legacy path: /downloads/book.m4b
    # Runtime path is: {tmp}/downloads/book.m4b
    legacy_path = "/converted/book.m4b"
    real_path = mock_settings.converted_dir / "book.m4b"
    real_path.touch()
    
    cv_data = {
        legacy_path: {
            "status": "success",
            "asin": SAMPLE_ASIN,
            "output_path": legacy_path
        }
    }
    cv_path.write_text(json.dumps(cv_data))
    
    # 2. Mock DB: Book exists
    book = Book(asin=SAMPLE_ASIN, title="Test", status=BookStatus.NEW)
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: book),
        MagicMock(scalar_one_or_none=lambda: None)
    ]
    
    result = await compute_dry_run(mock_session, SAMPLE_ASIN)
    
    # Should resolve to the real path on disk despite manifest having legacy path
    assert result["has_converted_manifest"] is True
    assert result["chosen_conversion"]["output_path"] == str(real_path)
    
    updates = result["proposed_book_updates"]
    assert updates["local_path_converted"]["to"] == str(real_path)
