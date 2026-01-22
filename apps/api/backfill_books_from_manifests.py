"""
Backfill `books` table using legacy manifest files.

This updates existing Book rows (the Audible-synced catalog) with:
- downloaded paths + status from download_manifest.json
- converted output path + status from converted_manifest.json

It is intended to be safe and idempotent. Start with --dry-run.

Notes on path formats:
- download_manifest.json may contain host paths (e.g. /Volumes/Media/...)
- converted_manifest.json typically contains container paths (e.g. /converted/...)

We translate host->container using explicit prefix mappings.

Usage:
  cd apps/api
  .venv/bin/python backfill_books_from_manifests.py \
    --download-manifest ../../specs/download_manifest.json \
    --converted-manifest ../../specs/converted_manifest.json \
    --dry-run
"""

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from db.models import Book, BookStatus
from db.session import async_session_maker, create_db_and_tables


HOST_TO_CONTAINER_PREFIXES = [
    ("/Volumes/Media/Audiobooks/Downloads", "/downloads"),
    ("/Volumes/Media/Audiobooks/Converted", "/converted"),
    ("/Volumes/Media/Audiobooks/Completed", "/completed"),
]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill Book statuses/paths from manifests")
    p.add_argument("--download-manifest", type=Path, required=True)
    p.add_argument("--converted-manifest", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--prefer-audiobook-path",
        action="store_true",
        default=True,
        help="Prefer converted output paths containing '/Audiobook/' when multiple entries exist.",
    )
    return p.parse_args()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _to_container_path(path: str | None) -> str | None:
    if not isinstance(path, str) or not path:
        return None

    # Already a container path
    if path.startswith(("/downloads/", "/converted/", "/completed/")):
        return path

    for host_prefix, container_prefix in HOST_TO_CONTAINER_PREFIXES:
        if path == host_prefix or path.startswith(host_prefix + "/"):
            return container_prefix + path[len(host_prefix) :]

    # Unknown format; return as-is
    return path


def _guess_format(output_path: str | None) -> str | None:
    if not isinstance(output_path, str) or not output_path:
        return None
    suffix = Path(output_path).suffix.lower().lstrip(".")
    return suffix or None


@dataclass
class DownloadEntry:
    asin: str
    aaxc_path: str | None
    voucher_path: str | None
    cover_path: str | None
    downloaded_at: str | None
    status: str | None


@dataclass
class ConvertEntry:
    asin: str
    output_path: str
    imported_at: str | None
    status: str | None


def _pick_best_convert(entries: list[ConvertEntry], prefer_audiobook_path: bool) -> ConvertEntry:
    if len(entries) == 1:
        return entries[0]

    def score(e: ConvertEntry) -> tuple[int, str]:
        audiobook_bonus = 1 if (prefer_audiobook_path and "/Audiobook/" in e.output_path) else 0
        # Higher imported_at should win; fall back to empty.
        return (audiobook_bonus, e.imported_at or "")

    # max by score
    return max(entries, key=score)


