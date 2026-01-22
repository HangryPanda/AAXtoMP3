"""
Backfill LocalItem rows from legacy manifest files.

This is intended to import "local-only" converted items that no longer appear in the
current Audible catalog (i.e. not present in the `books` table after sync).

Usage (host):
  cd apps/api
  .venv/bin/python backfill_local_items_from_manifests.py \
    --converted-manifest ../../specs/converted_manifest.json
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from db.models import Book, LocalItem
from db.session import async_session_maker, create_db_and_tables


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill local-only items from manifests")
    p.add_argument(
        "--converted-manifest",
        type=Path,
        required=True,
        help="Path to converted_manifest.json",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing to the database",
    )
    return p.parse_args()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _guess_format(output_path: str) -> str | None:
    suffix = Path(output_path).suffix.lower().lstrip(".")
    return suffix or None


async def main() -> None:
    args = _parse_args()
    await create_db_and_tables()

    manifest = _load_json(args.converted_manifest)
    if not isinstance(manifest, dict):
        raise SystemExit("converted_manifest must be a JSON object keyed by source path")

    async with async_session_maker() as session:
        # Build set of known Audible items (current catalog snapshot)
        res = await session.execute(select(Book.asin))
        known_asins = {row[0] for row in res.all()}

        # Build set of existing local items by output path for idempotency
        res2 = await session.execute(select(LocalItem.output_path))
        existing_output_paths = {row[0] for row in res2.all()}

        to_insert: list[LocalItem] = []

        for _source_key, entry in manifest.items():
            if not isinstance(entry, dict):
                continue

            asin = entry.get("asin")
            title = entry.get("title") or "Unknown"
            authors = entry.get("authors")  # optional, may not exist
            output_path = entry.get("output_path")
            status = entry.get("status")

            if status != "success":
                continue
            if not isinstance(output_path, str) or not output_path:
                continue
            if output_path in existing_output_paths:
                continue

            # Only import items not in current Audible library (local-only)
            if isinstance(asin, str) and asin in known_asins:
                continue

            item = LocalItem(
                asin=asin if isinstance(asin, str) else None,
                title=str(title),
                authors=str(authors) if isinstance(authors, str) else None,
                output_path=output_path,
                cover_path=None,
                format=_guess_format(output_path),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            to_insert.append(item)

        if args.dry_run:
            print(f"Would insert {len(to_insert)} local items (local-only).")
            for it in to_insert[:25]:
                print(f"- asin={it.asin} title={it.title} output_path={it.output_path}")
            return

        for it in to_insert:
            session.add(it)
        await session.commit()

        print(f"Inserted {len(to_insert)} local items.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
