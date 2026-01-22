# Application Feature List

## Overview
This project provides a comprehensive solution for downloading, managing, and converting Audible audiobooks (.aax/.aaxc) into DRM-free formats. It includes a robust command-line interface (CLI), an interactive terminal wizard, and a modern web-based graphical user interface (GUI).

## Core Conversion Engine (`AAXtoMP3`)
The backbone of the application is a Bash script wrapping FFmpeg.

### Input/Output
- **Input Formats:** Supports both legacy `.aax` and modern `.aaxc` Audible formats.
- **Output Formats:**
  - **MP3:** Standard audio format (default).
  - **M4A / M4B:** Apple MPEG-4 audio (M4B preferred for audiobooks).
  - **FLAC:** Lossless Free Lossless Audio Codec.
  - **OGG/Opus:** High-efficiency Opus coding in Ogg container.
- **Modes:**
  - **Single File:** Merges the entire audiobook into one file.
  - **Chaptered:** Splits output into individual files per chapter.

### Processing & Metadata
- **Decryption:** Handles DRM removal using user-provided Authcodes or AAXC keys/vouchers.
- **Metadata Preservation:** Retains standard tags (Artist, Title, Album, etc.).
- **Advanced Tagging:**
  - **Cover Art:** Embeds high-quality cover art (requires `mp4v2-utils` for M4A/M4B).
  - **Extended Tags:** Adds narrator and description tags (requires `mediainfo`).
- **Naming Schemes:** Fully customizable file and directory naming using variables:
  - `$genre`, `$artist`, `$title`, `$narrator`, `$series`, `$series_sequence`.
- **Validation:**
  - **Quick Check:** Validates file headers.
  - **Full Validation:** Transcodes to null to ensure file integrity before processing.
- **Concurrency:** Basic parallel processing support via batch input.

## User Interfaces

### 1. Web GUI (Streamlit)
A modern web interface for managing the entire workflow.
- **Library Management:**
  - **Sync:** Fetches user library directly from Audible using `audible-cli` integration.
  - **Visualization:** Grid view of books with cover art, metadata, and series info.
  - **Search & Filter:** Filter by status (Downloaded, Converted, Queued) or search text.
  - **Status Tracking:** Real-time tracking of download and conversion states.
- **Operations:**
  - **Download:** Direct download of AAX/AAXC files from Audible.
  - **Convert:** Trigger conversions with configurable settings directly from the UI.
  - **Batch Processing:** Queue multiple books for download or conversion.
- **Configuration:**
  - Output format selection (MP3, M4B, etc.).
  - Compression level adjustment.
  - Custom naming scheme configuration.
  - File management options (No Clobber, Move to Completed).

### 2. Interactive CLI (`interactiveAAXtoMP3`)
A wizard-style wrapper for the command line.
- **Guided Experience:** Step-by-step prompts for codec, quality, and mode selection.
- **State Persistence:** Remembers user choices (last used codec, authcode, etc.) for faster subsequent runs.
- **Compatibility:** Auto-detects system tools (`grep` vs `ggrep`, `sed` vs `gsed`) for macOS/Linux compatibility.

### 3. Command Line Interface (CLI)
- **Full Control:** Exposes all flags and options for advanced users and automation scripts.
- **Batching:** Accepts multiple input files or wildcards for bulk processing.

## System & Integration Features

### Environment & Setup
- **Dependency Management:**
  - `get_and_convert_audiobooks.sh` automates the check and installation of external tools (`mp4art`, `mediainfo`) on macOS (Homebrew) and Linux (apt/yum).
- **Docker Support:** Full containerization of the Web GUI for easy deployment.
- **Virtual Environment:** Python venv support for isolating `audible-cli` dependencies.

### External Integrations
- **Audible CLI:** Tight integration for:
  - Retrieving decryption keys (activation bytes).
  - Fetching high-resolution cover art.
  - Downloading detailed chapter metadata (titles, durations).
- **Metadata Aggregation:**
  - `generate_audiobook_metadata.py` scans local files and generates a comprehensive `audiobook_library.json` using `audible-cli`.

## Utility Scripts
- **`sync_audible_library_cli.py`:** Command-line version of the library synchronization logic.
- **`move_m4b_files.py` / `copy_audiobooks.sh`:** Helpers for organizing and archiving converted files.
