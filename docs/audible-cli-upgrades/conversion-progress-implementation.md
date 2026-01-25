# Conversion/Decryption Progress Implementation Plan

## Overview

This document outlines the implementation plan for adding machine-readable progress events and structured errors to the audible-cli decrypt command, enabling consumption by the Audible Library Manager (FastAPI + Next.js).

**Key Challenge**: FFmpeg processes run via `subprocess.check_output()` with no progress callback mechanism. Progress must be parsed from FFmpeg's stderr stats output.

---

## 1. Codebase Architecture

| Component | Location | Purpose |
|-----------|----------|---------|
| **Decrypt Command** | `plugin_cmds/cmd_decrypt.py` (684 lines) | CLI interface and orchestration |
| **FfmpegFileDecrypter** | `cmd_decrypt.py:355-551` | Core decryption logic |
| **ApiChapterInfo** | `cmd_decrypt.py:106-220` | Parse and process chapter metadata |
| **FFMeta** | `cmd_decrypt.py:222-336` | FFmpeg metadata file handling |
| **ChapterError** | `cmd_decrypt.py:31-32` | Chapter-specific exceptions |

---

## 2. Current Implementation Details

### 2.1 Decryption Flow

```
cli() L616
  ├─ Validate FFmpeg exists (L636-638)
  ├─ Validate option combinations (L640-658)
  ├─ Get input files (L668)
  └─ For each file:
      └─ FfmpegFileDecrypter.run() (L456-551)
          ├─ Check output file exists (L460-465)
          ├─ Build FFmpeg command (L467-547)
          │   ├─ Add credentials (AAX: activation_bytes, AAXC: key/iv)
          │   ├─ Optional: rebuild chapters from voucher/API
          │   └─ Optional: remove intro/outro
          └─ subprocess.check_output() (L549)
```

### 2.2 FFmpeg Command Structure

**For AAX files**:
```bash
ffmpeg -v quiet -stats -activation_bytes <bytes> -i <input.aax> -c copy <output.m4b>
```

**For AAXC files**:
```bash
ffmpeg -v quiet -stats -audible_key <key> -audible_iv <iv> -i <input.aaxc> -c copy <output.m4b>
```

**With chapter rebuild**:
```bash
ffmpeg -v quiet -stats -audible_key <key> -audible_iv <iv> \
  -i <input.aaxc> -i <metadata.ffmeta> \
  -map_metadata 0 -map_chapters 1 -c copy <output.m4b>
```

### 2.3 Current Progress Handling

**NONE** - The current implementation uses:
```python
subprocess.check_output(base_cmd, text=True)  # Line 549
```

This blocks until FFmpeg completes with no progress feedback.

### 2.4 Available Data Points

| Data Point | Source | Location |
|------------|--------|----------|
| Input file path | CLI argument | `self._source` |
| Output file path | Derived | `self._target_dir / oname` |
| File type | File suffix | `.aax` or `.aaxc` |
| Credentials type | File type | activation_bytes vs key/iv |
| Chapter count | FFMeta/ApiChapterInfo | `count_chapters()` |
| Runtime length (ms) | ApiChapterInfo | `get_runtime_length_ms()` |
| Intro duration (ms) | ApiChapterInfo | `get_intro_duration_ms()` |
| Outro duration (ms) | ApiChapterInfo | `get_outro_duration_ms()` |
| Chapter accuracy | ApiChapterInfo | `is_accurate()` |

---

## 3. FFmpeg Progress Parsing

### 3.1 FFmpeg Stats Output Format

When FFmpeg runs with `-stats`, it outputs to stderr:
```
frame=    0 fps=0.0 q=-1.0 size=   12800kB time=00:05:32.45 bitrate= 315.7kbits/s speed=42.3x
```

**Key fields**:
- `size`: Bytes processed so far
- `time`: Current position in HH:MM:SS.ms format
- `bitrate`: Current bitrate
- `speed`: Processing speed (e.g., 42.3x real-time)

### 3.2 Progress Parsing Regex

```python
FFMPEG_PROGRESS_REGEX = re.compile(
    r"size=\s*(?P<size>\d+)kB\s+"
    r"time=(?P<time>\d{2}:\d{2}:\d{2}\.\d{2})\s+"
    r"bitrate=\s*(?P<bitrate>[\d.]+)kbits/s\s+"
    r"speed=\s*(?P<speed>[\d.]+)x"
)
```

### 3.3 Time to Milliseconds Conversion

```python
def parse_ffmpeg_time(time_str: str) -> int:
    """Convert HH:MM:SS.ms to milliseconds"""
    h, m, s = time_str.split(":")
    seconds = int(h) * 3600 + int(m) * 60 + float(s)
    return int(seconds * 1000)
```

---

