# [LEGACY] Audible Library Manager (Streamlit)

**⚠️ NOTICE: This Streamlit-based application is deprecated and no longer maintained. It has been replaced by the modern FastAPI + React/Next.js architecture in the `apps/` directory.**

## Current Architecture
Please refer to:
- `apps/api/`: FastAPI Backend
- `apps/web/`: Next.js/React Frontend

---

A web UI to manage your Audible library. Download, validate, and convert audiobooks with full feature parity to the AAXtoMP3 command line tool.

## Quick Start

```bash
cd gui
chmod +x start.sh stop.sh
./start.sh
```

First run will ask for:
- Download directory (where AAXC files go)
- Converted directory (where M4B/MP3 files go)
- Completed directory (where source files move after conversion)
- Port number

Then open `http://your-nas-ip:8501` in your browser.

## Features

### Library Tab

| Button | Action |
|--------|--------|
| **⬇️ Download All** | Download entire library |
| **✅ Validate All** | Check all downloaded files for corruption |
| **🔄 Convert All** | Convert all (auto-resumes interrupted) |
| **🔁 Retry Failed** | Retry failed downloads/conversions |
| **🔄 Refresh** | Reload library from Audible |

### Settings Tab

#### Output Format
- **Audio format**: M4B, M4A, MP3, FLAC, Opus
- **Single/Chaptered**: One file or split by chapter

#### Compression Level
- **MP3**: 0 (best quality) to 9 (fastest)
- **FLAC**: 0 (fastest) to 12 (smallest file)
- **Opus**: 0 (fastest) to 10 (best quality)

#### Naming Schemes
Customize output directory and file names using variables:
- `$title`, `$artist`, `$album_artist`, `$genre`
- `$narrator`, `$series`, `$series_sequence`, `$year`
- Chapter-only: `$chapter`, `$chapternum`, `$chaptercount`

Examples:
- Directory: `$genre/$artist/$title` (default)
- Directory: `$series/$title` (organize by series)
- File: `$title - $narrator`

#### Metadata
- **Override author**: Force a specific author name
- **Keep author #**: If multiple authors, keep only the Nth one (1=first, 2=second)

#### Behavior
- **Skip existing (no-clobber)**: Don't overwrite existing output files
- **Move source after conversion**: Move AAXC files to completed directory
- **Auto-retry**: Automatically retry failed jobs
- **Max retries**: Limit retry attempts

#### Download
- **Cover size**: 500, 1215, or 2400 pixels
- **Auto-export library.tsv**: Enable series metadata for naming schemes

### Status Indicators

| Icon | Meaning |
|------|---------|
| ⏳ Pending | Not downloaded |
| 📥 Ready | Downloaded, ready to convert |
| ✓ Valid | Downloaded and validated |
| ⚠️ Invalid | Validation failed |
| ⏸️ Ch.N | Conversion interrupted at chapter N |
| ✅ Done | Fully converted |
| ❌ Failed | Error occurred |

### Interrupted Conversion Handling

If a conversion is interrupted:
1. The app detects partial chapter files
2. Shows last successful chapter number
3. **▶️ Resume** button continues from that chapter
4. "Convert All" automatically resumes interrupted books

## Commands

| Command | Description |
|---------|-------------|
| `./start.sh` | Start or restart the app |
| `./stop.sh` | Stop the app |
| `docker compose logs -f` | View logs |

## Configuration

Settings in `.env`:

```env
DOWNLOAD_PATH=/path/to/downloads     # AAXC files
CONVERTED_PATH=/path/to/audiobooks   # Output files
COMPLETED_PATH=/path/to/completed    # Source files after conversion
PORT=8501                            # Web UI port
TZ=America/Los_Angeles               # Timezone
```

Edit and run `./start.sh` to apply changes.

## Troubleshooting

### Login fails
1. Try logging into audible.com in a browser first
2. If CAPTCHA/2FA is required, the web login may not work

### Validation fails
- Usually indicates a corrupted download
- Delete the AAXC/voucher files and re-download

### Conversion fails
- Check logs: `docker compose logs -f`
- Ensure the book was downloaded with chapter metadata

### Reset everything
```bash
./stop.sh
docker volume rm gui_audible_data
rm .env
./start.sh
```
