# Download Workflow (Source of Truth)

This document is the **source of truth** for the Audible download workflow.

It is written to prevent regressions and breaking changes. If you change behavior, you **must** update this document and re-run the validation steps at the end.

---
## Data Flow (Mental Model)

This section describes the data flow from UI → API → background execution → persistence → UI updates.

### A. Request → Job Record → Queue

1. **UI** issues `POST /jobs/download` with `{asin}` or `{asins:[...]}`.
2. **API route** (`apps/api/api/routes/jobs.py`) creates **one** `Job` row:
   - `task_type=DOWNLOAD`
   - `payload_json={"asins":[...]}`
   - `book_asin=<asin>` only when single-ASIN (otherwise `null`)
3. **API route** calls `JobManager.queue_download(job_id, asins)` exactly once.
4. **JobManager** immediately emits an initial status update (`QUEUED`) which:
   - is persisted to the DB (status/progress/messages),
   - is broadcast on the global jobs WebSocket feed (`/jobs/ws`) as a `status` message.

### B. Execution → Progress/Telemetry → UI

1. **JobManager** (`apps/api/services/job_manager.py`) starts `_execute_download(job_id, asins)`.
2. For each ASIN, it spawns a `download_one(asin)` task that:
   - acquires the **global** semaphore `max_download_concurrent` (default 5),
   - calls `AudibleClient.download(asin, ...)`.
3. **AudibleClient** (`apps/api/services/audible_client.py`) runs `audible-cli download` as a subprocess and streams output.
4. **Progress signals**:
   - tqdm-like output lines are parsed into `(current_bytes, total_bytes)` for the main `.aax/.aaxc` download,
   - JobManager aggregates bytes across all active ASINs into:
     - `job.progress_percent` (aggregate bytes percent),
     - `status.meta.download_bytes_per_sec` (aggregate throughput).
5. **Status callback → DB + WebSocket** (`apps/api/api/routes/jobs.py`):
   - updates the `jobs` table (status/progress/message/error/log_file_path),
   - broadcasts `type:"status"` with `progress` and `meta` over `/jobs/ws`.
6. **Web UI**:
   - `useJobsFeedWebSocket` updates cached `Job` objects with `progress_percent` and download telemetry,
   - Job cards/active jobs/progress popover render:
     - percent from `job.progress_percent`,
     - throughput from `job.download_bytes_per_sec` (MB/s),
     - ETA from the UI’s progress model (until an ETA-bytes model is implemented).

### C. Completion → Manifest/Book Paths → Downstream Conversion

1. After an ASIN finishes successfully, JobManager:
   - discovers output files under `downloads_dir` (AAX/AAXC, voucher, cover, chapters JSON),
   - updates the `books` table paths + sets `Book.status=DOWNLOADED` (when the book exists),
   - updates the download manifest (success entries).
2. When the batch completes, the job is marked `COMPLETED` (or `FAILED` if any items failed), and the UI updates without polling via WebSocket.

## What This Workflow Guarantees (MUST-FOLLOW)

1. **Batch semantics are per-request:** `POST /jobs/download` creates **one** `DOWNLOAD` job record for the whole request (1..N ASINs) and queues it once.
2. **Global download concurrency is enforced:**
   - The system supports up to `max_download_concurrent` concurrent *file downloads* globally.
   - **Preference:** `max_download_concurrent` MUST be set to `1` (sequential).
   - **Reason:** Audible enforces a **per-account bandwidth cap** (approx. 10MB/s). Parallel downloads divide this bandwidth, slowing down individual book completion and delaying conversion pipelining.
3. **Download progress is bytes-based (not item-count-based):**
   - `Job.progress_percent` for `DOWNLOAD` jobs is computed from actual bytes transferred (parsed from `audible-cli` progress output).
   - This is **not** “completed ASINs / total ASINs”.
4. **Real-time telemetry is structured:** download throughput is sent over WebSocket `status.meta` as `download_bytes_per_sec` and rendered as MB/s in the UI.
5. **`audible-cli` is invoked without unsupported flags:** do **not** pass `--config-dir` (audible-cli 0.3.x does not support it).
6. **Retry is stable:** `/jobs/{job_id}/retry` must work for both:
   - current payload format `{"asins": [...]}`, and
   - legacy payload format `{"asin": "..."}` (backward compatibility).
