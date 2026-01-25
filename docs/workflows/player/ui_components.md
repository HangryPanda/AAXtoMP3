# UI Components & Interaction

This document details the key User Interface components of the player and their interaction logic.

## StickyPlayer (Mini Player)

The `ConnectedStickyPlayer` is a persistent "Mini Player" bar that appears at the bottom of the screen when a book is loaded. It allows users to browse the library while listening.

### Key Features
*   **Persistence:** Remains visible across all application routes (`/`, `/library`, `/settings`, etc.) as long as `playerStore.currentBookId` is set.
*   **State Sync:** Fully reactive to the global `playerStore`. Pausing in the StickyPlayer updates the main Full Screen player immediately, and vice-versa.
*   **View Transitions:** Clicking the cover art or title triggers a smooth **Shared Element Transition** (via the View Transitions API) to the full `/player` page, making the cover appear to expand from the footer to the main view.
*   **Smart Resume Toast:** Displays ephemeral notifications (e.g., "Rewound 20s for context") directly above the player bar.

### Logic
*   **Visibility:** Renders `null` if `playerStore.currentBookId` is null.
*   **Navigation:** Uses `router.push('/player?asin=...')` but wraps it in `document.startViewTransition()` for animation.
*   **Controls:** exposes a subset of the full player controls:
    *   Play/Pause
    *   Skip Back 15s / Forward 30s
    *   Volume / Mute
    *   Seek Bar

## Play Button Logic (`canPlay`)

The frontend currently uses a strict check to determine if the "Play" button is enabled on a Book Card.

### The Rule
A book is considered playable **only** if:
1.  `book.status` is `COMPLETED`.
2.  `book.local_path_converted` is not null/empty.

### Implications for JIT Streaming
*   **Current State:** Even though the backend *can* stream raw AAX/AAXC files (JIT Streaming), the frontend **does not yet allow** users to trigger playback for these files.
*   **Future Update:** To fully enable JIT Streaming, the `canPlay` helper in `types/book.ts` must be updated to also return `true` if `book.local_path_aax` exists, regardless of conversion status.

## Full Screen Player

The main player view (`/player`) provides the complete listening experience.

### Components
*   **PlayerHeader:** Navigation back to library and context menu.
*   **PlayerCover:** Large cover art display.
*   **PlayerProgressBar:** Precision seeking and chapter markers.
*   **PlayerControls:**
    *   **Primary:** Play/Pause, Skip Back/Fwd, Next/Prev Chapter.
    *   **Secondary:** Playback Speed (0.5x - 3.0x), Sleep Timer, Chapter List toggle.
*   **PlayerVolume:** Detailed volume slider.
*   **PlayerChapterList:** Scrollable list of all chapters with duration and current position indication.
