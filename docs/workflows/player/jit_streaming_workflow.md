# Just-In-Time (JIT) Streaming Workflow

This document explains the backend logic that enables "Play Immediately" functionality, allowing the player to stream audio before conversion is complete.

## Concept
Historically, users had to wait for the `AAX -> MP3/M4B` conversion to finish before playback. JIT Streaming removes this barrier by serving audio from *any* available source, prioritizing quality and efficiency.

## Data Flow (Backend)

### Endpoint: `GET /stream/{asin}`

### Priority 1: Direct File Serve (Converted)
*   **Condition:** The backend checks `Book.local_path_converted`.
*   **Check:** Does the file exist on disk?
*   **Action:** Returns a `FileResponse`.
*   **Behavior:**
    *   Uses standard HTTP Range requests (browser requests bytes 0-1024, etc.).
    *   Zero CPU overhead (static file serving).
    *   **Ideal for:** Validated, completed books.

### Priority 2: On-the-Fly Transcoding (AAX/AAXC)
*   **Condition:** Converted file is missing, but `Book.local_path_aax` exists.
*   **Action:** Spawns an `ffmpeg` subprocess.
*   **Command:**
    ```bash
    ffmpeg -activation_bytes {AUTH} -i input.aax -f mp3 -vn -acodec libmp3lame -q:a 4 -
    ```
    (Or uses the `.voucher` file for AAXC decryption).
*   **Streaming:** The output of `ffmpeg` (stdout) is piped directly to the HTTP response (`StreamingResponse`).
*   **Behavior:**
    *   **Latency:** Near-instant start (only startup time of ffmpeg).
    *   **Seeking:** Limited/Approximate. Since the file is being generated linearly, seeking backward works (browser cache), but seeking forward requires ffmpeg to seek input.
    *   **CPU:** High usage per listener.

### Priority 3: Local Item (Orphan)
*   **Endpoint:** `GET /stream/local/{id}`
*   **Logic:** Looks up `LocalItem` table for orphan files (files found on disk but not matched to an ASIN).
*   **Action:** Serves the file directly via `FileResponse`.

## Frontend Awareness
The frontend explicitly enables playback based on the availability of audio sources.

### Play Button Logic (`canPlay`)
The `canPlay` helper in `@/types/book.ts` determines if the "Play" button is enabled. It returns `true` if:
1.  **Converted Ready:** `book.status === 'COMPLETED'` AND `book.local_path_converted` exists.
2.  **JIT Ready:** `book.local_path_aax` exists (regardless of conversion status).

This allows users to play books as soon as the download finishes, even while the book is in `DOWNLOADED`, `VALIDATED`, or `CONVERTING` states.

### Playback Behavior
*   **URL Strategy:** The player always requests `${API_URL}/stream/{asin}`. The backend handles the waterfall priority (File vs. JIT) transparently.
*   **Duration:** The player uses the `duration` from the metadata database (or `X-Duration` header) to ensure the progress bar is accurate even when the `Content-Length` of a JIT stream is unknown.
*   **Seeking:** For JIT streams, the frontend uses the `?start_time=<seconds>` query parameter to request the backend to seek within the source file before transcoding.

## Future Implementation Considerations

### Client-Side Processing (ffmpeg.wasm)
We evaluated using `ffmpeg.wasm` to perform client-side transcoding, which would allow the browser to decrypt and play `.aax` files directly without backend involvement.

**Decision:** We have decided **AGAINST** this for the primary streaming player due to the following constraints:
1.  **Memory Constraints:** Audiobooks are typically 500MB+, and loading them into the browser's in-memory filesystem (MEMFS) can cause crashes, especially on mobile devices.
2.  **Decryption Complexity:** Standard `ffmpeg.wasm` builds often lack the proprietary Audible decryption filters, necessitating custom builds and maintenance.
3.  **Battery & Performance:** Decoding encrypted streams in WASM is significantly more CPU-intensive than using the browser's native `<audio>` element with a standard server-provided MP3 stream.
4.  **Security Headers:** `ffmpeg.wasm` requires `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp`, which can break external CDN resource loading (e.g., cover art).

**Potential Use Case:** `ffmpeg.wasm` remains a strong candidate for a future **"Offline Converter"** feature, allowing users to convert local `.aax` files entirely within their browser without uploading to the server.