7. **Logs are persisted:** job logs must be written under the downloads volume so they survive container restarts.
---

## Architecture Overview

### Key Actors

- **Web UI (Next.js):** shows progress %, MB/s, ETA and logs.
- **API route:** creates the job and queues it.
- **JobManager:** owns concurrency limits, orchestrates batch downloads, computes progress and throughput, updates manifests and DB.
- **AudibleClient:** runs `audible-cli download` (subprocess) and parses its progress output.

### Files & Directories (Container Paths)

- Downloads output dir: `Settings.downloads_dir` (default `/data/downloads`)
- Persisted job logs: `/data/downloads/.job_logs/{job_id}.log`
- Audible auth mounts:
  - dev compose mounts `~/.audible` into `/root/.audible` and also into `/audible-config` for the Python audible client auth file.
  - `audible-cli` reads config from `$HOME/.audible/config.toml` (so ensure `$HOME` matches the mount).

## End-to-End Flow

### 1) UI → API: Create Download Job

**Request:**
- Endpoint: `POST /jobs/download`
- Body: `{ "asin": "..." }` or `{ "asins": ["...", "..."] }`

**MUST:**
- Create **one** `Job` row with:
  - `task_type = DOWNLOAD`
  - `payload_json = {"asins":[...]}`
  - `book_asin = first asin if len(asins)==1 else null`
- Queue exactly once:
  - `JobManager.queue_download(job_id, asins)`

### 2) JobManager: Execute Batch Download (Concurrency + Progress)

JobManager spawns one asyncio task per ASIN but **all downloads share the same global semaphore**:

- `max_download_concurrent` limits how many `audible-cli download` subprocesses run simultaneously across **all jobs**.
- A batch job of 20 ASINs will run up to 5 in parallel, then the next ones start as slots free up.

### 3) AudibleClient: Run audible-cli and Parse Byte Progress

AudibleClient constructs and executes a command (example):

```bash
audible --profile "$AUDIBLE_PROFILE" download \
  --asin "$ASIN" \
  --output-dir "/data/downloads" \
  --cover --cover-size 1215 \
  --chapter \
  --filename-mode asin_unicode \
  --quality high \
  --no-confirm \
  --aaxc
```

**MUST:**
- `output_dir` must exist (AudibleClient ensures `mkdir -p` equivalent via `Path.mkdir()`).
- No `--config-dir` flag.
- For AAXC: the `.voucher` file is downloaded by audible-cli.

### Progress Source: tqdm parsing vs NDJSON (feature-flagged)

The API supports two methods for progress parsing, controlled by the `AUDIBLE_CLI_PROGRESS_FORMAT` environment variable.

**1. Default: tqdm parsing (`AUDIBLE_CLI_PROGRESS_FORMAT=tqdm` or unset)**
- **Behavior:** Parses the human-readable tqdm progress bar from stdout.
- **MUST:** Be the default behavior for safety.
- **MUST NOT:** Pass `--progress-format` to the CLI.

**2. NDJSON parsing (`AUDIBLE_CLI_PROGRESS_FORMAT=ndjson`)**
- **Behavior:** Parses machine-readable NDJSON events from stdout (requires `audible-cli` fork).
- **MUST:** Pass `--progress-format ndjson` to the CLI.
- **MUST:** Parse `download_progress` events for `current_bytes` and `total_bytes`.
- **MUST:** Handle `download_error` events as structured failures.
- **DO NOT:** Enable this in production until the fork is pinned and fully validated.

**Progress parsing (current implementation):**
- We stream subprocess output and parse tqdm-like lines to extract `(current_bytes, total_bytes)` for the main `.aax/.aaxc` file.
- This is used for:
  - `Job.progress_percent` (aggregate),
  - throughput `download_bytes_per_sec` (aggregate).

**Important limitations (MUST know):**
- This method is robust enough for now but relies on audible-cli output format. If you upgrade `audible-cli`, you **must** re-validate the parser.
- Totals may not be available until a parsable tqdm line appears; progress may stay at 0% briefly at start.

### 4) Job Progress, MB/s Throughput, and WebSocket Updates

**Aggregate progress for a batch job:**
- Let each active ASIN contribute `(cur_i, tot_i)`.
- `job.progress_percent = floor( sum(cur_i) / sum(tot_i) * 100 )`.

This makes progress a **weighted average by file size**, not a count of completed books.

