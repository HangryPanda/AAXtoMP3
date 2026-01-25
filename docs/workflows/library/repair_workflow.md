# Repair & Reconcile Workflow (Source of Truth)

This document is the **source of truth** for the Repair & Reconcile pipeline. This pipeline is responsible for synchronizing the database state with the external manifests and the actual state of the filesystem.

It is written to prevent regressions and ensure architectural consistency. If you change behavior, you **must** update this document and re-run the validation steps at the end.

---

## Data Flow (Mental Model)

1. **UI** triggers a Repair Preview: `GET /library/repair/preview`.
   - Returns counts of items found on disk vs. items in the DB.
2. **UI** applies Repair: `POST /library/repair/apply`.
   - Queues a single `REPAIR` job row.
3. **JobManager** (`apps/api/services/job_manager.py`) orchestrates the `REPAIR` job.
4. **RepairPipeline** (`apps/api/services/repair_pipeline.py`) executes the logic:
   - Scans media directories for actual files.
   - Normalizes paths (handling host/container differences).
   - Reconciles state: Filesystem ↔ Manifests ↔ Database.
5. **On Completion**:
   - Updates `Book` paths and statuses in the DB.
   - Inserts "Local-Only" items for converted files without library entries.
   - Generates a duplicates report TSV.

---

## What This Workflow Guarantees (MUST-FOLLOW)

1. **Truth From Disk**:
   - Counts and statuses MUST be derived from the actual filesystem and manifests, not just existing DB records.
2. **Non-Destructive**:
   - Repair MUST NOT delete any files automatically.
   - Any identified duplicates MUST be reported as `DELETE_CANDIDATE` for manual review.
3. **Scanning & Filtering Rules**:
   - **Ignore System Files**: The scanner MUST explicitly ignore files starting with `._` (AppleDouble), `.DS_Store`, and `Thumbs.db` to prevent `Permission denied` errors on bind mounts.
   - **Ignore Hidden Directories**: The scanner MUST ignore directories starting with `.`.
4. **Path Normalization**:
   - MUST be idempotent (normalizing an already normal path results in no change).
   - MUST support Windows (`C:\`), macOS (`/Users/`), and Linux/Container (`/data/`) path formats.
5. **Settings-Driven**:
   - Behavior MUST be controlled exclusively via settings (e.g., `repair_extract_metadata`, `repair_update_manifests`).
6. **Atomic Metadata**:
   - If a converted file is missing metadata, the pipeline MUST be able to extract it during reconciliation (if enabled).
7. **Local-Only Items**:
   - Converted files found on disk that do not have a matching `Book` entry MUST be added to the `LocalItem` table to remain playable.

---

## Duplicates Reporting

Repair MUST generate a stable duplicates report to identify multiple files for the same ASIN.

- **Location**: `${converted_dir}/.repair_reports/repair_<timestamp>_duplicates.tsv`.
- **Format**: TSV with columns: `asin`, `keep_or_delete`, `output_path`, `imported_at`, `reason`.
- **Requirement**: Mark duplicates as `DELETE_CANDIDATE` only.

---

## End-to-End Execution Details

### 1) Reconciliation Sequence
1. **Manifest → Filesystem**: Verify that every entry in `download_manifest.json` and `converted_manifest.json` points to an existing file.
2. **Filesystem → Manifest**: Backfill missing manifest entries from files found on disk using ASIN extraction or fuzzy title matching.
3. **Manifest → Database**: Update `Book` statuses and paths (e.g., `Book.status` to `DOWNLOADED` or `COMPLETED`).

### 2) Endpoint Contract
- `GET /library/repair/preview`: Returns a summary of findings (counts of missing vs. new items).
- `POST /library/repair/apply`: Queues the background job to perform the updates.

---

## Validation / Testing (MUST RUN Before Shipping)

### 1) API tests (inside dev container)

Run:
```bash
docker compose -f docker-compose.dev.yml exec -T api pytest -q \
  tests/unit/test_repair_pipeline_paths.py \
  tests/integration/test_repair_job.py
```

### 2) Manual validation (MUST RUN)

Use these commands inside the API container to validate the endpoints directly:

**1. Preview (Get Counts):**
```bash
docker compose -f docker-compose.dev.yml exec -T api python - <<'PY'
import httpx
r=httpx.get('http://127.0.0.1:8000/library/repair/preview', timeout=60.0)
print(f"Status: {r.status_code}")
r.raise_for_status()
print(r.json())
PY
```

**2. Apply (Queue Job):**
```bash
docker compose -f docker-compose.dev.yml exec -T api python - <<'PY'
import httpx
r=httpx.post('http://127.0.0.1:8000/library/repair/apply', timeout=60.0)
print(f"Status: {r.status_code}")
r.raise_for_status()
print(r.json())
PY
```

**3. Confirm Completion:**
Poll the jobs API until the `REPAIR` job reaches `COMPLETED` or `FAILED`.
```bash
docker compose -f docker-compose.dev.yml exec -T api python - <<'PY'
import httpx, time
while True:
    r = httpx.get('http://127.0.0.1:8000/jobs?task_type=REPAIR&limit=1')
    job = r.json()[0]
    print(f"Job {job['id']}: {job['status']}")
    if job['status'] in ['COMPLETED', 'FAILED']: break
    time.sleep(2)
PY
```

## Common Failure Modes

1. **Path Mismatch**: Files found on disk are not mapped correctly to container paths, leading to "Missing" reports.
2. **Manifest Corruption**: Malformed JSON in manifests causes the pipeline to abort (MUST be handled gracefully).
3. **DB Locking**: Large library repairs holding transactions too long (MUST use batching where appropriate).