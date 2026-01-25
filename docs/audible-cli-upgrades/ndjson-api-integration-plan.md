# Plan: Integrate `audible-cli` NDJSON Progress into API (Option B)

This document is the **implementation plan and handoff checklist** for integrating the forked `audible-cli` machine-readable progress (`--progress-format ndjson`) into this repo’s FastAPI download workflow.

It is written so work can resume safely after a crash/context loss, or be split across multiple agents.

**Scope**: downloads only (decrypt/conversion can follow the same pattern later).

---

## Summary (What We’re Doing)

We will add an **opt-in feature flag** to the API so it MUST:

1. Run `audible download ... --progress-format ndjson` when enabled.
2. Parse NDJSON events from stdout **line-by-line**.
3. Convert those events into our existing job telemetry:
   - `Job.progress_percent` (bytes-based aggregate)
   - `status.meta.download_bytes_current`
   - `status.meta.download_bytes_total`
   - `status.meta.download_bytes_per_sec`
4. Fall back to the existing tqdm-scrape parser when the flag is off (default), or if NDJSON is unavailable.

This keeps the change safe and reversible while we iterate and later pin the fork.

---

## Current State (Context Snapshot)

1. The running dev `api` container can install the fork temporarily (no `git` in container; install via GitHub ZIP).
2. After the fork fix (re-tested), **stdout is clean NDJSON**:
   - valid ASIN: stdout only JSON lines; logs go to stderr
   - invalid ASIN: stdout emits a structured `download_error` event; human error stays on stderr
3. Temporary install/testing is documented in:
   - `docs/audible-cli-upgrades/temporary-fork-testing.md`
4. Our app currently supports download progress via a tqdm-output parser, and the UI shows MB/s derived from `status.meta`.

---

## Non-Negotiables (MUST FOLLOW)

- **Container-first**: all validation and debugging for this work must run inside Docker:
  - `docker compose -f docker-compose.dev.yml exec -T api ...`
  - Never validate against host Python/venv for these changes.
- **Safe by default**: NDJSON integration must be behind a feature flag and off by default.
- **No regressions**:
  - Batch semantics remain “one `DOWNLOAD` job per request” (1..N ASINs).
  - Global concurrency cap remains enforced (`max_download_concurrent`).
  - Retry must remain backward compatible (legacy `{"asin": ...}` payloads).
- **No log spam**: high-frequency data stays in `status.meta`, not in `status_message`.
- **Parsing must be resilient**:
  - Do not crash the job runner on a malformed line; treat it as “unknown” and continue (but log it).
  - Still mark the job failed when an NDJSON `download_error` arrives.

---

## Feature Flag Design (MUST FOLLOW)

### Environment variables (authoritative)

#### `AUDIBLE_CLI_PROGRESS_FORMAT` (MUST IMPLEMENT)

- Allowed values: `tqdm`, `ndjson`
- Default: `tqdm` (when unset/empty/unknown)
- Required behavior:
  - `tqdm`:
    - DO NOT pass `--progress-format`.
    - Use the existing tqdm-scrape parsing logic (current behavior).
  - `ndjson`:
    - MUST pass `--progress-format ndjson`.
    - MUST parse progress from NDJSON events on stdout (line-by-line JSON).
    - MUST handle `download_error` as a structured failure (job fails cleanly).
    - MUST keep high-frequency updates in `status.meta` (no `status_message` spam).

#### `AUDIBLE_CLI_PROGRESS_STRICT` (OPTIONAL; DO NOT IMPLEMENT NOW)

- Default: `false`
- Intended behavior (future):
  - `true`: fail fast if any non-JSON line appears on stdout in `ndjson` mode.
  - `false`: skip/ignore unparsable lines (but log a warning).

### Where it lives

- MUST load from the existing settings/config module used by `AudibleClient` (do not introduce a parallel config system).
- MUST be read once at process start (or cached) to avoid per-line overhead.

### How to enable in dev (explicit)

This env var must be present when the `api` container starts (setting it only for a one-off `docker compose exec` will not affect the running worker).

Two supported approaches:

1. **Edit** `docker-compose.dev.yml`:
   - Under the `api:` service, add:
     - `environment:`
       - `AUDIBLE_CLI_PROGRESS_FORMAT: ndjson`
   - Restart only the API service:
     - `docker compose -f docker-compose.dev.yml up -d --no-deps --force-recreate api`

