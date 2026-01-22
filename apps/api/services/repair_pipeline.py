"""Repair pipeline: reconcile DB with manifests + filesystem."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from db.models import Book, BookStatus, LocalItem


@dataclass
class RepairPreview:
    remote_total: int
    downloaded_total: int
    converted_total: int
    converted_of_downloaded: int
    orphan_downloads: int
    orphan_conversions: int
    missing_files: int
    duplicate_conversions: int


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _map_path_to_runtime(path: str | None) -> str | None:
    """
    Normalize legacy manifest paths into the current runtime's container paths.

    Supports:
    - legacy absolute host paths (e.g. /Volumes/Media/Audiobooks/Downloads/...) in download manifest
    - legacy container roots (/downloads, /converted, /completed)
    - current runtime roots as configured in Settings (/data/downloads, etc)
    """
    if not isinstance(path, str) or not path:
        return None

    settings = get_settings()

    # Normalize legacy container roots to configured roots.
    legacy_to_runtime = {
        "/downloads": str(settings.downloads_dir),
        "/converted": str(settings.converted_dir),
        "/completed": str(settings.completed_dir),
    }
    for legacy_prefix, runtime_prefix in legacy_to_runtime.items():
        if path == legacy_prefix or path.startswith(legacy_prefix + "/"):
            return runtime_prefix + path[len(legacy_prefix) :]

    # Map known host paths to runtime roots when running on host (optional).
    host_to_runtime = [
        ("/Volumes/Media/Audiobooks/Downloads", str(settings.downloads_dir)),
        ("/Volumes/Media/Audiobooks/Converted", str(settings.converted_dir)),
        ("/Volumes/Media/Audiobooks/Completed", str(settings.completed_dir)),
    ]
    for host_prefix, runtime_prefix in host_to_runtime:
        if path == host_prefix or path.startswith(host_prefix + "/"):
            return runtime_prefix + path[len(host_prefix) :]

    return path


def _path_exists(runtime_path: str | None) -> bool:
    if not runtime_path:
        return False
    try:
        return Path(runtime_path).exists()
    except Exception:
        return False


def _guess_format(output_path: str | None) -> str | None:
    if not output_path:
        return None
    suf = Path(output_path).suffix.lower().lstrip(".")
    return suf or None


async def compute_dry_run(session: AsyncSession, asin: str) -> dict[str, Any]:
    """
    Compute what `apply_repair()` would do for a single ASIN, without mutating the DB.

    This is intentionally verbose and meant for debugging/diagnostics, not for the
    normal frontend data contract.
    """
    settings = get_settings()
    download_manifest_path = settings.manifest_dir / "download_manifest.json"
    converted_manifest_path = settings.manifest_dir / "converted_manifest.json"

    download_raw = _load_json(download_manifest_path)
    converted_raw = _load_json(converted_manifest_path)

    if not isinstance(download_raw, dict):
        raise ValueError("download_manifest.json must be a JSON object keyed by ASIN")
    if not isinstance(converted_raw, dict):
        raise ValueError("converted_manifest.json must be a JSON object keyed by source file path")

    result = await session.execute(select(Book).where(Book.asin == asin))
    book = result.scalar_one_or_none()

    dl = download_raw.get(asin)
    download_entry: dict[str, Any] | None = dl if isinstance(dl, dict) else None

    mapped_download = {
        "status": download_entry.get("status") if download_entry else None,
        "aaxc_path": _map_path_to_runtime(download_entry.get("aaxc_path")) if download_entry else None,
        "voucher_path": _map_path_to_runtime(download_entry.get("voucher_path")) if download_entry else None,
        "cover_path": _map_path_to_runtime(download_entry.get("cover_path")) if download_entry else None,
    }
    download_files = {
        "aaxc_exists": _path_exists(mapped_download["aaxc_path"]),
        "voucher_exists": _path_exists(mapped_download["voucher_path"]),
        "cover_exists": _path_exists(mapped_download["cover_path"]),
    }

    conversions: list[dict[str, Any]] = []
    for _key, entry in converted_raw.items():
        if not isinstance(entry, dict) or entry.get("status") != "success":
            continue
        if entry.get("asin") != asin:
            continue
        out = _map_path_to_runtime(entry.get("output_path"))
        if not _path_exists(out):
            continue
        conversions.append({"output_path": out, "imported_at": entry.get("imported_at")})

    def pick_best(convs: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not convs:
            return None
        if len(convs) == 1:
            return convs[0]

        def score(c: dict[str, Any]) -> tuple[int, str]:
            out = str(c.get("output_path") or "")
            audiobook_bonus = 1 if "/Audiobook/" in out else 0
            return (audiobook_bonus, str(c.get("imported_at") or ""))

        return max(convs, key=score)

    chosen = pick_best(conversions)

    local_existing = await session.execute(select(LocalItem).where(LocalItem.asin == asin))
    local_item = local_existing.scalar_one_or_none()

    proposed_updates: dict[str, Any] = {}
    notes: list[str] = []

    if book is None:
        # Not in current remote catalog: only relevant if a successful conversion exists.
        if chosen is None:
            notes.append("ASIN not in remote catalog DB and no successful conversion found; no action.")
            return {
                "asin": asin,
                "in_remote_catalog": False,
                "has_download_manifest": bool(download_entry),
                "has_converted_manifest": len(conversions) > 0,
                "download": mapped_download,
                "download_files": download_files,
                "conversions": conversions,
                "chosen_conversion": chosen,
                "local_item_exists": local_item is not None,
                "local_item_id": str(local_item.id) if local_item else None,
                "proposed_book_updates": None,
                "proposed_local_item_insert": None,
                "notes": notes,
            }

        if local_item is not None:
            notes.append("LocalItem already exists; no insert needed.")
            return {
                "asin": asin,
                "in_remote_catalog": False,
                "has_download_manifest": bool(download_entry),
                "has_converted_manifest": len(conversions) > 0,
                "download": mapped_download,
                "download_files": download_files,
                "conversions": conversions,
                "chosen_conversion": chosen,
                "local_item_exists": True,
                "local_item_id": str(local_item.id),
                "proposed_book_updates": None,
                "proposed_local_item_insert": None,
                "notes": notes,
            }

        notes.append("Would insert LocalItem for orphan conversion.")
        return {
            "asin": asin,
            "in_remote_catalog": False,
            "has_download_manifest": bool(download_entry),
            "has_converted_manifest": len(conversions) > 0,
            "download": mapped_download,
            "download_files": download_files,
            "conversions": conversions,
            "chosen_conversion": chosen,
            "local_item_exists": False,
            "local_item_id": None,
            "proposed_book_updates": None,
            "proposed_local_item_insert": {
                "asin": asin,
                "title": "Unknown",
                "authors": None,
                "output_path": chosen.get("output_path") if chosen else None,
                "cover_path": None,
                "format": _guess_format(chosen.get("output_path") if chosen else None),
            },
            "notes": notes,
        }

    # Book exists: compute what would change.
    current = {
        "status": book.status.value if hasattr(book.status, "value") else str(book.status),
        "local_path_aax": book.local_path_aax,
        "local_path_voucher": book.local_path_voucher,
        "local_path_cover": book.local_path_cover,
        "local_path_converted": book.local_path_converted,
        "conversion_format": book.conversion_format,
    }

    def consider(field: str, value: Any) -> None:
        if current.get(field) != value:
            proposed_updates[field] = {"from": current.get(field), "to": value}

    # Apply same guards as apply_repair (only set when file exists)
    if download_entry and download_entry.get("status") == "success":
        if mapped_download["aaxc_path"] and download_files["aaxc_exists"]:
            consider("local_path_aax", mapped_download["aaxc_path"])
        if mapped_download["voucher_path"] and download_files["voucher_exists"]:
            consider("local_path_voucher", mapped_download["voucher_path"])
        if mapped_download["cover_path"] and download_files["cover_exists"]:
            consider("local_path_cover", mapped_download["cover_path"])

        if current.get("status") == BookStatus.NEW.value and mapped_download["aaxc_path"] and download_files["aaxc_exists"]:
            consider("status", BookStatus.DOWNLOADED.value)

    if chosen is not None:
        out = chosen.get("output_path")
        if isinstance(out, str) and out:
            consider("local_path_converted", out)
            consider("conversion_format", _guess_format(out))
        if current.get("status") != BookStatus.COMPLETED.value:
            consider("status", BookStatus.COMPLETED.value)

    if not proposed_updates:
        notes.append("No changes needed (already consistent with repair logic).")

    return {
        "asin": asin,
        "in_remote_catalog": True,
        "has_download_manifest": bool(download_entry),
        "has_converted_manifest": len(conversions) > 0,
        "download": mapped_download,
        "download_files": download_files,
        "conversions": conversions,
        "chosen_conversion": chosen,
        "local_item_exists": local_item is not None,
        "local_item_id": str(local_item.id) if local_item else None,
        "current_book": current,
        "proposed_book_updates": proposed_updates,
        "notes": notes,
    }


async def compute_preview(session: AsyncSession) -> RepairPreview:
    settings = get_settings()
    download_manifest_path = settings.manifest_dir / "download_manifest.json"
    converted_manifest_path = settings.manifest_dir / "converted_manifest.json"

    download_raw = _load_json(download_manifest_path)
    converted_raw = _load_json(converted_manifest_path)

    if not isinstance(download_raw, dict):
        raise ValueError("download_manifest.json must be a JSON object keyed by ASIN")
    if not isinstance(converted_raw, dict):
        raise ValueError("converted_manifest.json must be a JSON object keyed by source file path")

    result = await session.execute(select(Book.asin))
    remote_asins = {row[0] for row in result.all()}

    downloaded_asins: set[str] = set()
    missing_files = 0
    orphan_downloads = 0

    for asin, entry in download_raw.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "success":
            continue
        asin_str = str(asin)
        aaxc_path = _map_path_to_runtime(entry.get("aaxc_path"))
        if not _path_exists(aaxc_path):
            missing_files += 1
            continue
        if asin_str in remote_asins:
            downloaded_asins.add(asin_str)
        else:
            orphan_downloads += 1

    conversions_by_asin: dict[str, list[dict[str, Any]]] = {}
    orphan_conversions = 0

    for _key, entry in converted_raw.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "success":
            continue
        asin = entry.get("asin")
        if not isinstance(asin, str) or not asin:
            continue
        output_path = _map_path_to_runtime(entry.get("output_path"))
        if not _path_exists(output_path):
            missing_files += 1
            continue
        if asin in remote_asins:
            conversions_by_asin.setdefault(asin, []).append({"output_path": output_path})
        else:
            orphan_conversions += 1

    converted_asins = set(conversions_by_asin.keys())
    converted_of_downloaded = len(converted_asins & downloaded_asins)
    duplicate_conversions = sum(1 for v in conversions_by_asin.values() if len(v) > 1)

    return RepairPreview(
        remote_total=len(remote_asins),
        downloaded_total=len(downloaded_asins),
        converted_total=len(converted_asins),
        converted_of_downloaded=converted_of_downloaded,
        orphan_downloads=orphan_downloads,
        orphan_conversions=orphan_conversions,
        missing_files=missing_files,
        duplicate_conversions=duplicate_conversions,
    )


async def apply_repair(session: AsyncSession) -> dict[str, int]:
    """
    Apply repair to the DB:
    - Update Book rows with validated download/convert paths + statuses.
    - Insert LocalItem rows for orphan conversions (converted but not in current remote catalog).
    """
    settings = get_settings()
    download_manifest_path = settings.manifest_dir / "download_manifest.json"
    converted_manifest_path = settings.manifest_dir / "converted_manifest.json"

    download_raw = _load_json(download_manifest_path)
    converted_raw = _load_json(converted_manifest_path)

    if not isinstance(download_raw, dict):
        raise ValueError("download_manifest.json must be a JSON object keyed by ASIN")
    if not isinstance(converted_raw, dict):
        raise ValueError("converted_manifest.json must be a JSON object keyed by source file path")

    result = await session.execute(select(Book))
    books = result.scalars().all()
    books_by_asin = {b.asin: b for b in books}

    now = datetime.utcnow()

    updated_books = 0
    inserted_local = 0

    # Precompute conversions per asin with file existence.
    conversions_by_asin: dict[str, list[dict[str, Any]]] = {}
    orphan_conversions: list[dict[str, Any]] = []
    for _key, entry in converted_raw.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "success":
            continue
        asin = entry.get("asin")
        output_path = _map_path_to_runtime(entry.get("output_path"))
        if not isinstance(asin, str) or not asin or not output_path:
            continue
        if not _path_exists(output_path):
            continue
        if asin in books_by_asin:
            conversions_by_asin.setdefault(asin, []).append(
                {
                    "output_path": output_path,
                    "imported_at": entry.get("imported_at"),
                }
            )
        else:
            orphan_conversions.append(
                {
                    "asin": asin,
                    "title": entry.get("title") or "Unknown",
                    "authors": entry.get("authors"),
                    "output_path": output_path,
                }
            )

    def pick_best(convs: list[dict[str, Any]]) -> dict[str, Any]:
        if len(convs) == 1:
            return convs[0]
        def score(c: dict[str, Any]) -> tuple[int, str]:
            out = str(c.get("output_path") or "")
            audiobook_bonus = 1 if "/Audiobook/" in out else 0
            return (audiobook_bonus, str(c.get("imported_at") or ""))
        return max(convs, key=score)

    # Apply downloads + conversions to books
    for asin, book in books_by_asin.items():
        changed = False

        d = download_raw.get(asin)
        if isinstance(d, dict) and d.get("status") == "success":
            aaxc_path = _map_path_to_runtime(d.get("aaxc_path"))
            voucher_path = _map_path_to_runtime(d.get("voucher_path"))
            cover_path = _map_path_to_runtime(d.get("cover_path"))

            if aaxc_path and _path_exists(aaxc_path) and book.local_path_aax != aaxc_path:
                book.local_path_aax = aaxc_path
                changed = True
            if voucher_path and _path_exists(voucher_path) and book.local_path_voucher != voucher_path:
                book.local_path_voucher = voucher_path
                changed = True
            if cover_path and _path_exists(cover_path) and book.local_path_cover != cover_path:
                book.local_path_cover = cover_path
                changed = True

            if book.status == BookStatus.NEW and aaxc_path and _path_exists(aaxc_path):
                book.status = BookStatus.DOWNLOADED
                changed = True

        convs = conversions_by_asin.get(asin) or []
        if convs:
            best = pick_best(convs)
            out = best.get("output_path")
            if isinstance(out, str) and out and book.local_path_converted != out:
                book.local_path_converted = out
                changed = True
            fmt = _guess_format(out if isinstance(out, str) else None)
            if fmt and book.conversion_format != fmt:
                book.conversion_format = fmt
                changed = True
            if book.status != BookStatus.COMPLETED:
                book.status = BookStatus.COMPLETED
                changed = True

        if changed:
            book.updated_at = now
            session.add(book)
            updated_books += 1

    # Insert local items for orphan conversions if not already present by output_path
    existing_paths_res = await session.execute(select(LocalItem.output_path))
    existing_paths = {row[0] for row in existing_paths_res.all()}
    for entry in orphan_conversions:
        out = entry.get("output_path")
        if not isinstance(out, str) or not out:
            continue
        if out in existing_paths:
            continue
        li = LocalItem(
            asin=entry.get("asin") if isinstance(entry.get("asin"), str) else None,
            title=str(entry.get("title") or "Unknown"),
            authors=str(entry.get("authors")) if isinstance(entry.get("authors"), str) else None,
            output_path=out,
            cover_path=None,
            format=_guess_format(out),
            created_at=now,
            updated_at=now,
        )
        session.add(li)
        inserted_local += 1

    await session.commit()
    return {"updated_books": updated_books, "inserted_local_items": inserted_local}
