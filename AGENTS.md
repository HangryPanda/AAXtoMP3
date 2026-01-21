# Repository Guidelines

## Project Structure & Module Organization

- `AAXtoMP3`: primary Bash script that validates and converts `.aax/.aaxc` to MP3/M4A/M4B/FLAC/Opus via `ffmpeg`.
- `interactiveAAXtoMP3`: interactive wrapper that prompts for options and calls `AAXtoMP3`.
- `*.sh`, `*.py` in repo root: helper utilities (Audible sync/metadata, environment setup, file moves).
- `gui/`: Streamlit-based “Audible Library Manager” with `docker-compose.yml`, `Dockerfile`, and `app.py`.
- Generated/working data (typically not source): `AAX/`, `Audiobooks/`, `MP3/`, `M4B/`, `Covers/`, `Chapters/`, `Metadata/`, `Vouchers/`, `LibraryData/`, `tmp/`.

## Build, Test, and Development Commands

- `bash AAXtoMP3 -A <AUTHCODE> <file.aax>`: convert a book using your Audible authcode.
- `bash interactiveAAXtoMP3`: guided conversion flow.
- `bash AAXtoMP3 -V -A <AUTHCODE> *.aax`: validate downloads without producing output (useful “smoke test”).
- `./setup_env.sh`: macOS-oriented setup for `audible` CLI in `./env/` (creates venv and authenticates if needed).
- `python3 sync_audible_library_cli.py --help`: sync/export library data and organize downloads into repo folders.
- GUI: `cd gui && ./start.sh` (build/start), `./stop.sh` (stop), `docker compose logs -f` (logs).

## Coding Style & Naming Conventions

- Bash: keep compatibility with Bash 3.2 (macOS default); prefer 2-space indentation; quote variables; avoid associative arrays.
- Python: 4-space indentation; keep scripts runnable via `python3 <script>.py` and add `--help`/`argparse` for new CLIs.
- Naming: new scripts use `snake_case.py` / `snake_case.sh`; keep user-facing flags stable and documented in `README.md`.

## Testing Guidelines

- There is no formal unit-test suite. Validate changes by running `AAXtoMP3 --validate` on a small sample and performing one end-to-end conversion.
- For `gui/`, start the container and verify a single download → validate → convert cycle.

## Commit & Pull Request Guidelines

- Commit history commonly uses Conventional Commit-style prefixes (e.g., `feat: ...`, `fix: ...`) with short, imperative subjects.
- PRs should include: what changed, how you validated (exact commands + OS), and any user-visible behavior changes.
- Do not commit secrets or local config: `.authcode`, `gui/.env`, and `~/.audible/*`.

## Security & Configuration Tips

- `--{dir,file,chapter}-naming-scheme` strings can evaluate shell command substitutions; treat untrusted input as code.

