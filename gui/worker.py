import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from datetime import datetime
from pathlib import Path

import audible
from audible.localization import Locale

DATA_DIR = Path("/data")
SETTINGS_FILE = DATA_DIR / "settings.json"
JOB_STATUS_FILE = DATA_DIR / "job_status.json"
LIBRARY_TSV_FILE = DATA_DIR / "library.tsv"
AUTH_FILE = DATA_DIR / "auth.json"

DOWNLOAD_DIR = Path("/downloads")
CONVERTED_DIR = Path("/converted")
COMPLETED_DIR = Path("/completed")

CONVERT_JOB_FILE = DATA_DIR / "convert_job.json"
CONVERT_LOG = DATA_DIR / "convert_all.log"
CONVERT_LOCKS_DIR = DATA_DIR / "convert_locks"

LIBRARY_JOB_FILE = DATA_DIR / "library_job.json"
LIBRARY_LOG = DATA_DIR / "library_refresh.log"

ASIN_RE = re.compile(r"\bB[A-Z0-9]{9}\b")
MATCH_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _now():
    return datetime.now().isoformat()


def log(msg: str):
    CONVERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CONVERT_LOG, "a", encoding="utf-8") as f:
        f.write(f"{_now()} {msg}\n")

def log_library(msg: str):
    LIBRARY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LIBRARY_LOG, "a", encoding="utf-8") as f:
        f.write(f"{_now()} {msg}\n")


def load_settings():
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _locale_from_auth_file():
    try:
        if not AUTH_FILE.exists():
            return Locale("us")
        data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
        code = data.get("locale_code") or "us"
        # Normalize values like "en_US"
        code = str(code).strip().lower().replace("-", "_")
        if len(code) == 5 and "_" in code:
            _, cc = code.split("_", 1)
            code = cc
        if code == "gb":
            code = "uk"
        try:
            return Locale(code)
        except Exception:
            return Locale("us")
    except Exception:
        return Locale("us")

def refresh_library_full(num_results=1000):
    """
    Fetch the full library via audible-python so the schema matches what the UI expects.
    Writes `/data/library_cache.json` as a JSON list of item dicts.
    """
    if not AUTH_FILE.exists():
        raise RuntimeError("Missing /data/auth.json (not logged in)")

    locale = _locale_from_auth_file()
    auth = audible.Authenticator.from_file(AUTH_FILE, locale=locale)

    params = {
        "num_results": int(num_results),
        "response_groups": "product_desc,product_attrs,contributors,media,series",
        "sort_by": "-PurchaseDate",
    }

    log_library(f"Fetching library (num_results={num_results}, locale={getattr(locale, 'value', locale)})")
    with audible.Client(auth=auth) as client:
        resp = client.get("1.0/library", params=params)
    items = resp.get("items", []) or []

    tmp = DATA_DIR / "library_cache.json.tmp"
    tmp.write_text(json.dumps(items, indent=2), encoding="utf-8")
    (DATA_DIR / "library_cache.json").write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
    tmp.unlink(missing_ok=True)

    log_library(f"Library refresh complete (items={len(items)})")
    return len(items)


def load_job_status():
    if JOB_STATUS_FILE.exists():
        try:
            return json.loads(JOB_STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"failed_downloads": {}, "failed_conversions": {}, "interrupted": {}, "validated": {}}
    return {"failed_downloads": {}, "failed_conversions": {}, "interrupted": {}, "validated": {}}


def save_job_status(status):
    JOB_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOB_STATUS_FILE.write_text(json.dumps(status, indent=2), encoding="utf-8")


def _extract_asin(text: str):
    if not text:
        return None
    m = ASIN_RE.search(text.upper())
    return m.group(0) if m else None


def _norm_match(s: str):
    if not s:
        return ""
    return MATCH_NORMALIZE_RE.sub("", s.lower())


def _converted_manifest_path():
    return DATA_DIR / "converted_manifest.json"


def load_converted_manifest():
    p = _converted_manifest_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_converted_manifest(m):
    p = _converted_manifest_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(m, indent=2), encoding="utf-8")