async def main() -> None:
    args = _parse_args()
    await create_db_and_tables()

    download_raw = _load_json(args.download_manifest)
    converted_raw = _load_json(args.converted_manifest)

    if not isinstance(download_raw, dict):
        raise SystemExit("download_manifest must be a JSON object keyed by ASIN")
    if not isinstance(converted_raw, dict):
        raise SystemExit("converted_manifest must be a JSON object keyed by source file path")

    downloads: dict[str, DownloadEntry] = {}
    for asin, entry in download_raw.items():
        if not isinstance(entry, dict):
            continue
        downloads[str(asin)] = DownloadEntry(
            asin=str(asin),
            aaxc_path=_to_container_path(entry.get("aaxc_path")),
            voucher_path=_to_container_path(entry.get("voucher_path")),
            cover_path=_to_container_path(entry.get("cover_path")),
            downloaded_at=entry.get("downloaded_at"),
            status=entry.get("status"),
        )

    conversions_by_asin: dict[str, list[ConvertEntry]] = {}
    for _key, entry in converted_raw.items():
        if not isinstance(entry, dict):
            continue
        asin = entry.get("asin")
        output_path = entry.get("output_path")
        if not isinstance(asin, str) or not asin:
            continue
        if not isinstance(output_path, str) or not output_path:
            continue
        conversions_by_asin.setdefault(asin, []).append(
            ConvertEntry(
                asin=asin,
                output_path=_to_container_path(output_path) or output_path,
                imported_at=entry.get("imported_at"),
                status=entry.get("status"),
            )
        )

    async with async_session_maker() as session:
        result = await session.execute(select(Book))
        books = result.scalars().all()
        books_by_asin = {b.asin: b for b in books}

        now = datetime.utcnow()

        would_update = 0
        set_downloaded = 0
        set_converted = 0
        set_cover = 0
        missing_books_in_db = 0
        orphan_conversions = 0
        orphan_downloads = 0

        for asin, d in downloads.items():
            if asin not in books_by_asin:
                orphan_downloads += 1
                if not args.dry_run:
                    # Create basic book record for orphan download
                    new_book = Book(
                        asin=asin,
                        title=f"Orphan Download {asin}",  # Placeholder title
                        status=BookStatus.DOWNLOADED,
                        local_path_aax=d.aaxc_path,
                        local_path_voucher=d.voucher_path,
                        local_path_cover=d.cover_path,
                        updated_at=now
                    )
                    session.add(new_book)
                    would_update += 1

        for asin, conv_list in conversions_by_asin.items():
            if asin not in books_by_asin and asin not in downloads:  # avoid double insert if in both
                orphan_conversions += 1
                if not args.dry_run:
                    best = _pick_best_convert(conv_list, prefer_audiobook_path=args.prefer_audiobook_path)
                    fmt = _guess_format(best.output_path)
                    
                    new_book = Book(
                        asin=asin,
                        title=f"Orphan Conversion {asin}",  # Placeholder title
                        status=BookStatus.COMPLETED,
                        local_path_converted=best.output_path,
                        conversion_format=fmt,
                        updated_at=now
                    )
                    session.add(new_book)
                    would_update += 1

        for asin, book in books_by_asin.items():
            changed = False

            # Apply download info
            d = downloads.get(asin)
            if d and d.status == "success":
                if d.aaxc_path and book.local_path_aax != d.aaxc_path:
                    book.local_path_aax = d.aaxc_path
                    changed = True
                if d.voucher_path and book.local_path_voucher != d.voucher_path:
                    book.local_path_voucher = d.voucher_path
                    changed = True
                if d.cover_path and book.local_path_cover != d.cover_path:
                    book.local_path_cover = d.cover_path
                    set_cover += 1
                    changed = True

                # Move status forward if currently NEW
                if book.status == BookStatus.NEW:
                    book.status = BookStatus.DOWNLOADED
                    set_downloaded += 1
                    changed = True

            # Apply conversion info
            convs = conversions_by_asin.get(asin) or []
            convs = [c for c in convs if c.status == "success"]
            if convs:
                best = _pick_best_convert(convs, prefer_audiobook_path=args.prefer_audiobook_path)
                if book.local_path_converted != best.output_path:
                    book.local_path_converted = best.output_path
                    changed = True
                fmt = _guess_format(best.output_path)
                if fmt and book.conversion_format != fmt:
                    book.conversion_format = fmt
                    changed = True

                if book.status != BookStatus.COMPLETED:
                    book.status = BookStatus.COMPLETED
                    set_converted += 1
                    changed = True

            if changed:
                book.updated_at = now
                would_update += 1
                if not args.dry_run:
                    session.add(book)

        if args.dry_run:
            print("Dry run: backfill_books_from_manifests")
            print(f"- Books in DB: {len(books_by_asin)}")
            print(f"- Would update: {would_update}")
            print(f"- Would mark downloaded: {set_downloaded}")
            print(f"- Would mark converted: {set_converted}")
            print(f"- Would set cover path (distinct updates): {set_cover}")
            print(f"- Orphan downloads (asin not in DB): {orphan_downloads}")
            print(f"- Orphan conversions (asin not in DB): {orphan_conversions}")
            return

        await session.commit()
        print(f"Updated {would_update} books.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
