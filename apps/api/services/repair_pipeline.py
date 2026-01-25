"""Repair pipeline: reconcile DB with manifests + filesystem."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import MoveFilesPolicy, Settings, get_settings
from db.models import Book, BookStatus, LocalItem, SettingsModel


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
    # Disk-derived metrics (source of truth / diagnostics)
    downloaded_on_disk_total: int
    downloaded_on_disk_remote_total: int
    converted_m4b_files_on_disk_total: int
    converted_m4b_titles_on_disk_total: int
    converted_m4b_in_audiobook_dir_total: int
    converted_m4b_outside_audiobook_dir_total: int
    # Database-derived metrics (primary source of truth for server workflow)
    downloaded_db_total: int = 0
    converted_db_total: int = 0
    # Misplaced files
    misplaced_files_count: int = 0


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_path_separators(path: str) -> str:
    """
    Normalize Windows backslashes to forward slashes for consistent matching.

    This is the first step in path normalization, ensuring we can match
    paths regardless of the host OS that created them.
    """
    return path.replace("\\", "/")


def _map_path_to_runtime(path: str | None) -> str | None:
    """
    Normalize legacy manifest paths into the current runtime's container paths.

    Supports:
    - Windows paths (C:\\Users\\...\\Downloads, D:\\Media\\Audiobooks\\...)
    - macOS paths (/Volumes/Media/Audiobooks/..., /Users/.../)
    - Linux paths (/home/.../, /mnt/.../)
    - legacy container roots (/downloads, /converted, /completed)
    - current runtime roots as configured in Settings (/data/downloads, etc)

    Idempotency: paths already in the configured runtime format are returned unchanged.
    """
    if not isinstance(path, str) or not path:
        return None

    settings = get_settings()
    downloads_dir = str(settings.downloads_dir)
    converted_dir = str(settings.converted_dir)
    completed_dir = str(settings.completed_dir)

    # Idempotency: if path already starts with configured runtime dirs, return as-is
    for runtime_dir in [downloads_dir, converted_dir, completed_dir]:
        if path == runtime_dir or path.startswith(runtime_dir + "/"):
            return path

    # Normalize Windows backslashes for consistent matching
    normalized = _normalize_path_separators(path)

    # Normalize legacy container roots to configured roots.
    legacy_to_runtime = {
        "/downloads": downloads_dir,
        "/converted": converted_dir,
        "/completed": completed_dir,
    }
    for legacy_prefix, runtime_prefix in legacy_to_runtime.items():
        if normalized == legacy_prefix or normalized.startswith(legacy_prefix + "/"):
            return runtime_prefix + normalized[len(legacy_prefix):]

    # Build a list of known host path patterns to match.
    # These patterns map host-specific directories to their runtime equivalents.
    # Format: (host_pattern, runtime_dir, dir_type)
    # dir_type is used to identify which directory segment to look for
    host_patterns: list[tuple[str, str, str]] = [
        # macOS Volumes paths
        ("/Volumes/Media/Audiobooks/Downloads", downloads_dir, "downloads"),
        ("/Volumes/Media/Audiobooks/Converted", converted_dir, "converted"),
        ("/Volumes/Media/Audiobooks/Completed", completed_dir, "completed"),
    ]

    # Match explicit host patterns first
    for host_prefix, runtime_prefix, _dir_type in host_patterns:
        if normalized == host_prefix or normalized.startswith(host_prefix + "/"):
            return runtime_prefix + normalized[len(host_prefix):]

    # Generic pattern matching for common host path structures.
    # This handles paths like:
    #   C:/Users/john/Audiobooks/Downloads/...
    #   /home/john/audiobooks/downloads/...
    #   /Users/john/Music/Audiobooks/converted/...
    #
    # We look for directory segments that indicate downloads/converted/completed
    # and map them to the runtime directories.
    dir_type_mappings = {
        "downloads": downloads_dir,
        "download": downloads_dir,
        "converted": converted_dir,
        "convert": converted_dir,
        "completed": completed_dir,
        "complete": completed_dir,
    }

    # Split path into segments and look for known directory type indicators
    segments = normalized.split("/")
    for i, segment in enumerate(segments):
        seg_lower = segment.lower()
        if seg_lower in dir_type_mappings:
            runtime_dir = dir_type_mappings[seg_lower]
            # Everything after this segment is the relative path
            relative_parts = segments[i + 1:]
            if relative_parts:
                return runtime_dir + "/" + "/".join(relative_parts)
            else:
                return runtime_dir

    return path


def _path_exists(runtime_path: str | None) -> bool:
    if not runtime_path:
        return False
    try:
        return Path(runtime_path).exists()
    except Exception:
        return False


def _normalize_asin(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    asin = raw.strip()
    if asin == "":
        return None
    # Audible ASINs are typically case-insensitive identifiers; normalize for matching.
    return asin.lower()


_AUDIBLE_SAFE_REPLACEMENT = "\uf022"  # "" (PUA) seen in some audible-cli filenames
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# System files and directories to skip during scanning
_SKIP_FILENAMES = frozenset({".DS_Store", "Thumbs.db", "._.DS_Store"})


def _should_skip_path(path: Path) -> bool:
    """
    Check if a path should be skipped during scanning.

    Skips:
    - AppleDouble files (starting with '._')
    - macOS .DS_Store files
    - Windows Thumbs.db files
    - Files in hidden directories (any parent starting with '.')
    """
    # Skip AppleDouble files (resource forks on macOS)
    if path.name.startswith("._"):
        return True

    # Skip known system files
    if path.name in _SKIP_FILENAMES:
        return True

    # Skip files inside hidden directories
    for parent in path.parents:
        if parent.name.startswith(".") and parent.name not in {".", ".."}:
            return True

    return False


def _candidate_paths(runtime_path: str) -> list[str]:
    """
    Generate likely-on-disk alternatives for a path.

    This compensates for:
    - legacy manifests that included an extra "Audiobook/" segment in converted paths
    - differing filename sanitization (e.g. ':' -> '') across tools/mounts
    """
    base: list[str] = [
        runtime_path,
        runtime_path.replace("/converted/Audiobook/", "/converted/"),
        runtime_path.replace("/data/converted/Audiobook/", "/data/converted/"),
    ]

    expanded: list[str] = []
    for p in base:
        expanded.append(p)
        if ":" in p:
            expanded.append(p.replace(":", _AUDIBLE_SAFE_REPLACEMENT))

    # Deduplicate while preserving order.
    out: list[str] = []
    seen: set[str] = set()
    for p in expanded:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _first_existing_path(runtime_path: str | None) -> str | None:
    if not runtime_path:
        return None
    for cand in _candidate_paths(runtime_path):
        if _path_exists(cand):
            return cand
    return None


_ASIN_PREFIX_RE = re.compile(r"^([A-Za-z0-9]{8,20})_")


def _extract_asin_prefix(filename: str) -> str | None:
    m = _ASIN_PREFIX_RE.match(filename)
    return _normalize_asin(m.group(1)) if m else None


def _build_download_file_index(*, settings: Any) -> dict[str, dict[str, str]]:
    """
    Index downloads/completed directories by ASIN.

    This is used as a fallback when manifest paths are stale due to filename
    changes (e.g. ':' replaced with '') or moves.
    """
    index: dict[str, dict[str, str]] = {}

    for base_dir in [settings.downloads_dir, settings.completed_dir]:
        try:
            if not Path(base_dir).exists():
                continue
            for p in Path(base_dir).rglob("*"):
                # Skip system files FIRST (before is_file() which can fail on AppleDouble)
                if _should_skip_path(p):
                    continue
                if not p.is_file():
                    continue
                asin = _extract_asin_prefix(p.name)
                if not asin:
                    continue
                entry = index.setdefault(asin, {})
                suf = p.suffix.lower()
                if suf == ".aaxc":
                    entry.setdefault("aaxc_path", str(p))
                elif suf == ".aax":
                    entry.setdefault("aax_path", str(p))
                elif suf == ".voucher":
                    entry.setdefault("voucher_path", str(p))
                elif suf in {".jpg", ".jpeg", ".png"}:
                    entry.setdefault("cover_path", str(p))
                elif p.name.endswith("-chapters.json"):
                    entry.setdefault("chapters_path", str(p))
        except Exception:
            # Best-effort: unreadable dirs shouldn't crash repair.
            continue

    return index


def _normalize_title_key(raw: str) -> str:
    s = (raw or "").lower()
    # The filesystem sometimes uses this PUA glyph for characters like ':'.
    s = s.replace(_AUDIBLE_SAFE_REPLACEMENT, ":")
    s = _NON_ALNUM_RE.sub(" ", s)
    return " ".join(s.split())


def _scan_converted_m4b(settings: Any) -> tuple[int, int, int, int]:
    """
    Returns:
      (m4b_files_total, unique_title_keys_total, m4b_in_audiobook_dir_total, m4b_outside_audiobook_dir_total)
    """
    root = Path(settings.converted_dir)
    audiobook_dir = root / "Audiobook"

    try:
        # Filter out system files FIRST (before is_file() which can fail on AppleDouble)
        files = [p for p in root.rglob("*.m4b") if not _should_skip_path(p) and p.is_file()]
    except Exception:
        files = []

    title_keys = {_normalize_title_key(p.stem) for p in files if p.stem}
    in_audiobook = 0
    for p in files:
        try:
            if audiobook_dir in p.parents:
                in_audiobook += 1
        except Exception:
            continue

    return (len(files), len(title_keys), in_audiobook, len(files) - in_audiobook)


async def _dedupe_local_items(session: AsyncSession) -> int:
    """
    De-duplicate LocalItem rows that refer to the same underlying output file.

    This can happen when paths differ only by legacy segments or filename sanitization
    (e.g. ':' vs '').
    """
    result = await session.execute(select(LocalItem))
    items = list(result.scalars().all())
    if len(items) <= 1:
        return 0

    # Group by canonical path (prefer an existing on-disk path if resolvable).
    grouped: dict[str, list[LocalItem]] = {}
    for item in items:
        canonical = _first_existing_path(item.output_path) or item.output_path
        grouped.setdefault(canonical, []).append(item)

    deleted = 0
    for canonical, group in grouped.items():
        if len(group) <= 1:
            # Keep single entry, but normalize path if we can.
            only = group[0]
            if only.output_path != canonical:
                only.output_path = canonical
                only.updated_at = datetime.utcnow()
                session.add(only)
            continue

        def score(it: LocalItem) -> tuple[int, str, str]:
            # Prefer entries whose current path exists, then newest created_at.
            exists = 1 if _path_exists(it.output_path) else 0
            created = it.created_at.isoformat() if it.created_at else ""
            return (exists, created, str(it.id))

        keep = max(group, key=score)
        if keep.output_path != canonical:
            keep.output_path = canonical
            keep.updated_at = datetime.utcnow()
            session.add(keep)

        for it in group:
            if it.id == keep.id:
                continue
            await session.delete(it)
            deleted += 1

    return deleted


def _guess_format(output_path: str | None) -> str | None:
    if not output_path:
        return None
    suf = Path(output_path).suffix.lower().lstrip(".")
    return suf or None


def _extract_asin_from_metadata_sync(path: Path) -> tuple[str | None, str | None]:
    """Extract ASIN and title from M4B metadata using ffprobe (sync version)."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            tags = data.get("format", {}).get("tags", {})
            # Check various tag names for ASIN (case-insensitive)
            asin = None
            for key in ["ASIN", "asin", "AUDIBLE_ASIN", "audible_asin"]:
                if key in tags:
                    asin = tags[key]
                    break
            # Also check comment field for ASIN pattern
            if not asin:
                comment = tags.get("comment") or tags.get("COMMENT") or ""
                asin_match = re.search(r"\b([A-Z0-9]{10})\b", comment)
                if asin_match:
                    asin = asin_match.group(1)
            title = tags.get("title") or tags.get("TITLE") or tags.get("album") or tags.get("ALBUM")
            return _normalize_asin(asin), title
    except Exception:
        pass
    return None, None


