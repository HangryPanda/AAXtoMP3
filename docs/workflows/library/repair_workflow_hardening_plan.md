# Plan: Repair Workflow Hardening (Truth From Disk)

This document is the **implementation plan and handoff checklist** for hardening the Repair workflow.

Repair is the pipeline that reconciles:

- the PostgreSQL DB state,
- legacy manifests (interop),
- and the **actual filesystem state** (bind-mounted media directories).

**Scope (this plan)**: make Repair behavior explicit, stable, testable, and aligned with product invariants (“Truth From Disk”).

---

## READ FIRST: Execution + Assignments (MUST FOLLOW)

### Agents MUST follow this exact structure

1. **Read this plan before making changes.**
2. **Work only within your assigned scope below.**
3. **Paste evidence into the single evidence log file:**
   - `docs/workflows/library/repair_workflow_hardening_status.md`
4. If you started work without an assignment, **STOP** and ask the orchestrator for clarification. Do not “guess” tasks.

### Assignments (authoritative)

- **Claude-A (API code)**:
  - Allowed to modify production code only in `apps/api`.
  - Owns: repair pipeline correctness (settings enforcement, path normalization, duplicates TSV generation).
- **Gemini-A (Docs)**:
  - Allowed to modify only `docs/workflows/library/repair_workflow.md`.
  - Owns: making the repair workflow doc explicit “source of truth” + validation steps.
- **Codex-A (Tests)**:
  - Allowed to modify only `apps/api/tests`.
  - Owns: preview/apply/report/local-only tests using temp dirs (no real media).
- **Codex-Orchestrator**:
  - Merges changes, resolves conflicts, runs final Docker gates, and performs manual validation.

---

## Data Flow (Mental Model)

1. **UI** triggers Repair preview:
   - `GET /library/repair/preview`
   - returns counts (downloaded/converted/orphans/missing) derived from manifests + filesystem scan
2. **UI** applies Repair:
   - `POST /library/repair/apply`
   - queues a single `REPAIR` job
3. **JobManager** runs Repair (async):
   - scans filesystem under configured dirs
   - normalizes mixed host/container paths
   - updates manifests (if enabled)
   - updates DB Book paths/statuses
   - inserts “local-only” items when converted files exist but no Book row exists
   - generates duplicates report TSV (non-destructive; no deletion)
4. **UI** displays results and provides access to local-only items and duplicates report path.

---

## Non-Negotiables (MUST FOLLOW)

- **Truth From Disk**:
  - “Downloaded” and “Converted” counts MUST be derived from filesystem/manifests, not only DB counters.
- **Non-destructive**:
  - Repair MUST NOT delete files automatically.
  - Duplicates are reported as `DELETE_CANDIDATE` only.
- **Path normalization MUST be robust**:
  - Must handle Windows/macOS/Linux host paths and container paths.
  - Must normalize legacy manifests (mixed formats) into consistent container-resolvable paths.
- **Settings govern Repair behavior** (stored in DB and editable via Web UI):
  - `repair_extract_metadata` (default true)
  - `repair_update_manifests` (default true)
  - `repair_delete_duplicates` (default false; RESERVED; DO NOT IMPLEMENT DELETION)
  - `move_files_policy` (`report_only` | `always_move` | `ask_each`)
- **Duplicates report location is stable**:
  - `${converted_dir}/.repair_reports/repair_*_duplicates.tsv`
- **Container-first validation**:
  - All tests/validation MUST run inside Docker.
- **No secrets in logs**:
  - Do not log auth tokens/cookies; treat `~/.audible/*` and `data/` as sensitive.

---

## Source of Truth Code Map (Where to Change)

- Repair pipeline: `apps/api/services/repair_pipeline.py`
- Repair job execution: `apps/api/services/job_manager.py` (`_execute_repair`)
- Repair routes:
  - `apps/api/api/routes/library.py` (`GET /library/repair/preview`, `POST /library/repair/apply`)
- Local-only items endpoints:
  - `GET /library/local`
  - `GET /stream/local/{local_id}`

---

## Implementation Steps (Checkpointed)

### Checkpoint 0 — Align documentation with actual behavior

