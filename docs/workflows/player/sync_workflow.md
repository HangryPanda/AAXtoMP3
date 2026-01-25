# Progress Sync Workflow

This document details how playback progress is persisted locally and synchronized with the backend server.

## Overview
The "Continuity Engine" ensures users never lose their place, even if the browser crashes or they switch devices. It uses a dual-layer strategy: **High-Frequency Local** + **Low-Frequency Remote**.

## Data Flow

### 1. The Sync Loop
*   **Initialization:** Started via `startPositionSaveInterval` when `isPlaying` becomes true.
*   **Frequency:** Runs every **5 seconds** (`SAVE_POSITION_INTERVAL`).

### 2. Local Persistence (IndexedDB)
*   **Action:** Calls `saveProgress(bookId, time, duration)` (via `lib/db` -> `idb`).
*   **Purpose:**
    *   Primary restore point for the *same device*.
    *   Works offline.
    *   Instant read access on page load.

### 3. Remote Persistence (Backend API)
*   **Action:** Calls `updatePlaybackProgress(bookId, payload)`.
*   **Payload:**
    *   `position_ms`: Current time in milliseconds.
    *   `playback_speed`: Current rate (to remember user preference).
    *   `is_finished`: Boolean (true if > 95% complete).
*   **Purpose:**
    *   Syncs progress across *different devices*.
    *   Updates "Last Played" timestamp for history.

### 4. Conflict Resolution
*   **Scenario:** User listens on Phone A, then opens Laptop B. Laptop B's local state is old, but the Server state is new.
*   **Detection:** `usePlayerLogic` checks for conflicts on load:
    *   Fetches `localProgress` (IndexedDB).
    *   Fetches `serverProgress` (API).
    *   Compares timestamps.
*   **Threshold:** If the difference is > **30 seconds**.
*   **Resolution:**
    *   The UI displays a "Position Conflict" modal (implemented in `PlayerContainer`).
    *   User chooses: "Keep Local" or "Jump to Server".

### 5. Final Save (Unload)
*   **Trigger:** `pause()`, `stop()`, or `unloadBook()`.
*   **Action:** Forces an immediate synchronous save to LocalStorage/IndexedDB and fires a final async request to the backend to ensure the exact stop time is captured.