## 4. Conversion Workflow Phases

| Phase | Progress Range | Description |
|-------|---------------|-------------|
| **Pre-flight** | 0-5% | FFmpeg check, credential validation, file checks |
| **Metadata Extraction** | 5-15% | Extract FFMeta from input file |
| **Chapter Processing** | 15-25% | Rebuild chapters if requested |
| **Decryption/Transcoding** | 25-95% | FFmpeg decrypt + remux |
| **Post-processing** | 95-100% | Cleanup, verification |

---

## 5. Implementation Plan

### 5.1 Add `--progress-format` Flag

**Location**: `cmd_decrypt.py` after line 614

```python
@click.option(
    "--progress-format",
    type=click.Choice(["tqdm", "json", "ndjson"]),
    default="tqdm",
    help="Progress output format: tqdm (default), json, or ndjson for machine-readable output"
)
```

### 5.2 Modify FFmpeg Execution

Replace `subprocess.check_output()` with streaming subprocess:

```python
async def run_ffmpeg_with_progress(
    cmd: List[str],
    total_duration_ms: int,
    progress_callback: Callable
) -> None:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    async for line in process.stderr:
        match = FFMPEG_PROGRESS_REGEX.search(line.decode())
        if match:
            current_time_ms = parse_ffmpeg_time(match.group("time"))
            progress_callback(
                current_ms=current_time_ms,
                total_ms=total_duration_ms,
                size_kb=int(match.group("size")),
                bitrate=float(match.group("bitrate")),
                speed=float(match.group("speed"))
            )

    await process.wait()
    if process.returncode != 0:
        raise ConversionError(f"FFmpeg exited with code {process.returncode}")
```

### 5.3 Create Progress Reporter for Conversion

```python
class ConversionProgressReporter:
    def __init__(
        self,
        format: ProgressFormat,
        input_file: str,
        output_file: str,
        asin: Optional[str] = None  # May not be available
    ):
        self.format = format
        self.input_file = input_file
        self.output_file = output_file
        self.asin = asin
        self._phase = "preflight"

    def emit_phase(self, phase: str, percent: float):
        """Emit phase transition event"""
        pass

    def emit_progress(
        self,
        current_ms: int,
        total_ms: int,
        size_kb: int,
        bitrate: float,
        speed: float
    ):
        """Emit FFmpeg progress event"""
        pass

    def emit_complete(self, output_size: int, duration_ms: int):
        """Emit completion event"""
        pass

    def emit_error(self, error_code: str, message: str):
        """Emit error event"""
        pass
```

---

## 6. Event Schema

### 6.1 Start Event

```json
{
  "type": "conversion_start",
  "input_file": "/path/to/book-AAX_44_128.aaxc",
  "output_file": "/path/to/book.m4b",
  "asin": "B00EXAMPLE",
  "file_type": "aaxc",
  "input_size_bytes": 157286400,
  "total_duration_ms": 36000000,
  "chapter_count": 25,
  "has_intro_outro": true,
  "intro_duration_ms": 2500,
  "outro_duration_ms": 5000,
  "rebuild_chapters": true,
  "remove_intro_outro": false,
  "timestamp": "2025-01-24T10:30:45.123Z"
}
```

### 6.2 Phase Event

```json
{
  "type": "conversion_phase",
  "input_file": "/path/to/book-AAX_44_128.aaxc",
  "phase": "decryption",
  "phase_percent": 25,
  "message": "Starting FFmpeg decryption",
  "timestamp": "2025-01-24T10:30:50.123Z"
}
```

### 6.3 Progress Event

```json
{
  "type": "conversion_progress",
  "input_file": "/path/to/book-AAX_44_128.aaxc",
  "output_file": "/path/to/book.m4b",
  "current_ms": 1800000,
  "total_ms": 36000000,
  "percent": 5.0,
  "size_kb": 31250,
  "bitrate_kbps": 128.5,
  "speed": 42.3,
  "eta_seconds": 850,
  "timestamp": "2025-01-24T10:31:00.123Z"
}
```

### 6.4 Complete Event

```json
{
  "type": "conversion_complete",
  "input_file": "/path/to/book-AAX_44_128.aaxc",
  "output_file": "/path/to/book.m4b",
  "asin": "B00EXAMPLE",
  "success": true,
  "output_size_bytes": 155000000,
  "duration_ms": 36000000,
  "processing_time_seconds": 850,
  "chapters_rebuilt": true,
  "intro_outro_removed": false,
  "timestamp": "2025-01-24T10:45:00.123Z"
}
```

### 6.5 Error Event