def _library_titles_by_asin():
    """
    Best-effort ASIN -> title mapping from cached library.
    """
    cache = DATA_DIR / "library_cache.json"
    if not cache.exists():
        return {}
    try:
        items = json.loads(cache.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for b in items:
        asin = b.get("asin")
        title = b.get("title")
        if asin and title and asin not in out:
            out[asin] = title
    return out


def _find_aaxc_ready_files():
    aaxc_files = sorted(DOWNLOAD_DIR.glob("*.aaxc"))
    ready = []
    for aaxc in aaxc_files:
        voucher = aaxc.with_suffix(".voucher")
        if not voucher.exists():
            continue
        ready.append(aaxc)
    return ready

def _lock_path_for(aaxc_path: Path) -> Path:
    h = hashlib.sha1(str(aaxc_path).encode("utf-8")).hexdigest()
    return CONVERT_LOCKS_DIR / f"{h}.lock"

def _try_acquire_lock(aaxc_path: Path) -> Path | None:
    CONVERT_LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    lp = _lock_path_for(aaxc_path)
    try:
        fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"pid={os.getpid()} started_at={_now()} path={aaxc_path}\n")
        return lp
    except FileExistsError:
        return None

def _release_lock(lock_path: Path):
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def _build_convert_cmd(aaxc_path: Path, settings: dict, library_file: Path | None):
    fmt = settings.get("output_format", "m4b")
    cmd = ["bash", "/app/AAXtoMP3"]

    if fmt in ["m4b", "m4a", "mp3"]:
        cmd.append(f"-e:{fmt}")
    elif fmt == "flac":
        cmd.append("--flac")
    elif fmt == "opus":
        cmd.append("--opus")

    cmd.append("--use-audible-cli-data")

    if library_file and library_file.exists():
        cmd.extend(["--audible-cli-library-file", str(library_file)])

    if settings.get("single_file", True):
        cmd.append("--single")
    else:
        cmd.append("--chaptered")

    if fmt == "mp3":
        cmd.extend(["--level", str(settings.get("compression_mp3", 4))])
    elif fmt == "flac":
        cmd.extend(["--level", str(settings.get("compression_flac", 5))])
    elif fmt == "opus":
        cmd.extend(["--level", str(settings.get("compression_opus", 5))])

    dir_scheme = settings.get("dir_naming_scheme")
    if dir_scheme and dir_scheme != "$genre/$artist/$title":
        cmd.extend(["--dir-naming-scheme", dir_scheme])

    file_scheme = settings.get("file_naming_scheme")
    if file_scheme and file_scheme != "$title":
        cmd.extend(["--file-naming-scheme", file_scheme])

    chapter_scheme = settings.get("chapter_naming_scheme")
    if chapter_scheme:
        cmd.extend(["--chapter-naming-scheme", chapter_scheme])

    author_override = (settings.get("author_override") or "").strip()
    if author_override:
        cmd.extend(["--author", author_override])
    elif int(settings.get("keep_author_index") or 0) > 0:
        cmd.extend(["--keep-author", str(int(settings["keep_author_index"]))])

    if settings.get("no_clobber", False):
        cmd.append("--no-clobber")

    cmd.extend(["--target_dir", str(CONVERTED_DIR)])
    cmd.append(str(aaxc_path))
    return cmd


def _maybe_library_file(settings: dict) -> Path | None:
    if not settings.get("auto_export_library", True):
        return None
    return LIBRARY_TSV_FILE if LIBRARY_TSV_FILE.exists() else None


def _mark_conversion_failed(status, asin, title, error, last_chapter=None):
    status.setdefault("failed_conversions", {})
    prev = status["failed_conversions"].get(asin, {})
    status["failed_conversions"][asin] = {
        "title": title,
        "error": error,
        "last_chapter": last_chapter,
        "retries": int(prev.get("retries", 0)) + 1,
        "timestamp": _now(),
    }
    save_job_status(status)


def _mark_conversion_success(status, asin):
    status.setdefault("failed_conversions", {}).pop(asin, None)
    status.setdefault("interrupted", {}).pop(asin, None)
    save_job_status(status)


def _move_sources_if_enabled(aaxc_path: Path, settings: dict):
    if not settings.get("move_after_complete", False):
        return
    COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
    for p in [
        aaxc_path,
        aaxc_path.with_suffix(".voucher"),
        Path(str(aaxc_path).replace(".aaxc", "-chapters.json")),
    ]:
        if p.exists():
            shutil.move(str(p), str(COMPLETED_DIR / p.name))

    # Covers are title-based; move any matching jpg files.
    stem = aaxc_path.stem
    for jpg in DOWNLOAD_DIR.glob(f"{stem}*jpg"):
        try:
            shutil.move(str(jpg), str(COMPLETED_DIR / jpg.name))
        except Exception:
            pass


