# Repair Workflow Hardening — Status & Evidence Log

This file is the **single place** where agents must paste their completion evidence for the repair workflow hardening plan.

Do **not** paste secrets.

---

## Claude-A (API code) — Evidence

**Status**: TODO

**Files changed**:
- TODO

**Commands (inside Docker) + output**:

1. `docker compose -f docker-compose.dev.yml exec -T api python -m compileall -q .`
```
TODO
```

2. `docker compose -f docker-compose.dev.yml exec -T api pytest -q` (or subset + justification)
```
TODO
```

**Notes (required)**:
- Which settings affect Repair and how they’re enforced: TODO
- How path normalization handles host/container paths: TODO
- How duplicates TSV is generated (path + columns): TODO

---

## Gemini-A (Docs) — Evidence

**Status**: Completed

**Files changed**:
- `docs/workflows/library/repair_workflow.md`

**Summary of MUST/DO NOT invariants added**:
- **Truth From Disk**: Counts and statuses MUST be derived from the filesystem and manifests, not just the DB.
- **Non-Destructive**: Repair MUST NOT delete files automatically; duplicates are reported as `DELETE_CANDIDATE`.
- **Path Normalization**: MUST be idempotent and support Windows, macOS, and Container path formats.
- **Settings-Driven**: Behavior MUST be controlled exclusively via settings.
- **Local-Only Items**: Converted files without `Book` entries MUST be added to the `LocalItem` table.
- **Duplicates Report**: MUST generate a TSV report at `${converted_dir}/.repair_reports/` with specific columns.

---

## Codex-A (Tests) — Evidence

**Status**: TODO

**Test files added/changed (must be under `apps/api/tests`)**:
- TODO

**Commands (inside Docker) + output**:

1. `docker compose -f docker-compose.dev.yml exec -T api pytest -q` (or subset + justification)
```
TODO
```

**Coverage confirmation (required)**:
- preview counts from filesystem/manifests: TODO
- apply updates DB + inserts local-only items: TODO
- duplicates TSV path + columns: TODO
- confirms no deletion: TODO

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