async def _extract_asin_from_metadata(path: Path) -> tuple[str | None, str | None]:
    """Extract ASIN and title from M4B metadata using ffprobe (async wrapper)."""
    import asyncio

    try:
        # Run the blocking subprocess in a thread pool to avoid blocking the event loop
        return await asyncio.to_thread(_extract_asin_from_metadata_sync, path)
    except Exception:
        return None, None


def _manifest_has_conversion(converted_raw: dict[str, Any], asin: str, output_path: str) -> bool:
    """Check if a conversion already exists in the manifest for the given ASIN or path."""
    asin_norm = _normalize_asin(asin)
    path_norm = output_path.lower()

    for _key, entry in converted_raw.items():
        if not isinstance(entry, dict):
            continue
        # Check if same ASIN
        entry_asin = _normalize_asin(entry.get("asin"))
        if entry_asin and entry_asin == asin_norm:
            return True
        # Check if same output path
        entry_path = entry.get("output_path") or ""
        if entry_path.lower() == path_norm:
            return True
    return False


async def _scan_m4b_with_asin(settings: Settings, session: AsyncSession) -> list[dict[str, Any]]:
    """Scan converted directory for M4B files and extract ASINs using robust title matching."""
    from services.title_matcher import (
        match_m4b_to_asin,
        build_title_index,
        quick_lookup,
        normalize_title,
        extract_asin_from_filename,
    )

    results: list[dict[str, Any]] = []
    converted_dir = Path(settings.converted_dir)

    if not converted_dir.exists():
        return results

    # Pre-fetch books for title matching
    book_result = await session.execute(select(Book.asin, Book.title))
    books_list: list[dict[str, Any]] = []
    for row in book_result.all():
        if row[0] and row[1]:  # has asin and title
            books_list.append({"asin": row[0], "title": row[1]})

    # Build fast lookup index for exact matches
    title_index = build_title_index(books_list)

    try:
        m4b_files = list(converted_dir.rglob("*.m4b"))
    except Exception:
        m4b_files = []

    for m4b_path in m4b_files:
        # Skip system files FIRST (before is_file() which can fail on AppleDouble)
        if _should_skip_path(m4b_path):
            continue
        if not m4b_path.is_file():
            continue

        asin: str | None = None
        title: str | None = None
        matched_by = "unknown"
        confidence = 0.0

        # 1. Try metadata tags (ffprobe) - run async to avoid blocking event loop
        meta_asin, meta_title = await _extract_asin_from_metadata(m4b_path)
        if meta_asin:
            asin = meta_asin
            title = meta_title
            matched_by = "metadata"
            confidence = 1.0

        # 2. Try ASIN/ISBN prefix in filename
        if not asin:
            prefix_asin, extracted_title = extract_asin_from_filename(m4b_path.name)
            if prefix_asin:
                asin = prefix_asin
                title = extracted_title
                matched_by = "filename_prefix"
                confidence = 0.99

        # 3. Try quick exact title lookup (fast path)
        if not asin:
            # Try metadata title first
            if meta_title:
                quick_asin = quick_lookup(meta_title, title_index)
                if quick_asin:
                    asin = _normalize_asin(quick_asin)
                    title = meta_title
                    matched_by = "title_exact_metadata"
                    confidence = 0.95

            # Try filename stem
            if not asin:
                quick_asin = quick_lookup(m4b_path.stem, title_index)
                if quick_asin:
                    asin = _normalize_asin(quick_asin)
                    matched_by = "title_exact_filename"
                    confidence = 0.95

        # 4. Try fuzzy title matching (slower but more robust)
        if not asin:
            # Use the full matching function with fuzzy matching
            match_result = match_m4b_to_asin(
                str(m4b_path),
                books_list,
                metadata_asin=None,  # Already tried above
                threshold=0.80,  # 80% similarity threshold
            )
            if match_result.matched and match_result.asin:
                asin = _normalize_asin(match_result.asin)
                matched_by = f"title_fuzzy_{match_result.match_method}"
                confidence = match_result.confidence
                title = match_result.original_title

        results.append(
            {
                "path": str(m4b_path),
                "asin": asin,
                "title": title or m4b_path.stem,
                "matched_by": matched_by,
                "confidence": confidence,
            }
        )

    return results


