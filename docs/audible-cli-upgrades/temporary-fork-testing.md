# Temporary Testing: Forked `audible-cli` in the Docker API Container

This document describes the **temporary (ephemeral)** way to install and test a forked `audible-cli` inside the running Docker **API** container.

This is intended for quick validation **without** committing/pinning the fork in the repo yet.

## Non-Negotiables (MUST FOLLOW)

- **Do not install on the host venv.** Always run these steps inside the running Docker container via `docker compose ... exec api ...`.
- This is **temporary**:
  - The install is lost when the container image is rebuilt (e.g. `docker compose up --build`, `docker compose build`, etc.).
  - If the container is recreated from the image, it reverts to the image’s packaged `audible-cli`.
- The `api` container image may **not** include `git`, so `pip install git+https://...` will fail. Use the GitHub ZIP install method below.

## Goal

Validate that the fork provides **machine-readable progress** via:

- `audible download --progress-format ndjson`
- (optionally) `audible decrypt --progress-format ndjson` if/when available in the installed fork

## Install the Fork (Option A)

Install into the running dev container (dev compose):

1. Confirm you’re in the repo root and the container is running:
   - `docker compose -f docker-compose.dev.yml ps`

2. Install the fork via GitHub ZIP (works without `git` in the container):
   - `docker compose -f docker-compose.dev.yml exec -T api python -m pip install --force-reinstall --no-deps "https://github.com/HangryPanda/audible-cli/archive/refs/heads/feature/machine-readable-progress.zip"`

Notes:
- We use `--force-reinstall` because the fork currently reports the same version string as upstream (e.g. `0.3.3`), and pip may otherwise keep the old code.
- We use `--no-deps` because the container already has the deps installed via the image build.

## Verify the Fork Is Active

1. Check the `audible` binary is the container’s binary:
   - `docker compose -f docker-compose.dev.yml exec -T api sh -lc 'which audible && audible --version'`

2. Confirm `--progress-format` exists:
   - `docker compose -f docker-compose.dev.yml exec -T api sh -lc 'audible download -h | grep -n \"progress-format\" || true'`

Expected: a line like `--progress-format [tqdm|json|ndjson]`.

## Manual Smoke Test (NDJSON)

Run a single download in NDJSON mode (example only; use a real ASIN and profile):

- `docker compose -f docker-compose.dev.yml exec -T api sh -lc 'audible -P \"$AUDIBLE_PROFILE\" download --asin \"$ASIN\" --aaxc --no-confirm --output-dir /data/downloads --progress-format ndjson'`

### IMPORTANT: Validate stdout/stderr separation

Example test values (replace with your own if needed):

- `ASIN=B0BKR654B3`
- Title: `Mastering Magic: Jeff the Game Master, Book 3 (Unabridged)`

For our API to parse NDJSON reliably:

- **stdout MUST contain only NDJSON events** (one JSON object per line)
- **stderr MUST contain all human logs / warnings / tqdm**

Capture and inspect:

- `docker compose -f docker-compose.dev.yml exec -T api sh -lc 'audible -P \"$AUDIBLE_PROFILE\" download --asin \"$ASIN\" --aaxc --no-confirm --output-dir /data/downloads --progress-format ndjson 1>/tmp/audible.ndjson 2>/tmp/audible.stderr; head -n 20 /tmp/audible.ndjson; echo \"---\"; tail -n 50 /tmp/audible.stderr'`

If non-JSON strings appear in `/tmp/audible.ndjson`, then NDJSON mode is **not safe to consume directly** yet, and we must either:
- fix the fork to keep stdout clean, or
- make the API parser tolerant (skip non-JSON lines) before enabling NDJSON in production.

#### Validate “every line is JSON” (no `jq` required)

The `api` container may not have `jq` installed. This validator runs with Python:

- `docker compose -f docker-compose.dev.yml exec -T api python - <<'PY'\nimport json\nfrom pathlib import Path\np=Path('/tmp/audible.ndjson')\nlines=p.read_text(encoding='utf-8',errors='replace').splitlines() if p.exists() else []\nbad=[]\nfor i,l in enumerate(lines,1):\n    l=l.strip()\n    if not l:\n        continue\n    try:\n        json.loads(l)\n    except Exception as e:\n        bad.append((i,l[:200],str(e)))\nprint('total_lines:', len(lines))\nprint('json_ok:', len(bad)==0)\nfor i,s,e in bad[:10]:\n    print(f'bad line {i}: {s!r} -> {e}')\nPY`

## Current Observations (Container Test)

As of the in-container test run on **January 25, 2026**, we observed **two states**:

### Before fork fix (earlier test)

- `Voucher file saved to ...` printed to stdout before the NDJSON events.
- Invalid ASIN errors printed plain text to stdout (e.g. `error: Asin ... not found in library.`) instead of emitting a structured `download_error` event.

### After fork fix (re-tested)

- **Valid ASIN**: stdout contained **only JSON lines**; non-JSON messages were redirected to **stderr**.
- **Invalid ASIN**: stdout contained a structured `download_error` JSON event; the human error message printed to **stderr**.

This means NDJSON mode is now **safe to parse** line-by-line from stdout for download progress/error events.

## Rollback (Back to Image `audible-cli`)

There is no clean “uninstall back to image version” without rebuilding/recreating the container from the image. Fastest reset:

- `docker compose -f docker-compose.dev.yml up -d --build api`

## TODO (Option B): Feature-Flag the API to Prefer NDJSON

**Not implemented yet.** When we’re ready, add an env flag so FastAPI can prefer NDJSON output (and fall back to the current tqdm scraping parser):

- Example env: `AUDIBLE_CLI_PROGRESS_FORMAT=ndjson`
- Behavior:
  - If the installed `audible` supports `--progress-format`, run with ndjson and parse events.
  - Otherwise fall back to the existing tqdm parsing.
  - MUST be container-first (never host venv).
