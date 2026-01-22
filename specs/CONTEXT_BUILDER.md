# Project Context & Architecture Overview

## Project Mission
Refactor an existing Python/Streamlit/Bash application ("Audiobook Library Manager") into a modern, enterprise-grade full-stack application.
**Goal:** Create a performant, mobile-friendly web GUI that prioritizes desktop power users, while strictly retaining the robust CLI conversion capabilities of the original project.

## Architecture: "The Hybrid Enterprise"

We are moving from a monolithic Script+GUI app to a 3-tier architecture:

```mermaid
graph TD
    UserWeb[Web Frontend
(React/Next.js)] <-->|REST/WS| API[Backend API
(Python/FastAPI)]
    UserCLI[Power User CLI] <-->|Direct Exec| CoreScripts[Core Shell Scripts
AAXtoMP3]
    API <-->|Subprocess/Queues| CoreScripts
    API <-->|Auth/Meta| AudibleCLI[Audible CLI
(Python Lib)]
    API <-->|Read/Write| DB[(Database
SQLite/Postgres)]
    API <-->|Read/Write| FileSys[Filesystem
/Audiobooks]
```

### 1. Frontend (The "View")
*   **Tech Stack:** React (Vite or Next.js), TypeScript, Tailwind CSS, Shadcn UI.
*   **Responsibility:** Pure UI/UX. No heavy logic. Communicates with Backend via REST API and WebSockets (for real-time conversion logs).
*   **Key Traits:** Mobile-responsive but dense "Data Grid" layouts for desktop.

### 2. Backend (The "Brain")
*   **Tech Stack:** Python (FastAPI).
*   **Responsibility:** 
    *   API endpoints for the Frontend.
    *   Job Queue Management (Celery or background tasks) for long-running conversions.
    *   Database management (Library metadata, Job history).
    *   **Crucial:** Wraps the existing `AAXtoMP3` bash scripts and `audible-cli` python tools securely.

### 3. Core (The "Engine")
*   **Tech Stack:** Bash, FFmpeg, Python (audible-cli).
*   **Responsibility:** The actual heavy lifting of decryption, conversion, and metadata tagging.
*   **Constraint:** These scripts MUST remain independent so they can be run manually by power users in the terminal without the Web UI if desired.

## Repository Structure (Target Monorepo)

```text
/
├── apps/
│   ├── web/                 # Next.js / React Frontend
│   └── api/                 # FastAPI Backend
├── core/                    # The "Engine" (Move original scripts here)
│   ├── AAXtoMP3             # The main bash script
│   └── audible-cli/         # Python audible-cli integration
├── data/                    # SHARED PERSISTENT DATA (Git Ignored)
│   ├── library/             # SQLite DB & Library JSON caches
│   ├── downloads/           # Raw .aax / .aaxc files
│   └── converted/           # Final .m4b / .mp3 files
├── specs/                   # Build Specifications (You are here)
├── docker-compose.yml       # Orchestrates apps + shared volumes
└── README.md
```

## Data & Volume Mapping
To ensure the Backend and Frontend remain in sync, agents must adhere to these paths:
*   **Audio Assets:** Must be stored in `./data/converted`. The Backend streams these via API, but the Frontend may need to know relative paths for caching.
*   **Database:** The SQLite file must live in `./data/library/metadata.db`.
*   **Environment Variables:** Each app (`apps/web` and `apps/api`) should have its own `.env` file, but a root-level `.env.example` should define shared variables like `DATA_DIR`.

## Dispatch & Execution Plan (CRITICAL)

To prevent race conditions and duplicated work, agents MUST follow this assignment:

### PHASE 1: Scaffolding (AGENT 1 ONLY)
**Responsibility:** One agent acts as the "Architect".
1.  Create the directory structure: `apps/web`, `apps/api`, `core/`, `data/`.
2.  **Web Scaffolding:** Run `npx create-next-app@latest apps/web` with the specified dependencies in `specs/FRONTEND_SERVICES.md`.
3.  **API Scaffolding:** Create `apps/api/main.py` and `requirements.txt` with the specified dependencies in `specs/BACKEND_API.md`.
4.  **Core Migration:** Move existing scripts into `core/`.
5.  **COMMIT:** This agent must finish and commit these changes BEFORE other agents start.