2. **Use a one-off override** (no file edits):
   - `AUDIBLE_CLI_PROGRESS_FORMAT=ndjson docker compose -f docker-compose.dev.yml up -d --no-deps --force-recreate api`

---

## NDJSON Contract (Downloads)

We will treat these event types as the contract the API consumes:

- `download_start`
  - MUST include: `asin`, `filename`, `total_bytes`, `resumed`, `timestamp`
- `download_progress`
  - MUST include: `asin`, `filename`, `current_bytes`, `total_bytes`, `bytes_per_sec`, `resumed`, `timestamp`
- `download_complete`
  - MUST include: `asin`, `filename`, `total_bytes`, `success`, `timestamp`
- `download_error`
  - MUST include: `asin`, `success:false`, `error_code`, `message`

Notes:
- API MUST use `current_bytes/total_bytes` as the source of truth for progress.
- API MUST use `bytes_per_sec` directly for throughput when present; if missing, it MUST fall back to the existing delta-based throughput computation.

---

## Implementation Steps (Checkpointed)

### Checkpoint 0 — Preparation

- Create a short-lived test ASIN list (1 valid, 1 invalid) for local dev testing.
- Ensure fork can be installed in container (temporary):
  - see `docs/audible-cli-upgrades/temporary-fork-testing.md`
- Sanity-check the installed `audible` in-container supports NDJSON:
  - `docker compose -f docker-compose.dev.yml exec -T api sh -lc 'audible download -h | grep -n \"progress-format\" || true'`

### Checkpoint 1 — Add the feature flag plumbing

Tasks:
- Add env var read (`AUDIBLE_CLI_PROGRESS_FORMAT`) in API config.
- Make the chosen format accessible to `AudibleClient` (dependency injection or module-level config).

Acceptance:
- API boots with no changes when env var unset.
- Setting `AUDIBLE_CLI_PROGRESS_FORMAT=ndjson` does not crash startup.

### Checkpoint 2 — Add NDJSON runner + parser (download only)

Tasks (in `apps/api/services/audible_client.py` or equivalent):
- When NDJSON mode enabled:
  - add CLI arg: `--progress-format ndjson`
  - stream stdout line-by-line
  - parse JSON per line
  - emit progress callbacks based on `download_progress` events
  - handle `download_error` and `download_complete`
- Keep the existing tqdm parsing path intact for `tqdm` mode.

Acceptance:
- In NDJSON mode:
  - progress updates arrive (bytes increase)
  - invalid ASIN triggers a structured failure path (job fails with meaningful message)
- In default mode (`tqdm`):
  - behavior remains unchanged

### Checkpoint 3 — Wire NDJSON events into JobManager aggregation

Tasks (in `apps/api/services/job_manager.py`):
- Ensure per-ASIN byte state updates use the NDJSON-provided `current_bytes/total_bytes`.
- Aggregate across ASINs for batch jobs:
  - `progress_percent = floor(sum(cur)/sum(total)*100)`
  - set `status.meta.*` for bytes + throughput

Acceptance:
- UI still shows:
  - single percent (job progress)
  - MB/s throughput line (not percent/s)
  - progress increases smoothly for a single ASIN and for batches

### Checkpoint 4 — Tests (inside Docker)

Integration tests (preferred):
- Add tests that simulate NDJSON stream parsing deterministically:
  - if we can’t run real `audible` downloads in CI, use a stub subprocess runner and feed NDJSON lines.

Unit tests:
- Parser unit tests for each event type and malformed lines.

Acceptance:
- `docker compose -f docker-compose.dev.yml exec -T api pytest` passes for the download-related suite.

### Checkpoint 5 — Docs + pinning follow-up

Tasks:
- Update `docs/workflows/library/download_workflow.md` with a new subsection:
  - “Progress Source: tqdm parsing vs NDJSON (feature-flagged)”
  - explicit guidance on when to enable NDJSON
- Add a follow-up task to pin the fork by commit SHA in the image build (separate PR).

Acceptance:
- Docs are explicit enough that a new agent can:
  - enable the flag,
  - validate behavior,
  - and know how to roll back.

### Pinning guidance (be explicit)

Because our `api` image may not have `git` installed, **do not rely on** `pip install git+https://...@<sha>`.

