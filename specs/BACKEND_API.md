# Specification: Backend API & Architecture

## Overview
The backend replaces the direct Streamlit logic. It exposes a REST API to manage the Audible library and orchestrates the execution of the legacy bash scripts (`AAXtoMP3`) and python tools (`audible-cli`).

## Tech Stack
*   **Framework:** Python 3.10+ with **FastAPI**.
*   **Asynchronous:** Full async/await support for non-blocking I/O.
*   **Database:** SQLite (MVP) or PostgreSQL. *Use `SQLModel` or `SQLAlchemy` for ORM.*
*   **Job Orchestration:** Custom `asyncio` Task Manager with separate semaphores for IO vs CPU bound tasks. (See Section 6).

## Target Dependencies (Python)
The agents should install these specific versions (or newer):

```text
# Core Framework
fastapi>=0.109.0
uvicorn[standard]>=0.27.0   # ASGI Server
pydantic>=2.5.0             # Data validation
pydantic-settings>=2.1.0    # 12-factor configuration

# Database
sqlmodel>=0.0.14            # SQLAlchemy + Pydantic wrapper
alembic>=1.13.0             # Migrations
aiosqlite>=0.19.0           # Async SQLite driver

# Utilities
httpx>=0.26.0               # Async HTTP client (for calling Audible/External APIs)
aiofiles>=23.2.1            # Async file I/O
python-multipart>=0.0.6     # Form data parsing
jinja2>=3.1.3               # Templating (if needed for emails/simple views)

# Domain Specific
audible>=0.9.1              # The existing audible-cli library
```

## Core Modules

### 1. API Layer (`apps/api`)
*   **Standard:** RESTful JSON API.
*   **Documentation:** Auto-generated OpenAPI (Swagger) docs at `/docs`.

#### Key Endpoints
*   **GET /library**: List books.
    *   *Delta Sync Support:* Accept `?since={timestamp}` query param. Return only records modified/created after this time to allow efficient frontend IndexDB updates.
*   **GET /library/{asin}**: Get details.
*   **POST /library/sync**: Trigger `audible-cli` library refresh.
*   **POST /jobs/download**: Queue a download for an ASIN.
*   **POST /jobs/convert**: Queue a conversion for an ASIN.
    *   *Payload:* `{ "asin": "...", "format": "m4b", "naming_scheme": "..." }`
*   **GET /jobs**: List active jobs.
*   **WS /ws/jobs**: WebSocket for real-time logs/progress.
*   **GET /stream/{file_id}**: Serve audio file with Range support.

### 2. Domain Logic: Wrapper Service
*   **Purpose:** Interface with the existing Shell/CLI tools.
*   **`AudibleClient` Class:**
    *   Wraps `audible-cli` (subprocess or library import).
    *   Handles Auth Profile management (`auth.json`).
*   **`ConverterEngine` Class:**
    *   Wraps `AAXtoMP3` bash script.
    *   Constructs command-line arguments safely.
    *   Captures `stdout`/`stderr` line-by-line to push to the Job Queue log stream.

### 3. Data Model (Database)
*   **Table: Books**
    *   `asin` (PK), `title`, `author`, `metadata_json` (blob), `cover_url`, `status` (Enum: NEW, DOWNLOADING, DOWNLOADED, CONVERTING, COMPLETED).
    *   `local_path_aax`, `local_path_converted`.
*   **Table: Jobs**
    *   `id` (UUID), `task_type` (DOWNLOAD/CONVERT), `status` (PENDING, RUNNING, COMPLETED, FAILED), `progress_percent`, `log_file_path`, `created_at`.

### 4. File System Manager
*   **Responsibility:** Ensure atomic file operations.
*   **Structure:**
    *   `/data/library` (Metadata DB)
    *   `/data/downloads` (Raw AAX)
    *   `/data/converted` (Final MP3/M4B)
*   **Safety:** Check disk space before starting jobs. Respect "No Clobber" rules.

## 5. Performance & Large File Strategy

### Audio Streaming (The "Zero-Copy" Goal)
*   **Problem:** M4B files are 500MB+. Reading them into Python memory (RAM) will crash the server under load.
*   **Solution:** Use Starlette's `FileResponse`.
    *   *Mechanism:* It uses a thread pool to offload file I/O and supports HTTP `Range` headers (seeking) out of the box.
    *   *Directive:* NEVER use `open()` + `read()` for audio endpoints. Always return `FileResponse(path, media_type="audio/mp4", filename=...)`.

### FFmpeg Orchestration
*   **Problem:** Video/Audio conversion is CPU bound.
*   **Solution:** Use `asyncio.create_subprocess_exec`.
    *   *Directive:* The API event loop must *never* be blocked by a conversion.
    *   *Pattern:*
        ```python
        process = await asyncio.create_subprocess_exec(
            "bash", "AAXtoMP3", ...,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        ```
    *   *Logs:* Read `stdout` stream line-by-line asynchronously to push to WebSockets.

## 6. Job Orchestration (Concurrency)

### The `JobManager` Service
The agent must implement a manager that allows Downloads and Conversions to run **simultaneously** but with different limits.

*   **Queue 1: Downloads (IO-Bound)**
    *   *Limit:* **5 Concurrent**.
    *   *Rationale:* Bandwidth is the bottleneck.
*   **Queue 2: Conversions (CPU-Bound)**
    *   *Limit:* **Max 2 Concurrent** (or `os.cpu_count() / 2`).
    *   *Rationale:* FFmpeg is heavy. Running 5 at once will freeze the host.
*   **Implementation:**
    *   Use `asyncio.Semaphore(5)` for downloads.
    *   Use `asyncio.Semaphore(2)` for conversions.
    *   The `POST /jobs/...` endpoints should **immediately** return a Job ID (202 Accepted) and spawn the background task, which then waits on its respective semaphore.

## Security & Auth
*   **App Auth:** Simple API Key or Basic Auth for the Web UI (single-user mode default).
*   **Audible Auth:** reuse existing `auth.json` mechanism but expose a UI flow to generate it (Open `audible-cli` login URL, paste code).

## Directory Structure (Backend)
```
apps/api/
├── main.py              # App Entrypoint
├── api/
│   ├── routes/          # Route controllers
│   └── dependencies.py  # DI
├── core/
│   ├── config.py        # Env vars
│   └── events.py        # Startup/Shutdown
├── services/
│   ├── audible_wrapper.py
│   ├── converter_wrapper.py  # The "Bridge" to AAXtoMP3
│   └── job_manager.py
├── db/
│   ├── models.py
│   └── session.py
└── utils/
```
