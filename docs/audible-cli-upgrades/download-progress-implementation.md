# Download Progress Implementation Plan

## Overview

This document outlines the implementation plan for adding machine-readable progress events and structured errors to the audible-cli download command, enabling consumption by the Audible Library Manager (FastAPI + Next.js) without scraping tqdm output.

---

## 1. Codebase Architecture

| Component | Location | Purpose |
|-----------|----------|---------|
| **Main CLI** | `src/audible_cli/cli.py` | Entry point, global error handling, exit codes |
| **Download Command** | `src/audible_cli/cmds/cmd_download.py` (988 lines) | CLI options, queue management, download orchestration |
| **Downloader** | `src/audible_cli/downloader.py` | HTTP streaming, tqdm progress, resume support |
| **Exceptions** | `src/audible_cli/exceptions.py` | Custom error classes |
| **Models** | `src/audible_cli/models.py` | Library/Item models, filename generation |

---

## 2. Current Progress Implementation

**Location**: `downloader.py:261-278` (tqdm progress bar)
```python
def get_progressbar(destination, total, start=0):
    progressbar = tqdm.tqdm(
        desc=description,
        total=total,           # From Content-Length header
        unit="B",
        unit_scale=True,
        unit_divisor=1024
    )
```

**Usage**: `_stream_download()` method (line 444-473) calls `progressbar.update(len(chunk))` per chunk

**Available Data During Download**:
- `total_bytes`: From `Content-Length` header
- `current_bytes`: Cumulative chunk sizes
- `speed`: Auto-calculated by tqdm (not directly accessible)
- `filename`: Passed as `target.path`
- **ASIN**: Not currently passed to downloader (must be threaded through)

---

## 3. Current Error Handling

### Exception Classes (`exceptions.py`)

| Exception | Proposed Error Code | Description |
|-----------|-------------------|-------------|
| `LicenseDenied` | AUTH | License request was not granted |
| `NoDownloadUrl` | AUTH | License response missing download URL |
| `DownloadUrlExpired` | AUTH | Download URL has expired |
| `VoucherNeedRefresh` | AUTH | Voucher refresh date reached |
| `NotFoundError` (audible lib) | NOT_FOUND | Item not found in library/API |
| `ItemNotPublished` | NOT_FOUND | Item not yet published |
| `NotDownloadableAsAAX` | IO | Item cannot be downloaded as AAX |
| `DirectoryDoesNotExists` | IO | Directory path does not exist |
| `FileDoesNotExists` | IO | File path does not exist |
| Generic httpx exceptions | NETWORK | Network/HTTP errors |
| Rate limiting (429) | RATE_LIMIT | API rate limiting |
| Everything else | UNKNOWN | Unexpected errors |

### Exit Codes (`cli.py:60-74`)

| Code | Condition |
|------|-----------|
| 0 | Success |
| 1 | User abort (`click.Abort`) |
| 2 | Application error (`AudibleCliException`, `CancelledError`) |
| 3 | Unexpected exception |

---

## 4. Download Flow (Key Files to Modify)

```
cmd_download.py                      downloader.py
================                     =============
cli() L765
  ├─ Library.from_api_full_sync()
  ├─ queue_job() L517
  │   └─ QUEUE.put_nowait()
  ├─ consume() L504
  │   └─ download_aaxc() L412
  │       └─ NewDownloader.run()  ───► run() L498
  │                                      └─ _stream_download() L444
  │                                           └─ progressbar.update(chunk)
  └─ display_counter()
```

---

## 5. Implementation Plan

### 5.1 Add `--progress-format` Flag

**Location**: `cmd_download.py` near line 761

```python
@click.option(
    "--progress-format",
    type=click.Choice(["tqdm", "json", "ndjson"]),
    default="tqdm",
    help="Progress output format: tqdm (default), json, or ndjson for machine-readable output"
)
```

### 5.2 Create New Module: `src/audible_cli/progress.py`

