# Repair Workflow Hardening — Status & Evidence Log

This file is the **single place** where agents must paste their completion evidence for the repair workflow hardening plan.

Do **not** paste secrets.

---

## Claude-A (API code) — Evidence

**Status**: COMPLETED

**Files changed**:
- `apps/api/services/repair_pipeline.py` — Settings enforcement + path normalization + system file filtering:
  - Added `_normalize_path_separators()` helper to convert Windows backslashes to forward slashes
  - Rewrote `_map_path_to_runtime()` to support:
    - Windows paths (`C:\Users\...\Downloads`, `D:\Media\Audiobooks\...`)
    - macOS paths (`/Volumes/...`, `/Users/...`)
    - Linux paths (`/home/...`, `/mnt/...`)
    - Legacy container roots (`/downloads`, `/converted`, `/completed`)
    - Idempotency check: already-normalized paths are returned unchanged
    - Generic pattern matching for directory segments (`downloads`, `converted`, `completed`)
  - Moved DB settings fetch earlier in `apply_repair()` to check `repair_update_manifests` before manifest modifications
  - Gated manifest update sections (A, B, C, D) with `repair_update_manifests` setting check
  - Removed redundant DB settings query later in the function (reuse already-fetched variable)
  - Added `_should_skip_path()` helper for filtering system files during scanning:
    - Skips AppleDouble files (starting with `._`)
    - Skips `.DS_Store` and `Thumbs.db`
    - Skips files inside hidden directories (parents starting with `.`)
  - Updated all scanning functions to use `_should_skip_path()`:
    - `_build_download_file_index()`: filters during ASIN indexing
    - `_scan_converted_m4b()`: filters M4B file list
    - `_scan_m4b_with_asin()`: skips system files before metadata extraction
    - `_detect_misplaced_files()`: filters both converted and downloads scans

**Commands (inside Docker) + output**:

1. `docker compose -f docker-compose.dev.yml exec -T api python -m compileall -q .`
```
(no output = success, all Python files compiled without errors)
```

2. `docker compose -f docker-compose.dev.yml exec -T api pytest -v tests/unit/test_repair_dry_run.py tests/integration/test_repair_workflow.py tests/integration/test_repair_hardening.py`
```
============================= test session starts ==============================
platform linux -- Python 3.11.14, pytest-9.0.2, pluggy-1.6.0
collected 11 items

tests/unit/test_repair_dry_run.py::test_dry_run_no_data PASSED
tests/unit/test_repair_dry_run.py::test_dry_run_orphan_conversion PASSED
tests/unit/test_repair_dry_run.py::test_dry_run_book_update_needed PASSED
tests/unit/test_repair_dry_run.py::test_dry_run_legacy_path_normalization PASSED
tests/integration/test_repair_workflow.py::test_repair_updates_book_status_from_filesystem PASSED
tests/integration/test_repair_workflow.py::test_repair_scans_m4b_and_updates_manifest PASSED
tests/integration/test_repair_workflow.py::test_library_manager_scan_book_populates_metadata PASSED
tests/integration/test_repair_hardening.py::test_map_path_to_runtime_maps_legacy_roots PASSED
tests/integration/test_repair_hardening.py::test_map_path_to_runtime_idempotent_for_runtime_paths PASSED
tests/integration/test_repair_hardening.py::test_compute_preview_counts_from_filesystem_and_manifests PASSED
tests/integration/test_repair_hardening.py::test_apply_repair_inserts_local_only_and_writes_duplicates_report PASSED

============================== 11 passed in 0.54s ==============================
```

**Notes (required)**:

- **Settings that affect Repair and how they're enforced**:
  - `repair_extract_metadata` (default true): Checked at line ~1134 before calling `LibraryManager.scan_book()` for metadata extraction
  - `repair_update_manifests` (default true): Checked at line ~860 before sections A/B/C/D that update `download_manifest.json` and `converted_manifest.json`. When false, manifests are read but never modified.
  - `repair_delete_duplicates` (default false, RESERVED): NOT implemented — duplicates are only reported as `DELETE_CANDIDATE` in the TSV, no deletion ever happens

