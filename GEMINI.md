# AAXtoMP3 Project Context

## Project Overview
This project provides tools to convert Audible `.aax` and `.aaxc` audiobook files into common DRM-free audio formats like MP3, M4A, M4B, FLAC, and OGG/Opus. It consists of a robust Bash script wrapper around FFmpeg and a modern Streamlit-based web GUI for managing downloads, library validation, and conversion.

The core philosophy is to allow users to archive their legally owned audiobooks. It supports metadata preservation (chapters, covers, tags), custom file/directory naming schemes, and integration with `audible-cli` for enhanced metadata (series information) and `.aaxc` decryption keys.

## Key Components

### 1. Core Conversion Script (`AAXtoMP3`)
*   **Type:** Bash Script
*   **Purpose:** The main engine for conversion. Wraps FFmpeg to handle decryption, transcoding, and metadata tagging.
*   **Key Dependencies:** `ffmpeg`, `ffprobe`, `grep`, `sed`, `find`, `jq` (optional), `mp4v2-utils` (optional for M4B covers), `mediainfo` (optional).
*   **Usage:**
    ```bash
    bash AAXtoMP3 [options] <AAX_FILES>
    ```
*   **Key Flags:**
    *   `--authcode <CODE>`: Decryption key for `.aax` files.
    *   `-e:m4b`, `-e:mp3`: Output format selection.
    *   `--single`: Output a single file.
    *   `--chaptered`: Split by chapter.
    *   `--use-audible-cli-data`: Use external metadata/keys from `audible-cli`.

### 2. Web GUI (`gui/`)
*   **Type:** Python (Streamlit) + Docker
*   **Purpose:** A user-friendly web interface to manage the entire workflow: downloading from Audible, validating files, and converting them.
*   **Entry Points:**
    *   `./start.sh`: Starts the application using Docker Compose.
    *   `app.py`: Main Streamlit application entry point.
*   **Configuration:** Managed via `.env` file (paths, port, timezone).

### 3. Utilities
*   **`setup_env.sh`**: Sets up a local Python virtual environment (`env/`), installs `audible-cli`, and checks for system dependencies (Homebrew).
*   **`interactiveAAXtoMP3`**: An interactive wizard wrapper for the main script.
*   **`copy_audiobooks.sh`**, **`move_m4b_files.py`**: Helpers for organizing output files.

## Setup & Usage

### Local Environment (CLI)
1.  **Dependencies:** Ensure FFmpeg and other tools are installed (`brew install ffmpeg gnu-sed grep findutils` on macOS).
2.  **Python Env:** Run `./setup_env.sh` to create the virtual environment and install `audible-cli`.
3.  **Running:**
    ```bash
    source env/bin/activate
    ./AAXtoMP3 --authcode <YOUR_CODE> -e:m4b --single path/to/book.aax
    ```

### Docker (GUI)
1.  **Navigate:** `cd gui`
2.  **Start:** `./start.sh` (First run will prompt for configuration).
3.  **Access:** Open `http://localhost:8501` (or configured port).
4.  **Manage:** Use the web interface to Authenticate, Download, and Convert.

## Directory Structure
*   **`AAX/`**: Default storage for downloaded `.aax` files.
*   **`M4B/`, `MP3/`, `Audiobooks/`**: Output directories for converted files.
*   **`Metadata/`**: Storage for extracted or generated metadata.
*   **`gui/`**: Source code for the Streamlit web application.
*   **`env/`**: Python virtual environment (ignored by git).

## Development Conventions
*   **Naming Schemes:** The project relies heavily on consistent naming conventions (Author/Book Title) for directory organization. Custom schemes can be defined via flags (e.g., `--dir-naming-scheme`).
*   **Validation:** "Validation" is a distinct step. It checks file integrity before conversion to avoid wasting time on corrupt downloads.
*   **No-Clobber:** Scripts generally respect existing files (`-n` or `--no-clobber`) to prevent accidental overwrites.
*   **Integration:** The project is designed to work closely with `audible-cli` for retrieving keys and advanced metadata that isn't embedded in the AAX file itself.