```json
{
  "type": "conversion_error",
  "input_file": "/path/to/book-AAX_44_128.aaxc",
  "output_file": "/path/to/book.m4b",
  "success": false,
  "error_code": "INVALID_CREDENTIALS",
  "message": "No key/iv found in voucher file",
  "phase": "preflight",
  "timestamp": "2025-01-24T10:30:45.123Z"
}
```

---

## 7. Error Codes

### 7.1 Pre-flight Errors

| Error Code | Exception/Condition | Description |
|------------|---------------------|-------------|
| `NO_FFMPEG` | `which("ffmpeg")` returns None | FFmpeg not installed |
| `INVALID_CREDENTIALS` | `get_aaxc_credentials()` fails | Missing/invalid key/iv |
| `NO_ACTIVATION_BYTES` | `activation_bytes is None` | No activation bytes for AAX |
| `VOUCHER_NOT_FOUND` | Voucher file doesn't exist | Missing .voucher file |
| `INPUT_NOT_FOUND` | Input file doesn't exist | File path invalid |
| `UNSUPPORTED_FORMAT` | Not .aax or .aaxc | Wrong file type |

### 7.2 Chapter Errors

| Error Code | Exception/Condition | Description |
|------------|---------------------|-------------|
| `CHAPTER_FILE_NOT_FOUND` | ChapterError from `from_file()` | Chapter JSON missing |
| `CHAPTER_PARSE_ERROR` | ChapterError from `_parse()` | Invalid chapter format |
| `CHAPTER_MISMATCH` | `ChapterError("Chapter mismatch")` | Chapter count mismatch |
| `CHAPTER_INACCURATE` | `is_accurate() == False` | API chapters not accurate |

### 7.3 FFmpeg Errors

| Error Code | Exception/Condition | Description |
|------------|---------------------|-------------|
| `FFMPEG_FAILED` | Non-zero exit code | FFmpeg execution failed |
| `DECRYPT_FAILED` | FFmpeg decryption error | Wrong credentials |
| `CODEC_ERROR` | FFmpeg codec issue | Codec not supported |
| `IO_ERROR` | File I/O failure | Disk full, permissions |
| `TIMEOUT` | Process timeout | FFmpeg hung |

### 7.4 Post-processing Errors

| Error Code | Exception/Condition | Description |
|------------|---------------------|-------------|
| `OUTPUT_MISSING` | Output file not created | FFmpeg silent failure |
| `OUTPUT_CORRUPT` | Size mismatch/validation | Output file invalid |
| `CLEANUP_FAILED` | Temp file cleanup failed | Non-critical |

---

## 8. Additional Data Points for UI/UX

### 8.1 Input File Metadata

| Field | Source | UI Value |
|-------|--------|----------|
| `input_file` | CLI argument | Full path |
| `input_size_bytes` | `os.path.getsize()` | File size for progress |
| `file_type` | File suffix | "aax" or "aaxc" |
| `codec` | Derived from filename | "AAX_44_128", etc. |
| `asin` | Parse from filename | If follows naming convention |

### 8.2 Chapter Metadata

| Field | Source | UI Value |
|-------|--------|----------|
| `chapter_count` | `ApiChapterInfo.count_chapters()` | Number of chapters |
| `total_duration_ms` | `get_runtime_length_ms()` | Total runtime |
| `intro_duration_ms` | `get_intro_duration_ms()` | Audible intro length |
| `outro_duration_ms` | `get_outro_duration_ms()` | Audible outro length |
| `chapters_accurate` | `is_accurate()` | API data quality |
| `chapter_titles` | `get_chapters()` | List of chapter names |

### 8.3 Conversion Options

| Field | Source | UI Value |
|-------|--------|----------|
| `rebuild_chapters` | CLI flag | Whether chapters rebuilt |
| `force_rebuild` | CLI flag | Force on mismatch |
| `skip_on_mismatch` | CLI flag | Skip vs fail on mismatch |
| `separate_intro_outro` | CLI flag | Intro/outro as chapters |
| `remove_intro_outro` | CLI flag | Trim Audible branding |
| `overwrite` | CLI flag | Overwrite existing |

### 8.4 Processing Metrics

| Field | Calculation | UI Value |
|-------|-------------|----------|
| `speed` | From FFmpeg stats | "42.3x" real-time |
| `eta_seconds` | `(total_ms - current_ms) / speed` | Estimated time remaining |
| `bitrate_kbps` | From FFmpeg stats | Current processing bitrate |
| `processing_time` | elapsed since start | Wall clock time |

---

## 9. Batch Processing Considerations

### 9.1 Batch Events

```json
{
  "type": "conversion_batch_start",
  "total_files": 5,
  "files": [
    {"input": "/path/a.aaxc", "size": 100000000},
    {"input": "/path/b.aaxc", "size": 200000000}
  ],
  "timestamp": "2025-01-24T10:30:45.123Z"
}
```