**Throughput:**
- `download_bytes_per_sec` is computed from the change in total `sum(cur_i)` over time.
- This is sent via the jobs WebSocket feed in `status.meta`:
  - `download_bytes_current`
  - `download_bytes_total`
  - `download_bytes_per_sec`

**MUST:**
- `status_message` must not be spammed; meta carries high-frequency data.

### 5) Post-Processing: DB + Manifest Updates

After each ASIN completes successfully:
- Find downloaded files under `downloads_dir` using `_find_downloaded_files(asin, output_dir)`.
- Update DB fields on `Book` (if book exists):
  - `local_path_aax` (AAX/AAXC)
  - `local_path_voucher` (voucher)
  - `local_path_cover` (cover)
  - `status = DOWNLOADED`
- Update download manifest (success entries).

Failures:
- Do not stop the whole batch; continue downloading remaining ASINs.
- Surface a helpful error string for single-ASIN jobs in `Job.error_message` (and always write full details to the persisted job log).

### 6) Retry Behavior (MUST remain stable)

Endpoint: `POST /jobs/{job_id}/retry`

**MUST:**
- Support:
  - `payload_json={"asins":[...]}` (current), and
  - `payload_json={"asin":"..."}` (legacy).
- Retry creates a new job with incremented `attempt` and queues it.

## Code Map (Where To Edit Safely)

- API job creation: `apps/api/api/routes/jobs.py`
  - `POST /jobs/download`
  - `POST /jobs/{job_id}/retry`
- Orchestration + concurrency + byte progress aggregation: `apps/api/services/job_manager.py`
- audible-cli subprocess + progress parsing: `apps/api/services/audible_client.py`
- Jobs WebSocket cache plumbing: `apps/web/src/hooks/useJobsFeedWebSocket.ts`
- UI rendering:
  - Job cards: `apps/web/src/components/domain/JobsView.tsx`
  - Active jobs view: `apps/web/src/components/domain/ActiveJobsView.tsx`
  - Progress popover: `apps/web/src/components/domain/ProgressPopover.tsx`

## Validation / Testing (MUST RUN Before Shipping)

### 1) API tests (inside dev container)

Run (fast subset covering downloads):

```bash
docker compose -f docker-compose.dev.yml exec -T api pytest -q \
  tests/integration/test_jobs.py::TestDownloadJobEndpoint \
  tests/integration/test_jobs_retry.py \
  tests/unit/test_job_manager.py \
  tests/unit/test_audible_client.py \
  tests/unit/test_audible_client_args.py \
  tests/unit/test_audible_cli_progress_parser.py
```

### 2) Manual validation (real Audible auth required)

1) Start dev API container:

```bash
docker compose -f docker-compose.dev.yml up -d --build api postgres
```

2) Queue a batch download (>=2 ASINs) and verify:
- The job is a single job id.
- Multiple “Downloading:” lines appear quickly (parallelism).

```bash
curl -sS -X POST http://localhost:8000/jobs/download \
  -H 'Content-Type: application/json' \
  -d '{"asins":["B09RX4LQTL","0063137321"]}' | jq
```

3) Verify progress and MB/s are non-placeholder while running:
- `progress_percent` increases and is **not** tied to completed count.
- UI shows `X.Y MB/s`.

4) Inspect persisted logs:

```bash
JOB_ID="..."; docker compose -f docker-compose.dev.yml exec -T api \
  sh -lc "tail -n 200 /data/downloads/.job_logs/$JOB_ID.log"
```

5) Validate concurrency (optional):

```bash
docker top audible-api-dev -eo pid,cmd | grep -E 'audible .* download' || true
```

Expected: up to `max_download_concurrent` concurrent `audible download` processes across all jobs.

## Common Failure Modes (What To Check First)

1. **Downloads run only 1 at a time:** you likely reintroduced per-job serialization (don’t hold a job-scoped semaphore around the whole batch).
2. **Progress stuck at 0%:** parser may not be matching current audible-cli output; re-check `audible_client.py` progress regex.
3. **No auth in container:** ensure `~/.audible` is mounted into the container user’s `$HOME/.audible` and `audible -P "$PROFILE" library export` works.
4. **No logs / “See logs” empty:** ensure log dir is `/data/downloads/.job_logs` and `Job.log_file_path` is populated during status updates.
