"""Script to backfill metadata for already converted books."""

import asyncio
import logging
import sys
from pathlib import Path

# Add the current directory to sys.path to allow imports from services, db, etc.
sys.path.append(str(Path(__file__).parent))

from db.session import async_session_maker
from services.metadata_extractor import MetadataExtractor
from services.library_manager import LibraryManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def backfill():
    extractor = MetadataExtractor()
    manager = LibraryManager(extractor)
    
    async with async_session_maker() as session:
        logger.info("Starting metadata backfill...")
        count = await manager.scan_library(session, force=True)
        logger.info(f"Backfill complete. Updated {count} books.")

if __name__ == "__main__":
    asyncio.run(backfill())