Prefer a deterministic ZIP-by-commit in the Docker build:

- `python -m pip install "https://github.com/HangryPanda/audible-cli/archive/<COMMIT_SHA>.zip"`

This ensures rebuilds get the same code even if the branch moves.

---

## Validation Commands (MUST RUN)

### Install fork temporarily (dev container)

See `docs/audible-cli-upgrades/temporary-fork-testing.md`.

### Run API tests inside container

- `docker compose -f docker-compose.dev.yml exec -T api pytest -q`

### Manual end-to-end validation

1. Enable NDJSON mode (dev):
   - set `AUDIBLE_CLI_PROGRESS_FORMAT=ndjson` in the `api` service env (dev compose), then restart api container.
2. Queue a download job from the UI and confirm:
   - progress increases based on bytes
   - MB/s throughput shows
   - invalid ASIN shows a structured error and does not crash the worker loop
3. Disable the flag and re-test to confirm fallback works.

---

## Rollback Plan

If anything goes wrong:

1. Set `AUDIBLE_CLI_PROGRESS_FORMAT=tqdm` (or unset it).
2. Restart the `api` container.
3. If the container had the fork installed ephemerally and you need the stock image:
   - rebuild/recreate container from image:
   - `docker compose -f docker-compose.dev.yml up -d --build api`

---

## Parallel Work (How Other Agents Can Help)

Assign these roles to parallel agents to speed up implementation:

- **Claude-A (API parsing core)**: Implement NDJSON parsing path in `apps/api/services/audible_client.py` behind `AUDIBLE_CLI_PROGRESS_FORMAT=ndjson`, keeping the existing tqdm path intact.
- **Gemini-A (Docs + dev enablement)**: Update `docs/workflows/library/download_workflow.md` with NDJSON flag + fallback behavior, and add a commented/off-by-default env entry in `docker-compose.dev.yml`.
- **Codex-A (Tests)**: Add parser unit tests and an integration-style test using a stubbed subprocess stdout stream of NDJSON lines (no network calls).
- **Codex-Orchestrator (You / this agent)**: Integrate branches, resolve conflicts, run tests inside Docker, and validate end-to-end in the UI.

### Agent Deliverables (MUST FOLLOW)

Each agent MUST deliver exactly what is listed here, and MUST NOT expand scope.

#### Claude-A Deliverables

- Modify production code only in `apps/api` (no web UI changes).
- Implement NDJSON download parsing behind `AUDIBLE_CLI_PROGRESS_FORMAT=ndjson`.
- Keep the existing tqdm parsing path unchanged.
- Malformed/unknown NDJSON lines MUST NOT crash the worker (log and continue).
- Run and paste results of container-first checks:
  - `docker compose -f docker-compose.dev.yml exec -T api python -m compileall -q .`
  - `docker compose -f docker-compose.dev.yml exec -T api pytest -q` (or a minimal download-related subset with justification)

#### Gemini-A Deliverables

- Modify only:
  - `docs/workflows/library/download_workflow.md`
  - `docker-compose.dev.yml`
- Add `AUDIBLE_CLI_PROGRESS_FORMAT=ndjson` as **commented/off-by-default** in dev compose.
- Use directive language for invariants (MUST/DO NOT); no “should/maybe”.

#### Codex-A Deliverables

- Add tests only under `apps/api/tests`.
- Add parser unit tests covering:
  - `download_start`, `download_progress`, `download_complete`, `download_error`
  - malformed/unknown NDJSON lines (must be handled deterministically)
- Add an integration-style test that feeds a stubbed subprocess stdout stream of NDJSON lines (no network calls).

#### Codex-Orchestrator Deliverables

- Merge changes, resolve conflicts, and run final validations in-container:
  - `docker compose -f docker-compose.dev.yml exec -T api pytest -q`
- Perform manual end-to-end validation in the UI using:
  - valid `1774241404`
  - invalid `0123456789`
- Update docs if any behavior changes during merge.

---

## Execution Order (MUST FOLLOW) - USER INSTSTRUCTIONS

Follow this sequence to minimize conflicts and ensure there is always clear evidence of progress.

1. **Dispatch all agents immediately**:
   - Claude-A, Gemini-A, and Codex-A start in parallel (no waiting on each other).