```python
from enum import Enum
from typing import Optional
import json
import sys
from datetime import datetime, timezone

class ProgressFormat(Enum):
    TQDM = "tqdm"
    JSON = "json"
    NDJSON = "ndjson"

class ErrorCode(Enum):
    AUTH = "AUTH"
    NETWORK = "NETWORK"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMIT = "RATE_LIMIT"
    IO = "IO"
    UNKNOWN = "UNKNOWN"

class ProgressReporter:
    def __init__(self, format: ProgressFormat, asin: str, filename: str):
        self.format = format
        self.asin = asin
        self.filename = filename
        self._start_time = None
        self._last_bytes = 0
        self._last_time = None

    def emit_progress(self, current_bytes: int, total_bytes: int, resumed: bool = False):
        # Calculate bytes_per_sec
        # Emit event based on format
        pass

    def emit_complete(self, total_bytes: int):
        pass

    def emit_error(self, error_code: ErrorCode, message: str):
        pass
```

### 5.3 Modify `Downloader` Class (`downloader.py`)

- Add optional `progress_callback` parameter to `__init__`
- Modify `_stream_download()` to call callback with progress data
- Track `bytes_per_sec` using `time.time()` deltas

### 5.4 Modify Download Functions (`cmd_download.py`)

- `download_aax()` (L309): Pass ASIN + progress reporter
- `download_aaxc()` (L412): Pass ASIN + progress reporter
- `consume()` (L504): Wrap with error event emission

### 5.5 Modify `queue_job()` (L517)

Pass `progress_format` and ASIN context through the download chain.

---

## 6. Event Schema

### 6.1 Progress Event

```json
{
  "type": "progress",
  "asin": "B00EXAMPLE",
  "filename": "book-AAX_44_128.aaxc",
  "current_bytes": 5242880,
  "total_bytes": 157286400,
  "bytes_per_sec": 2621440.5,
  "timestamp": "2025-01-24T10:30:45.123Z",
  "resumed": false
}
```

### 6.2 Complete Event

```json
{
  "type": "complete",
  "asin": "B00EXAMPLE",
  "filename": "book-AAX_44_128.aaxc",
  "total_bytes": 157286400,
  "success": true,
  "timestamp": "2025-01-24T10:31:15.789Z"
}
```

### 6.3 Error Event

```json
{
  "type": "error",
  "asin": "B00EXAMPLE",
  "filename": "book.aaxc",
  "success": false,
  "error_code": "AUTH",
  "message": "License not granted",
  "timestamp": "2025-01-24T10:30:45.123Z"
}
```

---

## 7. Resume/Recovery Status

The existing resume logic in `downloader.py` tracks:
- ETag-based resume files (L333-345)
- Resume detection via `await tmp_file.get_size()` (L520)
- Can add `resumed: true/false` based on `start > 0`

---

## 8. Batch Behavior

Already implemented correctly:
- `queue_job()` is called per-ASIN (L954-972)
- Each item processed independently through async queue
- ASIN available via `item.asin` at queue_job call time

---

## 9. Example Usage

```bash
audible -P <profile> download --asin B00EXAMPLE --output-dir ./downloads --aaxc --no-confirm --progress-format ndjson
```

Sample output:
```
{"type":"progress","asin":"B00EXAMPLE","filename":"book-AAX_44_128.aaxc","current_bytes":5242880,"total_bytes":157286400,"bytes_per_sec":2621440.5,"timestamp":"2025-01-24T10:30:45.123Z","resumed":false}
{"type":"progress","asin":"B00EXAMPLE","filename":"book-AAX_44_128.aaxc","current_bytes":10485760,"total_bytes":157286400,"bytes_per_sec":2500000.0,"timestamp":"2025-01-24T10:30:47.456Z","resumed":false}
{"type":"complete","asin":"B00EXAMPLE","filename":"book-AAX_44_128.aaxc","total_bytes":157286400,"success":true,"timestamp":"2025-01-24T10:31:15.789Z"}
```