- **How path normalization handles host/container paths**:
  1. **Idempotency first**: If path already starts with configured runtime dirs (`/data/downloads`, etc.), return unchanged
  2. **Windows normalization**: Backslashes (`\`) converted to forward slashes (`/`) for consistent matching
  3. **Legacy container roots**: `/downloads` → `/data/downloads`, `/converted` → `/data/converted`, `/completed` → `/data/completed`
  4. **Known host patterns**: Explicit mappings for `/Volumes/Media/Audiobooks/...` paths
  5. **Generic segment matching**: Scans path segments for keywords like `downloads`, `converted`, `completed` (case-insensitive) and maps everything after that segment to the runtime directory

- **How duplicates TSV is generated**:
  - **Path**: `${converted_dir}/.repair_reports/repair_{job_id}_{timestamp}_duplicates.tsv`
  - **Columns**: `asin | keep_or_delete | output_path | imported_at | reason`
  - **KEEP entries**: Marked with reason `chosen_by_repair` (best conversion chosen by scoring)
  - **DELETE_CANDIDATE entries**: Marked with reasons like `not_chosen` or `not_chosen_missing_audiobook_dir`
  - **Non-destructive**: No files are ever deleted; report is informational only

- **System file filtering (prevents "Operation not permitted" errors)**:
  - All scanning functions now explicitly skip:
    - AppleDouble files (filenames starting with `._`)
    - macOS `.DS_Store` files
    - Windows `Thumbs.db` files
    - Files inside hidden directories (any parent starting with `.`)
  - **CRITICAL**: `_should_skip_path()` MUST be called BEFORE `is_file()` because `is_file()` itself can trigger "Operation not permitted" on AppleDouble files. The check order is:
    1. `_should_skip_path(p)` — skip system files by name pattern (no filesystem access needed)
    2. `is_file()` — only called after passing the skip check

---

## Gemini-A (Docs) — Evidence

**Status**: Completed

**Files changed**:
- `docs/workflows/library/repair_workflow.md`

**Summary of MUST/DO NOT invariants added**:
- **Scanning & Filtering**: MUST explicitly ignore `._` files (AppleDouble), `.DS_Store`, `Thumbs.db`, and hidden directories to prevent permission errors.
- **Truth From Disk**: Counts and statuses MUST be derived from the filesystem and manifests, not just the DB.
- **Non-Destructive**: Repair MUST NOT delete files automatically; duplicates are reported as `DELETE_CANDIDATE`.
- **Path Normalization**: MUST be idempotent and support Windows, macOS, and Container path formats.
- **Settings-Driven**: Behavior MUST be controlled exclusively via settings.
- **Local-Only Items**: Converted files without `Book` entries MUST be added to the `LocalItem` table.
- **Duplicates Report**: MUST generate a TSV report at `${converted_dir}/.repair_reports/` with specific columns.

**Validation Steps Added**:
- Added exact `httpx` Python scripts for Preview, Apply, and Polling validation to `docs/workflows/library/repair_workflow.md`.

---

## Codex-A (Tests) — Evidence

**Status**: Completed

**Test files added/changed (must be under `apps/api/tests`)**:
- `apps/api/tests/integration/test_repair_hardening.py`

**Commands (inside Docker) + output**:

1. `docker compose -f docker-compose.dev.yml exec -T api pytest -q` (or subset + justification)
```
Ran focused integration subset for the new repair hardening tests:

docker compose -f docker-compose.dev.yml exec -T api python -m compileall -q .
time="2026-01-25T00:55:34-06:00" level=warning msg="/Volumes/code-projects/audible-library-react/docker-compose.dev.yml: the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion"

docker compose -f docker-compose.dev.yml exec -T api pytest -q tests/integration/test_repair_hardening.py
============================= test session starts ==============================
platform linux -- Python 3.11.14, pytest-9.0.2, pluggy-1.6.0
rootdir: /app
configfile: pyproject.toml
plugins: cov-7.0.0, anyio-4.12.1, asyncio-1.3.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 4 items

tests/integration/test_repair_hardening.py ....                          [100%]

============================== 4 passed in 0.37s ===============================
time="2026-01-25T01:36:45-06:00" level=warning msg="/Volumes/code-projects/audible-library-react/docker-compose.dev.yml: the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion"
```

**Coverage confirmation (required)**:
- preview counts from filesystem/manifests: Covered via `test_compute_preview_counts_from_filesystem_and_manifests`.
- apply updates DB + inserts local-only items: Covered via `test_apply_repair_inserts_local_only_and_writes_duplicates_report` (LocalItem insert asserted).
- duplicates TSV path + columns: Covered via the same test (header columns asserted; report in `${converted_dir}/.repair_reports`).
- confirms no deletion: Covered via the same test (duplicate/orphan files asserted to still exist after repair).

---

## Codex-Orchestrator — Final Gates

**Status**: TODO

**Merged branches / commits**:
- TODO

**Final commands (inside Docker) + output**:

1. `docker compose -f docker-compose.dev.yml exec -T api pytest -q`
```
TODO
```

**Manual validation (required)**:
- `GET /library/repair/preview` returns expected counts: TODO
- `POST /library/repair/apply` completes and writes duplicates TSV: TODO
