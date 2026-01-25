# Player Documentation

This directory contains detailed workflows for the Web Player component of the Audible Library.

## Workflows

- **[Initialization](./initialization_workflow.md)**: How the player loads books, restores state, and prepares for playback.
- **[Playback & Controls](./playback_workflow.md)**: The playback lifecycle, Howler.js integration, and UI control logic.
- **[Progress Sync](./sync_workflow.md)**: The "Continuity Engine" that syncs progress between LocalStorage (IndexedDB) and the Backend.
- **[JIT Streaming](./jit_streaming_workflow.md)**: The backend architecture enabling "Play Immediately" via on-the-fly transcoding.
- **[UI Components](./ui_components.md)**: Documentation for the StickyPlayer, Play Button logic, and Full Screen components.

## Key Components
- **Store:** `apps/web/src/store/playerStore.ts` (Zustand)
- **Logic:** `apps/web/src/app/player/hooks/usePlayerLogic.ts`
- **Audio Engine:** Howler.js (via `react-howler` or direct wrapper)