# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL: AI Agent Memory Files

The following files are **custom AI agent memory files** and must **NEVER be deleted**:
- `CLAUDE.md` - Memory/instructions for Claude Code
- `AGENTS.md` - Memory/instructions for Codex
- `gemini.md` - Memory/instructions for Gemini

These files contain project-specific context and instructions that persist across sessions. Treat them as sacred configuration.

## Project Overview

AAXtoMP3 is a bash script that converts Audible AAX/AAXC audiobook files to common audio formats (MP3, M4A, M4B, FLAC, Ogg/Opus) using ffmpeg. It handles DRM decryption using the user's personal authcode and supports chapter splitting, custom naming schemes, and integration with audible-cli for enhanced metadata.

## Running the Scripts

**Basic conversion:**
```bash
bash AAXtoMP3 -A <AUTHCODE> <file.aax>
```

**Interactive mode (guided prompts):**
```bash
bash interactiveAAXtoMP3
```

**Common conversion examples:**
```bash
# Convert to M4B (audiobook format)
bash AAXtoMP3 -e:m4b -A <AUTHCODE> file.aax

# Convert to chaptered MP3 (default)
bash AAXtoMP3 -A <AUTHCODE> file.aax

# Convert AAXC files (requires audible-cli data)
bash AAXtoMP3 -e:m4b --use-audible-cli-data file.aaxc

# Validate AAX files without converting
bash AAXtoMP3 -V -A <AUTHCODE> *.aax

# Debug mode (verbose output with timestamps)
bash AAXtoMP3 -d -A <AUTHCODE> file.aax
```

## Architecture

### Core Scripts

- **AAXtoMP3**: Main conversion script (~1000 lines). Handles argument parsing, validation, ffmpeg transcoding, chapter splitting, and metadata extraction.
- **interactiveAAXtoMP3**: Interactive wrapper that prompts users for options and calls AAXtoMP3. Saves user preferences to `.interactivesave` for subsequent runs.

### Key Processing Flow

1. **Argument parsing** (lines 47-109): Command-line options set codec, mode, naming schemes, etc.
2. **Dependency validation** (lines 236-323): Checks for GNU grep/sed/find (required on macOS), ffmpeg/ffprobe, mp4art (optional for cover art), mediainfo (optional for narrator metadata).
3. **AAX validation** (`validate_aax` function, line 407): Tests file existence, metadata validity, and optionally full file integrity.
4. **Metadata extraction** (`save_metadata` function, line 514): Uses ffprobe and optionally mediainfo to extract title, artist, genre, etc.
5. **Transcoding** (line 762): ffmpeg converts the full audiobook with DRM decryption.
6. **Chapter splitting** (chaptered mode, line 824): Parses chapter markers from metadata and splits into individual files.

### Platform Considerations

The script uses GNU versions of grep, sed, and find. On macOS, these must be installed via Homebrew and are prefixed with 'g' (ggrep, gsed, gfind). The script auto-detects the platform (lines 215-223) and sets the appropriate commands.

### AAXC Support

AAXC is Audible's newer encryption format requiring different decryption parameters (audible_key/audible_iv instead of activation_bytes). These are extracted from a `.voucher` file that must be downloaded alongside the AAXC file using audible-cli.

### Custom Naming Schemes

Directory, file, and chapter names can be customized using shell variables like `$title`, `$artist`, `$genre`, `$chapter`, `$series`, `$narrator`. Command substitutions are evaluated, so be careful with user input.

## Testing and Validation

There is no formal test suite. To validate changes:
- Use `bash AAXtoMP3 -V -A <AUTHCODE> <file.aax>` to validate AAX files without transcoding
- Use debug mode (`-d` or `--debug`) for verbose output with timestamps
- Log levels: 0 (progress only), 1 (default), 2 (verbose), 3 (debug)

## Dependencies

**Required:**
- bash 3.2.57+
- ffmpeg 2.8.3+ (4.4+ for AAXC files)
- GNU grep, sed, find (on macOS: `brew install grep gnu-sed findutils`)
- jq (for AAXC files or audible-cli integration)

**Optional:**
- mp4art/mp4chaps (for M4A/M4B cover art and chapters)
- mediainfo (for narrator and description metadata)
- audible-cli (for downloading AAXC files and enhanced metadata)

## Authcode

The authcode is a personal decryption key for AAX files. It can be provided via:
1. `--authcode <CODE>` flag
2. `.authcode` file in current directory
3. `~/.authcode` file (global default)

Not needed for AAXC files (uses voucher-based decryption instead).

## Custom audible-cli Fork (IMPORTANT)

This project uses a **custom fork** of audible-cli, NOT the PyPI version. The custom fork includes:
- `--progress-format ndjson` for structured progress events (required by the download job manager)
- Filename sanitization to replace problematic characters (`/`, `\`, `:`, etc.) in titles

**Repository:** `git+https://github.com/HangryPanda/audible-cli.git@feature/machine-readable-progress`

**After rebuilding the API Docker container, you MUST reinstall the custom fork:**
```bash
# Install git if not present
docker exec audible-api-dev apt-get update && docker exec audible-api-dev apt-get install -y git

# Install custom audible-cli
docker exec audible-api-dev pip install --force-reinstall git+https://github.com/HangryPanda/audible-cli.git@feature/machine-readable-progress
```

**Verification:**
```bash
docker exec audible-api-dev audible download --help | grep "progress-format"
# Should show: --progress-format [tqdm|json|ndjson]
```

The `AUDIBLE_CLI_PROGRESS_FORMAT: ndjson` env var in `docker-compose.dev.yml` requires this custom fork. If downloads fail with `No such option: --progress-format`, the custom fork needs to be reinstalled.
