# Plan: Conversion Workflow Hardening (Progress + Reliability)

This document is the **implementation plan and handoff checklist** for hardening the conversion workflow (AAX/AAXC → converted output) in this repo.

It is written so work can be resumed after a crash/context loss, and so multiple agents can work in parallel without overlapping scope.

**Scope (this plan)**: conversion execution + progress/telemetry + reliability checks for the existing `core/AAXtoMP3` pipeline.

**Out of scope**: switching the conversion engine to use `audible-cli decrypt` (that would be a separate migration plan).

---

## READ FIRST: Execution + Assignments (MUST FOLLOW)

### Agents MUST follow this exact structure

1. **Read this plan before making changes.**
2. **Work only within your assigned scope below.**
3. **Paste evidence into the single evidence log file:**
   - `docs/workflows/library/conversion_workflow_hardening_status.md`
4. If you started work without an assignment, **STOP** and ask the orchestrator for clarification. Do not “guess” tasks.

### Assignments (authoritative)

- **Claude-A (API code)**:
  - Allowed to modify production code only in `apps/api`.
  - Owns: `ConverterEngine` parsing robustness + JobManager `status.meta` emission + throttling.
- **Gemini-A (Docs)**:
  - Allowed to modify only `docs/workflows/library/conversion_workflow.md`.
  - Owns: making the conversion workflow doc explicit “source of truth” + validation steps.
- **Codex-A (Tests)**:
  - Allowed to modify only `apps/api/tests`.
  - Owns: parser tests + JobManager meta emission/throttling tests (no real conversions).
- **Codex-Orchestrator**:
  - Merges changes, resolves conflicts, runs final Docker gates, and performs manual UI validation.

---

## Data Flow (Mental Model)

1. **UI** queues a conversion: `POST /jobs/convert` (single ASIN per job).
2. **API route** creates one `CONVERT` job row and calls `JobManager.queue_conversion(job_id, asin, format, naming_scheme)`.
3. **JobManager** enforces `max_convert_concurrent` (global conversion semaphore), resolves input file/voucher/chapters, then runs conversion.
4. **ConverterEngine** executes `core/AAXtoMP3` (bash) which runs `ffmpeg` and emits progress lines.
5. **Progress → DB + WebSocket**:
   - `job.progress_percent` is updated (currently % based on ffmpeg time vs duration)
   - structured conversion telemetry MUST be emitted in `status.meta` (new requirement in this plan)
6. **On success**: DB book status + `local_path_converted` are updated; manifests updated; sources moved if configured; metadata scan runs.

---

## Non-Negotiables (MUST FOLLOW)

- **Do not change the conversion engine**: conversion MUST continue to run via `core/AAXtoMP3` invoked by `apps/api/services/converter_engine.py`.
- **Container-first validation**: all tests/validation MUST run inside Docker (`docker compose -f docker-compose.dev.yml exec -T api ...`).
- **No regressions**:
  - `max_convert_concurrent` remains a **global cap**.
  - Output file formats and paths must remain stable.
  - Jobs must still be cancellable/pauseable (cooperative; subprocess may not stop immediately).
- **No secret leakage**: never log authcodes, voucher contents, or any sensitive file content.
- **Do not spam job messages**:
  - high-frequency updates go in `status.meta`
  - `status_message` is sparse (e.g., every 5%)
- **Reliability over cleverness**:
  - do not crash the worker on unexpected ffmpeg output lines
  - subprocesses MUST be cleaned up on exceptions

---

## Source of Truth Code Map (Where to Change)

- Conversion orchestration: `apps/api/services/job_manager.py` (`_execute_conversion`)
- Conversion execution + parsing: `apps/api/services/converter_engine.py` (`convert`, `_parse_progress`)
- Conversion route: `apps/api/api/routes/jobs.py` (`POST /jobs/convert`)
- Repair pipeline interactions (post-conversion scan / manifests): `apps/api/services/repair_pipeline.py` (only if needed; avoid scope creep)

---

## Required Output: Structured Conversion Telemetry in `status.meta`

We will standardize conversion telemetry keys (the UI MAY choose not to render these yet, but the API MUST emit them when available):

