# Audiobook Metadata Scanning & Persistence

This feature adds a normalized database schema for rich audiobook metadata and a pipeline to extract it from converted `.m4b` files.

## Components

1.  **Metadata Extractor (`services/metadata_extractor.py`)**:
    *   Uses `ffprobe` to extract metadata from media files.
    *   Extracts chapters, technical info (bitrate, duration), and tags.
    *   Extracts embedded cover images to a cache directory.

2.  **Library Manager (`services/library_manager.py`)**:
    *   Manages the scanning process.
    *   Implements invalidation logic using file fingerprints (mtime + size).
    *   Persists normalized data into Postgres tables (`books`, `people`, `series`, `chapters`, etc.).

3.  **Job Manager Integration**:
    *   Scanning is integrated as a background job (`JobType.SCAN`).
    *   Automatically triggered after a successful conversion.

## Usage

### API Endpoints

*   **Scan entire library**: `POST /api/library/scan?force=false`
    *   Queues a background job to scan all completed books.
    *   `force=true` re-scans even if the file hasn't changed.

*   **Scan single book**: `POST /api/library/{asin}/scan?force=false`
    *   Scans a specific book immediately (or queues it, depending on implementation).

*   **Get Book Details**: `GET /api/library/{asin}/details`
    *   Returns the full enriched metadata object, including authors, narrators, series, chapters, and technical stats.

### CLI Backfill

To populate metadata for existing books in your library:

```bash
# From apps/api directory
python backfill_metadata.py
```

## Database Schema

New tables added:
*   `people`: Authors and narrators.
*   `series`: Series titles.
*   `chapters`: Chapter start/end times and titles.
*   `book_assets`: References to cover images.
*   `book_technical`: Format, bitrate, sample rate, etc.
*   `book_scan_state`: Tracks file fingerprints to avoid redundant scans.
*   `playback_progress`: User progress (ready for player integration).

## Troubleshooting

*   **Missing Metadata**: Ensure `ffprobe` is installed and the `.m4b` files have proper tags.
*   **Scan Failures**: Check the job logs in `data/job_logs/`.