def validate_aaxc(aaxc_path: Path) -> bool:
    """
    Validate an AAXC file using ffprobe and its voucher.
    """
    try:
        voucher_path = aaxc_path.with_suffix('.voucher')
        if not voucher_path.exists():
            log(f"Validation failed: Missing voucher for {aaxc_path.name}")
            return False

        with open(voucher_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        key = data.get('content_license', {}).get('license_response', {}).get('key')
        iv = data.get('content_license', {}).get('license_response', {}).get('iv')
        
        if not key or not iv:
            log(f"Validation failed: Missing key/iv in voucher for {aaxc_path.name}")
            return False

        # Quick validation with ffprobe
        # We check only the first few seconds to ensure decryption works
        cmd = [
            "ffprobe",
            "-v", "error",
            "-audible_key", key,
            "-audible_iv", iv,
            "-i", str(aaxc_path)
        ]
        # Run with timeout to prevent hanging on bad files
        subprocess.run(cmd, check=True, timeout=30, capture_output=True)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        log(f"Validation failed for {aaxc_path.name}: {e}")
        return False


def _find_output_file(asin, title, start_time):
    """
    Search CONVERTED_DIR for a file created after start_time that matches the book.
    """
    safe_title = "".join(c for c in title if c.isalnum()).lower()
    
    # We walk the directory because output files might be nested (Chaptered mode or Naming schemes)
    for root, _, files in os.walk(CONVERTED_DIR):
        for f in files:
            fp = Path(root) / f
            try:
                # Check modification time
                mtime = datetime.fromtimestamp(fp.stat().st_mtime)
                # Allow a small buffer (files might be touched just before we started?) 
                # No, better to be strict: created *after* we started this job.
                # Actually, 'started_at' passed here should be a datetime object.
                if isinstance(start_time, str):
                    start_dt = datetime.fromisoformat(start_time)
                else:
                    start_dt = start_time

                if mtime < start_dt:
                    continue
                
                # Check Name Match
                f_norm = "".join(c for c in f if c.isalnum()).lower()
                
                # 1. ASIN match (strongest)
                if asin.lower() in f_norm:
                    return fp
                
                # 2. Title match
                if len(safe_title) > 10 and safe_title in f_norm:
                    return fp
            except Exception:
                continue
    return None


def _convert_one(aaxc: Path, titles_by_asin: dict):
    """
    Convert exactly one file. Uses a per-file lock to avoid duplicate conversions.
    """
    lock_path = _try_acquire_lock(aaxc)
    if not lock_path:
        return ("skipped_locked", aaxc, "")

    try:
        settings = load_settings()
        status = load_job_status()
        library_file = _maybe_library_file(settings)

        max_retries = int(settings.get("max_retries", 3))
        backoff_base = 5

        asin = _extract_asin(aaxc.name) or aaxc.stem
        title = titles_by_asin.get(_extract_asin(aaxc.name) or "", aaxc.stem)

        manifest = load_converted_manifest()
        key = str(aaxc)
        entry = manifest.get(key, {})
        
        if entry.get("status") == "success":
            return ("already_success", aaxc, "")

        # --- VALIDATION & AUTO-REPAIR ---
        # Only validate if we haven't already validated it successfully this session
        if not validate_aaxc(aaxc):
            repair_count = entry.get("repair_count", 0)
            if repair_count < 2:  # Allow up to 2 repairs
                log(f"Corrupt download detected: {aaxc.name}. Attempting auto-repair ({repair_count+1}/2)...")
                
                manifest[key] = {
                    "status": "repairing", 
                    "repair_count": repair_count + 1,
                    "last_repair": _now(),
                    "asin": asin
                }
                save_converted_manifest(manifest)

                try:
                    aaxc.unlink(missing_ok=True)
                    aaxc.with_suffix('.voucher').unlink(missing_ok=True)
                except Exception as e:
                    log(f"Failed to delete corrupt files: {e}")

                cover_size = settings.get("cover_size", "1215")
                success, err = _download_one(asin, cover_size)
                
                if success:
                    return ("repaired_downloaded", aaxc, "")
                else:
                    return ("repair_failed", aaxc, err)
            else:
                err = "Validation failed (max repairs exceeded)"
                log(f"Giving up on {aaxc.name}: {err}")
                _mark_conversion_failed(status, asin, title, err)
                manifest[key] = {"status": "failed_validation", "repair_count": repair_count, "error": err}
                save_converted_manifest(manifest)
                return ("failed_validation", aaxc, err)

        # --- CONVERSION ---
        tries = int(entry.get("tries", 0))
        if tries >= max_retries:
            return ("retry_exhausted", aaxc, entry.get("error", ""))

        cmd = _build_convert_cmd(aaxc, settings, library_file)

        start_time = datetime.now() # Capture exact start time object
        
        log(f"Converting: asin={asin} file={aaxc.name} try={tries+1}/{max_retries}")
        manifest[key] = {
            "status": "running", 
            "tries": tries + 1, 
            "started_at": start_time.isoformat(), 
            "asin": asin, 
            "title": title,
            "repair_count": entry.get("repair_count", 0)
        }
        save_converted_manifest(manifest)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=7200,
                cwd=str(DOWNLOAD_DIR),
            )
        except subprocess.TimeoutExpired:
            err = "Timeout - conversion took too long"
            log(f"Failed: {aaxc.name} {err}")
            _mark_conversion_failed(status, asin, title, err)
            manifest = load_converted_manifest()
            manifest[key].update({"status": "failed", "ended_at": _now(), "error": err})
            save_converted_manifest(manifest)
            time.sleep(backoff_base * (tries + 1))
            return ("timeout", aaxc, err)

        if result.returncode == 0:
            # --- OUTPUT VERIFICATION ---
            # Verify that a file was actually created!
            out_file = _find_output_file(asin, title, start_time)
            
            if out_file:
                log(f"Success: {aaxc.name} -> {out_file.name}")
                _mark_conversion_success(status, asin)
                manifest = load_converted_manifest()
                manifest[key].update({
                    "status": "success", 
                    "ended_at": _now(),
                    "output_path": str(out_file)
                })
                save_converted_manifest(manifest)
                _move_sources_if_enabled(aaxc, settings)
                return ("success", aaxc, "")
            else:
                err = "Conversion reported success but no output file found."
                log(f"Failed Verification: {aaxc.name} - {err}")
                _mark_conversion_failed(status, asin, title, err)
                manifest = load_converted_manifest()
                manifest[key].update({"status": "failed", "ended_at": _now(), "error": err})
                save_converted_manifest(manifest)
                return ("failed_verification", aaxc, err)

        err = (result.stderr or result.stdout or "Unknown error")[:400]
        log(f"Failed: {aaxc.name} {err}")
        _mark_conversion_failed(status, asin, title, err)
        manifest = load_converted_manifest()
        manifest[key].update({"status": "failed", "ended_at": _now(), "error": err})
        save_converted_manifest(manifest)
        time.sleep(backoff_base * (tries + 1))
        return ("failed", aaxc, err)
    finally:
        _release_lock(lock_path)