- `convert_current_ms`: current position processed (ms)
- `convert_total_ms`: total duration (ms)
- `convert_speed_x`: ffmpeg speed multiplier (float, e.g. `42.3`)
- `convert_bitrate_kbps`: ffmpeg bitrate (float) when available; otherwise omitted

**Throttling requirement**:
- Emit telemetry at most **2 times per second** per job.

---

## Implementation Steps (Checkpointed)

### Checkpoint 0 — Baseline understanding

MUST confirm current behavior in code before editing:

- `ConverterEngine.convert()` reads stdout/stderr and calls `progress_callback(percent, line)` for progress lines.
- `JobManager._execute_conversion()` wraps the callback and updates DB status every 5% (currently).

### Checkpoint 1 — Make ffmpeg parsing robust (ConverterEngine)

Change requirements (MUST IMPLEMENT):

- Progress parsing MUST accept variable decimal places in time (e.g. `.4`, `.45`, `.456`).
- Speed/bitrate parsing MUST handle `N/A` safely (do not throw).
- Progress parsing MUST work whether ffmpeg progress appears in stdout or stderr (current implementation parses both; preserve this).

### Checkpoint 2 — Emit structured telemetry without spamming (JobManager)

Change requirements (MUST IMPLEMENT):

- Extend the progress callback path to extract and send telemetry via `status.meta`:
  - percent remains `job.progress_percent`
  - telemetry goes in `status.meta` (keys listed above)
- Enforce throttling (≤2 updates/sec) for meta updates.

### Checkpoint 3 — Reliability gates (atomic output + integrity)

Current `ConverterEngine` already uses a temp dir + atomic moves + ffprobe-based checks.

MUST ensure:

- A failed integrity check results in a failed job (no “COMPLETED” with corrupt output).
- Temp directories are cleaned up (TemporaryDirectory should handle this; verify no leaks).

### Checkpoint 4 — Tests (inside Docker)

We will add deterministic tests without running real conversions:

- Unit tests for progress parsing:
  - variable decimal time
  - missing/`N/A` bitrate and speed
  - malformed lines (must not raise)
- Unit tests for JobManager meta emission throttling (stub converter progress callback).

### Checkpoint 5 — Workflow doc update

Update `docs/workflows/library/conversion_workflow.md` to be “source of truth” (explicit MUST/DO NOT) and include:

- the `status.meta` telemetry keys above
- how conversion progress is computed
- how to validate changes (commands)

---

## Validation Commands (MUST RUN)

Run inside Docker:

- `docker compose -f docker-compose.dev.yml exec -T api python -m compileall -q .`
- `docker compose -f docker-compose.dev.yml exec -T api pytest -q`

Manual validation (dev UI):

- Convert a known-downloaded book and confirm:
  - progress increases smoothly
  - job card shows a single percent
  - conversion telemetry is present using ONE of these methods (MUST DO at least one):
    1) UI renders telemetry (if/when implemented), OR
    2) Inspect the jobs WebSocket `status.meta` payload in the browser devtools Network panel, OR
    3) Query the job record via the API (`GET /jobs/<job_id>`) and confirm `meta` includes `convert_*` keys.

---

## Execution Order + Agent Assignments (MUST FOLLOW)

Agents run in parallel. Evidence MUST be pasted into:

- `docs/workflows/library/conversion_workflow_hardening_status.md`

Assignments:

- **Claude-A (API code)**: ConverterEngine parsing + JobManager meta emission + throttling (production code only in `apps/api`).
- **Gemini-A (Docs)**: Update `docs/workflows/library/conversion_workflow.md` to match the hardened workflow and add explicit validation steps.
- **Codex-A (Tests)**: Add tests in `apps/api/tests` for parsing + meta emission/throttling.
- **Codex-Orchestrator**: Merge, resolve conflicts, run final gates, do manual UI validation.

---

## Definition of Done (Quick Checklist)

- [ ] Conversion behavior unchanged (still uses `core/AAXtoMP3`).
- [ ] Progress parsing robust to time decimals and `N/A` values.
- [ ] `status.meta` includes `convert_*` telemetry (when available) and is throttled.
- [ ] `docker compose -f docker-compose.dev.yml exec -T api pytest -q` passes.
- [ ] `docs/workflows/library/conversion_workflow.md` updated to be explicit “source of truth”.