2. **Each agent completes their scoped work and produces evidence** (see next section).
3. **Codex-Orchestrator merges** the agent changes and resolves conflicts.
4. **Codex-Orchestrator runs final gates** (tests + manual UI validation).
5. **Only after gates pass**, proceed to pinning work (separate follow-up).

Agents MUST NOT start working outside their scoped files, even if blocked. If blocked, they report the blocker and stop.

---

## Agent Evidence (MUST PROVIDE) - AGENT INSTRUCTIONS

Agents must paste the following artifacts into:

- `docs/audible-cli-upgrades/ndjson-api-integration-status.md`

This is the single shared “ground truth” evidence log so the orchestrator can review without relying on chat history.

Agents MAY also paste a short summary in chat, but the status file is required.

### Claude-A Evidence

- List of files changed (paths).
- Output of (run inside Docker):
  - `docker compose -f docker-compose.dev.yml exec -T api python -m compileall -q .`
  - `docker compose -f docker-compose.dev.yml exec -T api pytest -q` (or the smallest relevant subset, with justification)
- One paragraph describing:
  - how malformed NDJSON lines are handled (log + continue; must not crash),
  - how `download_error` maps to job failure.

### Gemini-A Evidence

- List of files changed (must be only `docs/workflows/library/download_workflow.md` and `docker-compose.dev.yml`).
- Confirmation the dev compose env var is **commented/off-by-default**.
- Short summary of new MUST/DO NOT invariants added to the workflow doc.

### Codex-A Evidence

- List of test files added/changed (must be under `apps/api/tests`).
- Output of (run inside Docker):
  - `docker compose -f docker-compose.dev.yml exec -T api pytest -q` (or the smallest relevant subset, with justification)
- Confirmation tests cover:
  - `download_start`, `download_progress`, `download_complete`, `download_error`
  - malformed/unknown line handling (deterministic; no crash)

---

## Definition of Done (Quick Checklist)

Use this as a progress/checkpoint list while implementing Option B.

### Behavior

- [ ] Default behavior unchanged when `AUDIBLE_CLI_PROGRESS_FORMAT` is unset (tqdm mode).
- [ ] When `AUDIBLE_CLI_PROGRESS_FORMAT=ndjson`:
  - [ ] API uses `audible download --progress-format ndjson`.
  - [ ] Download progress updates are driven by NDJSON `current_bytes/total_bytes`.
  - [ ] Invalid ASIN produces a structured failure (job fails cleanly, no worker crash).
  - [ ] Logs do not spam `status_message`; high-frequency data stays in `status.meta`.

### Data contract / parsing

- [ ] NDJSON parsing is line-by-line and resilient (malformed lines do not crash the runner).
- [ ] `download_error` events are handled explicitly and mapped to job failure reasons.
- [ ] Throughput uses NDJSON `bytes_per_sec` when present (fallback to delta computation otherwise).

### UI impact (manual confirmation)

- [ ] Job card shows a single percent (job progress) and the MB/s throughput line.
- [ ] Batch downloads still show weighted-by-bytes progress (not count-based).

### Tests (inside Docker)

- [ ] `docker compose -f docker-compose.dev.yml exec -T api pytest -q` passes for download-related tests.
- [ ] Added/updated parser unit tests for:
  - [ ] `download_start`
  - [ ] `download_progress`
  - [ ] `download_complete`
  - [ ] `download_error`

### Docs / reproducibility

- [ ] `docs/workflows/library/download_workflow.md` documents the NDJSON feature flag and fallback behavior.
- [ ] Follow-up task created to pin the fork in the image build by commit SHA ZIP (not a moving branch).

---

## Shared Manual Test Inputs (For All Agents)

Do **not** copy/export secrets. Use the auth already present **inside the `api` container**.

### Profile / auth (secure usage)

- Use the existing configured profile in-container (currently `jc4369@gmail.com`).
- Do not print the contents of `~/.audible/audibleAuth`.

Safe checks:
- `docker compose -f docker-compose.dev.yml exec -T api audible manage profile list`
- `docker compose -f docker-compose.dev.yml exec -T api sh -lc 'ls -la ~/.audible && ls -la ~/.audible/audibleAuth ~/.audible/config.toml'`

### ASINs

- Valid: `1774241404` (Title: `Blood Moon`, Subtitle: `Painting the Mists, Book 2`)
- Invalid: `0123456789`