```json
{
  "type": "conversion_batch_progress",
  "completed": 2,
  "total": 5,
  "current_file": "/path/c.aaxc",
  "failed": 0,
  "timestamp": "2025-01-24T10:35:45.123Z"
}
```

### 9.2 Per-File Identification

Since conversion works on files (not ASINs directly), we need to:
1. Parse ASIN from filename if following standard naming: `{title}-{codec}.aaxc`
2. Or look up ASIN from voucher file content
3. Include both `input_file` and optional `asin` in all events

---

## 10. Stream Output Considerations

### 10.1 Current Output Pollution

The decrypt command uses `echo()` and `secho()` which write to stdout:
- Line 168: `echo("Separate Audible Brand Intro...")`
- Line 204: `echo("Delete Audible Brand Intro...")`
- Line 298: `echo("Metadata from API is not accurate...")`
- Line 303: `echo("Force rebuild chapters...")`
- Line 307: `echo(f"Found {count} chapters...")`
- Line 406: `echo(f"Using chapters from...")`
- Line 462-464: `secho(f"Overwrite/Skip...")`
- Line 551: `echo(f"File decryption successful...")`

### 10.2 Recommended Solution

When `--progress-format` is `json`/`ndjson`:
1. Redirect all `echo()`/`secho()` to stderr
2. Or suppress and include as `message` field in events
3. Capture FFmpeg stderr separately for progress parsing

---

## 11. Integration with Download Workflow

### 11.1 Combined Download + Convert Flow

For a complete workflow, the API might:
1. Call `audible download --aaxc --progress-format ndjson`
2. Parse download events until complete
3. Call `audible decrypt --progress-format ndjson`
4. Parse conversion events until complete

### 11.2 Event Correlation

Use common identifiers across download and conversion:
- `asin`: Available in download, may need extraction in conversion
- `filename`: Base filename without extension
- `session_id`: Optional, if added for correlation

### 11.3 Unified Event Prefix

Consider prefixing events for easy routing:
- `download_*` events for download phase
- `conversion_*` events for decrypt phase

---

## 12. Example Usage

```bash
# Single file conversion
audible decrypt /path/to/book-AAX_44_128.aaxc --progress-format ndjson

# With chapter rebuild
audible decrypt /path/to/book.aaxc --rebuild-chapters --progress-format ndjson

# Batch conversion
audible decrypt --all --progress-format ndjson

# Remove Audible branding
audible decrypt /path/to/book.aaxc --rebuild-chapters --remove-intro-outro --progress-format ndjson
```

Sample output:
```
{"type":"conversion_start","input_file":"/path/to/book.aaxc","output_file":"/path/to/book.m4b","total_duration_ms":36000000,"timestamp":"2025-01-24T10:30:45.123Z"}
{"type":"conversion_phase","phase":"metadata","phase_percent":5,"timestamp":"2025-01-24T10:30:46.123Z"}
{"type":"conversion_phase","phase":"decryption","phase_percent":25,"timestamp":"2025-01-24T10:30:50.123Z"}
{"type":"conversion_progress","current_ms":1800000,"total_ms":36000000,"percent":5.0,"speed":42.3,"timestamp":"2025-01-24T10:31:00.123Z"}
{"type":"conversion_progress","current_ms":18000000,"total_ms":36000000,"percent":50.0,"speed":41.8,"timestamp":"2025-01-24T10:35:00.123Z"}
{"type":"conversion_complete","success":true,"output_size_bytes":155000000,"timestamp":"2025-01-24T10:45:00.123Z"}
```

---

## 13. Testing Considerations

### 13.1 Test Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Valid AAX with activation bytes | Complete flow with progress |
| Valid AAXC with voucher | Complete flow with progress |
| Missing voucher file | `VOUCHER_NOT_FOUND` error event |
| Invalid credentials | `INVALID_CREDENTIALS` error event |
| Chapter mismatch (no force) | `CHAPTER_MISMATCH` error event |
| Chapter mismatch (with force) | Warning + successful conversion |
| FFmpeg not installed | `NO_FFMPEG` error event |
| Output file exists (no overwrite) | Skip event |
| Output file exists (with overwrite) | Complete with overwrite note |

### 13.2 Progress Emission Testing

- Verify progress events emitted at reasonable intervals
- Verify ETA calculations are reasonable
- Verify speed metrics match FFmpeg output
- Test with various file sizes (small, medium, large)

---

## 14. Implementation Priority

1. **Phase 1**: Add `--progress-format` flag, basic start/complete/error events
2. **Phase 2**: FFmpeg progress parsing and progress events
3. **Phase 3**: Phase events and detailed metadata
4. **Phase 4**: Batch processing events
5. **Phase 5**: ETA calculations and speed metrics
