# ProgressPopover UX Review (apps/web)

## Why this component matters
The ProgressPopover is the user’s “at-a-glance” control panel for background work (download/convert/sync/repair). It should:
- Provide a real-time view of active work (what, how far, and what’s happening now).
- Give users control (pause/resume/cancel; ideally at batch + item level).
- Make failures actionable (what failed, why, and clear paths to retry + view logs).
- Offer job history (status over time) with the ability to clear/prune.

This review focuses on the current implementation in:
- `apps/web/src/components/domain/ProgressPopover.tsx`
- Related UI plumbing: `apps/web/src/components/layout/GlobalUI.tsx`, `apps/web/src/hooks/useJobsFeedWebSocket.ts`, `apps/web/src/hooks/useJobs.ts`
- Backend behavior that affects the UX: `apps/api/api/routes/jobs.py`, `apps/api/services/job_manager.py`, `apps/api/db/models.py`

---

## Current behavior (what the user sees today)
### Active tab
- Lists “active” jobs with a percent bar and a fallback “Processing…” message.
- Shows computed speed (`%/s`) + ETA derived from percent changes.
- No job-level controls (cancel/pause/logs/details) from the popover.

### Failed tab
- Lists failed jobs and shows a `Retry` icon for `DOWNLOAD`/`CONVERT` jobs (only when `job.book_asin` exists).
- No “View logs” affordance from the popover.

### History tab
- Shows up to 50 recent jobs filtered to `COMPLETED | FAILED | CANCELLED`.
- No “clear history” control.
- No navigation to “View Jobs” / job details, and no filtering/sorting controls.

### Realtime mechanics (important)
- `GlobalUI` mounts a global WS feed (`useJobsFeedWebSocket`) and also fetches active jobs once (`useActiveJobs`), intended to avoid polling.
- The popover itself does **not** subscribe to per-job websockets; it relies on caches being updated elsewhere.

---

## UX gaps (prioritized)

### P0) Interrupted jobs can look “active” forever (dead-but-still-running)
Observed failure mode: if the API server restarts (or the in-memory job runner is interrupted) while a job is `RUNNING/PENDING/QUEUED`, the UI can still show the job as active even though no background work is happening.

Root causes in the current stack:
- **Jobs are executed in-memory** (`apps/api/services/job_manager.py` tracks tasks in `self._tasks`). On process restart, the tasks are gone.
- **Job state in DB isn’t reconciled on startup**: jobs can remain `RUNNING` in the database even though there is no worker executing them.
- **The global WS initial “batch” snapshot is not authoritative in the web cache**:
  - `apps/api/api/routes/jobs.py` sends a batch snapshot of *currently active* jobs when the client connects to `/jobs/ws`.
  - `apps/web/src/hooks/useJobsFeedWebSocket.ts` only upserts/removes jobs when it receives per-job status messages; it does **not** replace the active list with the snapshot. If a job was previously “active” in the client cache but is missing from the snapshot, the client won’t remove it.
- **No “last update / heartbeat” surfaced in UI**: the user can’t tell if a job is actively progressing vs. stale.

Impact:
- Users see “active” work that is actually dead/stuck after restarts or connection drops.
- Troubleshooting devolves into manual log-diving (“is it really running?”).

### P0) Not enough control surface for a “process monitor”
The popover is currently informational-only for active jobs:
- No `Cancel` action (even though cancel exists via `useCancelJob` and is exposed in `JobDrawer`).
- No `Pause/Resume` controls (not currently supported by the API/JobManager).
- No quick link to “View Jobs” (JobDrawer) or “View Logs” (JobLogsModal).

Impact:
- Users must hunt for controls elsewhere (or can’t take action at all).
- The popover doesn’t match its intended purpose as a realtime “control panel”.

### P0) Status messages exist in the backend, but the UI largely drops them
Backend emits useful status messages:
- `JobManager._notify_status(..., message=...)` is called frequently (e.g., “Downloading: 3/20 completed”). See `apps/api/services/job_manager.py`.
- These messages are included in WS payloads (`message` field) in `apps/api/api/routes/jobs.py`.

But on the web side:
- `useJobsFeedWebSocket.ts` updates only `status`, `progress_percent`, and `error_message`, and ignores `message`.
- The database/API `JobRead` schema doesn’t include `status_message`, so REST fetches don’t provide it either (`apps/api/db/models.py`).

Impact:
- The popover often shows “Processing…” even though we have richer, realtime text available.

