# Conversion Workflow (Source of Truth)

This document is the **source of truth** for the audiobook conversion workflow (AAX/AAXC → DRM-free formats).

It is written to prevent regressions and ensure architectural consistency. If you change behavior, you **must** update this document and re-run the validation steps at the end.

---

## Data Flow (Mental Model)

1. **UI** queues a conversion: `POST /jobs/convert` with `{asin, format, naming_scheme}`.
2. **API route** (`apps/api/api/routes/jobs.py`) creates **one** `CONVERT` job row.
3. **JobManager** (`apps/api/services/job_manager.py`) orchestrates execution:
   - Enforces the **global** `max_convert_concurrent` semaphore.
   - Resolves input files (`.aax/.aaxc`), vouchers, and chapters.
4. **ConverterEngine** (`apps/api/services/converter_engine.py`) executes the conversion:
   - Invokes `core/AAXtoMP3` (Bash) as a subprocess.
   - Parses `ffmpeg` output for progress and telemetry.
5. **Telemetry → DB + WebSocket**:
   - Updates `job.progress_percent`.
   - Populates `status.meta` with structured telemetry.
6. **Persistence**:
   - Atomic move of output to the library.
   - Update `Book.status` and `Book.local_path_converted`.
   - Update manifests and trigger a library scan.

---

## What This Workflow Guarantees (MUST-FOLLOW)

1. **Engine Invariant**: Conversion MUST continue to run via `core/AAXtoMP3` invoked by `ConverterEngine`.
2. **Concurrency Control**: `max_convert_concurrent` MUST remain a **global cap** enforced by `JobManager`.
3. **Stability**: Output file formats and paths MUST remain stable to prevent library corruption.
4. **Atomic Operations**:
   - MUST convert to a temporary isolation directory first.
   - MUST run `ffprobe` integrity checks on the output before moving to the library.
   - MUST perform an atomic `mv` only after verification passes.
5. **Progress Source**:
   - `job.progress_percent` MUST be computed from `ffmpeg` time/duration strings.
   - Parsing MUST be robust to variable decimal places in time strings (e.g., `12.3` vs `12.345`).
   - Parsing MUST handle `N/A` for bitrate/speed without crashing.
6. **No Secret Leakage**: DO NOT log authcodes, voucher contents, or sensitive internal paths.
7. **Telemetry Throttling**:
   - High-frequency telemetry MUST be stored in `status.meta`, not `status_message`.
   - `status.meta` updates MUST be throttled to at most **2 times per second** per job.

---

## Structured Conversion Telemetry (`status.meta`)

The API MUST emit the following keys in `status.meta` when available:

- `convert_current_ms`: Current position processed (in milliseconds).
- `convert_total_ms`: Total duration of the book (in milliseconds).
- `convert_speed_x`: Ffmpeg speed multiplier (float, e.g., `42.3`).
- `convert_bitrate_kbps`: Ffmpeg bitrate (float) if available.

---

## End-to-End Execution Details

### 1) Input Resolution Priority
JobManager MUST locate the source file using this sequence:
1. DB Record (`Book.local_path_aax`).
2. Filesystem Scan: `downloads/` directory (matching ASIN).
3. Filesystem Scan: `completed/` directory (matching ASIN).
4. Fallback: Book Title match.

### 2) Subprocess Execution
Command structure MUST follow:
```bash
bash core/AAXtoMP3 -e:{format} -s -A {authcode} ...
```
For `.aaxc`, `--use-audible-cli-data` is used with the `.voucher` file.

### 3) Post-Processing & Cleanup
- **On Success**: Move source files to `completed/` if `move_after_complete` is enabled.
- **On Failure**: DO NOT leave partial files in the library; cleanup the temporary directory.
- **Integrity**: A failed `ffprobe` check MUST mark the job as `FAILED`.

---

## Validation / Testing (MUST RUN Before Shipping)

### 1) API tests (inside dev container)

Run:
```bash
docker compose -f docker-compose.dev.yml exec -T api pytest -q \
  tests/unit/test_converter_engine_parsing.py \
  tests/unit/test_job_manager_telemetry.py \
  tests/integration/test_conversion_jobs.py
```

### 2) Manual validation

1. Enable a conversion job for a downloaded book.
2. Confirm progress increases smoothly in the UI.
3. Verify telemetry exists in the `status.meta` payload via one of:
   - Browser DevTools -> Network -> WS (search for `convert_speed_x`).
   - `curl -s http://localhost:8000/jobs/{job_id} | jq .meta`.

## Common Failure Modes

1. **Stuck at 0%**: Progress parser regex failed to match current `ffmpeg` output.
2. **Permission Denied**: `ConverterEngine` cannot write to the temp directory or move to the final destination.
3. **Invalid Duration**: `ffprobe` check failed due to a corrupt or partial conversion.