---

## 10. Open Questions / Gaps

### 10.1 Missing Event Types

| Event Type | Trigger Location | Purpose |
|------------|------------------|---------|
| `start` | Before download begins | UI shows "Starting download..." before first progress update |
| `skip` | `downloader.py:166-170`, `cmd_download.py:427-434` | File already exists, skip download |
| `voucher_reused` | `cmd_download.py:362-409` | Cached voucher was used |
| `voucher_refreshed` | `cmd_download.py:437-443` | New license fetched due to expiry |
| `voucher_fetch_start` / `voucher_fetch_complete` | `cmd_download.py:448` | Track license API calls |
| `multipart_detected` | `cmd_download.py:345, 487` | Item requires individual part downloads |
| `multipart_start` / `multipart_complete` | `cmd_download.py:261-306` | Track multi-part audio downloads |
| `batch_start` | `cmd_download.py:927-930` | With total item count |
| `batch_progress` | During queue processing | X of Y items completed |
| `batch_complete` | `cmd_download.py:987` | With summary stats |
| `podcast_expanded` | `cmd_download.py:935-952` | Parent podcast resolved to episodes |

### 10.2 Missing Error Scenarios

| Error Code | Exception/Condition | Notes |
|------------|---------------------|-------|
| `TIMEOUT` | httpx timeout | Connection timeout |
| `CONNECTION_RESET` | httpx connection errors | Connection reset by server |
| `SSL_ERROR` | SSL/TLS certificate errors | Certificate validation failures |
| `DNS_ERROR` | DNS resolution failures | Host not found |
| `CONNECTION_REFUSED` | Server refused connection | Service unavailable |
| `PARTIAL_DOWNLOAD` | `downloader.py:182-187` | File incomplete but resumable |
| `DOWNLOAD_INCOMPLETE` | Server cut connection | Mid-stream failure |
| `CORRUPT_DOWNLOAD` | Size mismatch | Downloaded size != Content-Length |
| `NOT_PUBLISHED` | `ItemNotPublished` | Should include publication_date in event |

### 10.3 Stream Output Pollution (CRITICAL)

**Problem**: When `--progress-format` is `json`/`ndjson`, logger output will be mixed with JSON events.

**Polluting Locations**:
- `logger.info()` calls throughout `cmd_download.py` (L167-168, 174, 190, 214-216, 428-432)
- `logger.debug()` calls in `models.py` (L199, 372-376, 380, 389)
- tqdm output from `downloader.py:268-278`
- ETag logging in `downloader.py:361`

**Recommended Solution**:
- When JSON mode active, redirect ALL logging to `stderr`
- Or suppress non-JSON output to separate log file
- Or add filtering in `ClickHandler` (`_logging.py:100-112`)
- Use `DummyProgressBar` in JSON mode to avoid tqdm interference

### 10.4 Batch/Queue Visibility Gaps

| Gap | Current Behavior | Needed |
|-----|------------------|--------|
| Overall batch progress | Not tracked | X of Y items completed events |
| Dynamic batch size | Podcast children added at runtime (L939-947) | `batch_size_updated` event |
| Concurrent job identification | No visibility | `job_number: 1 of 3 concurrent` |
| Queue status | No events | Emit when queue empties, items added |

### 10.5 Implementation Architecture Gaps

| Gap | Location | Issue |
|-----|----------|-------|
| Progress callback | `downloader.py:288-299` | `Downloader.__init__` doesn't accept callback |
| Resume file events | `downloader.py:333-345` | No events for resume file found/used/deleted |
| Quality fallback | `models.py:198-201` | No event when requested codec unavailable |
| Exit code mapping | `cli.py:60-74` | Need correlation between error_code and exit code |

---

## 11. Additional Data Points for UI/UX

### 11.1 Item Metadata Available (from `models.py` and API)