### P0) Failures are not actionable enough (especially for batch download)
Today’s download job semantics can hide item-level failures:
- In `JobManager._execute_download`, partial failures result in a final status of `COMPLETED` with the message “Downloaded X/Y items (some failed)”. The job is *not* marked `FAILED`.
- Individual item failures are written to the job log, but they aren’t summarized into `error_message` or structured data the UI can display.
- `Retry` in the popover only works when `job.book_asin` is set. For batch download jobs (multiple ASINs), `book_asin` is `null` by design (`apps/api/api/routes/jobs.py`), so retry is unavailable.

Impact:
- The Failed tab can be empty even though “some failed”.
- Users can’t retry failed items in a batch from the popover (or at all, without re-running a full batch elsewhere).

### P0) No history management (clear/prune) and no “job story”
History is capped at 50 and read-only:
- No “Clear history” action.
- No retention controls (e.g., clear completed older than N days).
- History entries don’t show time/duration consistently (created/started/completed aren’t surfaced).

Impact:
- Job list becomes noisy and less useful over time.
- Users can’t keep their workspace clean.

### P1) Layout/design doesn’t fit a SaaS “process monitor” (too narrow + too decorative)
The current popover styling feels like a compact “marketing status widget” rather than an operational job monitor.

Observed issues:
- **Too narrow for operational data**: `w-80` (~320px) forces truncation/line-clamps and hides key identifiers (title/asin), statuses, timestamps, and error context.
- **Typography hierarchy is decorative**: lots of tiny uppercase labels + muted microcopy; a SaaS monitor needs scanability (primary “what”, secondary “state”, and stable action affordances).
- **No action affordances in Active**: the Active list has no `Cancel`, `Logs`, or `Details`, making the popover passive instead of a control panel.
- **Progress without context**: percent + “Processing…” reads like a generic loading state; users need identifiers, status (`QUEUED/RUNNING`), “what’s happening”, and last-update indicators.

Impact:
- Users can’t quickly answer “What is running?” and “What can I do about it?” from the popover.
- Users don’t trust the UI because important context is hidden behind truncation and missing controls.

### P1) Tab counts are misleading (failures can be invisible)
In `ProgressPopover.tsx`, the “Failed” and “History” queries are only enabled when that tab is active, and only when the popover is not minimized:
- `Failed ({failedJobs.length})` shows `0` until the user clicks the Failed tab (because the query is disabled otherwise).
- In minimized mode, the popover still tries to display failed counts, but typically has no failed data loaded.

Impact:
- Users can have failures and never notice unless they click into the Failed tab.
- Counts appear “wrong” and erode trust in the progress UI.

### P1) The “meaning” of progress is often unclear
Problems that reduce interpretability:
- Active list doesn’t clearly show `PENDING vs QUEUED vs RUNNING` (only percent).
- For batch downloads (a single job with many ASINs), percent jumps in discrete steps; `%/s` and ETA can be noisy/misleading.
- The UI doesn’t show *what* the job is working on (book title/asin), except via `status_message` (which is usually missing today; see P0 status-message gap).

Impact:
- Users can’t answer “What is it doing right now?” or “Is it stuck?” quickly.

### P1) Dragging/positioning issues reduce polish and trust
Current drag implementation directly mutates DOM styles on every mousemove, while React can re-render frequently (job updates + stats interval):
- This can cause position “jitter” during drag if React re-applies the stored `position` mid-drag.
- The popover position is not persisted (Zustand `partialize` only persists sidebar/viewMode) and is not clamped to the viewport, so it can end up off-screen after resize.

Impact:
- The popover can feel glitchy or disappear.

### P2) Accessibility / keyboard UX is underdeveloped
- Tabs aren’t a semantic tablist (no `role="tablist"`, `aria-selected`, keyboard arrow navigation).
- No obvious keyboard shortcuts (e.g., open jobs, focus popover, close).
- Drag handle is mouse-only.

Impact:
- Power users and keyboard-only users have friction.

---

## Remediation plan (must-have, ordered by priority)

### P0) Make job state reliable and user-verifiable (no more “dead active” jobs)
1) Server-side restart/stale-job recovery (authoritative source of truth)
   - Add `updated_at` (or `last_heartbeat_at`) to `jobs` (`apps/api/db/models.py`) and update it whenever status/progress/message changes (in `handle_job_status_update` in `apps/api/api/routes/jobs.py`).
   - On API startup, reconcile: any job in `RUNNING/PENDING/QUEUED` whose `updated_at` is older than a threshold becomes `FAILED` (or a dedicated `INTERRUPTED/STALE` status) with a clear reason like “Interrupted by server restart”.
   - Optional: add a watchdog background task that marks jobs stale if they stop heartbeating.

2) Frontend active list reconciliation on WS connect
   - In `apps/web/src/hooks/useJobsFeedWebSocket.ts`, treat the server’s initial `/jobs/ws` `batch` snapshot as authoritative for `jobKeys.active()`:
     - Replace the active cache with the snapshot’s active jobs.
     - Remove any previously-cached active jobs missing from the snapshot.
   - In the popover, show the WS connection state and a “data may be stale” banner when disconnected.

