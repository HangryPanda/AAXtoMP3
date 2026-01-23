# Architectural Decision: Resilient Chapter Loading Strategy

## Context
Currently, the `get_book_details` API endpoint returns chapter data solely from the database. If chapters are missing (e.g., the book hasn't been scanned), the frontend receives an empty list. This creates a brittle dependency: the player UI relies on navigation metadata (chapters) to function correctly, potentially blocking playback or rendering a broken state if that metadata is missing, even if the audio file itself is present and playable.

## Decision
We will decouple **Playback Capability** from **Navigation Metadata** to ensure the player is always functional, implementing a **Progressive Enhancement** strategy for chapter loading.

### Core Principles
1.  **Playback First:** The ability to play audio and scrub (seek) takes precedence over displaying chapter markers.
2.  **Self-Healing:** Accessing a book should trigger metadata repair if it's missing, without blocking the immediate user request.
3.  **Graceful Fallback:** The UI should handle missing chapters by rendering a simplified interface rather than failing.

## Implementation Strategy

### 1. Backend (`get_book_details`)
The API endpoint will be modified to handle missing DB chapters as follows:

-   **Check:** Does the database have chapters for this ASIN?
-   **Hit (Happy Path):** Return the chapters as usual.
-   **Miss (Missing Data):**
    1.  **Synthetic Fallback:** Construct and return a single "synthetic" chapter covering the full duration:
        ```json
        [{
          "index": 0,
          "title": "Full Duration",
          "start_offset_ms": 0,
          "length_ms": <book_total_duration>,
          "end_offset_ms": <book_total_duration>
        }]
        ```
    2.  **Trigger Repair:** Queue a background job (or asynchronous task) to run `scan_book(asin)`. This effectively "heals" the missing data for future requests.

### 2. Frontend (Player Component)
The player will be designed to handle this asynchronous state transition:

-   **Initialization:** The player initializes audio using `audioUrl` and `duration` immediately.
-   **Rendering:** It renders the timeline based on the returned chapters (whether real or synthetic).
    -   *Synthetic Detection:* If the API returns a specific flag (e.g., `is_synthetic: true`) or the frontend detects a single chapter matching the full duration with a generic title, it can optionally show a "Loading chapters..." indicator.
-   **Live Update:** The frontend listens for data updates (via WebSocket `BOOK_UPDATED` event or SWR re-validation).
    -   When the background scan completes, the frontend receives the new, detailed chapter list.
    -   The timeline component re-renders with the new markers *without* interrupting playback.

## Benefits
-   **Zero-Latency Playback:** Users never wait for metadata extraction to start listening.
-   **Robustness:** Playback works even if metadata extraction fails completely (fallback to simple duration-based scrubbing).
-   **Improved UX:** The interface progressively enhances itself, providing a "living" feel rather than a broken one.