| Field | Source | UI Value |
|-------|--------|----------|
| `title`, `subtitle` | `item.full_title` | Display name |
| `asin` | `item.asin` | Unique identifier |
| `product_images` | API response | Cover art at 252, 315, 360, 408, 500, 558, 570, 882, 900, 1215px |
| `series` | response_groups | Series name & position |
| `publication_datetime` | API response | Release date |
| `rating` | response_groups | Customer rating |
| `available_codecs` | API response | AAX_44_128 (high), AAX_44_64 (normal) |
| `content_type` | API response | "Podcast", "Audiobook", etc. |
| `content_delivery_type` | API response | AudioPart, MultiPartBook, Periodical, PodcastParent |
| `benefit_id` | `item.benefit_id` | "AYCL" for special benefits |
| `is_ayce` | Flag | Special account type |
| `has_children` | API response | Multi-part indicator |
| `duration_ms` | API response (if available) | Runtime for ETA display |

### 11.2 Quality/Codec Information

| Field | Derivation | UI Value |
|-------|------------|----------|
| `quality_requested` | User input ("best", "high", "normal") | Requested quality |
| `codec_format` | From download URL | "AAX_44_128", "MPEG" |
| `sample_rate` | Parsed from codec (models.py:183-185) | 44100 Hz |
| `bitrate` | Parsed from codec | 128 kbps |
| `quality_granted` | Actual codec used | May differ from requested |

### 11.3 Enhanced Event Schema (Recommended)

#### Start Event
```json
{
  "type": "start",
  "asin": "B00EXAMPLE",
  "title": "Book Title",
  "author": "Author Name",
  "filename": "book-AAX_44_128.aaxc",
  "total_bytes": 157286400,
  "codec": "AAX_44_128",
  "quality_requested": "best",
  "quality_granted": "high",
  "cover_url": "https://...",
  "series_name": "Series Name",
  "series_position": 3,
  "is_multipart": false,
  "resumed": false,
  "timestamp": "2025-01-24T10:30:45.123Z"
}
```

#### Skip Event
```json
{
  "type": "skip",
  "asin": "B00EXAMPLE",
  "filename": "book-AAX_44_128.aaxc",
  "reason": "already_exists",
  "existing_size": 157286400,
  "timestamp": "2025-01-24T10:30:45.123Z"
}
```

#### Batch Events
```json
{
  "type": "batch_start",
  "total_items": 5,
  "asins": ["B00A", "B00B", "B00C", "B00D", "B00E"],
  "concurrent_jobs": 3,
  "timestamp": "2025-01-24T10:30:45.123Z"
}
```

```json
{
  "type": "batch_progress",
  "completed": 2,
  "total": 5,
  "in_progress": 3,
  "failed": 0,
  "timestamp": "2025-01-24T10:30:45.123Z"
}
```

#### Voucher Events
```json
{
  "type": "voucher_reused",
  "asin": "B00EXAMPLE",
  "voucher_file": "/path/to/file.voucher",
  "expires_at": "2025-02-24T10:30:45.123Z",
  "timestamp": "2025-01-24T10:30:45.123Z"
}
```

### 11.4 API Response Groups Available but Unused

Currently requested (L866-868):
```
"product_desc, media, product_attrs, relationships, series, customer_rights, pdf_url"
```

Available for richer UI data:
- `contributors` - Author/narrator information
- `listening_status`, `is_finished`, `percent_complete` - User progress
- `categories`, `category_ladders` - Genre/categorization
- `badge_types` - Special badges
- `review_attrs`, `reviews` - Review data
- `price` - Purchase info
- `periodicals` - Content relationships

### 11.5 Progress Event Frequency Considerations

| Consideration | Recommendation |
|---------------|----------------|
| Emit frequency | Every 100KB or 500ms, whichever first |
| Small files | At least start + complete events |
| Large files | Cap at ~2 events/second to avoid flooding |
| Batch operations | Aggregate if >50 items |

