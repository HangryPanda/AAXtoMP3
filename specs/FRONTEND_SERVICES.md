# Specification: Frontend Application Services

## Overview
This document defines the core infrastructure services required by the React frontend. These services handle data fetching, state management, authentication, and real-time communication.

## Tech Stack Recommendations
*   **Framework:** Next.js (App Router) or Vite (SPA). *Recommendation: Next.js for easy API proxying.*
*   **Language:** TypeScript (Strict).
*   **State/Cache:** TanStack Query (React Query) for server state; Zustand for local app state (player, UI settings).
*   **Styling:** Tailwind CSS + Shadcn UI (Radix Primitives).

## Target Dependencies (Node.js)
The agents should initialize the project with these core libraries (targeting React 19 + Compiler):

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "next": "15.x",
    
    // State & Data Fetching
    "@tanstack/react-query": "^5.0.0",
    "axios": "^1.6.0",
    "zustand": "^4.5.0",
    
    // UI & Styling
    "tailwindcss": "^3.4.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0",
    "lucide-react": "^0.300.0",
    "class-variance-authority": "^0.7.0",
    
    // UI Primitives (Shadcn dependencies)
    "@radix-ui/react-slot": "^1.0.0",
    "@radix-ui/react-dialog": "^1.0.0",
    "@radix-ui/react-progress": "^1.0.0",
    "@radix-ui/react-toast": "^1.1.0",
    
    // Utilities
    "date-fns": "^3.3.0",
    "zod": "^3.22.0",

    // Caching & PWA
    "dexie": "^3.2.4",         # IndexedDB Wrapper
    "next-pwa": "^5.6.0",      # Service Worker generation

    // Media & Terminal
    "howler": "^2.2.4",         # Audio Engine
    "xterm": "^5.3.0",          # Terminal Rendering (for logs)
    "xterm-addon-fit": "^0.8.0"
  },
  "devDependencies": {
    "eslint-plugin-react-compiler": "latest" # ENABLE REACT COMPILER
  }
}
```

## 6. Caching & Background Services

### IndexedDB Strategy (Local-First)
To support libraries with 1000+ items without lag, we will mirror the database on the client.
*   **Library Cache:** Use `Dexie.js` to store the full library metadata.
    *   *Table:* `books` (Indexes: `asin`, `status`, `author`, `title`).
    *   *Logic:* On load, serve from IDB immediately. Background fetch updates from API and syncs changes to IDB.
*   **Query Persistence:** Configure TanStack Query's `Persister` to hydrate state from IndexedDB on app launch.

### Service Workers
*   **App Shell:** Cache all JS/CSS bundles for instant second-load.
*   **Offline Fallback:** Serve the "Manager" view from cache if the backend is unreachable.
*   **Background Sync:** (Advanced) If the user clicks "Download" while offline, queue the request in the Service Worker to replay when online.

### Web Workers
*   **Search Indexing:** If client-side fuzzy search becomes heavy (e.g., searching 5000 books), move the search logic to a Web Worker to prevent UI blocking.
```

## Service Modules

### 1. API Client Service (`services/api.ts`)
*   **Base Configuration:** Axios or Fetch wrapper with base URL handling.
*   **Error Handling:** Global interceptor for network errors (401/403/500) to trigger UI toasts.
*   **Type Safety:** All API responses must be typed via Zod schemas or TypeScript interfaces matching the Backend DTOs.

### 2. Library Service (`hooks/useLibrary.ts`)
*   **Purpose:** Interface with the library data.
*   **Hooks:**
    *   `useBooks(filterParams)`: Paginated/Filtered fetch of library items.
    *   `useBookDetails(asin)`: Fetch single book metadata + file status.
    *   `useSyncLibrary()`: Mutation to trigger `audible-cli` sync.

### 3. Job/Queue Service (`hooks/useJobs.ts`)
*   **Purpose:** Manage background conversion tasks.
*   **Hooks:**
    *   `useJobs()`: Fetch list of active/completed jobs.
    *   `useCreateJob()`: Mutation to start a download/conversion.
    *   `useCancelJob()`: Mutation to stop a job.
*   **Real-time Connection:**
    *   Implement a WebSocket or Server-Sent Events (SSE) hook (`useJobSocket`) to listen for progress updates and log lines.
    *   **Log Buffering:** The service should buffer incoming log lines (e.g., every 100ms) before pushing to the UI component to prevent "render thrashing" during high-speed FFmpeg output.

### 4. Player Service (`store/playerStore.ts`)
*   **Type:** Zustand Store + Howler.js Controller.
*   **State:** `isPlaying`, `currentTime`, `duration`, `currentBookId`, `volume`, `playbackRate`.
*   **Audio Controller:** Encapsulate the `Howl` instance. Do not expose `Howl` directly to the UI components.
*   **Sync Logic (Middleware):**
    *   *Subscribe* to `currentTime` changes.
    *   *Debounce* writes to `localStorage` (5s).
    *   *Debounce* writes to API `POST /progress` (30s + onPause).
*   **Actions:** `play(bookId)`, `pause()`, `seek(time)`, `setRate(rate)`.

### 5. Settings Service (`hooks/useSettings.ts`)
*   **Purpose:** Manage application configuration.
*   **Scope:**
    *   Naming schemes (Artist/Title vs Title/Author).
    *   Format preferences (M4B vs MP3).
    *   Theme (Dark/Light).
    *   Path configuration (if editable via UI).

## Directory Structure (Frontend)
```
src/
├── components/
│   ├── ui/           # Shadcn primitive components
│   ├── layout/       # AppShell, Sidebar, Header
│   └── domain/       # Feature-specific (BookCard, PlayerControls)
├── lib/              # Utilities (formatting, date-fns)
├── hooks/            # React Query hooks
├── services/         # API clients
├── store/            # Zustand stores
└── app/              # Next.js pages/routes
```
