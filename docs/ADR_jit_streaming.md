# Architectural Decision: Just-In-Time (JIT) Streaming & Transcoding

## Context
Currently, the `GET /stream/{asin}` endpoint strictly serves files that have completed the full conversion pipeline (`BookStatus.COMPLETED` and `local_path_converted` exists).

This limitation creates a poor user experience:
1.  **Delay to Playback:** Users must wait for the entire conversion process (which can be slow) before they can listen to a book they have already downloaded.
2.  **Brittle Playback:** If the conversion fails or the converted file is missing, the user cannot listen, even if the raw AAX/AAXC source file is intact.
3.  **Storage Inefficiency:** We are forced to store converted files to enable playback, even if we could technically stream the source on-the-fly.

## Decision
We will implement a **Just-In-Time (JIT) Streaming** strategy that allows the API to serve audio from *any* valid source file available (Converted > AAX/AAXC), falling back to on-the-fly transcoding/decryption when necessary.

## Implementation Strategy

### 1. Unified Stream Endpoint (`GET /stream/{asin}`)
The stream endpoint logic will be upgraded to a waterfall priority system:

**Priority 1: Direct File Serve (Converted)**
-   **Condition:** `local_path_converted` exists on disk.
-   **Action:** Serve using `FileResponse` (Zero-copy, standard HTTP range support).
-   **Pros:** Lowest CPU usage, best seek performance.

**Priority 2: On-the-Fly Decryption (AAX/AAXC)**
-   **Condition:** `local_path_converted` missing, but `local_path_aax` exists on disk.
-   **Action:**
    1.  Retrieve authentication secrets (activation bytes or audible-cli keys).
    2.  Spawn an `ffmpeg` subprocess to decrypt and transcode the input stream to a browser-compatible format (e.g., MP3 or AAC/M4A) in real-time.
    3.  Serve the output via `StreamingResponse`.
-   **Pros:** Instant playback after download; no conversion wait time.
-   **Cons:** Higher CPU usage during playback; seeking is more complex (may require HLS or accepting inaccurate seeks).

### 2. Frontend Awareness
-   The frontend does not need to know *how* the file is being served, only that `/stream/{asin}` is the source.
-   However, metadata (like duration) must be available. If the book hasn't been converted/scanned, we may need to rely on the metadata embedded in the AAX header (via `ffprobe`) to provide accurate duration to the player.

## Technical Requirements
-   **FFmpeg Integration:** The backend must be able to manage long-running `ffmpeg` processes for streaming, ensuring they are terminated when the client disconnects.
-   **Secrets Management:** The stream service requires access to the Audible activation bytes/keys used by `audible-cli`.
-   **Concurrency:** The server must handle multiple concurrent transcoding streams without exhausting resources (may require a semaphore/limit).

## Benefits
-   **"Play Immediately":** Drastically reduces the time from "Purchase" to "Listening".
-   **Resilience:** Playback works as long as *any* version of the audiobook exists.
-   **Simplification:** The player component treats all books as playable, removing "Converting..." blocking states from the UI.
