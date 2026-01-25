"""Integration tests for Repair workflow hardening (Truth From Disk)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Book, BookStatus, LocalItem
from services.repair_pipeline import apply_repair, compute_preview, _map_path_to_runtime


@pytest.fixture
def repair_fs(tmp_path: Path) -> dict[str, Path]:
    """Temporary filesystem layout for repair tests."""
    manifest_dir = tmp_path / "specs"
    downloads_dir = tmp_path / "downloads"
    converted_dir = tmp_path / "converted"
    completed_dir = tmp_path / "completed"

    manifest_dir.mkdir()
    downloads_dir.mkdir()
    converted_dir.mkdir()
    completed_dir.mkdir()

    (manifest_dir / "download_manifest.json").write_text("{}", encoding="utf-8")
    (manifest_dir / "converted_manifest.json").write_text("{}", encoding="utf-8")

    return {
        "manifest_dir": manifest_dir,
        "downloads_dir": downloads_dir,
        "converted_dir": converted_dir,
        "completed_dir": completed_dir,
    }


@pytest.fixture
def mock_repair_settings(repair_fs: dict[str, Path]):
    """Patch services.repair_pipeline.get_settings to point at temp dirs."""
    with patch("services.repair_pipeline.get_settings") as mock_get:
        settings = MagicMock()
        settings.manifest_dir = repair_fs["manifest_dir"]
        settings.downloads_dir = repair_fs["downloads_dir"]
        settings.converted_dir = repair_fs["converted_dir"]
        settings.completed_dir = repair_fs["completed_dir"]
        settings.move_files_policy = "report_only"
        mock_get.return_value = settings
        yield settings


def _write_download_manifest(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_converted_manifest(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def test_map_path_to_runtime_maps_legacy_roots(mock_repair_settings) -> None:
    settings = mock_repair_settings

    assert (
        _map_path_to_runtime("/downloads/ASIN_Title.aaxc") == f"{settings.downloads_dir}/ASIN_Title.aaxc"
    )
    assert (
        _map_path_to_runtime("/converted/Title.m4b") == f"{settings.converted_dir}/Title.m4b"
    )
    assert (
        _map_path_to_runtime("/completed/ASIN_Title.aaxc") == f"{settings.completed_dir}/ASIN_Title.aaxc"
    )


def test_map_path_to_runtime_idempotent_for_runtime_paths(mock_repair_settings) -> None:
    settings = mock_repair_settings
    already = f"{settings.downloads_dir}/ASIN_Title.aaxc"
    assert _map_path_to_runtime(already) == already


@pytest.mark.asyncio
async def test_compute_preview_counts_from_filesystem_and_manifests(
    test_session: AsyncSession, repair_fs: dict[str, Path], mock_repair_settings
) -> None:
    # Remote catalog (DB books)
    test_session.add(Book(asin="B00AAA0001", title="A", status=BookStatus.NEW))
    test_session.add(Book(asin="B00BBB0002", title="B", status=BookStatus.NEW))
    await test_session.commit()

    # On-disk downloads (affects downloaded_on_disk_* via index)
    aaxc_a = repair_fs["downloads_dir"] / "B00AAA0001_Test.aaxc"
    aaxc_a.write_text("x", encoding="utf-8")
    (repair_fs["downloads_dir"] / "B00CCC0003_Orphan.aaxc").write_text("x", encoding="utf-8")

    # download manifest: one good, one orphan, one missing
    download_manifest = {
        "B00AAA0001": {"status": "success", "aaxc_path": str(aaxc_a), "voucher_path": None, "cover_path": None},
        "B00CCC0003": {"status": "success", "aaxc_path": str(repair_fs["downloads_dir"] / "B00CCC0003_Orphan.aaxc")},
        "B00BBB0002": {"status": "success", "aaxc_path": str(repair_fs["downloads_dir"] / "B00BBB0002_Missing.aaxc")},
    }
    _write_download_manifest(repair_fs["manifest_dir"] / "download_manifest.json", download_manifest)

    # converted manifest: two conversions for AAA (duplicate), one orphan, one missing
    m4b_a_best = repair_fs["converted_dir"] / "Audiobook" / "A" / "A.m4b"
    m4b_a_best.parent.mkdir(parents=True, exist_ok=True)
    m4b_a_best.write_text("m4b", encoding="utf-8")

    m4b_a_other = repair_fs["converted_dir"] / "Other" / "A_alt.m4b"
    m4b_a_other.parent.mkdir(parents=True, exist_ok=True)
    m4b_a_other.write_text("m4b", encoding="utf-8")

    m4b_orphan = repair_fs["converted_dir"] / "Orphan.m4b"
    m4b_orphan.write_text("m4b", encoding="utf-8")

    converted_manifest = {
        str(m4b_a_best): {"status": "success", "asin": "B00AAA0001", "output_path": str(m4b_a_best)},
        str(m4b_a_other): {"status": "success", "asin": "B00AAA0001", "output_path": str(m4b_a_other)},
        str(m4b_orphan): {"status": "success", "asin": "B00CCC0003", "output_path": str(m4b_orphan)},
        "/data/converted/Missing.m4b": {"status": "success", "asin": "B00BBB0002", "output_path": "/data/converted/Missing.m4b"},
    }
    _write_converted_manifest(repair_fs["manifest_dir"] / "converted_manifest.json", converted_manifest)

    preview = await compute_preview(test_session)

    assert preview.remote_total == 2
    assert preview.downloaded_total == 1  # only AAA is in remote + exists
    assert preview.converted_total == 1  # AAA only (remote)
    assert preview.converted_of_downloaded == 1
    assert preview.orphan_downloads == 1  # CCC
    assert preview.orphan_conversions == 1  # CCC
    assert preview.duplicate_conversions == 1  # AAA has 2
    assert preview.missing_files == 2  # BBB missing download + missing conversion

    assert preview.downloaded_on_disk_total == 2  # AAA + CCC files exist
    assert preview.downloaded_on_disk_remote_total == 1  # AAA only
    assert preview.converted_m4b_files_on_disk_total == 3  # best + other + orphan


@pytest.mark.asyncio
async def test_apply_repair_inserts_local_only_and_writes_duplicates_report(
    test_session: AsyncSession, repair_fs: dict[str, Path], mock_repair_settings
) -> None:
    # Remote book AAA (for duplicates); orphan asin for local-only
    test_session.add(Book(asin="B00AAA0001", title="A", status=BookStatus.DOWNLOADED))
    await test_session.commit()

    # Converted files + manifest entries
    best = repair_fs["converted_dir"] / "Audiobook" / "A" / "A.m4b"
    best.parent.mkdir(parents=True, exist_ok=True)
    best.write_text("m4b", encoding="utf-8")

    other = repair_fs["converted_dir"] / "Other" / "A_alt.m4b"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text("m4b", encoding="utf-8")

    orphan = repair_fs["converted_dir"] / "Orphan.m4b"
    orphan.write_text("m4b", encoding="utf-8")

    converted_manifest = {
        str(best): {
            "status": "success",
            "asin": "B00AAA0001",
            "title": "A",
            "output_path": str(best),
            "imported_at": "2026-01-25T00:00:00Z",
        },
        str(other): {
            "status": "success",
            "asin": "B00AAA0001",
            "title": "A",
            "output_path": str(other),
            "imported_at": "2026-01-25T00:00:01Z",
        },
        str(orphan): {
            "status": "success",
            "asin": "B00CCC0003",
            "title": "Orphan",
            "output_path": str(orphan),
            "imported_at": "2026-01-25T00:00:02Z",
        },
    }
    _write_converted_manifest(repair_fs["manifest_dir"] / "converted_manifest.json", converted_manifest)
    _write_download_manifest(repair_fs["manifest_dir"] / "download_manifest.json", {})

    result = await apply_repair(test_session, job_id=None)

    # Local-only inserted
    res = await test_session.execute(select(LocalItem))
    items = list(res.scalars().all())
    assert len(items) == 1
    assert items[0].asin == "B00CCC0003"
    assert Path(items[0].output_path).resolve() == orphan.resolve()

    # Duplicates report exists with required columns and is non-destructive
    report_path = Path(result["duplicates_report_path"])
    assert report_path.exists()
    assert report_path.parent == repair_fs["converted_dir"] / ".repair_reports"

    content = report_path.read_text(encoding="utf-8").splitlines()
    assert content[0].split("\t") == ["asin", "keep_or_delete", "output_path", "imported_at", "reason"]
    assert any("\tKEEP\t" in line for line in content[1:])
    assert any("\tDELETE_CANDIDATE\t" in line for line in content[1:])

    # No deletion
    assert best.exists()
    assert other.exists()
    assert orphan.exists()