def _detect_misplaced_files(settings: Settings) -> list[dict[str, Any]]:
    """Find M4B files not in the expected Audiobook directory."""
    misplaced: list[dict[str, Any]] = []
    converted_dir = Path(settings.converted_dir)
    downloads_dir = Path(settings.downloads_dir)
    expected_dir = converted_dir / "Audiobook"

    # Check converted directory for M4Bs outside Audiobook subfolder
    if converted_dir.exists():
        try:
            for m4b_path in converted_dir.rglob("*.m4b"):
                # Skip system files FIRST (before is_file() which can fail on AppleDouble)
                if _should_skip_path(m4b_path):
                    continue
                if not m4b_path.is_file():
                    continue
                # Check if it's inside the Audiobook directory
                try:
                    is_in_audiobook = expected_dir in m4b_path.parents or m4b_path.parent == expected_dir
                except Exception:
                    is_in_audiobook = False

                if not is_in_audiobook:
                    misplaced.append(
                        {
                            "current_path": str(m4b_path),
                            "suggested_path": str(expected_dir / m4b_path.name),
                            "reason": "outside_audiobook_dir",
                        }
                    )
        except Exception:
            pass

    # Check downloads directory for stray M4Bs (shouldn't be there)
    if downloads_dir.exists():
        try:
            for m4b_path in downloads_dir.rglob("*.m4b"):
                # Skip system files FIRST (before is_file() which can fail on AppleDouble)
                if _should_skip_path(m4b_path):
                    continue
                if not m4b_path.is_file():
                    continue
                misplaced.append(
                    {
                        "current_path": str(m4b_path),
                        "suggested_path": str(expected_dir / m4b_path.name),
                        "reason": "in_downloads_dir",
                    }
                )
        except Exception:
            pass

    return misplaced


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

    download_index = _build_download_file_index(settings=settings)
    indexed = download_index.get(_normalize_asin(asin) or asin.lower(), {})

    mapped_download = {
        "status": download_entry.get("status") if download_entry else None,
        "aaxc_path": _first_existing_path(_map_path_to_runtime(download_entry.get("aaxc_path")))
        if download_entry
        else None,
        "voucher_path": _first_existing_path(_map_path_to_runtime(download_entry.get("voucher_path")))
        if download_entry
        else None,
        "cover_path": _first_existing_path(_map_path_to_runtime(download_entry.get("cover_path")))
        if download_entry
        else None,
    }
    # Fallback to directory index if manifest paths are stale.
    if not mapped_download["aaxc_path"]:
        mapped_download["aaxc_path"] = indexed.get("aaxc_path") or indexed.get("aax_path")
    if not mapped_download["voucher_path"]:
        mapped_download["voucher_path"] = indexed.get("voucher_path")
    if not mapped_download["cover_path"]:
        mapped_download["cover_path"] = indexed.get("cover_path")

    download_files = {
        "aaxc_exists": _path_exists(mapped_download["aaxc_path"]),
        "voucher_exists": _path_exists(mapped_download["voucher_path"]),
        "cover_exists": _path_exists(mapped_download["cover_path"]),
    }

    conversions: list[dict[str, Any]] = []
    for _key, entry in converted_raw.items():
        if not isinstance(entry, dict) or entry.get("status") != "success":
            continue
        if _normalize_asin(entry.get("asin")) != _normalize_asin(asin):
            continue
        out = _first_existing_path(_map_path_to_runtime(entry.get("output_path")))
        if not out:
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
    remote_asins = {_normalize_asin(row[0]) for row in result.all() if _normalize_asin(row[0])}

    # Database-derived stats (source of truth for server workflow)
    downloaded_db_result = await session.execute(
        select(func.count()).select_from(Book).where(
            Book.status.in_([
                BookStatus.DOWNLOADED,
                BookStatus.VALIDATED,
                BookStatus.CONVERTING,
                BookStatus.COMPLETED,
            ])
        )
    )
    downloaded_db_total = downloaded_db_result.scalar() or 0

    converted_db_result = await session.execute(
        select(func.count()).select_from(Book).where(Book.status == BookStatus.COMPLETED)
    )
    converted_db_total = converted_db_result.scalar() or 0

    # Detect misplaced files
    misplaced_files = _detect_misplaced_files(settings)
    misplaced_files_count = len(misplaced_files)

    download_index = _build_download_file_index(settings=settings)
    downloaded_on_disk_total = len(
        [asin for asin, entry in download_index.items() if entry.get("aaxc_path") or entry.get("aax_path")]
    )
    downloaded_on_disk_remote_total = len(
        [
            asin
            for asin, entry in download_index.items()
            if (entry.get("aaxc_path") or entry.get("aax_path")) and asin in remote_asins
        ]
    )
    (
        converted_m4b_files_on_disk_total,
        converted_m4b_titles_on_disk_total,
        converted_m4b_in_audiobook_dir_total,
        converted_m4b_outside_audiobook_dir_total,
    ) = _scan_converted_m4b(settings)

    downloaded_asins: set[str] = set()
    missing_files = 0
    orphan_downloads = 0

    for asin, entry in download_raw.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "success":
            continue
        asin_str = str(asin)
        asin_norm = _normalize_asin(asin_str)
        if not asin_norm:
            continue
        aaxc_path = _first_existing_path(_map_path_to_runtime(entry.get("aaxc_path")))
        if not aaxc_path:
            idx = download_index.get(asin_norm, {})
            aaxc_path = idx.get("aaxc_path") or idx.get("aax_path")

        if not aaxc_path or not _path_exists(aaxc_path):
            missing_files += 1
            continue
        if asin_norm in remote_asins:
            downloaded_asins.add(asin_norm)
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
        asin_norm = _normalize_asin(asin)
        if not asin_norm:
            continue
        output_path = _first_existing_path(_map_path_to_runtime(entry.get("output_path")))
        if not output_path:
            missing_files += 1
            continue
        if asin_norm in remote_asins:
            conversions_by_asin.setdefault(asin_norm, []).append({"output_path": output_path})
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
        downloaded_on_disk_total=downloaded_on_disk_total,
        downloaded_on_disk_remote_total=downloaded_on_disk_remote_total,
        converted_m4b_files_on_disk_total=converted_m4b_files_on_disk_total,
        converted_m4b_titles_on_disk_total=converted_m4b_titles_on_disk_total,
        converted_m4b_in_audiobook_dir_total=converted_m4b_in_audiobook_dir_total,
        converted_m4b_outside_audiobook_dir_total=converted_m4b_outside_audiobook_dir_total,
        downloaded_db_total=downloaded_db_total,
        converted_db_total=converted_db_total,
        misplaced_files_count=misplaced_files_count,
    )


