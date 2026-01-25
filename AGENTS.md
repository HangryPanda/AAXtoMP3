# Repository Guidelines

## Project Structure & Module Organization

- `apps/web/`: primary frontend (Next.js + React + TypeScript). User-facing library, jobs, player, and settings UI.
- `apps/api/`: primary backend (FastAPI + SQLModel + Alembic + PostgreSQL). Owns library sync, download/convert jobs, WebSockets, and streaming endpoints.
- `core/`: conversion engine scripts (`AAXtoMP3`, `interactiveAAXtoMP3`) invoked by the API (mounted read-only in Docker).
- `docker/`: nginx reverse proxy config + container entrypoints.
- `docs/`: project documentation and notes.
- `data/`: local dev bind-mount dirs for downloads/converted/completed/postgres (gitignored; may contain secrets).
- `docker-compose.yml`: local “prod-like” stack (Postgres + API + Web + nginx).
- `docker-compose.dev.yml`: local dev stack with hot reload (API `uvicorn --reload`, Next.js `npm run dev`).
- `*.sh`, `*.py` in repo root: legacy/auxiliary utilities (library sync/metadata, environment setup, file moves).
- `app/`: legacy Streamlit-based GUI (kept for reference; new features should target `apps/web` + `apps/api`).
- `specs/`: legacy/interop manifests used for “repair” and backfill (`library_cache.json`, `download_manifest.json`, `converted_manifest.json`).
- Generated/working data (not source): `AAX/`, `Audiobooks/`, `MP3/`, `M4B/`, `Covers/`, `Chapters/`, `Metadata/`, `Vouchers/`, `LibraryData/`, `tmp/`, and Docker volumes (`postgres-data*`).

## Product Objective (Important)

This app is an **Audible Library Manager** with *feature parity* to the legacy Streamlit GUI:
- Show what exists in the Audible cloud vs what’s downloaded locally vs what’s converted (and playable).
- Support batch download and batch conversion.
- Provide job monitoring (queue/pending/running/completed) + logs + cancellation.
- Stream/play converted audiobooks from the web UI.

### Repair Pipeline (Truth From Disk)
Stats like “Downloaded” and “Converted” are **not** just DB counters. They should be derived from:
- Manifests in `specs/` (legacy) and/or the filesystem (bind-mounted media dirs in Docker).
- Normalization of mixed host/container path formats.

Repair also generates a duplicates report TSV for manual cleanup:
- `${converted_dir}/.repair_reports/repair_*_duplicates.tsv` (columns: `asin | keep_or_delete | output_path | imported_at | reason`)
- The repair workflow **does not delete** files automatically; it only reports `DELETE_CANDIDATE`s.

Repair behavior is controlled by Settings (stored in DB and editable in the Web UI):
- `repair_extract_metadata` (default: true) - extract chapters/metadata from converted M4B files during repair.
- `repair_update_manifests` (default: true) - update manifests from filesystem scan during repair.
- `repair_delete_duplicates` (default: false) - reserved for future automation; duplicates are currently reported only.
- `move_files_policy` (`report_only` | `always_move` | `ask_each`) - policy for misplaced files.

Key endpoints:
- `GET /library/repair/preview` (counts: downloaded/converted/orphans/missing files)
- `POST /library/repair/apply` (queues a `REPAIR` job to update DB + insert local-only items)
- `GET /library/local` and `GET /stream/local/{local_id}` for “local-only” (delisted/orphan) items.

## Build, Test, and Development Commands

### Full stack (recommended)
- `docker compose up --build`: start Postgres + API + Web + nginx (ports: `3000`, `8000`, `80`, `5432`).
- `docker compose -f docker-compose.dev.yml up --build`: dev mode w/ hot reload (web at `http://localhost:3000`, API at `http://localhost:8000`).
- `docker compose down`: stop services.
- `docker compose logs -f api` / `docker compose logs -f web`: follow logs.

### API (FastAPI)
- `cd apps/api && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- `cd apps/api && uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- Recommended (avoids PATH/Python confusion): `cd apps/api && ./run_dev.sh`
- Restart helper (stops only this API + waits for `/health`): `bash apps/api/restart_api.sh`
- `cd apps/api && pytest`
- Use the venv explicitly to avoid the “wrong python” problem: `cd apps/api && source .venv_test/bin/activate && python -m pytest`
- `cd apps/api && ruff check . && mypy .`
- Migrations: `cd apps/api && alembic upgrade head`
  - If you add/change DB models or Settings fields, create an Alembic migration.

