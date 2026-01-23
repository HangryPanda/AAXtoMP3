"""Metadata extraction service for audiobooks."""

import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class TechnicalMetadata(BaseModel):
    format: str | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    duration_ms: int | None = None
    file_size: int | None = None

class ChapterMetadata(BaseModel):
    index: int
    title: str
    start_offset_ms: int
    length_ms: int
    end_offset_ms: int

class BookMetadata(BaseModel):
    asin: str | None = None
    title: str | None = None
    subtitle: str | None = None
    authors: list[str] = []
    narrators: list[str] = []
    series: str | None = None
    series_index: str | None = None
    publisher: str | None = None
    release_date: str | None = None
    description: str | None = None
    genres: list[str] = []
    language: str | None = None
    chapters: list[ChapterMetadata] = []
    technical: TechnicalMetadata | None = None
    cover_extracted_path: str | None = None

class MetadataExtractor:
    """Extractor for audiobook metadata using ffprobe and mediainfo."""
    
    VERSION = "1.0.0"

    def __init__(self, ffprobe_path: str = "ffprobe", mediainfo_path: str = "mediainfo"):
        self.ffprobe_path = ffprobe_path
        self.mediainfo_path = mediainfo_path

    async def extract(self, file_path: Path, cover_output_dir: Path | None = None) -> BookMetadata:
        """Extract metadata from a media file."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Run ffprobe
        ffprobe_data = await self._run_ffprobe(file_path)
        
        # Normalize data
        metadata = self._parse_ffprobe_output(ffprobe_data, file_path)
        
        # Extract cover if requested
        if cover_output_dir:
            metadata.cover_extracted_path = await self.extract_cover(file_path, cover_output_dir)
            
        return metadata

    async def _run_ffprobe(self, file_path: Path) -> dict[str, Any]:
        """Execute ffprobe and return JSON output."""
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            str(file_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error("ffprobe failed with code %d: %s", process.returncode, stderr.decode())
                return {}
                
            return json.loads(stdout.decode())
        except Exception as e:
            logger.exception("Error running ffprobe")
            return {}

    def _parse_ffprobe_output(self, data: dict[str, Any], file_path: Path) -> BookMetadata:
        """Parse and normalize ffprobe JSON output."""
        fmt = data.get("format", {})
        tags = fmt.get("tags", {})
        
        # Helper to get tags case-insensitively
        def get_tag(*keys: str) -> str | None:
            for k in keys:
                # Check exact match
                if k in tags: return tags[k]
                # Check lowercase match
                k_lower = k.lower()
                for tk in tags:
                    if tk.lower() == k_lower:
                        return tags[tk]
            return None

        # Technical info
        tech = TechnicalMetadata(
            format=fmt.get("format_name"),
            bitrate=int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else None,
            duration_ms=int(float(fmt.get("duration", 0)) * 1000) if fmt.get("duration") else None,
            file_size=int(fmt.get("size", 0)) if fmt.get("size") else None
        )
        
        # Find audio stream for sample rate and channels
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                tech.sample_rate = int(stream.get("sample_rate", 0)) if stream.get("sample_rate") else None
                tech.channels = int(stream.get("channels", 0)) if stream.get("channels") else None
                break

        # Chapters
        chapters = []
        raw_chapters = data.get("chapters", [])
        
        if not raw_chapters and tech.duration_ms:
            # Create a single implicit chapter if none exist
            chapters.append(ChapterMetadata(
                index=0,
                title="Full Book",
                start_offset_ms=0,
                length_ms=tech.duration_ms,
                end_offset_ms=tech.duration_ms
            ))
        else:
            for i, c in enumerate(raw_chapters):
                start_ms = int(float(c.get("start_time", 0)) * 1000)
                end_ms = int(float(c.get("end_time", 0)) * 1000)
                
                # Handle untitled chapters
                title = c.get("tags", {}).get("title")
                if not title or not title.strip():
                    title = f"Chapter {i+1}"
                
                chapters.append(ChapterMetadata(
                    index=i,
                    title=title,
                    start_offset_ms=start_ms,
                    length_ms=max(0, end_ms - start_ms),
                    end_offset_ms=end_ms
                ))

        # Mapping Audible/MP4 tags to our model
        authors_raw = get_tag("artist", "album_artist", "author")
        narrators_raw = get_tag("composer", "narrator")
        title_tag = get_tag("title")
        album_tag = get_tag("album")

        # Extract ASIN from metadata tags (written by AAXtoMP3)
        asin = get_tag("ASIN", "AUDIBLE_ASIN", "asin", "audible_asin")

        # Validate ASIN format (B + 9 alphanumeric or 10-digit ISBN)
        if asin:
            asin = asin.strip()
            if not (re.match(r'^B[A-Z0-9]{9}$', asin, re.IGNORECASE) or re.match(r'^\d{10}$', asin)):
                asin = None  # Invalid format, ignore

        series_name: str | None = None
        series_index: str | None = None

        # Try to get series info from tags
        series_tag = get_tag("series", "SERIES")
        series_seq_tag = get_tag("series_sequence", "SERIES_SEQUENCE", "series-part")

        if series_tag:
            series_name = series_tag.strip()
            series_index = series_seq_tag.strip() if series_seq_tag else None
        # Heuristic fallback: when both title and album are present, treat album as series (common for audiobooks).
        elif title_tag and album_tag and album_tag.strip() and album_tag.strip() != title_tag.strip():
            series_name = album_tag.strip()

        metadata = BookMetadata(
            asin=asin,
            title=title_tag or album_tag,
            subtitle=get_tag("subtitle"),
            authors=self._split_list(authors_raw),
            narrators=self._split_list(narrators_raw),
            series=series_name,
            series_index=series_index,
            publisher=get_tag("publisher", "copyright"),
            release_date=get_tag("date", "year", "creation_time"),
            description=get_tag("comment", "description", "synopsis"),
            genres=self._split_list(get_tag("genre")),
            language=get_tag("language"),
            technical=tech,
            chapters=chapters
        )
        
        return metadata

    def _split_list(self, raw: str | None) -> list[str]:
        """Split a string of names/items into a list."""
        if not raw:
            return []
        # Split by semicolon, comma (if followed by space), or &
        parts = re.split(r';|, | & ', raw)
        return [p.strip() for p in parts if p.strip()]

    async def extract_cover(self, file_path: Path, output_dir: Path) -> str | None:
        """Extract embedded cover image to a file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Use a hash of the file path or content to generate a stable cover filename
        file_hash = hashlib.md5(str(file_path).encode()).hexdigest()
        cover_path = output_dir / f"{file_hash}.jpg"
        
        if cover_path.exists():
            return str(cover_path)

        # ffmpeg -i input.m4b -an -vcodec copy cover.jpg
        cmd = [
            "ffmpeg",
            "-v", "quiet",
            "-i", str(file_path),
            "-an",
            "-vcodec", "copy",
            "-f", "mjpeg",
            "-y",
            str(cover_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            if process.returncode == 0 and cover_path.exists() and cover_path.stat().st_size > 0:
                return str(cover_path)
            
            # If it failed, it might not have a MJPEG cover, try PNG
            cover_path_png = output_dir / f"{file_hash}.png"
            cmd[cmd.index(str(cover_path))] = str(cover_path_png)
            cmd[cmd.index("mjpeg")] = "image2" # generic image format
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            if process.returncode == 0 and cover_path_png.exists() and cover_path_png.stat().st_size > 0:
                return str(cover_path_png)
                
        except Exception:
            logger.exception("Failed to extract cover")
            
        return None

    def get_fingerprint(self, file_path: Path) -> dict[str, Any]:
        """Get file fingerprint for invalidation."""
        stats = file_path.stat()
        return {
            "mtime": stats.st_mtime,
            "size": stats.st_size,
            "path": str(file_path.absolute())
        }
