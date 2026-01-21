import streamlit as st
import streamlit.components.v1 as components
import audible
import audible.login
try:
    import tomllib
except ImportError:
    import toml as tomllib # Fallback if needed, though 3.11 has tomllib
from audible.localization import Locale
from audible.login import extract_code_from_url
from audible.register import register as register_device
import httpx
import json
import base64
from pathlib import Path
from datetime import datetime
import subprocess
import time
import re
import shutil
import os
import signal

# Configuration
AUTH_FILE = Path("/data/auth.json")
LIBRARY_CACHE = Path("/data/library_cache.json")
SETTINGS_FILE = Path("/data/settings.json")
DOWNLOAD_DIR = Path("/downloads")
CONVERTED_DIR = Path("/converted")
COMPLETED_DIR = Path("/completed")  # For moving source files after conversion
LIBRARY_BACKUPS_DIR = Path("/library_backups")
JOB_STATUS_FILE = Path("/data/job_status.json")
LIBRARY_TSV_FILE = Path("/data/library.tsv")
DOWNLOAD_JOB_FILE = Path("/data/download_job.json")
DOWNLOAD_ALL_LOG = Path("/data/download_all.log")
DOWNLOAD_BATCH_LOG = Path("/data/download_batch.log")

# Keep conservative defaults to reduce the risk of Amazon/Audible rate limiting.
MAX_PARALLEL_DOWNLOADS = 5

CONVERT_JOB_FILE = Path("/data/convert_job.json")
CONVERT_ALL_LOG = Path("/data/convert_all.log")

# Conversions are CPU+IO heavy; keep a reasonable cap for NAS hardware.
MAX_PARALLEL_CONVERSIONS = 4

LIBRARY_JOB_FILE = Path("/data/library_job.json")
LIBRARY_REFRESH_LOG = Path("/data/library_refresh.log")

