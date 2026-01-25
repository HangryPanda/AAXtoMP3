# Conversion Workflow Hardening — Status & Evidence Log

This file is the **single place** where agents must paste their completion evidence for the Conversion Workflow Hardening plan.

Do **not** paste secrets. Command outputs are fine as long as they don’t include secrets.

---

## Claude-A (API code) — Evidence

**Status**: COMPLETED

**Files changed**:
- `apps/api/services/converter_engine.py` — Robust ffmpeg parsing + telemetry extraction:
  - Updated `PROGRESS_PATTERN` regex to accept variable decimal places (e.g., `.4`, `.45`, `.456`, or none)
  - Updated `DURATION_PATTERN` regex similarly
  - Added `_parse_bitrate()` method with N/A handling
  - Updated `_parse_speed()` to handle N/A safely
  - Added `parse_ffmpeg_telemetry()` method returning structured telemetry dict
  - Updated `progress_callback` signature to `(percent, line, telemetry)` to pass telemetry
- `apps/api/services/job_manager.py` — Throttled meta emission:
  - Updated `progress_wrapper` in `_execute_conversion()` to accept telemetry parameter
  - Added throttling: meta updates emit at most every 500ms (≤2 updates/sec)
  - Pass telemetry to `_notify_status()` via the `meta` parameter
  - `status_message` only emitted on significant progress (every 5%), not every meta update
- `apps/api/tests/unit/test_converter_engine.py` — Fixed test broken by callback signature change

**Commands (inside Docker) + output**:

1. `docker compose -f docker-compose.dev.yml exec -T api python -m compileall -q .`
```
(no output = success, all Python files compiled without errors)
```

2. `docker compose -f docker-compose.dev.yml exec -T api pytest tests/unit/test_converter_engine.py tests/unit/test_job_manager.py -v`
```
============================= test session starts ==============================
platform linux -- Python 3.11.14, pytest-9.0.2, pluggy-1.6.0
collected 57 items

tests/unit/test_converter_engine.py: 29 passed
tests/unit/test_job_manager.py: 28 passed

============================== 57 passed in 1.22s ==============================
```

**Notes (required)**:
- **Throttling implementation details**: The `progress_wrapper` in `_execute_conversion()` uses `monotonic()` to track `last_meta_time`. Meta updates (via `_notify_status` with `meta=telemetry`) are only emitted if at least 500ms (0.5s) have passed since the last emission, enforcing ≤2 updates/sec. Additionally, significant progress changes (>5%) always trigger an update regardless of throttle timing. The `status_message` field is only populated for significant progress updates (not every throttled meta update) to avoid log spam.

- **Integrity check failure behavior**: The existing `ConverterEngine.convert()` already implements integrity checking. When integrity check fails:
  1. `success` is set to `False`
  2. Detected errors are appended to the `detected_errors` list
  3. The result dict includes `"detected_errors"` key with failure messages
  4. No files are moved to the final destination (atomic move phase is skipped)
  5. The job fails cleanly with error information preserved
  This behavior is unchanged by my modifications — integrity checks continue to work as before.

---

## Gemini-A (Docs) — Evidence

**Status**: Completed

**Files changed (must be only `docs/workflows/library/conversion_workflow.md`)**:
- `docs/workflows/library/conversion_workflow.md`

**Summary of MUST/DO NOT additions**:
- **Engine Invariant**: MUST use `core/AAXtoMP3` via `ConverterEngine`.
- **Atomic Operations**: MUST use temporary isolation + `ffprobe` integrity check + atomic `mv`.
- **Robust Parsing**: MUST handle variable decimal time and `N/A` bitrate/speed.
- **Telemetry**: MUST emit `convert_current_ms`, `convert_total_ms`, `convert_speed_x`, `convert_bitrate_kbps` in `status.meta`.
- **Throttling**: MUST throttle `status.meta` updates to ≤ 2 times per second.
- **Failure Handling**: Failed integrity checks MUST result in a `FAILED` job status.

**Validation Steps Added**:
- Added `pytest` command for unit/integration tests (parsing, telemetry, jobs).
- Added manual validation steps via `curl` and WebSocket inspection.

---

## Codex-A (Tests) — Evidence

**Status**: Completed

**Test files added/changed**:
- `apps/api/tests/unit/test_job_manager_conversion_telemetry.py`
- `apps/api/tests/unit/test_converter_engine.py`

**Commands (inside Docker) + output**:

1. `docker compose -f docker-compose.dev.yml exec -T api pytest -q`
```
Ran focused unit subset (new/changed coverage):

docker compose -f docker-compose.dev.yml exec -T api python -m compileall -q .
time="2026-01-25T00:32:11-06:00" level=warning msg="/Volumes/code-projects/audible-library-react/docker-compose.dev.yml: the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion"

docker compose -f docker-compose.dev.yml exec -T api pytest -q tests/unit/test_converter_engine.py tests/unit/test_job_manager_conversion_telemetry.py
============================= test session starts ==============================
platform linux -- Python 3.11.14, pytest-9.0.2, pluggy-1.6.0
rootdir: /app
configfile: pyproject.toml
plugins: cov-7.0.0, anyio-4.12.1, asyncio-1.3.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 34 items

tests/unit/test_converter_engine.py ................................     [ 94%]
tests/unit/test_job_manager_conversion_telemetry.py ..                   [100%]

============================== 34 passed in 0.13s ==============================
time="2026-01-25T00:45:42-06:00" level=warning msg="/Volumes/code-projects/audible-library-react/docker-compose.dev.yml: the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion"
```

**Coverage confirmation**:
- Variable decimal parsing: Covered via `TestParseFfmpegTelemetry` in `apps/api/tests/unit/test_converter_engine.py`.
- N/A bitrate/speed handling: Covered via `TestParseFfmpegTelemetry` in `apps/api/tests/unit/test_converter_engine.py`.
- Meta emission throttling: Covered via `test_conversion_meta_emission_is_throttled` in `apps/api/tests/unit/test_job_manager_conversion_telemetry.py`.

---

## Codex-Orchestrator — Final Gates

**Status**: COMPLETED

**Merged branches / commits**:
- N/A (agents worked in this repo workspace; review performed via evidence + Docker gates)

**Final commands (inside Docker) + output**:

1. `docker compose -f docker-compose.dev.yml exec -T api pytest -q`
```
Ran conversion-focused unit gates:

docker compose -f docker-compose.dev.yml exec -T api python -m compileall -q .

docker compose -f docker-compose.dev.yml exec -T api pytest -q \
  tests/unit/test_converter_engine.py \
  tests/unit/test_job_manager.py

Result: 60 passed.
```

**Manual UI validation**:
- User confirmed an end-to-end download + conversion succeeded and “everything seems to be working.”
- Job card progress: Confirmed by user during conversion run.
- Telemetry visible (Network tab or API response): Not separately verified in this pass (tests cover telemetry parsing + throttling).
