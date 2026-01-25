# Player Initialization Workflow

This document details how the player loads a book, restores state, and prepares for playback.

## Data Flow

### 1. Route Entry
*   **URL:** `/player?asin={ASIN}` or `/player?local_id={ID}`
*   **Hook:** `usePlayerLogic` initializes and parses query params.
*   **Fetching:**
    *   Calls `useBookDetails(asin)` to fetch basic metadata (Title, Cover).
    *   Calls `useBookDetailsEnriched(asin)` to fetch deep metadata (Chapters, Series).
    *   Calls `useLocalItemDetails(localId)` if playing a local/orphan file.

### 2. Audio Loading (Store)
*   **Trigger:** `useEffect` in `usePlayerLogic` detects when book data is ready.
*   **Action:** Calls `playerStore.loadBook(id, url, title)`.
*   **URL Generation:**
    *   Standard: `${API_URL}/stream/{asin}`
    *   Local: `${API_URL}/stream/local/{localId}`
*   **State Reset:**
    *   Sets `isLoading: true`.
    *   Unloads any previous `Howl` instance (stopping audio).

### 3. State Restoration (Smart Resume)
*   **Persistence:** The player checks `IndexedDB` (via `lib/db`) for saved progress for this book ID.
*   **Resume Logic:**
    *   **Position:** Restores `currentTime` from the saved record.
    *   **Smart Rewind:**
        *   If `lastPlayedAt` was > 24 hours ago, rewinds 20 seconds for context.
        *   Sets `smartResumeMessage` (e.g., "Rewound 20s for context") to notify the user.
*   **Settings:** Restores Volume, Playback Rate, and Mute state from `localStorage` (Zustand persistence).

### 4. Audio Engine (Howler.js)
*   **Instantiation:** A new `Howl` instance is created with `html5: true` (forces HTML5 Audio for streaming).
*   **Event Binding:**
    *   `onload`: Updates `duration` and seeks to the restored position. Sets `isLoading: false`.
    *   `onplay`: Starts the sync loop.
    *   `onend`: Marks the book as finished in the backend.

## Key Handling Mechanisms

| Mechanism | Description |
| :--- | :--- |
| **HTML5 Audio** | Uses `html5: true` in Howler to enable streaming of large files without loading them fully into RAM (which Web Audio API would require). |
| **Smart Resume** | Automatically rewinds playback if the user hasn't listened in a while (default: 24h), providing "contextual continuity". |
| **Optimistic UI** | Shows the player UI with metadata immediately while the audio stream initializes in the background. |
