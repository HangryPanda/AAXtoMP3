"""Unit tests for repair pipeline helpers and duplicate report generation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from db.models import Book, SettingsModel
from services.repair_pipeline import _map_path_to_runtime, _normalize_path_separators, apply_repair


def test_normalize_path_separators() -> None:
    assert _normalize_path_separators(r"C:\Users\me\Downloads\file.aaxc") == "C:/Users/me/Downloads/file.aaxc"


def test_map_path_to_runtime_maps_legacy_and_windows_paths(tmp_path: Path) -> None:
    settings = Settings(
        downloads_dir=tmp_path / "downloads",
        converted_dir=tmp_path / "converted",
        completed_dir=tmp_path / "completed",
        manifest_dir=tmp_path / "specs",
        core_scripts_dir=tmp_path / "core",
    )
    with patch("services.repair_pipeline.get_settings", return_value=settings):
        assert _map_path_to_runtime("/downloads/B001.aaxc") == str(settings.downloads_dir / "B001.aaxc")
        assert _map_path_to_runtime(r"C:\Users\me\Audiobooks\Downloads\B002.aaxc") == str(settings.downloads_dir / "B002.aaxc")


@pytest.mark.asyncio
async def test_apply_repair_writes_duplicates_report(
    tmp_path: Path,
    test_session: AsyncSession,
) -> None:
    downloads_dir = tmp_path / "downloads"
    converted_dir = tmp_path / "converted"
    completed_dir = tmp_path / "completed"
    manifest_dir = tmp_path / "specs"
    for d in [downloads_dir, converted_dir, completed_dir, manifest_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Create output files on disk so apply_repair treats them as valid conversions.
    out1 = converted_dir / "Audiobook" / "DupBook-1.m4b"
    out1.parent.mkdir(parents=True, exist_ok=True)
    out1.write_bytes(b"1")
    out2 = converted_dir / "DupBook-2.m4b"
    out2.write_bytes(b"2")

    settings = Settings(
        downloads_dir=downloads_dir,
        converted_dir=converted_dir,
        completed_dir=completed_dir,
        manifest_dir=manifest_dir,
        core_scripts_dir=tmp_path / "core",
    )

    (manifest_dir / "download_manifest.json").write_text("{}", encoding="utf-8")
    converted_manifest = {
        "k1": {"status": "success", "asin": "B00DUPLICATE", "output_path": str(out1), "imported_at": "t1"},
        "k2": {"status": "success", "asin": "B00DUPLICATE", "output_path": str(out2), "imported_at": "t2"},
    }
    (manifest_dir / "converted_manifest.json").write_text(json.dumps(converted_manifest), encoding="utf-8")

    test_session.add(Book(asin="B00DUPLICATE", title="Dup Book"))
    # Ensure settings row exists to cover settings-controlled flags.
    test_session.add(SettingsModel(id=1, repair_update_manifests=False, repair_extract_metadata=False))
    await test_session.commit()

    with patch("services.repair_pipeline.get_settings", return_value=settings), patch(
        "services.repair_pipeline._scan_m4b_with_asin", AsyncMock(return_value=[])
    ):
        result = await apply_repair(test_session)

    assert result["duplicate_asins"] == 1
    report_path = Path(result["duplicates_report_path"])
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "KEEP" in text
    assert "DELETE_CANDIDATE" in text

