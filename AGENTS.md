# Repository Guidelines

## Project Structure & Module Organization

- `apps/web/`: primary frontend (Next.js + React + TypeScript). User-facing library, jobs, player, and settings UI.
- `apps/api/`: primary backend (FastAPI + SQLModel + Alembic + PostgreSQL). Owns library sync, download/convert jobs, WebSockets, and streaming endpoints.
- `core/`: conversion engine scripts (`AAXtoMP3`, `interactiveAAXtoMP3`) invoked by the API (mounted read-only in Docker).
- `docker/`: nginx reverse proxy config + container entrypoints.
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

### Web (Next.js)
- `cd apps/web && npm ci`
- `cd apps/web && npm run dev`
- `cd apps/web && npm run lint`
- `cd apps/web && npm test` (Vitest)
- `cd apps/web && npm run test:e2e` (Playwright)

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

## Security & Configuration Tips

- `--{dir,file,chapter}-naming-scheme` strings can evaluate shell command substitutions; treat untrusted input as code.
- Never `eval` user-provided strings. When the API invokes `core/AAXtoMP3`, pass arguments as an array and validate/escape any naming-scheme inputs.
- Avoid logging secrets (auth, cookies, tokens). Treat `~/.audible/*` as sensitive.
- Debug-only endpoints and any “raw Audible payload” views must stay behind `DEBUG=true`.