def convert_watch(poll_seconds: int, max_parallel: int):
    max_parallel = max(1, int(max_parallel))
    titles = _library_titles_by_asin()

    log(f"convert_watch starting (poll={poll_seconds}s, max_parallel={max_parallel})")

    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        in_flight = set()

        while True:
            # Reap completed tasks
            if in_flight:
                done, in_flight = wait(in_flight, timeout=0, return_when=FIRST_COMPLETED)
                for fut in done:
                    try:
                        kind, aaxc, err = fut.result()
                        if kind in ("success", "failed", "timeout"):
                            log(f"Result: {kind} file={aaxc.name} err={err[:120] if err else ''}")
                    except Exception as e:
                        log(f"Worker exception: {e}")

            # Fill queue
            ready = _find_aaxc_ready_files()
            if ready:
                for aaxc in ready:
                    if len(in_flight) >= max_parallel:
                        break
                    in_flight.add(pool.submit(_convert_one, aaxc, titles))

            time.sleep(poll_seconds)


def library_fetch(num_results: int):
    LIBRARY_JOB_FILE.parent.mkdir(parents=True, exist_ok=True)
    LIBRARY_JOB_FILE.write_text(
        json.dumps(
            {"status": "running", "started_at": _now(), "num_results": int(num_results)},
            indent=2,
        ),
        encoding="utf-8",
    )
    try:
        n = refresh_library_full(num_results=num_results)
        LIBRARY_JOB_FILE.write_text(
            json.dumps(
                {"status": "success", "started_at": _now(), "finished_at": _now(), "items": n},
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as e:
        log_library(f"Library refresh failed: {e}")
        LIBRARY_JOB_FILE.write_text(
            json.dumps(
                {"status": "failed", "started_at": _now(), "finished_at": _now(), "error": str(e)},
                indent=2,
            ),
            encoding="utf-8",
        )
        raise


def convert_batch(asins: list, max_parallel: int, paths: list = None):
    log(f"Batch convert starting: {len(asins)} items, parallel={max_parallel}")
    log(f"Batch convert: ASINs received: {asins}")
    log(f"Batch convert: Paths received: {paths}")
    max_parallel = max(1, min(int(max_parallel), 5))
    titles = _library_titles_by_asin()

    # If paths are provided directly, use them (preferred - more reliable matching)
    to_process = []
    if paths and len(paths) == len(asins):
        log(f"Batch convert: Using {len(paths)} provided paths")
        for p_str in paths:
            p = Path(p_str)
            if p.exists() and p.with_suffix(".voucher").exists():
                to_process.append(p)
                log(f"Batch convert: Added {p}")
            else:
                log(f"Batch convert: Skipping {p_str} - file or voucher missing (exists={p.exists()}, voucher={p.with_suffix('.voucher').exists()})")

    # Fallback: scan download dir for matching AAXC files (legacy behavior)
    if not to_process:
        ready_files = _find_aaxc_ready_files()
        target_asins = set(asins)

        for p in ready_files:
            file_asin = _extract_asin(p.name) or p.stem
            if file_asin in target_asins:
                to_process.append(p)

    if not to_process:
        log("Batch convert: No matching ready files found for provided ASINs.")
        return

    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {pool.submit(_convert_one, p, titles): p for p in to_process}
        for fut in wait(futures, return_when=FIRST_COMPLETED)[0]:
            pass
        wait(futures)
        
    log("Batch convert complete")


def _tokenize(text):
    return set(re.findall(r"\w+", str(text).lower()))

def sync_manifest():
    """
    Scan CONVERTED_DIR and populate manifest for existing files using token-based matching.
    """
    log("Starting manifest sync...")
    manifest = load_converted_manifest()
    library_titles = _library_titles_by_asin()
    
    # Pre-compute tokens for library titles
    # We map ASIN -> Token Set
    lib_tokens = {asin: _tokenize(title) for asin, title in library_titles.items()}
    
    extensions = {".m4b", ".m4a", ".mp3", ".flac", ".ogg", ".opus"}
    count = 0
    scanned = 0
    
    for root, _, files in os.walk(CONVERTED_DIR):
        for f in files:
            fp = Path(root) / f
            if fp.suffix.lower() not in extensions:
                continue
            
            scanned += 1
            
            # Check overlap with existing manifest output paths
            already_tracked = False
            for v in manifest.values():
                if v.get("output_path") == str(fp):
                    already_tracked = True
                    break
            
            if already_tracked:
                continue

            # 1. Try exact ASIN match from filename/path
            asin = _extract_asin(f)
            if not asin:
                asin = _extract_asin(fp.parent.name)
            
            # 2. Token-based fuzzy match
            if not asin:
                # Combine filename + parent + grandparent to get "Author / Series / Title" context
                file_tokens = _tokenize(fp.stem) | _tokenize(fp.parent.name) | _tokenize(fp.parent.parent.name)
                
                best_match_asin = None
                best_score = 0.0
                
                for t_asin, t_tokens in lib_tokens.items():
                    if not t_tokens: continue
                    
                    # Calculate coverage: How much of the Library Title is in the File Path?
                    # We care if the file *is* this book, so the file path should contain the book title words.
                    common = t_tokens & file_tokens
                    score = len(common) / len(t_tokens)
                    
                    if score > 0.85 and score > best_score: # Strict threshold (85%)
                        best_score = score
                        best_match_asin = t_asin
                
                if best_match_asin:
                    asin = best_match_asin
                    # log(f"Fuzzy matched: {fp.name} -> {library_titles[asin]} (Score: {best_score:.2f})")

            if asin:
                title = library_titles.get(asin, fp.stem)
                
                # Check for source AAXC file to use as the canonical key
                # We check Downloads, Completed, AND the current Converted folder (recursive)
                aaxc_candidates = list(DOWNLOAD_DIR.glob(f"*{asin}*.aaxc")) + \
                                  list(COMPLETED_DIR.rglob(f"*{asin}*.aaxc")) + \
                                  list(CONVERTED_DIR.rglob(f"*{asin}*.aaxc"))
                
                key = str(aaxc_candidates[0]) if aaxc_candidates else f"legacy_import_{asin}"
                
                # Cleanup: If we found a valid ASIN, check if this file was previously 
                # imported under a garbage key (like legacy_import_ELEMENTALS)
                garbage_keys = [k for k, v in manifest.items() if v.get("output_path") == str(fp) and k != key]
                for gk in garbage_keys:
                    del manifest[gk]

                # Only update if not present or failed
                if key not in manifest or manifest[key].get("status") != "success":
                    manifest[key] = {
                        "status": "success",
                        "asin": asin,
                        "title": title,
                        "output_path": str(fp),
                        "imported_at": _now()
                    }
                    count += 1
                    log(f"Imported: {title} ({asin})")

    save_converted_manifest(manifest)
    log(f"Manifest sync complete. Scanned {scanned} files, Imported {count} new items.")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    cw = sub.add_parser("convert-watch", help="Continuously convert ready downloads")
    cw.add_argument("--poll-seconds", type=int, default=10)
    cw.add_argument("--max-parallel", type=int, default=1)

    lf = sub.add_parser("library-fetch", help="Refresh full library cache in background")
    lf.add_argument("--num-results", type=int, default=1000)

    db = sub.add_parser("download-batch", help="Batch download specific ASINs")
    db.add_argument("--asins", type=str, required=True)
    db.add_argument("--cover-size", type=str, default="1215")
    db.add_argument("--max-parallel", type=int, default=3)

    cb = sub.add_parser("convert-batch", help="Batch convert specific ASINs")
    cb.add_argument("--asins", type=str, required=True)
    cb.add_argument("--paths", type=str, default="", help="Comma-separated file paths corresponding to ASINs")
    cb.add_argument("--max-parallel", type=int, default=3)

    sm = sub.add_parser("sync-manifest", help="Scan output dir and update manifest")

    args = parser.parse_args()

    if args.cmd == "convert-watch":
        convert_watch(args.poll_seconds, args.max_parallel)
        return 0
    if args.cmd == "library-fetch":
        library_fetch(args.num_results)
        return 0
    if args.cmd == "download-batch":
        download_batch(args.asins.split(","), args.cover_size, args.max_parallel)
        return 0
    if args.cmd == "convert-batch":
        paths = [p for p in args.paths.split(",") if p] if args.paths else []
        convert_batch(args.asins.split(","), args.max_parallel, paths)
        return 0
    if args.cmd == "sync-manifest":
        sync_manifest()
        return 0

    return 1


DOWNLOAD_LOG = DATA_DIR / "download_batch.log"
# ... rest of file (log_download etc) ...

def log_download(msg: str):
    DOWNLOAD_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(DOWNLOAD_LOG, "a", encoding="utf-8") as f:
        f.write(f"{_now()} {msg}\n")

def _download_one(asin: str, cover_size: str):
    try:
        cmd = [
            "audible", "download",
            "--asin", asin,
            "--aaxc",
            "--cover", "--cover-size", cover_size,
            "--chapter",
            "--filename-mode", "asin_unicode",
            "--output-dir", str(DOWNLOAD_DIR),
            "--no-confirm"
        ]
        log_download(f"Starting download: {asin}")
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(DOWNLOAD_DIR))
        if res.returncode == 0:
            log_download(f"Success: {asin}")
            return True, ""
        else:
            err = (res.stderr or res.stdout or "")[:200]
            log_download(f"Failed: {asin} - {err}")
            return False, err
    except Exception as e:
        log_download(f"Exception: {asin} - {e}")
        return False, str(e)

def download_batch(asins: list, cover_size: str, max_parallel: int):
    log_download(f"Batch download starting: {len(asins)} items, parallel={max_parallel}")
    max_parallel = max(1, min(int(max_parallel), 5)) # Cap at 5 to be safe
    
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {pool.submit(_download_one, asin, cover_size): asin for asin in asins if asin}
        for fut in wait(futures, return_when=FIRST_COMPLETED)[0]:
            pass
        # Wait for all
        wait(futures)
    
    log_download("Batch download complete")


if __name__ == "__main__":
    raise SystemExit(main())
