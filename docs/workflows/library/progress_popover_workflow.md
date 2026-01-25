# ProgressPopover Workflow

The `ProgressPopover` is a floating, draggable UI component that provides real-time visibility into background tasks (Downloads, Conversions, Syncs, Repairs). It is designed to be informative without being intrusive.

## 1. Automatic Activation
The popover is managed globally by the `GlobalUI` component.
*   **Trigger:** It monitors the `activeCount` of jobs.
*   **Auto-Open:** If `activeCount` transitions from 0 to >0, the popover automatically opens to notify the user that work has started.
*   **User Preference:** If a user manually closes the popover while jobs are still active, it remains "dismissed" (hidden) for that session unless new jobs are started.

## 2. Real-Time Data & Feed
*   **WebSocket Integration:** It connects to the global Jobs WebSocket feed. While initial state comes from a standard API poll, status updates (progress, state changes) are pushed in real-time.
*   **Connection Status:** A "Live/Stale" indicator shows if the WebSocket connection is active. If disconnected, it falls back to polling or warns the user that data may be stale.

## 3. Progress & ETA Calculations
Calculations are performed by the `useProgressStats` hook:
*   **Sampling:** Progress percentage is sampled every 1 second.
*   **Speed Calculation:** `(current_progress - last_progress) / time_delta`.
*   **Smoothing:** To prevent erratic jumping, the speed is smoothed using a weighted average: `(current_speed * 0.3) + (previous_speed * 0.7)`.
*   **ETA:** `remaining_percentage / smoothed_speed`.

## 4. UI States & Interaction

### Draggable Interface
*   The popover can be dragged anywhere within the viewport using the header handle.
*   **Viewport Clamping:** Logic ensures the popover cannot be dragged off-screen.
*   **Persistence:** The last position is saved in `localStorage` via the `uiStore`.

### Minimized Mode
*   Users can "Minimize" the popover into a small, floating circular badge.
*   The badge shows a summary (e.g., "3 Active • 1 Failed") and an activity spinner.
*   Clicking the badge restores the full view.

### Tabbed Views
1.  **Active:** Shows current jobs with progress bars, speed, and ETA.
2.  **Failed:** Shows failed jobs with error messages and a "Retry" button.
3.  **History:** Shows a summary of recently completed or cancelled jobs.

## 5. Intelligent Monitoring (Stall Detection)
*   The popover monitors the `updated_at` timestamp of running jobs.
*   **Stall Warning:** If a job is in the `RUNNING` state but hasn't received a progress update for more than 90 seconds, it is visually flagged as "Stalled".

## 6. Global Actions
The popover provides shortcuts to:
*   **Pause/Resume:** Control individual jobs.
*   **Cancel:** Stop a specific job or "Cancel All" active jobs.
*   **View Logs:** Opens a modal with the real-time stdout/stderr of the job.
*   **Clear History:** Purges completed/failed records from the UI.
