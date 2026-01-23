# Audible Library API

Modern FastAPI backend for managing Audible libraries, downloads, and conversions.

## Features
- **FastAPI Core**: High-performance asynchronous API.
- **Audible Integration**: Full support for `.aax` and `.aaxc` via `audible` and `audible-cli`.
- **Job Management**: background workers for download and conversion tasks.
- **WebSocket Updates**: Real-time progress tracking for the frontend.
- **Database**: SQLModel/PostgreSQL for persistent state tracking.

## Development

### Setup
1. Ensure Python 3.11+ is installed.
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run the API:
   ```bash
   ./run_dev.sh
   ```

### Architecture
- `api/`: Route definitions and schemas.
- `services/`: Core logic (Audible client, Converter engine, Job manager).
- `db/`: Database models and session management.
- `core/`: Configuration and logging.

## Requirements
- `ffmpeg` (version 4.4+ recommended for `.aaxc` support).
- `audible-cli` (installed in the environment).
