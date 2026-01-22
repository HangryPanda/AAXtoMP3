# Specification: Player View

## Overview
A web-based audio player for listening to **converted** (DRM-free) audiobooks directly in the browser. This allows users to verify conversions or listen from any device on the network without syncing files first.

## User Experience (UX) Goals
*   **Accessibility:** Large, easy-to-hit controls (Mobile driving mode friendly).
*   **Continuity:** Remember playback position for every book (Server-side sync preferred, LocalStorage MVP).
*   **Metadata Rich:** Show current chapter name, cover art, and progress.

## Core Features

### 1. Audio Engine
*   **Streaming:** Support HTTP Range requests to stream large M4B/MP3 files without full download.
*   **Format Support:** Native browser support for MP3/AAC (M4B). Transcoding or WASM decoders needed for FLAC/Ogg/Opus if not natively supported by target browsers (Safari/Chrome). *MVP: Focus on MP3/M4B.*

### 2. Player Controls
*   **Transport:** Play/Pause, Skip Forward (30s), Skip Back (10s), Next/Prev Chapter.
*   **Scrubbing:** Precision seek bar.
*   **Speed Control:** Variable playback speed (0.5x to 3.0x) with pitch correction.
*   **Volume:** Slider with mute toggle.

### 3. Playlist / Chapter Navigation
*   **Chapter List:** Scrollable list of chapters with titles and durations.
*   **Active Chapter:** Highlight current chapter.
*   **Click-to-Play:** Jump to specific chapter start time.

### 4. "Now Playing" Context
*   **Mini Player:** A persistent footer player when browsing the "Manager" view.
*   **Full Screen Mode:** Immersive view with large cover art and simplified controls.

## Technical Implementation

### Audio Engine: Howler.js
We will use **Howler.js** (via `react-howler` or custom wrapper) instead of the raw HTML5 Audio element.
*   **Why:** Normalizes behavior across browsers (Safari/Chrome), simplifies handling of "unlocking" audio contexts on mobile, and provides robust volume/rate/seek APIs.
*   **Format Handling:** Howler will attempt to use HTML5 Audio for large files (streaming) via `html5: true` to avoid loading the entire 500MB+ audiobook into RAM.

### State Persistence (The "Continuity" Engine)
*   **Local Loop (High Frequency):** Save current timestamp to **IndexedDB/LocalStorage** every **5 seconds**. This ensures if the browser crashes or tab closes, the user loses at most 5s of progress.
*   **Remote Loop (Low Frequency):** Send a "Heartbeat" to the backend (`POST /api/progress`) every **30 seconds**, and strictly on `Pause` or `Unload` events.
*   **Resume Logic:** On load, check LocalStorage vs Backend timestamp. Use the *latest* value to prompt the user (e.g., "Resume from 5:42?").

## Component Breakdown (Suggestions)
*   `PlayerContext`: Global state provider for the active audio session.
*   `StickyPlayer`: The footer bar component.
*   `ChapterList`: Sidebar/Modal component for navigation.
*   `SpeedSelector`: Dropdown/Slider for playback rate.