### PHASE 2: Parallel Implementation
Once Phase 1 is complete, multiple agents can work in isolation:

*   **AGENT 2 (The API Agent):** Works ONLY in `apps/api`. Implements routes, models, and script wrappers. Refer to `specs/BACKEND_API.md`.
*   **AGENT 3 (The Web Agent):** Works ONLY in `apps/web`. Implements UI components and layouts. Refer to `specs/VIEW_MANAGER.md` and `specs/VIEW_PLAYER.md`.
*   **AGENT 4 (The Service Agent):** Works ONLY in `apps/web/src/services` and `hooks`. Implements API clients, stores, and IndexedDB logic. Refer to `specs/FRONTEND_SERVICES.md`.

### Mandatory Rules for All Agents:
1.  **NO INITIALIZATION:** If you are NOT Agent 1, do not run `npm init`, `npx create-*`, or `pip install` globally. Expect the directories and boilerplate to exist.
2.  **PATH RESTRAINT:** Do not modify files outside of your assigned directory.
3.  **COMMUNICATION:** If you need a new API endpoint, the Web Agent must request it from the API Agent (or check the spec) rather than trying to build it themselves.



## How to Use These Specs
1.  **Context:** Read this document first to understand the system boundaries.
2.  **Select Your Task:** Pick a specific spec document (`VIEW_*.md` or `BACKEND_*.md`) to implement.
3.  **Cross-Reference:** 
    *   Frontend Agents: Reference `FRONTEND_SERVICES.md` for data fetching patterns.
    *   Backend Agents: Reference `FEATURE_LIST.md` (root) to ensure no feature regression from the old app.

## Critical Mandates
*   **Zero Regression:** All flags in `AAXtoMP3` (naming schemes, formats) must be exposable via the API/UI.
*   **Real-time Feedback:** The conversion process is slow. The UI must show real-time console output (logs) via WebSockets.
*   **Non-Destructive:** The app works on a user's media library. Never delete files without explicit confirmation.

## Shared Protocols & Data Contracts

### 1. JSON Case Convention
*   **Rule:** The API MUST return **camelCase** JSON keys.
*   **Backend Responsibility:** Use `alias_generator` in Pydantic to convert Python `snake_case` models to `camelCase` JSON.
*   **Frontend Responsibility:** Expect `camelCase`.

### 2. Core DTO: `Book`
Agents must adhere to this structure for the main Library object:
```typescript
interface Book {
  asin: string;              // Primary Key
  title: string;
  author: string;
  narrator?: string;
  series?: {
    title: string;
    sequence?: string;
  };
  duration: number;          // Seconds
  coverUrl: string;
  purchaseDate: string;      // ISO Date
  status: "NEW" | "DOWNLOADING" | "DOWNLOADED" | "CONVERTED" | "FAILED";
  files?: {
    aax?: string;            // Absolute path
    m4b?: string;            // Absolute path
  };
}
```

### 3. WebSocket Protocol (`/ws/jobs`)
Messages sent over the WebSocket must be JSON objects, not raw strings:
```typescript
interface LogMessage {
  jobId: string;
  timestamp: string;
  level: "INFO" | "WARN" | "ERROR" | "PROGRESS";
  payload: string | number; // String for logs, 0-100 number for PROGRESS
}
```

### 4. Authentication Flow (Audible)
Since we cannot embed the Audible login page (iframe protections), we follow a "2-Step External" flow:
1.  **Frontend:** Calls `GET /auth/link` -> Receives external URL.
2.  **User:** Opens URL in new tab, logs in, and copies the "Paste this code" string.
3.  **Frontend:** Show input field "Paste Auth Code".
4.  **Frontend:** Calls `POST /auth/register` with the code.
5.  **Backend:** Runs `audible-cli` registration and saves `auth.json`.