st.set_page_config(
    page_title="Audible Library Manager",
    page_icon="📚",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
        /* Global & Layout */
        section.main > div.block-container {
            max-width: 1200px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }
        
        /* Metric Cards */
        div[data-testid="stMetric"] {
            background-color: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.1);
            padding: 1rem;
            border-radius: 0.75rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        div[data-testid="stMetric"] label { font-size: 0.85rem; opacity: 0.8; }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: 700; }

        /* ===== Book Card Styling ===== */
        /* Target the container wrapping our row marker */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.aa-row-marker) {
            border: 1px solid rgba(128, 128, 128, 0.15) !important;
            border-radius: 0.75rem !important;
            background-color: var(--secondary-background-color);
            padding: 1rem !important;
            margin-bottom: 0.75rem;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        
        /* Hover Effect */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.aa-row-marker):hover {
            border-color: rgba(128, 128, 128, 0.35) !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.08);
            transform: translateY(-1px);
        }

        /* Typography */
        .aa-title {
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--text-color);
            line-height: 1.3;
            margin-bottom: 0.25rem;
        }
        .aa-author {
            font-size: 0.95rem;
            color: var(--text-color);
            opacity: 0.85;
            margin-bottom: 0.2rem;
        }
        .aa-meta-row {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            flex-wrap: wrap;
            font-size: 0.8rem;
            opacity: 0.7;
            margin-top: 0.25rem;
        }
        .aa-meta-item {
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }

        /* Badges / Pills */
        .aa-pill {
            display: inline-flex;
            align-items: center;
            padding: 0.15rem 0.5rem;
            border-radius: 99px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .aa-pill--series {
            background-color: rgba(128, 128, 128, 0.1);
            color: var(--text-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            font-size: 0.75rem;
            text-transform: none;
            letter-spacing: normal;
        }
        
        /* Status Colors */
        .status-success { color: #2ecc71; background: rgba(46, 204, 113, 0.1); border: 1px solid rgba(46, 204, 113, 0.2); }
        .status-warning { color: #f1c40f; background: rgba(241, 196, 15, 0.1); border: 1px solid rgba(241, 196, 15, 0.2); }
        .status-danger  { color: #e74c3c; background: rgba(231, 76, 60, 0.1); border: 1px solid rgba(231, 76, 60, 0.2); }
        .status-info    { color: #3498db; background: rgba(52, 152, 219, 0.1); border: 1px solid rgba(52, 152, 219, 0.2); }
        .status-neutral { color: var(--text-color); opacity: 0.6; background: rgba(128, 128, 128, 0.1); border: 1px solid rgba(128, 128, 128, 0.2); }

        /* Expander Styling Cleanup */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.aa-row-marker) details {
            border: none !important;
            margin-top: 0.5rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.aa-row-marker) summary {
            font-size: 0.8rem;
            opacity: 0.6;
            padding-left: 0;
            list-style: none; /* Attempt to hide triangle, depends on browser */
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.aa-row-marker) summary:hover {
            opacity: 1;
            color: var(--primary-color);
        }

        /* Hide the 'aa-row-marker' span itself */
        .aa-row-marker { display: none; }
    </style>
""", unsafe_allow_html=True)

# ============== SETTINGS ==============

DEFAULT_SETTINGS = {
    # Output format
    "output_format": "m4b",
    "single_file": True,

    # Compression (format-specific)
    "compression_mp3": 4,      # 0-9, lower = better quality
    "compression_flac": 5,     # 0-12, higher = smaller file
    "compression_opus": 5,     # 0-10, higher = better quality

    # Download
    "cover_size": "1215",

    # Naming schemes
    "dir_naming_scheme": "$genre/$artist/$title",
    "file_naming_scheme": "$title",
    "chapter_naming_scheme": "",  # Empty = use default

    # Behavior
    "no_clobber": False,           # Skip if output exists
    "move_after_complete": False,  # Move source to completed dir
    "auto_retry": True,
    "max_retries": 3,

    # Metadata
    "author_override": "",         # Override author name
    "keep_author_index": 0,        # 0 = all, 1+ = specific author

    # Library
    "auto_export_library": True,   # Export library.tsv for series metadata
    "selected_library_backups": [], # List of backup filenames to use
}

# Compression level ranges per format
COMPRESSION_RANGES = {
    "mp3": {"min": 0, "max": 9, "help": "0 = best quality, 9 = fastest"},
    "flac": {"min": 0, "max": 12, "help": "0 = fastest, 12 = smallest file"},
    "opus": {"min": 0, "max": 10, "help": "0 = fastest, 10 = best quality"},
}

# Naming scheme variables
NAMING_VARIABLES = ["$title", "$artist", "$album_artist", "$genre", "$narrator", "$series", "$series_sequence", "$year"]
CHAPTER_NAMING_VARIABLES = NAMING_VARIABLES + ["$chapter", "$chapternum", "$chaptercount"]


def load_settings():
    """Load settings from file."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
                return {**DEFAULT_SETTINGS, **saved}
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    """Save settings to file."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


# ============== JOB STATUS ==============

def load_job_status():
    """Load job status (failed downloads, interrupted conversions)."""
    if JOB_STATUS_FILE.exists():
        try:
            with open(JOB_STATUS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"failed_downloads": {}, "failed_conversions": {}, "interrupted": {}, "validated": {}}


def save_job_status(status):
    """Save job status."""
    JOB_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(JOB_STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)


def load_converted_manifest():
    """Load the detailed conversion manifest from worker.py."""
    manifest_path = Path("/data/converted_manifest.json")
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def mark_download_failed(asin, title, error=""):
    """Mark a download as failed."""
    status = load_job_status()
    status["failed_downloads"][asin] = {
        "title": title,
        "error": error,
        "retries": status["failed_downloads"].get(asin, {}).get("retries", 0) + 1,
        "timestamp": datetime.now().isoformat()
    }
    save_job_status(status)

def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

def load_download_job():
    if DOWNLOAD_JOB_FILE.exists():
        try:
            with open(DOWNLOAD_JOB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def save_download_job(job):
    DOWNLOAD_JOB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DOWNLOAD_JOB_FILE, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2)

def clear_download_job():
    DOWNLOAD_JOB_FILE.unlink(missing_ok=True)

def start_download_all_job(settings, jobs=3):
    existing = load_download_job()
    if existing and _pid_alive(existing.get("pid", 0)):
        return False, "Download job already running"

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_ALL_LOG.parent.mkdir(parents=True, exist_ok=True)

    jobs = max(1, min(int(jobs), MAX_PARALLEL_DOWNLOADS))

    cmd = [
        "audible", "download",
        "--all",
        "--aaxc",
        "--cover", "--cover-size", settings.get("cover_size", "1215"),
        "--chapter",
        "--filename-mode", "asin_unicode",
        "--jobs", str(int(jobs)),
        "--ignore-errors",
        "--no-confirm",
        "--output-dir", str(DOWNLOAD_DIR),
    ]

    log_f = open(DOWNLOAD_ALL_LOG, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        cwd=str(DOWNLOAD_DIR),
        preexec_fn=os.setsid,
        text=True,
    )

    job = {
        "kind": "download_all",
        "pid": proc.pid,
        "pgid": os.getpgid(proc.pid),
        "started_at": datetime.now().isoformat(),
        "paused": False,
        "jobs": int(jobs),
        "cmd": cmd,
        "log_path": str(DOWNLOAD_ALL_LOG),
    }
    save_download_job(job)
    return True, ""


def start_batch_download_job(asins, settings, jobs=3):
    existing = load_download_job()
    if existing and _pid_alive(existing.get("pid", 0)):
        return False, "Download job already running"
    
    if not asins:
        return False, "No items to download"

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_BATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    jobs = max(1, min(int(jobs), MAX_PARALLEL_DOWNLOADS))
    cover_size = settings.get("cover_size", "1215")
    asins_str = ",".join(asins)

    cmd = [
        "python", "/app/worker.py", "download-batch",
        "--asins", asins_str,
        "--cover-size", cover_size,
        "--max-parallel", str(jobs)
    ]

    log_f = open(DOWNLOAD_BATCH_LOG, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        cwd=str(DOWNLOAD_DIR),
        preexec_fn=os.setsid,
        text=True,
    )

    job = {
        "kind": "download_batch",
        "pid": proc.pid,
        "pgid": os.getpgid(proc.pid),
        "started_at": datetime.now().isoformat(),
        "paused": False,
        "jobs": int(jobs),
        "cmd": cmd,
        "log_path": str(DOWNLOAD_BATCH_LOG),
        "item_count": len(asins)
    }
    save_download_job(job)
    return True, ""


CONVERT_BATCH_LOG = Path("/data/convert_batch.log")

def start_batch_convert_job(asins, settings, jobs=3, paths=None):
    # Note: We don't check for existing batch convert jobs because we might want to
    # queue multiple batches or they might be different items.
    # However, for simplicity in UI tracking, let's limit to one explicit batch at a time for now
    # or just fire-and-forget.
    # Fire-and-forget is better for "clicking convert on multiple items".

    if not asins:
        return False, "No items to convert"

    CONVERT_BATCH_LOG.parent.mkdir(parents=True, exist_ok=True)

    jobs = max(1, min(int(jobs), MAX_PARALLEL_CONVERSIONS))
    asins_str = ",".join(asins)

    cmd = [
        "python", "/app/worker.py", "convert-batch",
        "--asins", asins_str,
        "--max-parallel", str(jobs)
    ]

    # Pass file paths if provided (enables reliable matching for files without ASIN in name)
    if paths:
        paths_str = ",".join(str(p) for p in paths)
        cmd.extend(["--paths", paths_str])

    log_f = open(CONVERT_BATCH_LOG, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        cwd=str(DOWNLOAD_DIR),
        preexec_fn=os.setsid,
        text=True,
    )
    
    # We don't strictly track this job in a file for now, 
    # relying on the logs and the file-locks in worker.py to manage concurrency.
    return True, ""

def _signal_job(sig):
    job = load_download_job()
    if not job:
        return False, "No job"
    pid = job.get("pid", 0)
    pgid = job.get("pgid", 0)
    if not pid or not _pid_alive(pid):
        return False, "Job not running"
    try:
        os.killpg(int(pgid), sig)
        return True, ""
    except Exception as e:
        return False, str(e)

def pause_download_job():
    ok, err = _signal_job(signal.SIGSTOP)
    if ok:
        job = load_download_job() or {}
        job["paused"] = True
        save_download_job(job)
    return ok, err

def resume_download_job():
    ok, err = _signal_job(signal.SIGCONT)
    if ok:
        job = load_download_job() or {}
        job["paused"] = False
        save_download_job(job)
    return ok, err

def stop_download_job():
    job = load_download_job()
    if not job:
        return False, "No job"
    pid = job.get("pid", 0)
    pgid = job.get("pgid", 0)
    if not pid or not _pid_alive(pid):
        clear_download_job()
        return True, "Job already stopped"
    try:
        os.killpg(int(pgid), signal.SIGTERM)
        time.sleep(1.0)
        if _pid_alive(pid):
            os.killpg(int(pgid), signal.SIGKILL)
        clear_download_job()
        return True, ""
    except Exception as e:
        return False, str(e)

def _tail_log(path: Path, max_lines=80):
    try:
        if not path.exists():
            return ""
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return "".join(lines[-max_lines:])
    except Exception:
        return ""


def render_activity_log_drawer():
    """Render a drawer-style activity log with copy to clipboard functionality."""
    # Gather all logs
    combined_log = _tail_log(DOWNLOAD_ALL_LOG, 10) + \
                   _tail_log(DOWNLOAD_BATCH_LOG, 10) + \
                   _tail_log(CONVERT_ALL_LOG, 15) + \
                   _tail_log(CONVERT_BATCH_LOG, 15)

    # Clean up extra blank lines
    lines = [line for line in combined_log.split('\n') if line.strip()]
    combined_log = '\n'.join(lines[-30:])  # Keep last 30 non-empty lines

    if not combined_log.strip():
        combined_log = "No recent activity"

    # Escape for JavaScript
    log_escaped = combined_log.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')

    # Generate unique ID for this component
    drawer_id = f"activity_drawer_{id(combined_log) % 10000}"

    drawer_html = f"""
    <style>
        .activity-drawer {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 9999;
            font-family: 'Source Code Pro', 'Monaco', 'Menlo', monospace;
        }}
        .drawer-toggle {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            padding: 8px 16px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid #333;
            user-select: none;
        }}
        .drawer-toggle:hover {{
            background: linear-gradient(135deg, #1f1f3a 0%, #1a2744 100%);
        }}
        .drawer-title {{
            font-weight: 600;
            font-size: 14px;
        }}
        .drawer-actions {{
            display: flex;
            gap: 8px;
        }}
        .drawer-btn {{
            background: #2d3748;
            border: 1px solid #4a5568;
            color: #e0e0e0;
            padding: 4px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }}
        .drawer-btn:hover {{
            background: #4a5568;
            border-color: #718096;
        }}
        .drawer-btn.copied {{
            background: #276749;
            border-color: #48bb78;
        }}
        .drawer-content {{
            background: #0d1117;
            color: #c9d1d9;
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
            border-top: 1px solid #333;
        }}
        .drawer-content.open {{
            max-height: 300px;
            overflow-y: auto;
        }}
        .drawer-content pre {{
            margin: 0;
            padding: 12px 16px;
            font-size: 12px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .drawer-content::-webkit-scrollbar {{
            width: 8px;
        }}
        .drawer-content::-webkit-scrollbar-track {{
            background: #1a1a2e;
        }}
        .drawer-content::-webkit-scrollbar-thumb {{
            background: #4a5568;
            border-radius: 4px;
        }}
        .chevron {{
            transition: transform 0.3s;
        }}
        .chevron.open {{
            transform: rotate(180deg);
        }}
    </style>

    <div class="activity-drawer" id="{drawer_id}">
        <div class="drawer-toggle" onclick="toggleDrawer_{drawer_id}()">
            <span class="drawer-title">📡 Activity Log</span>
            <div class="drawer-actions">
                <button class="drawer-btn" id="copy_btn_{drawer_id}" onclick="event.stopPropagation(); copyLog_{drawer_id}()">
                    📋 Copy
                </button>
                <button class="drawer-btn" onclick="event.stopPropagation(); clearLog_{drawer_id}()">
                    🗑️ Clear
                </button>
                <span class="chevron" id="chevron_{drawer_id}">▲</span>
            </div>
        </div>
        <div class="drawer-content" id="content_{drawer_id}">
            <pre id="log_text_{drawer_id}">{combined_log}</pre>
        </div>
    </div>

    <script>
        const logText_{drawer_id} = `{log_escaped}`;

        function toggleDrawer_{drawer_id}() {{
            const content = document.getElementById('content_{drawer_id}');
            const chevron = document.getElementById('chevron_{drawer_id}');
            content.classList.toggle('open');
            chevron.classList.toggle('open');

            // Auto-scroll to bottom when opened
            if (content.classList.contains('open')) {{
                content.scrollTop = content.scrollHeight;
            }}
        }}

        function copyLog_{drawer_id}() {{
            const text = document.getElementById('log_text_{drawer_id}').textContent;
            navigator.clipboard.writeText(text).then(() => {{
                const btn = document.getElementById('copy_btn_{drawer_id}');
                const originalText = btn.textContent;
                btn.textContent = '✓ Copied!';
                btn.classList.add('copied');
                setTimeout(() => {{
                    btn.textContent = originalText;
                    btn.classList.remove('copied');
                }}, 2000);
            }}).catch(err => {{
                // Fallback for older browsers
                const textarea = document.createElement('textarea');
                textarea.value = text;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);

                const btn = document.getElementById('copy_btn_{drawer_id}');
                btn.textContent = '✓ Copied!';
                btn.classList.add('copied');
                setTimeout(() => {{
                    btn.textContent = '📋 Copy';
                    btn.classList.remove('copied');
                }}, 2000);
            }});
        }}

        function clearLog_{drawer_id}() {{
            document.getElementById('log_text_{drawer_id}').textContent = 'Log cleared (refresh to reload)';
        }}

        // Auto-open drawer if there's activity
        if (logText_{drawer_id}.trim() && logText_{drawer_id}.trim() !== 'No recent activity') {{
            // Keep closed by default, user can open
        }}
    </script>
    """

    components.html(drawer_html, height=45)


def load_library_job():
    if LIBRARY_JOB_FILE.exists():
        try:
            with open(LIBRARY_JOB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def start_library_refresh_job(num_results=1000):
    job = load_library_job()
    if job and job.get("status") == "running":
        return False, "Library refresh already running"

    LIBRARY_REFRESH_LOG.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["python", "/app/worker.py", "library-fetch", "--num-results", str(int(num_results))]
    log_f = open(LIBRARY_REFRESH_LOG, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        cwd=str(Path("/data")),
        preexec_fn=os.setsid,
        text=True,
    )

    LIBRARY_JOB_FILE.write_text(
        json.dumps(
            {
                "status": "running",
                "pid": proc.pid,
                "pgid": os.getpgid(proc.pid),
                "started_at": datetime.now().isoformat(),
                "num_results": int(num_results),
                "cmd": cmd,
                "log_path": str(LIBRARY_REFRESH_LOG),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return True, ""

def ensure_library_cache_background():
    """
    Ensure a full library cache exists without blocking the UI.
    If missing/stale, kick off a background refresh and return cached (if any).
    """
    if LIBRARY_CACHE.exists():
        cache_age = datetime.now().timestamp() - LIBRARY_CACHE.stat().st_mtime
        if cache_age < 3600:
            try:
                with open(LIBRARY_CACHE, "r", encoding="utf-8") as f:
                    return json.load(f), False
            except Exception:
                pass

    # Kick off refresh if not already running.
    job = load_library_job()
    if not (job and job.get("status") == "running"):
        start_library_refresh_job(num_results=1000)

    # Return whatever we have (may be empty) and signal that we're refreshing.
    if LIBRARY_CACHE.exists():
        try:
            with open(LIBRARY_CACHE, "r", encoding="utf-8") as f:
                return json.load(f), True
        except Exception:
            return [], True
    return [], True

def load_convert_job():
    if CONVERT_JOB_FILE.exists():
        try:
            with open(CONVERT_JOB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def save_convert_job(job):
    CONVERT_JOB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONVERT_JOB_FILE, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2)

def clear_convert_job():
    CONVERT_JOB_FILE.unlink(missing_ok=True)

def start_convert_watch_job(poll_seconds=10, max_parallel=1):
    existing = load_convert_job()
    if existing and _pid_alive(existing.get("pid", 0)):
        return False, "Convert job already running"

    CONVERTED_DIR.mkdir(parents=True, exist_ok=True)
    CONVERT_ALL_LOG.parent.mkdir(parents=True, exist_ok=True)

    max_parallel = max(1, min(int(max_parallel), MAX_PARALLEL_CONVERSIONS))
    cmd = [
        "python",
        "/app/worker.py",
        "convert-watch",
        "--poll-seconds",
        str(int(poll_seconds)),
        "--max-parallel",
        str(int(max_parallel)),
    ]
    log_f = open(CONVERT_ALL_LOG, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        cwd=str(DOWNLOAD_DIR),
        preexec_fn=os.setsid,
        text=True,
    )

    job = {
        "kind": "convert_watch",
        "pid": proc.pid,
        "pgid": os.getpgid(proc.pid),
        "started_at": datetime.now().isoformat(),
        "paused": False,
        "poll_seconds": int(poll_seconds),
        "max_parallel": int(max_parallel),
        "cmd": cmd,
        "log_path": str(CONVERT_ALL_LOG),
    }
    save_convert_job(job)
    return True, ""

def _signal_convert_job(sig):
    job = load_convert_job()
    if not job:
        return False, "No job"
    pid = job.get("pid", 0)
    pgid = job.get("pgid", 0)
    if not pid or not _pid_alive(pid):
        return False, "Job not running"
    try:
        os.killpg(int(pgid), sig)
        return True, ""
    except Exception as e:
        return False, str(e)

def pause_convert_job():
    ok, err = _signal_convert_job(signal.SIGSTOP)
    if ok:
        job = load_convert_job() or {}
        job["paused"] = True
        save_convert_job(job)
    return ok, err

def resume_convert_job():
    ok, err = _signal_convert_job(signal.SIGCONT)
    if ok:
        job = load_convert_job() or {}
        job["paused"] = False
        save_convert_job(job)
    return ok, err

def stop_convert_job():
    job = load_convert_job()
    if not job:
        return False, "No job"
    pid = job.get("pid", 0)
    pgid = job.get("pgid", 0)
    if not pid or not _pid_alive(pid):
        clear_convert_job()
        return True, "Job already stopped"
    try:
        os.killpg(int(pgid), signal.SIGTERM)
        time.sleep(1.0)
        if _pid_alive(pid):
            os.killpg(int(pgid), signal.SIGKILL)
        clear_convert_job()
        return True, ""
    except Exception as e:
        return False, str(e)


def mark_download_success(asin):
    """Remove from failed list on success."""
    status = load_job_status()
    status["failed_downloads"].pop(asin, None)
    save_job_status(status)


def mark_conversion_failed(asin, title, error="", last_chapter=None):
    """Mark a conversion as failed/interrupted."""
    status = load_job_status()
    status["failed_conversions"][asin] = {
        "title": title,
        "error": error,
        "last_chapter": last_chapter,
        "retries": status["failed_conversions"].get(asin, {}).get("retries", 0) + 1,
        "timestamp": datetime.now().isoformat()
    }
    save_job_status(status)


def mark_conversion_success(asin):
    """Remove from failed list on success."""
    status = load_job_status()
    status["failed_conversions"].pop(asin, None)
    status["interrupted"].pop(asin, None)
    save_job_status(status)


def mark_validated(asin, valid, error=""):
    """Mark a file as validated."""
    status = load_job_status()
    status["validated"][asin] = {
        "valid": valid,
        "error": error,
        "timestamp": datetime.now().isoformat()
    }
    save_job_status(status)


# ============== AUTH ==============

def log_debug(msg):
    with open("/data/debug.log", "a") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")

def _normalize_locale_code(raw):
    if raw is None:
        return "us"
    code = str(raw).strip()
    if not code:
        return "us"
    code = code.replace("-", "_").lower()
    # Handle values like "en_US" / "en-us" by converting to the marketplace code ("us").
    if len(code) == 5 and "_" in code:
        _, cc = code.split("_", 1)
        code = cc
    # Common alias: Audible CLI sometimes uses GB, Audible uses UK.
    if code == "gb":
        code = "uk"
    return code

def _locale_arg(raw):
    code = _normalize_locale_code(raw)
    try:
        return Locale(code)
    except Exception:
        return code

def _read_locale_code_from_auth_file(auth_path: Path):
    try:
        if not auth_path.exists():
            return None
        with open(auth_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("locale_code")
    except Exception:
        return None

def get_locale_from_config():
    """Determine locale (prefer auth locale, then audible-cli config)."""
    host_audible_config = Path("/host_audible")
    audible_cli_config = Path("/root/.audible")
    
    log_debug(f"Checking for config in: {host_audible_config}, {audible_cli_config}")

    # Prefer locale embedded in auth files (most reliable, avoids config mismatches).
    for auth_path in [AUTH_FILE, host_audible_config / "audibleAuth", audible_cli_config / "audibleAuth"]:
        locale_code = _read_locale_code_from_auth_file(auth_path)
        if locale_code:
            log_debug(f"Found locale_code='{locale_code}' in {auth_path}")
            return _locale_arg(locale_code)
    
    for config_path in [host_audible_config, audible_cli_config]:
        if config_path.exists():
            log_debug(f"Found config path: {config_path}")
            config_toml = config_path / "config.toml"
            if config_toml.exists():
                try:
                    with open(config_toml, "rb") as f:
                        data = tomllib.load(f)
                        primary = data.get("APP", {}).get("primary_profile")
                        log_debug(f"Primary profile: {primary}")
                        if primary:
                            code = data.get("profile", {}).get(primary, {}).get("country_code", "us")
                            log_debug(f"Found country code: {code}")
                            return _locale_arg(code)
                except Exception as e:
                    log_debug(f"Error reading config: {e}")
                    pass
    log_debug("Defaulting to 'us'")
    return _locale_arg("us")


def get_auth():
    """Load existing authentication."""
    if AUTH_FILE.exists():
        try:
            locale = get_locale_from_config()
            log_debug(f"Loading auth from {AUTH_FILE} with locale {locale}")
            auth = audible.Authenticator.from_file(AUTH_FILE, locale=locale)
            log_debug(f"Loaded auth. Marketplace: {getattr(auth, 'market_place', 'Unknown')}")
            return auth
        except Exception as e:
            log_debug(f"Error loading auth: {e}")
            pass
    return None


def save_auth(auth):
    """Save authentication."""
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    auth.to_file(AUTH_FILE)


# ============== LIBRARY ==============

ASIN_RE = re.compile(r"\b[A-Z0-9]{10}\b")

def _extract_asin(text: str):
    if not text:
        return None
    m = ASIN_RE.search(text.upper())
    return m.group(0) if m else None

_MATCH_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")

def _norm_match(s: str):
    if not s:
        return ""
    return _MATCH_NORMALIZE_RE.sub("", s.lower())

def _find_by_title(norm_paths, title: str):
    title_norm = _norm_match(title)
    if len(title_norm) < 8:
        return None
    for path_norm, path in norm_paths:
        if title_norm in path_norm:
            return path
    return None

def _index_files_by_asin(paths):
    index = {}
    for p in paths:
        asin = _extract_asin(p.name) or _extract_asin(str(p))
        if asin and asin not in index:
            index[asin] = p
    return index

def export_library_tsv(client):
    """Export library to TSV file for series metadata."""
    try:
        result = subprocess.run(
            ["audible", "library", "export", "-o", str(LIBRARY_TSV_FILE)],
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.returncode == 0
    except Exception:
        return False


def fetch_library(client, force_refresh=False):
    """Fetch library with caching and pagination."""
    settings = load_settings()

    if LIBRARY_CACHE.exists() and not force_refresh:
        cache_age = datetime.now().timestamp() - LIBRARY_CACHE.stat().st_mtime
        if cache_age < 3600:
            with open(LIBRARY_CACHE) as f:
                return json.load(f)

    try:
        items = []
        next_page_token = None
        page = 1
        
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        status_text.text("Fetching library page 1...")
        
        while True:
            params = {
                "num_results": 50, # Smaller chunks for reliability
                "response_groups": "product_desc,product_attrs,contributors,media,series",
                "sort_by": "-PurchaseDate"
            }
            if next_page_token:
                params["page_token"] = next_page_token
                
            response = client.get("1.0/library", params=params)
            
            batch = response.get("items", [])
            items.extend(batch)
            
            # Pagination info
            pagination = response.get("response_groups", []) # API quirk: sometimes info is here? No, usually in response root
            # Actually, standard Audible response has 'next_page_token' at root if more pages exist
            next_page_token = response.get("next_page_token")
            
            if not next_page_token:
                break
                
            page += 1
            status_text.text(f"Fetching library page {page} ({len(items)} items so far)...")
            
            # Approximate progress? We don't know total, so just pulse or fill slowly
            if page < 20:
                progress_bar.progress(page * 0.05)

        status_text.empty()
        progress_bar.empty()
        
        LIBRARY_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(LIBRARY_CACHE, "w") as f:
            json.dump(items, f)

        # Auto-export library.tsv for series metadata
        if settings.get("auto_export_library", True):
            export_library_tsv(client)

        return items
    except Exception as e:
        st.error(f"Failed to fetch library: {e}")
        log_debug(f"Library fetch error: {e}")
        return []

def build_status_cache(library, settings, job_status):
    """
    Build a lightweight per-ASIN status cache.
    """
    fmt = settings.get("output_format", "m4b")

    # Load manifest for accurate conversion status (handles migrated files without ASIN in filename)
    manifest = load_converted_manifest()
    manifest_success_asins = {v.get("asin") for v in manifest.values() if v.get("asin") and v.get("status") == "success"}

    # Scan DOWNLOAD_DIR (flat) and COMPLETED_DIR (recursive) for source files
    # Don't scan CONVERTED_DIR - AAXC files there are leftovers from completed conversions
    aaxc_files = list(DOWNLOAD_DIR.glob("*.aaxc")) + list(COMPLETED_DIR.rglob("*.aaxc"))
    voucher_files = list(DOWNLOAD_DIR.glob("*.voucher")) + list(COMPLETED_DIR.rglob("*.voucher"))
    cover_files = list(DOWNLOAD_DIR.glob("*.jpg")) + list(COMPLETED_DIR.rglob("*.jpg"))

    aaxc_by_asin = _index_files_by_asin(aaxc_files)
    voucher_by_asin = _index_files_by_asin(voucher_files)
    cover_by_asin = _index_files_by_asin(cover_files)

    aaxc_by_title = [(_norm_match(p.name), p) for p in aaxc_files]
    voucher_by_title = [(_norm_match(p.name), p) for p in voucher_files]
    cover_by_title = [(_norm_match(p.name), p) for p in cover_files]

    # Scan for output files by ASIN in filename (fallback method)
    output_files = list(CONVERTED_DIR.rglob(f"*.{fmt}"))
    converted_asins_from_files = set()
    for p in output_files:
        asin = _extract_asin(p.name) or _extract_asin(str(p))
        if asin:
            converted_asins_from_files.add(asin)

    cache = {}
    for book in library:
        asin = book.get("asin", "") or ""
        title = book.get("title", "") or ""

        aaxc_path = aaxc_by_asin.get(asin) or _find_by_title(aaxc_by_title, title)
        voucher_path = voucher_by_asin.get(asin) or _find_by_title(voucher_by_title, title)
        cover_path = cover_by_asin.get(asin) or _find_by_title(cover_by_title, title)
        downloaded = bool(aaxc_path and voucher_path)
        # Check both filesystem (ASIN in filename) AND manifest (handles migrated files)
        converted = asin in converted_asins_from_files or asin in manifest_success_asins
        validation = job_status.get("validated", {}).get(asin, {})

        cache[asin] = {
            "downloaded": downloaded,
            "converted": converted,
            "interrupted": False,
            "last_chapter": None,
            "aaxc_path": aaxc_path,
            "voucher_path": voucher_path,
            "cover_path": cover_path,
            "validated": validation.get("valid"),
            "validation_error": validation.get("error", ""),
            "_title": title,
        }

    return cache


def get_book_status(asin, title, settings=None):
    """Check download/convert status for a book."""
    if settings is None:
        settings = load_settings()

    # Locate AAXC and Voucher (Check Download and Completed dirs only)
    # Don't check CONVERTED_DIR - AAXC files there are leftovers from completed conversions
    aaxc_by_asin = list(DOWNLOAD_DIR.glob(f"*{asin}*.aaxc")) + \
                   list(COMPLETED_DIR.rglob(f"*{asin}*.aaxc"))

    voucher_by_asin = list(DOWNLOAD_DIR.glob(f"*{asin}*.voucher")) + \
                      list(COMPLETED_DIR.rglob(f"*{asin}*.voucher"))

    # Locate Cover (can check all dirs - covers are useful even after conversion)
    cover_by_asin = list(DOWNLOAD_DIR.glob(f"*{asin}*.jpg")) + \
                    list(COMPLETED_DIR.rglob(f"*{asin}*.jpg")) + \
                    list(CONVERTED_DIR.rglob(f"*{asin}*.jpg"))
    
    cover_path = cover_by_asin[0] if cover_by_asin else None

    if not aaxc_by_asin or not voucher_by_asin:
        # Fallback for filename modes that don't include ASIN (match by title).
        title_norm = _norm_match(title)
        if len(title_norm) >= 8:
            if not aaxc_by_asin:
                aaxc_by_asin = [p for p in DOWNLOAD_DIR.glob("*.aaxc") if title_norm in _norm_match(p.name)] + \
                               [p for p in COMPLETED_DIR.rglob("*.aaxc") if title_norm in _norm_match(p.name)]
            if not voucher_by_asin:
                voucher_by_asin = [p for p in DOWNLOAD_DIR.glob("*.voucher") if title_norm in _norm_match(p.name)] + \
                                  [p for p in COMPLETED_DIR.rglob("*.voucher") if title_norm in _norm_match(p.name)]
            if not cover_path:
                covers = [p for p in DOWNLOAD_DIR.glob("*.jpg") if title_norm in _norm_match(p.name)] + \
                         [p for p in COMPLETED_DIR.rglob("*.jpg") if title_norm in _norm_match(p.name)] + \
                         [p for p in CONVERTED_DIR.rglob("*.jpg") if title_norm in _norm_match(p.name)]
                if covers:
                    cover_path = covers[0]

    # Check for output files based on format
    fmt = settings.get("output_format", "m4b")
    output_files = list(CONVERTED_DIR.rglob(f"*.{fmt}"))

    downloaded = len(aaxc_by_asin) > 0 and len(voucher_by_asin) > 0

    converted = False
    # Normalize title: remove non-alnum, lowercase
    safe_title = "".join(c for c in title if c.isalnum()).lower()
    
    # Check manifest first (most reliable if converted by this system)
    manifest = load_converted_manifest()
    # We need to find the key in manifest that corresponds to this book
    # Manifest matches by file path, but we can search values for ASIN
    if not converted:
        for entry in manifest.values():
            if entry.get("asin") == asin and entry.get("status") == "success":
                converted = True
                break

    # Fallback: Check filesystem
    if not converted:
        for f in output_files:
            # Normalize filename similarly
            f_norm = "".join(c for c in f.name if c.isalnum()).lower()
            
            # Check 1: ASIN in path (very reliable)
            if asin.lower() in str(f).lower():
                converted = True
                break
            
            # Check 2: Title match (fuzzy)
            # We check if the simplified title is contained in the simplified filename
            # Use a reasonable length to avoid false positives on short titles
            if len(safe_title) > 10 and safe_title in f_norm:
                converted = True
                break

    # Check for partial conversion (interrupted) - chaptered mode
    partial_chapters = list(CONVERTED_DIR.rglob(f"*{asin}*/*.mp3")) + \
                       list(CONVERTED_DIR.rglob(f"*{asin}*/*.m4a")) + \
                       list(CONVERTED_DIR.rglob(f"*{asin}*/*.ogg")) + \
                       list(CONVERTED_DIR.rglob(f"*{asin}*/*.flac"))
    interrupted = downloaded and not converted and len(partial_chapters) > 0

    # Get last chapter number if interrupted
    last_chapter = None
    if interrupted:
        chapter_nums = []
        for f in partial_chapters:
            match = re.search(r'-(\d+)\s', f.name)
            if match:
                chapter_nums.append(int(match.group(1)))
        if chapter_nums:
            last_chapter = max(chapter_nums)

    # Check validation status
    job_status = load_job_status()
    validation = job_status.get("validated", {}).get(asin, {})

    return {
        "downloaded": downloaded,
        "converted": converted,
        "interrupted": interrupted,
        "last_chapter": last_chapter,
        "aaxc_path": aaxc_by_asin[0] if aaxc_by_asin else None,
        "cover_path": cover_path,
        "validated": validation.get("valid"),
        "validation_error": validation.get("error", "")
    }


# ============== DOWNLOAD/CONVERT/VALIDATE ==============

def download_book(asin, title, settings):
    """Download a single book."""
    try:
        # If a download-all job is running, don't start a competing foreground download.
        job = load_download_job()
        if job and _pid_alive(job.get("pid", 0)):
            return False, "Download job already running"

        cmd = [
            "audible", "download",
            "--asin", asin,
            "--aaxc",
            "--cover", "--cover-size", settings.get("cover_size", "1215"),
            "--chapter",
            # Make filenames predictable for status detection (keeps ASIN in the name).
            "--filename-mode", "asin_unicode",
            "--output-dir", str(DOWNLOAD_DIR)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,
            cwd=str(DOWNLOAD_DIR),
        )

        if result.returncode == 0:
            mark_download_success(asin)
            return True, ""
        else:
            error = result.stderr[:200] if result.stderr else "Unknown error"
            mark_download_failed(asin, title, error)
            return False, error
    except subprocess.TimeoutExpired:
        mark_download_failed(asin, title, "Timeout")
        return False, "Download timed out"
    except Exception as e:
        mark_download_failed(asin, title, str(e))
        return False, str(e)


def validate_book(aaxc_path, asin, title):
    """Validate an AAXC file without converting."""
    try:
        # Get voucher for decryption keys
        voucher_path = aaxc_path.with_suffix('.voucher')
        if not voucher_path.exists():
            mark_validated(asin, False, "Voucher file not found")
            return False, "Voucher file not found"

        # Read keys from voucher
        with open(voucher_path) as f:
            voucher = json.load(f)

        key = voucher.get('content_license', {}).get('license_response', {}).get('key', '')
        iv = voucher.get('content_license', {}).get('license_response', {}).get('iv', '')

        if not key or not iv:
            mark_validated(asin, False, "Invalid voucher - missing keys")
            return False, "Invalid voucher - missing keys"

        # Use ffprobe to validate
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-audible_key", key,
                "-audible_iv", iv,
                "-i", str(aaxc_path)
            ],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            mark_validated(asin, True)
            return True, ""
        else:
            error = result.stderr[:200] if result.stderr else "Validation failed"
            mark_validated(asin, False, error)
            return False, error

    except subprocess.TimeoutExpired:
        mark_validated(asin, False, "Timeout")
        return False, "Validation timed out"
    except Exception as e:
        mark_validated(asin, False, str(e))
        return False, str(e)


def merge_library_files(settings):
    """Merge current library.tsv with selected backups into a temporary file."""
    merged_file = Path("/tmp/merged_library.tsv")
    
    # Files to merge
    files = []
    if LIBRARY_TSV_FILE.exists():
        files.append(LIBRARY_TSV_FILE)
    
    for filename in settings.get("selected_library_backups", []):
        backup_path = LIBRARY_BACKUPS_DIR / filename
        if backup_path.exists():
            files.append(backup_path)
    
    if not files:
        return None
    
    try:
        seen_headers = False
        with open(merged_file, 'w', encoding='utf-8') as outfile:
            for fpath in files:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as infile:
                    header = infile.readline()
                    if not seen_headers:
                        outfile.write(header)
                        seen_headers = True
                    
                    # Write the rest
                    shutil.copyfileobj(infile, outfile)
        return merged_file
    except Exception as e:
        print(f"Error merging library files: {e}")
        return LIBRARY_TSV_FILE if LIBRARY_TSV_FILE.exists() else None


def convert_book(aaxc_path, title, asin, settings, continue_from=None):
    """Convert a single book."""
    try:
        fmt = settings.get("output_format", "m4b")

        # Check no-clobber
        if settings.get("no_clobber", False):
            existing = list(CONVERTED_DIR.rglob(f"*{asin}*.{fmt}"))
            if existing:
                return True, "Skipped (already exists)"

        # Build command
        cmd = ["bash", "/app/AAXtoMP3"]

        # Format
        if fmt in ["m4b", "m4a", "mp3"]:
            cmd.append(f"-e:{fmt}")
        elif fmt == "flac":
            cmd.append("--flac")
        elif fmt == "opus":
            cmd.append("--opus")

        # Always use audible-cli data for AAXC
        cmd.append("--use-audible-cli-data")

        # Library file for series metadata
        # Merge backups if selected
        library_file_to_use = merge_library_files(settings)
        if library_file_to_use and library_file_to_use.exists():
            cmd.extend(["--audible-cli-library-file", str(library_file_to_use)])

        # Single vs chaptered
        if settings.get("single_file", True):
            cmd.append("--single")
        else:
            cmd.append("--chaptered")

        # Compression level (only for formats that support it)
        if fmt == "mp3":
            level = settings.get("compression_mp3", 4)
            cmd.extend(["--level", str(level)])
        elif fmt == "flac":
            level = settings.get("compression_flac", 5)
            cmd.extend(["--level", str(level)])
        elif fmt == "opus":
            level = settings.get("compression_opus", 5)
            cmd.extend(["--level", str(level)])

        # Naming schemes
        dir_scheme = settings.get("dir_naming_scheme", "")
        if dir_scheme and dir_scheme != "$genre/$artist/$title":
            cmd.extend(["--dir-naming-scheme", dir_scheme])

        file_scheme = settings.get("file_naming_scheme", "")
        if file_scheme and file_scheme != "$title":
            cmd.extend(["--file-naming-scheme", file_scheme])

        chapter_scheme = settings.get("chapter_naming_scheme", "")
        if chapter_scheme:
            cmd.extend(["--chapter-naming-scheme", chapter_scheme])

        # Author override
        author_override = settings.get("author_override", "").strip()
        if author_override:
            cmd.extend(["--author", author_override])
        elif settings.get("keep_author_index", 0) > 0:
            cmd.extend(["--keep-author", str(settings["keep_author_index"])])

        # No-clobber
        if settings.get("no_clobber", False):
            cmd.append("--no-clobber")

        # Resume from chapter
        if continue_from:
            cmd.extend(["--continue", str(continue_from)])

        # Target directory
        cmd.extend(["--target_dir", str(CONVERTED_DIR)])

        # Input file
        cmd.append(str(aaxc_path))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,
            cwd=str(DOWNLOAD_DIR)
        )

        if result.returncode == 0:
            mark_conversion_success(asin)

            # Move source to completed directory if enabled
            if settings.get("move_after_complete", False):
                COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
                try:
                    # Move AAXC and associated files
                    for ext in ['.aaxc', '.voucher', '-chapters.json']:
                        src = aaxc_path.with_suffix(ext) if ext.startswith('.') else Path(str(aaxc_path).replace('.aaxc', ext))
                        if src.exists():
                            shutil.move(str(src), str(COMPLETED_DIR / src.name))
                    # Move cover
                    cover_pattern = aaxc_path.stem.rsplit('-', 1)[0] + "_*.jpg"
                    for cover in DOWNLOAD_DIR.glob(cover_pattern):
                        shutil.move(str(cover), str(COMPLETED_DIR / cover.name))
                except Exception:
                    pass  # Don't fail if move fails

            return True, ""
        else:
            error = result.stderr[:200] if result.stderr else result.stdout[:200] if result.stdout else "Unknown error"
            last_chapter = None
            match = re.search(r'Chapter\s+(\d+)', result.stdout or "")
            if match:
                last_chapter = int(match.group(1))
            mark_conversion_failed(asin, title, error, last_chapter)
            return False, error
    except subprocess.TimeoutExpired:
        mark_conversion_failed(asin, title, "Timeout - conversion took too long")
        return False, "Conversion timed out"
    except Exception as e:
        mark_conversion_failed(asin, title, str(e))
        return False, str(e)


def format_duration(minutes):
    """Format minutes to hours:minutes."""
    if not minutes:
        return ""
    return f"{minutes // 60}h {minutes % 60}m"


def terminal_page():
    """Terminal page."""
    st.header("💻 Terminal")
    st.caption("Access the container shell directly. Use `aaxtomp3` commands here.")

    # We use JS to dynamically determine the terminal URL based on the current hostname
    # Assumes terminal is on port 7681 (default)
    html_code = """
    <div style="height: 80vh; width: 100%;">
        <iframe id="terminal-frame" style="width: 100%; height: 100%; border: 1px solid #ddd; border-radius: 4px;"></iframe>
    </div>
    <script>
        // Get current hostname (e.g. localhost or 192.168.1.x)
        const hostname = window.location.hostname;
        // Construct terminal URL (assuming default port 7681)
        // You can change this port in docker-compose.yml and here if needed
        const terminalUrl = window.location.protocol + "//" + hostname + ":7681";
        
        console.log("Loading terminal from:", terminalUrl);
        document.getElementById("terminal-frame").src = terminalUrl;
    </script>
    """
    components.html(html_code, height=700, scrolling=False)


# ============== PAGES ==============

def login_page():
    """Login page."""
    st.title("📚 Audible Library Manager")
    st.header("Login to Audible")

    # Check if host audible config exists (mounted from host)
    host_audible_config = Path("/host_audible")
    audible_cli_config = Path("/root/.audible")

    # Try to auto-login from mounted credentials
    for config_path in [host_audible_config, audible_cli_config]:
        if config_path.exists():
            # Get locale from config
            locale = get_locale_from_config()
            locale_code = getattr(locale, 'country_code', None) or str(locale)
            
            # Look for .json files AND 'audibleAuth'
            potential_files = list(config_path.glob("*.json"))
            if (config_path / "audibleAuth").exists():
                potential_files.append(config_path / "audibleAuth")
            
            log_debug(f"Potential auth files in {config_path}: {[f.name for f in potential_files]}")
            
            for auth_file in potential_files:
                try:
                    log_debug(f"Trying to login with {auth_file}...")
                    # Pass the locale explicitly
                    auth = audible.Authenticator.from_file(auth_file, locale=locale)
                    save_auth(auth)
                    log_debug(f"Login SUCCESS with {auth_file}!")
                    st.success(f"Login successful using {auth_file.name} (Region: {locale_code})!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    log_debug(f"Login FAILED with {auth_file}: {e}")
                    continue

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("""
        ### Setup Instructions

        Run these commands on your **host machine** (where Docker is running):

        ```bash
        # Install audible-cli
        pip install audible-cli

        # Authenticate (this opens a browser)
        audible quickstart
        ```

        Then restart the container to pick up the credentials:

        ```bash
        cd /path/to/AAXtoMP3/gui
        ./stop.sh
        ./start.sh
        ```

        The app will automatically detect and use your credentials.
        """)

        st.divider()

        st.markdown("### Or: Authenticate inside Docker")
        st.caption("Run this in a terminal on your host:")

        st.code("""docker exec -it audible-library-manager audible quickstart""", language="bash")

        st.markdown("After completing authentication, click the button below:")

        if st.button("🔄 Check for credentials", use_container_width=True, type="primary"):
            # Check if audible-cli created credentials
            if audible_cli_config.exists():
                auth_files = list(audible_cli_config.glob("*.json"))
                if auth_files:
                    try:
                        auth = audible.Authenticator.from_file(auth_files[0])
                        save_auth(auth)
                        st.success("Login successful!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not read credentials: {e}")
                else:
                    st.warning("No credentials found. Please complete `audible quickstart` first.")
            else:
                st.warning("No credentials found. Please complete `audible quickstart` first.")


def settings_page():
    """Settings page."""
    st.header("⚙️ Settings")

    settings = load_settings()

    with st.form("settings_form"):
        # === OUTPUT FORMAT ===
        st.subheader("📁 Output Format")
        col1, col2 = st.columns(2)

        with col1:
            output_format = st.selectbox(
                "Audio Format",
                ["m4b", "m4a", "mp3", "flac", "opus"],
                index=["m4b", "m4a", "mp3", "flac", "opus"].index(settings.get("output_format", "m4b")),
                help="M4B is recommended for audiobooks (supports chapters)"
            )

        with col2:
            single_file = st.checkbox(
                "Single file output",
                value=settings.get("single_file", True),
                help="Uncheck to split into separate chapter files"
            )

        # === COMPRESSION ===
        st.subheader("🎚️ Compression Level")
        st.caption("Only applies to MP3, FLAC, and Opus formats")

        col1, col2, col3 = st.columns(3)
        with col1:
            compression_mp3 = st.slider(
                "MP3 (0=best, 9=fast)",
                min_value=0, max_value=9,
                value=settings.get("compression_mp3", 4)
            )
        with col2:
            compression_flac = st.slider(
                "FLAC (0=fast, 12=smallest)",
                min_value=0, max_value=12,
                value=settings.get("compression_flac", 5)
            )
        with col3:
            compression_opus = st.slider(
                "Opus (0=fast, 10=best)",
                min_value=0, max_value=10,
                value=settings.get("compression_opus", 5)
            )

        # === NAMING SCHEMES ===
        st.subheader("📝 Naming Schemes")
        st.caption(f"Variables: {', '.join(NAMING_VARIABLES)}")

        dir_naming_scheme = st.text_input(
            "Directory naming",
            value=settings.get("dir_naming_scheme", "$genre/$artist/$title"),
            help="How to organize output folders"
        )

        file_naming_scheme = st.text_input(
            "File naming",
            value=settings.get("file_naming_scheme", "$title"),
            help="How to name output files"
        )

        chapter_naming_scheme = st.text_input(
            "Chapter naming (chaptered mode only)",
            value=settings.get("chapter_naming_scheme", ""),
            placeholder="Leave empty for default",
            help=f"Additional variables: $chapter, $chapternum, $chaptercount"
        )

        # === METADATA ===
        st.subheader("👤 Metadata")
        col1, col2 = st.columns(2)

        with col1:
            author_override = st.text_input(
                "Override author name",
                value=settings.get("author_override", ""),
                placeholder="Leave empty to use original",
                help="Force a specific author name for all conversions"
            )

        with col2:
            keep_author_index = st.number_input(
                "Keep author # (0=all)",
                min_value=0, max_value=10,
                value=settings.get("keep_author_index", 0),
                help="If book has multiple authors, keep only this one (1=first, 2=second, etc.)"
            )

        # === BEHAVIOR ===
        st.subheader("⚡ Behavior")
        col1, col2 = st.columns(2)

        with col1:
            no_clobber = st.checkbox(
                "Skip existing files (no-clobber)",
                value=settings.get("no_clobber", False),
                help="Don't overwrite if output already exists"
            )

            auto_retry = st.checkbox(
                "Auto-retry failed jobs",
                value=settings.get("auto_retry", True)
            )

        with col2:
            move_after_complete = st.checkbox(
                "Move source after conversion",
                value=settings.get("move_after_complete", False),
                help=f"Move AAXC files to {COMPLETED_DIR} after successful conversion"
            )

            max_retries = st.number_input(
                "Max retry attempts",
                min_value=1, max_value=10,
                value=settings.get("max_retries", 3)
            )

        # === DOWNLOAD ===
        st.subheader("⬇️ Download Settings")
        col1, col2 = st.columns(2)

        with col1:
            cover_size = st.selectbox(
                "Cover art size",
                ["500", "1215", "2400"],
                index=["500", "1215", "2400"].index(settings.get("cover_size", "1215")),
                help="Higher = better quality but larger file"
            )

        with col2:
            auto_export_library = st.checkbox(
                "Auto-export library.tsv",
                value=settings.get("auto_export_library", True),
                help="Export library metadata for series info"
            )

        # === LIBRARY BACKUPS ===
        st.subheader("📚 External Library Metadata")
        st.caption(f"Place backup library.tsv files in: `{LIBRARY_BACKUPS_DIR}`")
        
        # Scan for backup files
        backup_files = []
        if LIBRARY_BACKUPS_DIR.exists():
            backup_files = [f.name for f in LIBRARY_BACKUPS_DIR.glob("*.tsv")] + \
                           [f.name for f in LIBRARY_BACKUPS_DIR.glob("*.csv")]
            backup_files.sort()
        
        selected_library_backups = st.multiselect(
            "Select backup files to merge with current library",
            options=backup_files,
            default=[f for f in settings.get("selected_library_backups", []) if f in backup_files],
            help="Useful if you have old backups with series info not present in current export"
        )

        if st.form_submit_button("💾 Save Settings", use_container_width=True):
            new_settings = {
                "output_format": output_format,
                "single_file": single_file,
                "compression_mp3": compression_mp3,
                "compression_flac": compression_flac,
                "compression_opus": compression_opus,
                "dir_naming_scheme": dir_naming_scheme,
                "file_naming_scheme": file_naming_scheme,
                "chapter_naming_scheme": chapter_naming_scheme,
                "author_override": author_override,
                "keep_author_index": keep_author_index,
                "no_clobber": no_clobber,
                "move_after_complete": move_after_complete,
                "auto_retry": auto_retry,
                "max_retries": int(max_retries),
                "cover_size": cover_size,
                "auto_export_library": auto_export_library,
                "selected_library_backups": selected_library_backups,
            }
            save_settings(new_settings)
            st.success("Settings saved!")
            time.sleep(1)
            st.rerun()

    st.divider()

    # === HEALTH ===
    st.subheader("🩺 Health")
    
    if st.button("🔄 Sync Manifest (Import existing files)", help="Scan converted folder and update status for existing files"):
        cmd = ["python", "/app/worker.py", "sync-manifest"]
        subprocess.Popen(cmd, preexec_fn=os.setsid)
        st.success("Manifest sync started in background. Check activity log.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f"Downloads: `{DOWNLOAD_DIR}`")
        st.caption("Writable" if os.access(DOWNLOAD_DIR, os.W_OK) else "Not writable")
    with col2:
        st.caption(f"Converted: `{CONVERTED_DIR}`")
        st.caption("Writable" if os.access(CONVERTED_DIR, os.W_OK) else "Not writable")
    with col3:
        st.caption(f"Completed: `{COMPLETED_DIR}`")
        st.caption("Writable" if os.access(COMPLETED_DIR, os.W_OK) else "Not writable")

    try:
        du = shutil.disk_usage(str(DOWNLOAD_DIR))
        st.caption(f"Free space (downloads mount): {du.free/1024/1024/1024:.1f} GB")
    except Exception:
        pass

    # Quick counts
    try:
        aaxc_n = len(list(DOWNLOAD_DIR.glob('*.aaxc')))
        voucher_n = len(list(DOWNLOAD_DIR.glob('*.voucher')))
        st.caption(f"Downloads: {aaxc_n} AAXC, {voucher_n} vouchers")
    except Exception:
        pass

    # === FAILED JOBS ===
    job_status = load_job_status()

    if job_status.get("failed_downloads"):
        st.subheader("❌ Failed Downloads")
        for asin, info in job_status["failed_downloads"].items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(f"{info['title'][:50]}")
                st.caption(f"Error: {info['error'][:100]}... | Retries: {info['retries']}")
            with col2:
                if st.button("🗑️", key=f"clear_dl_{asin}", help="Clear"):
                    job_status["failed_downloads"].pop(asin)
                    save_job_status(job_status)
                    st.rerun()

    if job_status.get("failed_conversions"):
        st.subheader("❌ Failed Conversions")
        for asin, info in job_status["failed_conversions"].items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(f"{info['title'][:50]}")
                st.caption(f"Error: {info['error'][:100]}...")
                if info.get('last_chapter'):
                    st.caption(f"Last chapter: {info['last_chapter']}")
            with col2:
                if st.button("🗑️", key=f"clear_cv_{asin}", help="Clear"):
                    job_status["failed_conversions"].pop(asin)
                    save_job_status(job_status)
                    st.rerun()

    if job_status.get("failed_downloads") or job_status.get("failed_conversions"):
        if st.button("🗑️ Clear All Failed", use_container_width=True):
            save_job_status({"failed_downloads": {}, "failed_conversions": {}, "interrupted": {}, "validated": {}})
            st.rerun()

    # === PATHS INFO ===
    st.divider()
    st.subheader("📁 Paths")
    st.caption(f"Downloads: `{DOWNLOAD_DIR}`")
    st.caption(f"Converted: `{CONVERTED_DIR}`")
    st.caption(f"Completed (source): `{COMPLETED_DIR}`")
    st.caption(f"Library TSV: `{LIBRARY_TSV_FILE}`")


def main_page(auth):
    """Main library page."""
    settings = load_settings()
    job_status = load_job_status()

    # Navigation
    tab1, tab2, tab3 = st.tabs(["📚 Library", "⚙️ Settings", "💻 Terminal"])

    with tab3:
        terminal_page()

    with tab2:
        settings_page()

    with tab1:
        st.title("📚 Audible Library Manager")

        # Fetch library (prefer background refresh + cache to keep UI responsive)
        library, is_refreshing = ensure_library_cache_background()

        if is_refreshing:
            st.info("Refreshing full library in the background… (auto-updates shortly)")
            components.html("<script>setTimeout(()=>window.location.reload(), 2500);</script>", height=0)

        if not library:
            st.warning("Library is loading…")
            if st.button("🔄 Force refresh"):
                LIBRARY_CACHE.unlink(missing_ok=True)
                LIBRARY_JOB_FILE.unlink(missing_ok=True)
                start_library_refresh_job(num_results=1000)
                st.rerun()
            return

        status_cache = build_status_cache(library, settings, job_status)
        
        # Load Manifest for accurate status
        manifest = load_converted_manifest()
        manifest_by_asin = {v.get("asin"): v for v in manifest.values() if v.get("asin")}

        # Calculate stats
        stats = {"total": len(library), "downloaded": 0, "converted": 0, "interrupted": 0, "failed": 0, "validated": 0}
        for book in library:
            asin = book.get("asin", "")
            status = status_cache.get(asin, {})
            
            # Check manifest for conversion status
            is_manifest_success = manifest_by_asin.get(asin, {}).get("status") == "success"
            
            if status.get("downloaded"):
                stats["downloaded"] += 1
            
            if status.get("converted") or is_manifest_success:
                stats["converted"] += 1
            
            if status.get("interrupted"):
                stats["interrupted"] += 1
            
            if status.get("validated") is True:
                stats["validated"] += 1

        stats["failed"] = len(job_status.get("failed_downloads", {})) + len(job_status.get("failed_conversions", {}))

        # === SIDEBAR ===
        with st.sidebar:
            st.header("⚡ Actions")
            
            # 1. Global Controls
            c_g1, c_g2 = st.columns(2)
            with c_g1:
                if st.button("🔄 Refresh", use_container_width=True, help="Reload library cache"):
                    LIBRARY_CACHE.unlink(missing_ok=True)
                    st.rerun()
            with c_g2:
                if st.button("🚪 Logout", use_container_width=True):
                    AUTH_FILE.unlink(missing_ok=True)
                    LIBRARY_CACHE.unlink(missing_ok=True)
                    st.rerun()
            
            auto_convert = st.checkbox(
                "Auto-convert downloads", 
                value=False,
                help="Automatically start conversion job when downloads begin"
            )
            
            st.divider()

            # 2. Bulk Actions
            with st.expander("📦 Bulk Operations", expanded=True):
                # Download All
                not_downloaded = [b for b in library if not status_cache.get(b.get("asin", ""), {}).get("downloaded", False)]
                if not_downloaded:
                    st.caption(f"**Download** ({len(not_downloaded)} items)")
                    dl_jobs = st.slider("Parallel DLs", 1, MAX_PARALLEL_DOWNLOADS, min(2, MAX_PARALLEL_DOWNLOADS), key="slider_dl_all")
                    if st.button(f"⬇️ Download All", use_container_width=True):
                        ok, err = start_download_all_job(settings, jobs=dl_jobs)
                        if not ok: st.error(err)
                        if auto_convert and ok:
                            cjob = load_convert_job()
                            if not (cjob and _pid_alive(cjob.get("pid", 0))):
                                start_convert_watch_job(poll_seconds=10, max_parallel=2)
                        st.rerun()
                
                # Convert All
                to_convert = []
                to_convert_paths = []
                for book in library:
                    asin = book.get("asin", "")
                    s = status_cache.get(asin, {})

                    # Check if already converted via manifest (by ASIN)
                    is_manifest_success = manifest_by_asin.get(asin, {}).get("status") == "success"

                    if s.get("downloaded") and not s.get("converted") and not is_manifest_success:
                        # Double check manifest by AAXC path for running/repairing status
                        aaxc = s.get("aaxc_path")
                        if aaxc:
                            entry = manifest.get(str(aaxc), {})
                            if entry.get("status") not in ["running", "repairing"]:
                                to_convert.append(asin)
                                to_convert_paths.append(aaxc)

                if to_convert:
                    st.caption(f"**Convert** ({len(to_convert)} items)")
                    if st.button(f"🔄 Convert All", use_container_width=True):
                        start_batch_convert_job(to_convert, settings, paths=to_convert_paths)
                        st.success(f"Queued {len(to_convert)} items")
                        time.sleep(1)
                        st.rerun()

                # Validate All
                downloaded_books = [(b, status_cache.get(b.get("asin", ""), {})) for b in library]
                to_validate = [(b, s) for b, s in downloaded_books if s.get("downloaded") and s.get("validated") is None and s.get("aaxc_path")]
                if to_validate:
                    st.caption(f"**Validate** ({len(to_validate)} items)")
                    if st.button(f"✅ Validate All", use_container_width=True):
                        progress = st.progress(0)
                        status_text = st.empty()
                        for i, (book, status) in enumerate(to_validate):
                            status_text.text(f"Validating: {book.get('title', 'Unknown')[:20]}...")
                            validate_book(status["aaxc_path"], book.get("asin", ""), book.get("title", ""))
                            progress.progress((i + 1) / len(to_validate))
                        status_text.text("Done!")
                        time.sleep(1)
                        st.rerun()

                # Retry Failed
                failed_count = len(job_status.get("failed_downloads", {})) + len(job_status.get("failed_conversions", {}))
                if failed_count > 0:
                    st.divider()
                    if st.button(f"🔁 Retry Failed ({failed_count})", use_container_width=True, type="primary"):
                        # Retry Downloads
                        for asin, info in job_status.get("failed_downloads", {}).items():
                            if info["retries"] < settings.get("max_retries", 3):
                                download_book(asin, info["title"], settings)
                        # Retry Conversions
                        re_conv = []
                        re_conv_paths = []
                        for asin, info in job_status.get("failed_conversions", {}).items():
                            s = status_cache.get(asin, {})
                            if s.get("aaxc_path"):
                                re_conv.append(asin)
                                re_conv_paths.append(s["aaxc_path"])
                        if re_conv:
                            start_batch_convert_job(re_conv, settings, paths=re_conv_paths)
                        st.rerun()

            # 3. Job Monitor
            with st.expander("⚙️ Background Jobs", expanded=True):
                # Library Refresh
                lj = load_library_job()
                if lj and lj.get("status") == "running":
                    st.info("📚 Library Refreshing...")
                
                # Download Job
                job = load_download_job()
                running = bool(job and _pid_alive(job.get("pid", 0)))
                paused = bool(job and job.get("paused"))
                
                if running:
                    st.success(f"⬇️ Downloading ({job.get('jobs')} threads)")
                    c1, c2, c3 = st.columns(3)
                    if c1.button("⏸️", key="p_dl", disabled=paused): pause_download_job(); st.rerun()
                    if c2.button("▶️", key="r_dl", disabled=not paused): resume_download_job(); st.rerun()
                    if c3.button("⏹", key="s_dl"): stop_download_job(); st.rerun()
                
                # Convert Job
                cjob = load_convert_job()
                crunning = bool(cjob and _pid_alive(cjob.get("pid", 0)))
                cpaused = bool(cjob and cjob.get("paused"))
                
                if crunning:
                    st.success(f"🔄 Converting")
                    c1, c2, c3 = st.columns(3)
                    if c1.button("⏸️", key="p_cv", disabled=cpaused): pause_convert_job(); st.rerun()
                    if c2.button("▶️", key="r_cv", disabled=not cpaused): resume_convert_job(); st.rerun()
                    if c3.button("⏹", key="s_cv"): stop_convert_job(); st.rerun()

                # Convert Watcher (Auto)
                if not crunning and st.button("Start Auto-Convert Watcher", help="Monitors for new files"):
                    start_convert_watch_job(poll_seconds=10, max_parallel=2)
                    st.rerun()

            # Auto-refresh when jobs are running
            if crunning or running:
                components.html("<script>setTimeout(()=>window.location.reload(), 5000);</script>", height=0)

        # === STATS ===
        cols = st.columns(6)
        cols[0].metric("📚 Total", stats["total"])
        cols[1].metric("⬇️ Downloaded", stats["downloaded"])
        cols[2].metric("✅ Validated", stats["validated"])
        cols[3].metric("🔄 Converted", stats["converted"])
        cols[4].metric("⏸️ Interrupted", stats["interrupted"])
        cols[5].metric("❌ Failed", stats["failed"])

        st.divider()

        # === TOOLBAR & FILTERS ===
        with st.container(border=True):
            # Top row: Search & View Options
            c_search, c_view = st.columns([5, 1], gap="medium", vertical_alignment="center")
            with c_search:
                search = st.text_input(
                    "Search",
                    placeholder="🔍 Search title, author, series, or narrator...",
                    label_visibility="collapsed"
                )
            with c_view:
                page_size = st.selectbox(
                    "Page size",
                    [25, 50, 100, 200],
                    index=1,
                    format_func=lambda x: f"{x} / page",
                    label_visibility="collapsed"
                )

            # Bottom row: Filters, Sort, Pagination
            c_filter, c_sort, c_page = st.columns([2, 2, 2], gap="medium", vertical_alignment="center")
            with c_filter:
                filter_status = st.selectbox(
                    "Status",
                    ["All", "Not Downloaded", "Downloaded", "Validated", "Converted", "Ready to Convert", "Interrupted", "Failed"],
                    format_func=lambda x: f"Filter: {x}",
                    label_visibility="collapsed",
                )
            with c_sort:
                sort_by = st.selectbox(
                    "Sort",
                    ["Purchase Date", "Title (A→Z)", "Author (A→Z)"],
                    format_func=lambda x: f"Sort: {x}",
                    label_visibility="collapsed",
                )

        # Apply Filters & Sort
        filtered_library = library
        
        # 1. Search
        if search:
            q = search.lower().strip()
            filtered_library = [
                b for b in filtered_library 
                if q in b.get("title", "").lower() 
                or q in ", ".join([a.get("name", "") for a in b.get("authors", [])]).lower()
                or (b.get("series") and q in b["series"][0].get("title", "").lower())
            ]

        # 2. Status Filter
        if filter_status != "All":
            # Pre-calc status for filtering (optimization: only calc for search results)
            # We need to map the readable status to the cache check
            final_filtered = []
            for book in filtered_library:
                s = status_cache.get(book.get("asin", ""))
                if not s:
                    s = get_book_status(book.get("asin", ""), book.get("title", ""), settings)
                
                is_failed = book.get("asin") in job_status.get("failed_downloads", {}) or book.get("asin") in job_status.get("failed_conversions", {})
                
                match = False
                if filter_status == "Not Downloaded" and not s.get("downloaded"): match = True
                elif filter_status == "Downloaded" and s.get("downloaded"): match = True
                elif filter_status == "Validated" and s.get("validated") is True: match = True
                elif filter_status == "Converted" and s.get("converted"): match = True
                elif filter_status == "Ready to Convert" and (s.get("downloaded") and not s.get("converted")): match = True
                elif filter_status == "Interrupted" and s.get("interrupted"): match = True
                elif filter_status == "Failed" and is_failed: match = True
                
                if match:
                    final_filtered.append(book)
            filtered_library = final_filtered

        # 3. Sort
        if sort_by == "Title (A→Z)":
            filtered_library = sorted(filtered_library, key=lambda b: (b.get("title") or "").lower())
        elif sort_by == "Author (A→Z)":
            def _first_author(book):
                authors = book.get("authors") or []
                if authors:
                    return (authors[0].get("name") or "").lower()
                return ""
            filtered_library = sorted(filtered_library, key=_first_author)
        elif sort_by == "Purchase Date":
            # Audible API returns dates like '2023-10-27T...'
            filtered_library = sorted(filtered_library, key=lambda b: b.get("purchase_date", ""), reverse=True)

        # Pagination Control
        total_items = len(filtered_library)
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        
        if 'page' not in st.session_state or st.session_state.page > total_pages:
            st.session_state.page = 1

        with c_page:
            cp1, cp2, cp3 = st.columns([1, 2, 1], gap="small")
            with cp1:
                if st.button("⬅️", disabled=st.session_state.page <= 1, key="prev_page"):
                    st.session_state.page -= 1
                    st.rerun()
            with cp2:
                st.markdown(f'<div style="text-align:center; padding-top:5px; font-weight:600;">Page {st.session_state.page} / {total_pages}</div>', unsafe_allow_html=True)
            with cp3:
                if st.button("➡️", disabled=st.session_state.page >= total_pages, key="next_page"):
                    st.session_state.page += 1
                    st.rerun()

        start = (st.session_state.page - 1) * page_size
        end = start + page_size

        manifest = load_converted_manifest()
        manifest_by_asin = {v.get("asin"): v for v in manifest.values() if v.get("asin")}

        # === BATCH ACTIONS ===
        page_books = filtered_library[start:end]
        page_to_download = []
        page_to_convert = []
        page_to_convert_paths = []

        for b in page_books:
            asin = b.get("asin", "")
            s = status_cache.get(asin)
            if not s:
                s = get_book_status(asin, b.get("title", ""), settings)
                status_cache[asin] = s

            if not s.get("downloaded"):
                page_to_download.append(asin)
            elif not s.get("converted"):
                # Check manifest by ASIN
                entry = manifest_by_asin.get(asin, {})
                if entry.get("status") not in ["running", "repairing", "success"]:
                    aaxc = s.get("aaxc_path")
                    if aaxc:
                        page_to_convert.append(asin)
                        page_to_convert_paths.append(aaxc)

        # Batch Action Bar
        if page_to_download or page_to_convert:
            dl_job = load_download_job()
            dl_running = bool(dl_job and _pid_alive(dl_job.get("pid", 0)))
            
            c_batch1, c_batch2, c_batch3 = st.columns([2.5, 2.5, 5])
            
            with c_batch1:
                if page_to_download:
                    if st.button(f"⬇️ Download Page ({len(page_to_download)})", disabled=dl_running, type="primary", use_container_width=True):
                        ok, err = start_batch_download_job(page_to_download, settings, jobs=3)
                        if not ok: st.error(err)
                        else:
                            if auto_convert:
                                cjob = load_convert_job()
                                if not (cjob and _pid_alive(cjob.get("pid", 0))):
                                    start_convert_watch_job(poll_seconds=10, max_parallel=2)
                            st.rerun()
            
            with c_batch2:
                if page_to_convert:
                    if st.button(f"🔄 Convert Page ({len(page_to_convert)})", type="primary", use_container_width=True):
                        start_batch_convert_job(page_to_convert, settings, paths=page_to_convert_paths)
                        st.success("Added to conversion queue")
                        time.sleep(1)
                        st.rerun()

            with c_batch3:
                if dl_running:
                    st.caption("📥 Download job in progress...")
            st.divider()

        # === BOOK LIST ===
        for book in filtered_library[start:end]:
            asin = book.get("asin", "")
            title = book.get("title", "Unknown")
            authors = ", ".join([a.get("name", "") for a in (book.get("authors") or [])])
            duration = format_duration(book.get("runtime_length_min", 0))

            series_info = ""
            if book.get("series"):
                s = book["series"][0]
                series_info = f"{s.get('title', '')} #{s.get('sequence', '')}"

            status = status_cache.get(asin)
            if not status:
                status = get_book_status(asin, title, settings)
            is_failed = asin in job_status.get("failed_downloads", {}) or asin in job_status.get("failed_conversions", {})

            # Check Manifest Status via ASIN (Robust)
            manifest_entry = manifest_by_asin.get(asin, {})
            
            is_converting = manifest_entry.get("status") == "running"
            is_repairing = manifest_entry.get("status") == "repairing"
            is_manifest_success = manifest_entry.get("status") == "success"
            
            # Trust manifest success even if file scan missed it (temporarily)
            is_converted = status.get("converted") or is_manifest_success

            # --- CARD LAYOUT ---
            with st.container(border=True):
                # CSS Marker
                st.markdown('<span class="aa-row-marker"></span>', unsafe_allow_html=True)
                
                c_cover, c_info, c_actions = st.columns([1.2, 6.8, 2.0], gap="medium", vertical_alignment="top")

                # 1. Cover Art
                with c_cover:
                    cover_path = status.get("cover_path")
                    # Extract remote URL from metadata (Audible API structure)
                    remote_url = book.get("product_images", {}).get("500") or \
                                 book.get("product_images", {}).get("250")
                    
                    if cover_path and Path(cover_path).exists():
                        st.image(str(cover_path), use_container_width=True)
                    elif remote_url:
                        st.image(remote_url, use_container_width=True)
                    else:
                        # Placeholder if no cover
                        st.markdown(
                            f'<div style="background:#eee; width:100%; aspect-ratio:1; display:flex; align-items:center; justify-content:center; border-radius:4px; color:#aaa; font-size:0.8rem;">No Cover</div>', 
                            unsafe_allow_html=True
                        )

                # 2. Book Info
                with c_info:
                    # Title
                    st.markdown(f'<div class="aa-title">{title}</div>', unsafe_allow_html=True)
                    
                    # Author
                    if authors:
                        st.markdown(f'<div class="aa-author">by {authors}</div>', unsafe_allow_html=True)

                    # Metadata Row (Series, Duration, Status)
                    meta_html = '<div class="aa-meta-row">'
                    
                    # Series Badge
                    if series_info:
                        meta_html += f'<span class="aa-pill aa-pill--series">{series_info}</span>'
                    
                    # Duration
                    if duration:
                        meta_html += f'<span class="aa-meta-item">🕒 {duration}</span>'

                    # Status Pill Logic
                    if is_repairing:
                        pill_cls, pill_text = "status-warning", "Repairing..."
                    elif is_converting:
                        pill_cls, pill_text = "status-info", "Converting..."
                    elif is_converted:
                        pill_cls, pill_text = "status-success", "Converted"
                    elif status.get("interrupted"):
                        ch = status.get("last_chapter") or "?"
                        pill_cls, pill_text = "status-warning", f"Interrupted (Ch.{ch})"
                    elif status.get("downloaded"):
                        if status.get("validated") is True:
                            pill_cls, pill_text = "status-success", "Validated"
                        elif status.get("validated") is False:
                            pill_cls, pill_text = "status-danger", "Invalid"
                        else:
                            pill_cls, pill_text = "status-info", "Ready to Convert"
                    elif is_failed:
                        pill_cls, pill_text = "status-danger", "Failed"
                    else:
                        pill_cls, pill_text = "status-neutral", "Not Downloaded"

                    meta_html += f'<span class="aa-pill {pill_cls}">{pill_text}</span>'
                    meta_html += '</div>'
                    
                    st.markdown(meta_html, unsafe_allow_html=True)

                    # Expandable Details (Technical Info)
                    with st.expander("Technical Details", expanded=False):
                        st.caption(f"**ASIN:** `{asin}`")
                        if status.get("aaxc_path"):
                            st.caption(f"**File:** `{Path(status['aaxc_path']).name}`")
                        if is_failed:
                            err = job_status.get("failed_downloads", {}).get(asin, {}).get("error") or \
                                  job_status.get("failed_conversions", {}).get(asin, {}).get("error")
                            st.error(f"Error: {err}")
                        if is_converting:
                            st.info("Conversion in progress (check activity log)")

                # 3. Smart Actions
                with c_actions:
                    # Determine Primary Action
                    if is_converting or is_repairing:
                        st.button("⏳ Queued", key=f"q_{asin}", disabled=True, use_container_width=True)
                    
                    elif not status.get("downloaded"):
                        # STATE: Not Downloaded
                        if st.button("⬇️ Download", key=f"dl_{asin}", type="primary", use_container_width=True):
                            with st.spinner("Starting download..."):
                                success, msg = download_book(asin, title, settings)
                                if not success: st.error(msg)
                                else: st.rerun()
                    
                    elif status.get("interrupted"):
                         # STATE: Interrupted -> Resume
                         if st.button("▶️ Resume", key=f"res_{asin}", type="primary", use_container_width=True):
                            aaxc = status.get("aaxc_path")
                            start_batch_convert_job([asin], settings, paths=[aaxc] if aaxc else None)
                            st.toast(f"Resuming {title}...")
                            time.sleep(0.5)
                            st.rerun()

                    elif not is_converted and status.get("aaxc_path"):
                        # STATE: Ready (Downloaded) -> Convert or Validate
                        # Primary: Convert
                        if st.button("🔄 Convert", key=f"cv_{asin}", type="primary", use_container_width=True):
                            start_batch_convert_job([asin], settings, paths=[status["aaxc_path"]])
                            st.toast(f"Queued {title} for conversion")
                            time.sleep(0.5)
                            st.rerun()
                        
                        # Secondary: Validate (Icon button to save space?)
                        if status.get("validated") is None:
                            if st.button("✓ Validate", key=f"val_{asin}", use_container_width=True):
                                with st.spinner("Validating..."):
                                    validate_book(status["aaxc_path"], asin, title)
                                    st.rerun()
                        elif status.get("validated") is True:
                             st.button("✓ Valid", key=f"val_ok_{asin}", disabled=True, use_container_width=True)
                        else:
                             st.button("⚠️ Invalid", key=f"val_bad_{asin}", disabled=True, use_container_width=True)

                    elif is_converted:
                        # STATE: Done
                        st.button("✅ Done", key=f"done_{asin}", disabled=True, use_container_width=True)
                        # Maybe a small 'Redo' button?
                        if st.button("🔄 Redo", key=f"redo_{asin}", help="Convert again", use_container_width=True):
                             aaxc = status.get("aaxc_path")
                             start_batch_convert_job([asin], settings, paths=[aaxc] if aaxc else None)
                             st.toast(f"Re-queued {title}")
                             time.sleep(0.5)
                             st.rerun()

                    # Error State Actions
                    if is_failed:
                        if st.button("🔁 Retry", key=f"retry_{asin}", type="primary", use_container_width=True):
                            # Retry logic simplified for single item
                            if asin in job_status.get("failed_downloads", {}):
                                download_book(asin, title, settings)
                            elif asin in job_status.get("failed_conversions", {}):
                                aaxc = status.get("aaxc_path")
                                start_batch_convert_job([asin], settings, paths=[aaxc] if aaxc else None)
                            st.rerun()

        # Render activity log drawer at the bottom of the page
        render_activity_log_drawer()


def main():
    """Main entry point."""
    for d in [DOWNLOAD_DIR, CONVERTED_DIR, COMPLETED_DIR, Path("/data")]:
        d.mkdir(parents=True, exist_ok=True)

    auth = get_auth()

    if auth is None:
        login_page()
    else:
        main_page(auth)


if __name__ == "__main__":
    main()