MUST update `docs/workflows/library/repair_workflow.md` to match the invariants above and the real endpoints/settings.

This includes:

- explicit “Truth From Disk” rules
- explicit statement that repair is non-destructive
- duplicates report TSV format and location
- exact endpoints and what they return
- how manifests and filesystem scan are used

### Checkpoint 1 — Verify settings are the only behavior switches

MUST ensure Repair behavior toggles only via the settings listed above.

DO NOT:

- introduce new flags without updating docs + DB settings migrations
- implement delete automation (reserved)

### Checkpoint 2 — Path normalization hardening

MUST ensure path normalization supports:

- `C:\\...` style
- `/Users/...` style
- `/data/...` container style

MUST be idempotent:

- normalizing an already-normal path does not change it

### Checkpoint 3 — Duplicates report correctness

MUST ensure the report is generated consistently with columns:

- `asin | keep_or_delete | output_path | imported_at | reason`

MUST:

- mark duplicates as `DELETE_CANDIDATE` only
- include a stable reason string explaining why it’s considered duplicate

### Checkpoint 4 — Tests (inside Docker)

MUST add tests that do not require real media files:

- use a temp directory tree to simulate downloads/converted/completed
- write small dummy files with expected naming patterns
- verify:
  - preview counts reflect filesystem
  - apply updates DB paths/status
  - local-only items are inserted when needed
  - duplicates report is created at the correct path with correct columns
  - no deletion happens

### Checkpoint 5 — Manual validation

MUST validate in the dev stack:

- run preview and confirm counts match the filesystem
- apply repair and confirm:
  - job completes
  - duplicates TSV exists
  - local-only item playback endpoint works for at least one item (if present)

---

## Validation Commands (MUST RUN)

Inside Docker:

- `docker compose -f docker-compose.dev.yml exec -T api python -m compileall -q .`
- `docker compose -f docker-compose.dev.yml exec -T api pytest -q`

Manual API checks (MUST RUN; inside Docker)

These commands call the running FastAPI inside the `api` container at `http://127.0.0.1:8000`.

1) Preview:

- `docker compose -f docker-compose.dev.yml exec -T api python - <<'PY'\nimport httpx\nr=httpx.get('http://127.0.0.1:8000/library/repair/preview', timeout=60.0)\nprint('status:', r.status_code)\nr.raise_for_status()\nprint(r.json())\nPY`

2) Apply (queues a REPAIR job):

- `docker compose -f docker-compose.dev.yml exec -T api python - <<'PY'\nimport httpx\nr=httpx.post('http://127.0.0.1:8000/library/repair/apply', timeout=60.0)\nprint('status:', r.status_code)\nr.raise_for_status()\nprint(r.json())\nPY`

3) Confirm job completion:

- Use the UI Jobs view OR poll the jobs API until the REPAIR job reaches `COMPLETED/FAILED`.
- If polling via API, use:
  - `GET /jobs?task_type=REPAIR` and check the most recent job’s status.

---

## Execution Order + Agent Assignments (MUST FOLLOW)

Evidence MUST be pasted into:

- `docs/workflows/library/repair_workflow_hardening_status.md`

Assignments:

- **Claude-A (API code)**: repair pipeline correctness (settings/path normalization/report generation) in `apps/api` only.
- **Gemini-A (Docs)**: update `docs/workflows/library/repair_workflow.md` to be explicit source of truth.
- **Codex-A (Tests)**: add tests under `apps/api/tests` covering preview/apply/report/local-only behaviors.
- **Codex-Orchestrator**: merge, final gates, manual validation.

---

## Definition of Done (Quick Checklist)

- [ ] `docs/workflows/library/repair_workflow.md` is explicit and matches current behavior.
- [ ] Preview/apply endpoints match Truth From Disk invariants.
- [ ] Path normalization is robust and idempotent.
- [ ] Duplicates TSV generated at `${converted_dir}/.repair_reports/repair_*_duplicates.tsv` with required columns.
- [ ] No deletion occurs (ever) during Repair.
- [ ] `docker compose -f docker-compose.dev.yml exec -T api pytest -q` passes.
