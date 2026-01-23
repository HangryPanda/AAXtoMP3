"""Service for managing the audiobook library and metadata persistence."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session

from db.models import (
    Book, Person, BookAuthor, BookNarrator, Series, BookSeries, 
    Chapter, BookAsset, BookTechnical, BookScanState, PlaybackProgress
)
from services.metadata_extractor import MetadataExtractor, BookMetadata

logger = logging.getLogger(__name__)

class LibraryManager:
    """Manager for library metadata persistence and scanning."""

    def __init__(self, extractor: MetadataExtractor):
        self.extractor = extractor

    async def scan_book(self, session: AsyncSession, asin: str, force: bool = False) -> bool:
        """Scan a book's media file and update its metadata in the database."""
        # 1. Get book info
        result = await session.execute(select(Book).where(Book.asin == asin))
        book = result.scalar_one_or_none()
        if not book:
            logger.error("Book not found: %s", asin)
            return False

        if not book.local_path_converted:
            logger.warning("Book %s has no converted path, skipping scan", asin)
            return False

        file_path = Path(book.local_path_converted)
        if not file_path.exists():
            logger.error("Converted file not found for book %s: %s", asin, file_path)
            return False

        # 2. Check scan state / fingerprint
        fingerprint = self.extractor.get_fingerprint(file_path)
        result = await session.execute(select(BookScanState).where(BookScanState.book_asin == asin))
        scan_state = result.scalar_one_or_none()

        needs_scan = force or not scan_state or \
                     scan_state.file_mtime != fingerprint["mtime"] or \
                     scan_state.file_size != fingerprint["size"] or \
                     scan_state.extractor_version != self.extractor.VERSION

        if not needs_scan:
            logger.info("Book %s is up to date, skipping scan", asin)
            return True

        # 3. Extract metadata
        logger.info("Extracting metadata for book %s from %s", asin, file_path)
        try:
            # Determine cover cache dir from settings or use a default
            cover_cache_dir = Path("/app/data/covers") 
            metadata = await self.extractor.extract(file_path, cover_output_dir=cover_cache_dir)
            logger.info("Metadata extracted for %s: %s", asin, metadata.title)
        except Exception:
            logger.exception("Failed to extract metadata for book %s", asin)
            return False

        # 4. Persist normalized metadata
        if metadata.title:
            book.title = metadata.title
        await self._persist_metadata(session, asin, metadata)

        # 5. Update scan state
        if not scan_state:
            scan_state = BookScanState(
                book_asin=asin, 
                file_path=str(file_path.absolute()), 
                file_mtime=fingerprint["mtime"], 
                file_size=fingerprint["size"],
                extractor_version=self.extractor.VERSION
            )
            session.add(scan_state)
        else:
            scan_state.file_mtime = fingerprint["mtime"]
            scan_state.file_size = fingerprint["size"]
            scan_state.extracted_at = datetime.utcnow()
            scan_state.extractor_version = self.extractor.VERSION
        
        await session.commit()
        logger.info("Successfully updated metadata for book %s", asin)
        return True

    async def _persist_metadata(self, session: AsyncSession, asin: str, metadata: BookMetadata):
        """Update normalized tables with extracted metadata."""
        
        # --- Authors ---
        # Clear existing associations (simpler than syncing for now)
        await session.execute(delete(BookAuthor).where(BookAuthor.book_asin == asin))
        for i, name in enumerate(metadata.authors):
            person = await self._get_or_create_person(session, name)
            session.add(BookAuthor(book_asin=asin, person_id=person.id, ordinal=i))

        # --- Narrators ---
        await session.execute(delete(BookNarrator).where(BookNarrator.book_asin == asin))
        for i, name in enumerate(metadata.narrators):
            person = await self._get_or_create_person(session, name)
            session.add(BookNarrator(book_asin=asin, person_id=person.id, ordinal=i))

        # --- Series ---
        await session.execute(delete(BookSeries).where(BookSeries.book_asin == asin))
        if metadata.series:
            series = await self._get_or_create_series(session, metadata.series)
            session.add(BookSeries(book_asin=asin, series_id=series.id, series_index=metadata.series_index))

        # --- Chapters ---
        await session.execute(delete(Chapter).where(Chapter.book_asin == asin))
        for c in metadata.chapters:
            session.add(Chapter(
                book_asin=asin,
                index=c.index,
                title=c.title,
                start_offset_ms=c.start_offset_ms,
                length_ms=c.length_ms,
                end_offset_ms=c.end_offset_ms
            ))

        # --- Assets (Cover) ---
        if metadata.cover_extracted_path:
            # Check if cover asset already exists
            result = await session.execute(
                select(BookAsset).where(BookAsset.book_asin == asin, BookAsset.asset_type == 'cover')
            )
            asset = result.scalar_one_or_none()
            if not asset:
                session.add(BookAsset(book_asin=asin, asset_type='cover', path=metadata.cover_extracted_path))
            else:
                asset.path = metadata.cover_extracted_path

        # --- Technical ---
        if metadata.technical:
            result = await session.execute(select(BookTechnical).where(BookTechnical.book_asin == asin))
            tech = result.scalar_one_or_none()
            if not tech:
                tech = BookTechnical(book_asin=asin)
                session.add(tech)
            
            tech.format = metadata.technical.format
            tech.bitrate = metadata.technical.bitrate
            tech.sample_rate = metadata.technical.sample_rate
            tech.channels = metadata.technical.channels
            tech.duration_ms = metadata.technical.duration_ms
            tech.file_size = metadata.technical.file_size
            tech.extracted_at = datetime.utcnow()

    async def _get_or_create_person(self, session: AsyncSession, name: str) -> Person:
        result = await session.execute(select(Person).where(Person.name == name))
        person = result.scalar_one_or_none()
        if not person:
            person = Person(name=name)
            session.add(person)
            await session.flush() # Get ID
        return person

    async def _get_or_create_series(self, session: AsyncSession, name: str) -> Series:
        result = await session.execute(select(Series).where(Series.name == name))
        series = result.scalar_one_or_none()
        if not series:
            series = Series(name=name)
            session.add(series)
            await session.flush() # Get ID
        return series

    async def scan_library(self, session: AsyncSession, force: bool = False):
        """Batch scan all completed books in the library."""
        result = await session.execute(select(Book).where(Book.local_path_converted != None))
        books = result.scalars().all()
        
        logger.info("Starting batch library scan for %d books", len(books))
        count = 0
        for book in books:
            success = await self.scan_book(session, book.asin, force=force)
            if success:
                count += 1
        
        logger.info("Library scan complete. Updated %d books.", count)
        return count

    async def get_book_details(self, session: AsyncSession, asin: str) -> dict[str, Any]:
        """Fetch all enriched metadata for a book."""
        # This would be used by the API to return a full view
        # Implementation omitted for brevity but would join all new tables
        pass