async def apply_repair(session: AsyncSession, *, job_id: UUID | None = None) -> dict[str, Any]:
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
    books = list(result.scalars().all())
    books_by_asin: dict[str, Book] = {}
    for b in books:
        norm = _normalize_asin(b.asin)
        if norm:
            books_by_asin[norm] = b

    download_index = _build_download_file_index(settings=settings)

    now = datetime.utcnow()

    # Fetch DB settings early to check repair behavior flags
    db_settings_result = await session.execute(select(SettingsModel).where(SettingsModel.id == 1))
    db_settings = db_settings_result.scalar_one_or_none()
    repair_update_manifests = db_settings.repair_update_manifests if db_settings else True

    updated_books = 0
    inserted_local = 0
    duplicate_asins = 0
    deduped_local_items = 0
    manifest_updates_download = 0
    manifest_updates_converted = 0
    inferred_downloads = 0
    updates_breakdown: dict[str, int] = {
        "set_local_path_aax": 0,
        "set_local_path_voucher": 0,
        "set_local_path_cover": 0,
        "set_local_path_converted": 0,
        "set_status_downloaded": 0,
        "set_status_completed": 0,
        "set_conversion_format": 0,
    }

    # === Manifest reconciliation: sync manifests with filesystem ===
    # Only update manifests when repair_update_manifests=true (DB setting)

    # A. Update download_manifest from filesystem index
    if repair_update_manifests:
        for asin, files in download_index.items():
            aax_path = files.get("aaxc_path") or files.get("aax_path")
            if aax_path:
                existing = download_raw.get(asin)
                if not existing or not isinstance(existing, dict) or existing.get("status") != "success":
                    download_raw[asin] = {
                        "status": "success",
                        "aaxc_path": aax_path,
                        "voucher_path": files.get("voucher_path"),
                        "cover_path": files.get("cover_path"),
                        "discovered_at": now.isoformat(),
                        "source": "filesystem_scan",
                    }
                    manifest_updates_download += 1

    # B. Scan M4B files (always needed for conversion matching)
    m4b_scan_results = await _scan_m4b_with_asin(settings, session)

    # Update converted_manifest only when repair_update_manifests=true
    if repair_update_manifests:
        for m4b_info in m4b_scan_results:
            asin = m4b_info.get("asin")
            output_path = m4b_info.get("path")
            if output_path and not _manifest_has_conversion(converted_raw, asin or "", output_path):
                key = output_path  # Use path as key
                converted_raw[key] = {
                    "status": "success",
                    "asin": asin,
                    "title": m4b_info.get("title"),
                    "output_path": output_path,
                    "discovered_at": now.isoformat(),
                    "source": "filesystem_scan",
                    "matched_by": m4b_info.get("matched_by"),
                }
                manifest_updates_converted += 1

        # C. Infer download status from M4B existence (if M4B exists, download must have happened)
        for m4b_info in m4b_scan_results:
            asin = m4b_info.get("asin")
            if asin:
                asin_norm = _normalize_asin(asin)
                # Check if not already in download manifest
                has_download = False
                for k in download_raw:
                    if _normalize_asin(k) == asin_norm:
                        has_download = True
                        break
                if not has_download:
                    download_raw[asin] = {
                        "status": "success",
                        "inferred_from": "m4b_exists",
                        "m4b_path": m4b_info.get("path"),
                        "discovered_at": now.isoformat(),
                        "source": "inferred",
                    }
                    inferred_downloads += 1

        # D. Write updated manifests
        download_manifest_path.write_text(json.dumps(download_raw, indent=2, ensure_ascii=False), encoding="utf-8")
        converted_manifest_path.write_text(json.dumps(converted_raw, indent=2, ensure_ascii=False), encoding="utf-8")

    # Precompute conversions per asin with file existence.
    conversions_by_asin: dict[str, list[dict[str, Any]]] = {}
    orphan_conversions: list[dict[str, Any]] = []
    for _key, entry in converted_raw.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "success":
            continue
        asin = entry.get("asin")
        asin_norm = _normalize_asin(asin)
        output_path = _first_existing_path(_map_path_to_runtime(entry.get("output_path")))
        if not asin_norm or not output_path:
            continue
        if asin_norm in books_by_asin:
            conversions_by_asin.setdefault(asin_norm, []).append(
                {
                    "output_path": output_path,
                    "imported_at": entry.get("imported_at"),
                }
            )
        else:
            orphan_conversions.append(
                {
                    "asin": str(asin),
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

    # Build a duplicates report so the user can manually delete redundant outputs.
    # We DO NOT delete any files automatically in the repair workflow.
    reports_dir = settings.converted_dir / ".repair_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    report_name = f"repair_{job_id}_{stamp}_duplicates.tsv" if job_id else f"repair_{stamp}_duplicates.tsv"
    duplicates_report_path = reports_dir / report_name

    rows: list[str] = [
        "\t".join(["asin", "keep_or_delete", "output_path", "imported_at", "reason"])
    ]

    for asin, convs in conversions_by_asin.items():
        if len(convs) <= 1:
            continue
        duplicate_asins += 1

        best = pick_best(convs)
        best_path = str(best.get("output_path") or "")
        rows.append(
            "\t".join(
                [
                    asin,
                    "KEEP",
                    best_path,
                    str(best.get("imported_at") or ""),
                    "chosen_by_repair",
                ]
            )
        )
        for c in convs:
            out = str(c.get("output_path") or "")
            if out == best_path:
                continue
            reason = "not_chosen"
            if "/Audiobook/" in best_path and "/Audiobook/" not in out:
                reason = "not_chosen_missing_audiobook_dir"
            rows.append(
                "\t".join(
                    [
                        asin,
                        "DELETE_CANDIDATE",
                        out,
                        str(c.get("imported_at") or ""),
                        reason,
                    ]
                )
            )

    duplicates_report_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    # De-dupe local items up-front so we don't compound duplicates across repairs.
    deduped_local_items = await _dedupe_local_items(session)

    # Apply downloads + conversions to books
    for asin_norm, book in books_by_asin.items():
        changed = False

        # download_manifest is keyed by raw ASIN; match case-insensitively
        d = None
        for k, v in download_raw.items():
            if _normalize_asin(k) == asin_norm:
                d = v
                break
        if isinstance(d, dict) and d.get("status") == "success":
            aaxc_path = _first_existing_path(_map_path_to_runtime(d.get("aaxc_path")))
            voucher_path = _first_existing_path(_map_path_to_runtime(d.get("voucher_path")))
            cover_path = _first_existing_path(_map_path_to_runtime(d.get("cover_path")))

            # Fallback to index if manifest paths don't resolve (common with filename sanitization changes).
            idx = download_index.get(asin_norm, {})
            if not aaxc_path:
                aaxc_path = idx.get("aaxc_path") or idx.get("aax_path")
            if not voucher_path:
                voucher_path = idx.get("voucher_path")
            if not cover_path:
                cover_path = idx.get("cover_path")

            if aaxc_path and _path_exists(aaxc_path) and book.local_path_aax != aaxc_path:
                book.local_path_aax = aaxc_path
                updates_breakdown["set_local_path_aax"] += 1
                changed = True
            if voucher_path and _path_exists(voucher_path) and book.local_path_voucher != voucher_path:
                book.local_path_voucher = voucher_path
                updates_breakdown["set_local_path_voucher"] += 1
                changed = True
            if cover_path and _path_exists(cover_path) and book.local_path_cover != cover_path:
                book.local_path_cover = cover_path
                updates_breakdown["set_local_path_cover"] += 1
                changed = True

            if book.status == BookStatus.NEW and aaxc_path and _path_exists(aaxc_path):
                book.status = BookStatus.DOWNLOADED
                updates_breakdown["set_status_downloaded"] += 1
                changed = True

        convs = conversions_by_asin.get(asin_norm) or []
        if convs:
            best = pick_best(convs)
            out = best.get("output_path")
            if isinstance(out, str) and out and book.local_path_converted != out:
                book.local_path_converted = out
                updates_breakdown["set_local_path_converted"] += 1
                changed = True
            fmt = _guess_format(out if isinstance(out, str) else None)
            if fmt and book.conversion_format != fmt:
                book.conversion_format = fmt
                updates_breakdown["set_conversion_format"] += 1
                changed = True
            if book.status != BookStatus.COMPLETED:
                book.status = BookStatus.COMPLETED
                updates_breakdown["set_status_completed"] += 1
                changed = True

        if changed:
            book.updated_at = now
            session.add(book)
            updated_books += 1

    # Insert local items for orphan conversions if not already present by output_path
    existing_paths_res = await session.execute(select(LocalItem.output_path))
    existing_paths = {row[0] for row in existing_paths_res.all()}
    existing_canon = {_first_existing_path(p) or p for p in existing_paths}
    for entry in orphan_conversions:
        out = entry.get("output_path")
        if not isinstance(out, str) or not out:
            continue
        canonical_out = _first_existing_path(out) or out
        if canonical_out in existing_canon or out in existing_paths:
            continue
        li = LocalItem(
            asin=entry.get("asin") if isinstance(entry.get("asin"), str) else None,
            title=str(entry.get("title") or "Unknown"),
            authors=str(entry.get("authors")) if isinstance(entry.get("authors"), str) else None,
            output_path=canonical_out,
            cover_path=None,
            format=_guess_format(canonical_out),
            created_at=now,
            updated_at=now,
        )
        session.add(li)
        inserted_local += 1

    # === Metadata extraction (controlled by settings flag) ===
    # Note: db_settings was already fetched earlier for repair_update_manifests check
    metadata_scanned = 0

    if db_settings and db_settings.repair_extract_metadata:
        # Import here to avoid circular dependency
        from services.metadata_extractor import MetadataExtractor
        from services.library_manager import LibraryManager
        import logging
        logger = logging.getLogger(__name__)

        extractor = MetadataExtractor()
        manager = LibraryManager(extractor)

        # Scan books that have a converted path
        for book in books:
            if book.local_path_converted:
                converted_path = Path(book.local_path_converted)
                if converted_path.exists():
                    try:
                        await manager.scan_book(session, book.asin, force=False)
                        metadata_scanned += 1
                    except Exception as e:
                        logger.warning(f"Metadata extraction failed for {book.asin}: {e}")

    await session.commit()
    return {
        "updated_books": updated_books,
        "inserted_local_items": inserted_local,
        "deduped_local_items": deduped_local_items,
        "duplicate_asins": duplicate_asins,
        "duplicates_report_path": str(duplicates_report_path),
        "updates_breakdown": updates_breakdown,
        "manifest_updates_download": manifest_updates_download,
        "manifest_updates_converted": manifest_updates_converted,
        "inferred_downloads": inferred_downloads,
        "metadata_scanned": metadata_scanned,
    }
