# Playback & Controls Workflow

This document explains the playback lifecycle, state management, and user controls in the player.

## Architecture

The player uses **Zustand** for global state management and **Howler.js** as the audio engine. The UI components (`PlayerControls`, `PlayerProgressBar`, etc.) are pure consumers of this store.

## Playback Loop

### 1. State Updates
*   **Trigger:** `requestAnimationFrame` loop initiated in `howl.onplay`.
*   **Action:**
    *   Reads `howl.seek()` to get the exact current time.
    *   Updates `playerStore.currentTime` via `_setCurrentTime`.
*   **Result:** The `PlayerProgressBar` and `PlayerMetaControls` (time display) re-render smoothly.

### 2. User Actions
*   **Play/Pause:** Toggles `isPlaying` state and calls `howl.play()` / `howl.pause()`.
*   **Seek:**
    *   Updates `currentTime` optimistically in the UI.
    *   Calls `howl.seek(time)` to jump the audio stream.
*   **Volume/Speed:**
    *   Updates store state (persisted to localStorage).
    *   Calls `howl.volume()` or `howl.rate()` immediately.
*   **Skip:** `seekRelative(+30)` or `seekRelative(-10)` calls the seek action with a delta.

### 3. Chapter Navigation
*   **Calculation:** `usePlayerLogic` derives the `currentChapter` by comparing `currentTime` against the sorted list of chapters.
*   **Next/Prev:**
    *   **Next:** Seeks to the `start_offset_ms` of `currentChapterIndex + 1`.
    *   **Prev:**
        *   If > 3s into the chapter, restarts the *current* chapter.
        *   If < 3s, skips to the *previous* chapter.

## Sleep Timer

### Logic (`usePlayerLogic`)
*   **Modes:**
    *   **Time-Based:** Sets a timestamp (`sleepTimerEndTime`). Pauses when `Date.now() > timestamp`.
    *   **Chapter End:** Monitors `currentTime`. Pauses when `currentTime >= currentChapter.end_offset`.
*   **Fade Out:**
    *   Detects when < 60s remains (or < 2s for chapter end).
    *   Gradually reduces volume from 100% to 0% before pausing.
    *   Restores original volume after pausing.

## Media Session API
*   **Integration:** The player hooks into the browser's `navigator.mediaSession` API.
*   **Features:**
    *   Shows metadata (Title, Author, Cover) in OS lock screens and notification centers.
    *   Maps hardware media keys (Play, Pause, Next, Prev) to store actions.