### Web (Next.js)
- `cd apps/web && npm ci`
- `cd apps/web && npm run dev`
- `cd apps/web && npm run lint`
- `cd apps/web && npm test` (Vitest)
- `cd apps/web && npm run test:e2e` (Playwright)

If your repo lives on a network filesystem and Next.js fails with `.next/` persistence or `ENOTEMPTY` errors, run with a local dist dir:
- `cd apps/web && rm -rf .next && NEXT_DIST_DIR=/tmp/audible-library-web-next npm run dev`

### Core engine (CLI)
- `bash core/AAXtoMP3 -A <AUTHCODE> <file.aax>`: convert a book using your Audible authcode.
- `bash core/interactiveAAXtoMP3`: guided conversion flow.
- `bash core/AAXtoMP3 -V -A <AUTHCODE> *.aax`: validate downloads without producing output (useful “smoke test”).

## Coding Style & Naming Conventions

- Bash: keep compatibility with Bash 3.2 (macOS default); prefer 2-space indentation; quote variables; avoid associative arrays.
- Python (API): 4-space indentation; type hints required; keep `mypy --strict` passing; format/style via `ruff` settings in `apps/api/pyproject.toml`.
- TypeScript (Web): strict TypeScript; avoid `any`; validate API shapes (prefer `zod`); keep lint and tests green.
- Naming: new scripts use `snake_case.py` / `snake_case.sh`; keep user-facing flags stable and documented in `README.md`.

## Testing Guidelines

- API: add/maintain `pytest` coverage for new routes/services; run `pytest` before shipping.
- Web: add/maintain unit tests (Vitest) for hooks/components; use Playwright for critical flows.
- Core conversion changes: validate with `bash core/AAXtoMP3 -V -A <AUTHCODE> <file.aax>` and one end-to-end conversion.
- End-to-end: run the dev or prod-like compose stack and verify a single sync/download → validate → convert → stream/play cycle.

## Commit & Pull Request Guidelines

- Commit history commonly uses Conventional Commit-style prefixes (e.g., `feat: ...`, `fix: ...`) with short, imperative subjects.
- PRs should include: what changed, how you validated (exact commands + OS), and any user-visible behavior changes.
- Do not commit secrets or local config: `.authcode`, `apps/api/.env`, `apps/web/.env*`, and `~/.audible/*`.

## Custom audible-cli Fork

This project uses a **custom fork** of audible-cli with additional features:
- `--progress-format ndjson` for structured progress events (used by the download job manager)
- Filename sanitization to replace problematic characters (`/`, `\`, `:`, etc.) in titles

**Repository:** `git+https://github.com/HangryPanda/audible-cli.git@feature/machine-readable-progress`

**Important:** After rebuilding the API Docker container, the custom fork must be reinstalled manually:
```bash
# Install git if not present
docker exec audible-api-dev apt-get update && docker exec audible-api-dev apt-get install -y git

# Install custom audible-cli
docker exec audible-api-dev pip install --force-reinstall git+https://github.com/HangryPanda/audible-cli.git@feature/machine-readable-progress
```

**Verification:**
```bash
docker exec audible-api-dev audible download --help | grep "progress-format"
# Should show: --progress-format [tqdm|json|ndjson]
```

The `AUDIBLE_CLI_PROGRESS_FORMAT: ndjson` env var in `docker-compose.dev.yml` requires this custom fork. If you see errors like `No such option: --progress-format`, the custom fork needs to be reinstalled.

## Security & Configuration Tips

- `--{dir,file,chapter}-naming-scheme` strings can evaluate shell command substitutions; treat untrusted input as code.
- Never `eval` user-provided strings. When the API invokes `core/AAXtoMP3`, pass arguments as an array and validate/escape any naming-scheme inputs.
- Avoid logging secrets (auth, cookies, tokens). Treat `~/.audible/*` as sensitive.
- Treat `data/` as sensitive; it may contain local tokens/cookies/keys and should remain untracked.
- Debug-only endpoints and any “raw Audible payload” views must stay behind `DEBUG=true`.