3) Surface “freshness” to the user
   - Display “Last update” (or “Stalled”) per active job once `updated_at` is available.
   - If a job is stalled, show it prominently and offer the likely next actions: `Logs`, `Retry`, `View job`.

### P0) Restore real-time meaning: show status + status_message everywhere
1) Persist `status_message` end-to-end
   - Add `status_message` to the DB model and API responses (`apps/api/db/models.py`).
   - Persist latest message in `handle_job_status_update` (`apps/api/api/routes/jobs.py`).
   - Update `apps/web/src/hooks/useJobsFeedWebSocket.ts` to write `msg.message` into the cached job (`status_message`).

### P0) Make the popover a control panel (not just a viewer)
1) Add row-level actions for Active jobs
   - `Cancel` (existing `DELETE /jobs/{id}` via `useCancelJob`)
   - `Logs` (open `JobLogsModal`)
   - `View job(s)` (open `JobDrawer` or a dedicated job detail view)

2) Add failure actions
   - Always show `Logs` for failed jobs.
   - Add a retry mechanism that works for batch jobs (see next section).

### P0) Make failures actionable for batch download (retry the right thing)
1) Define partial-failure semantics
   - Pick a user-facing rule:
     - Introduce `COMPLETED_WITH_ERRORS`, or
     - Mark job `FAILED` when any item fails (still `progress_percent=100`), with a clear summary message.

2) Persist a structured result summary
   - Store counts + failing ASINs (and optionally per-asin error snippets) on the job so the UI can render a “what failed” panel.

3) Add job-based retry
   - Add `POST /jobs/{job_id}/retry` so retry doesn’t depend on `book_asin`.
   - If a summary exists, retry only failed items.

### P0) Add history management (clear/prune) and improve the “job story”
1) Add a history-clear API
   - `DELETE /jobs/history` with filters (statuses, older-than date, optionally delete logs).

2) Add History tab controls
   - `Clear completed`, `Clear all`, and basic filters (status/type/time).
   - Show timestamps/duration (created/started/completed) for scanning.

### P1) Redesign layout for SaaS monitoring (wider, scannable, actionable)
1) Increase base width and optionally add resize
   - Target ~420–520px; keep a compact mode but don’t force it.

2) Use a table-like row structure
   - Left: icon + type + title/asin (primary line)
   - Middle: status badge + status_message (secondary line)
   - Right: progress% + row actions (`Cancel`, `Logs`, `Details`; `Pause/Resume` when supported)

3) Promote the header into a control bar
   - Summary (“Downloads: 2 running • Conversions: 1 queued”), realtime indicator, `View jobs`, and relevant batch actions (`Cancel all`, `Clear history`).

### P1) Fix misleading counts and improve interpretability
1) Make tab counts honest
   - Fetch lightweight counts even when tabs aren’t active (or poll infrequently).

2) Make progress interpretable
   - Show explicit status (`PENDING/QUEUED/RUNNING`), avoid noisy speed/ETA for step-based progress, and prioritize status_message + last-update.

### P1) Fix drag/position persistence and clamping
1) Persist popover position/minimized state in `apps/web/src/store/uiStore.ts`.
2) Clamp to viewport bounds and avoid React-vs-DOM drag jitter (use local drag state during drag).

### P2) Accessibility / keyboard UX
1) Convert tabs to a semantic tablist with keyboard navigation and `aria-selected`.
2) Ensure actions are keyboard reachable and have tooltips/labels.

---

## Suggested UX shape (what a “meaningful” ProgressPopover could look like)
This is a recommended structure, not a UI mandate:

1) Header summary
   - “Downloads: 2 running • Conversions: 1 queued” + realtime connection indicator.
   - Buttons: `View jobs`, `Pause all`, `Cancel all` (with confirmation).

2) Active list (actionable rows)
   - Row content: icon + title/asin + status + progress + compact “what’s happening” line.
   - Row actions: `Pause/Resume` (when supported), `Cancel`, `Logs`.

3) Failed list
   - Row content: title/asin + short error summary + timestamp.
   - Row actions: `Retry`, `Logs`, `View job`.

4) History (cleanable + filterable)
   - Filters: status/type/time range.
   - Actions: `Clear completed`, `Clear all history`, plus retention hint.

---

## Notes / risks to track
- “Pause” is not currently supported by the API; any UI needs backend primitives first.
- Batch downloads are currently a single job; item-level controls require new modeling.
- Web types include `status_message`, but the API does not return it today; align schemas so the UI can reliably show “what’s happening”.
