"""Audible API client wrapper for audible-cli integration."""

import asyncio
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import audible
from core.config import AudibleCliProgressFormat, get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NDJSON Event Parsing (for --progress-format ndjson)
# ---------------------------------------------------------------------------


@dataclass
class NdjsonDownloadEvent:
    """Parsed NDJSON download event from audible-cli."""

    event_type: str
    asin: str | None = None
    filename: str | None = None
    current_bytes: int | None = None
    total_bytes: int | None = None
    bytes_per_sec: float | None = None
    success: bool | None = None
    resumed: bool | None = None
    error_code: str | None = None
    message: str | None = None
    timestamp: str | None = None
    raw: dict[str, Any] | None = None


def parse_ndjson_download_line(line: str) -> NdjsonDownloadEvent | None:
    """
    Parse a single NDJSON line from audible-cli --progress-format ndjson.

    Expected event types:
    - download_start: {asin, filename, total_bytes, resumed, timestamp}
    - download_progress: {asin, filename, current_bytes, total_bytes, bytes_per_sec, resumed, timestamp}
    - download_complete: {asin, filename, total_bytes, success, timestamp}
    - download_error: {asin, success:false, error_code, message}

    Returns:
        NdjsonDownloadEvent if parsing succeeds, None if line is malformed or not JSON.
        Malformed lines are logged at WARNING level but do NOT raise exceptions.
    """
    line = line.strip()
    if not line:
        return None

    try:
        data = json.loads(line)
    except json.JSONDecodeError as e:
        # Malformed JSON - log and continue (MUST NOT crash)
        logger.warning("NDJSON parse error (ignoring line): %s | line=%r", e, line[:200])
        return None

    if not isinstance(data, dict):
        logger.warning("NDJSON line is not a dict (ignoring): %r", line[:200])
        return None

    event_type = data.get("event_type") or data.get("type") or "unknown"

    return NdjsonDownloadEvent(
        event_type=event_type,
        asin=data.get("asin"),
        filename=data.get("filename"),
        current_bytes=_safe_int(data.get("current_bytes")),
        total_bytes=_safe_int(data.get("total_bytes")),
        bytes_per_sec=_safe_float(data.get("bytes_per_sec")),
        success=data.get("success"),
        resumed=data.get("resumed"),
        error_code=data.get("error_code"),
        message=data.get("message"),
        timestamp=data.get("timestamp"),
        raw=data,
    )


def _safe_int(val: Any) -> int | None:
    """Safely convert value to int, return None on failure."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _safe_float(val: Any) -> float | None:
    """Safely convert value to float, return None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


class AudibleError(Exception):
    """Base exception for Audible operations."""
    pass


class AudibleClientError(AudibleError):
    """General client error."""
    pass


class AudibleAuthError(AudibleError):
    """Authentication failed."""
    pass


class AudibleLibraryError(AudibleError):
    """Library fetch failed."""
    pass


class AudibleDownloadError(AudibleError):
    """Download failed."""
    pass


class AudibleNdjsonDownloadError(AudibleDownloadError):
    """Download failed with structured NDJSON error event.

    Attributes:
        asin: The ASIN that failed.
        error_code: Structured error code from audible-cli.
        message: Human-readable error message.
    """

    def __init__(self, asin: str, error_code: str, message: str):
        self.asin = asin
        self.error_code = error_code
        self.message = message
        super().__init__(f"Download failed for {asin}: [{error_code}] {message}")


class AudibleClient:
    """Wrapper for audible operations."""

    def __init__(self) -> None:
        """Initialize Audible client."""
        self.settings = get_settings()
        self.auth_file = self.settings.audible_auth_file
        self.profile = self.settings.audible_profile

    async def is_authenticated(self) -> bool:
        """
        Check whether we can authenticate to Audible.

        This intentionally does a very small library request to validate the auth file.
        """
        if not self.auth_file.exists():
            return False

        try:
            # Use a tiny request as the most reliable validation.
            auth = audible.Authenticator.from_file(self.auth_file)
            client = audible.Client(auth)

            def _probe() -> bool:
                resp = client.get(
                    "1.0/library",
                    params={
                        "num_results": 1,
                        "response_groups": "product_attrs",
                        "sort_by": "-PurchaseDate",
                    },
                )
                return isinstance(resp, dict) and "items" in resp

            return await asyncio.to_thread(_probe)
        except Exception as e:
            logger.warning("Audible authentication probe failed: %s", e)
            return False

    async def get_library(
        self,
        limit: int | None = None,
        response_groups: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch library from Audible using audible library directly.

        Args:
            limit: Maximum number of items to fetch.
            response_groups: Specific response groups to request.

        Returns:
            List of book metadata dictionaries.

        Raises:
            AudibleLibraryError: If the library fetch fails.
        """
        if not response_groups:
            # Default groups that include product_images (media)
            response_groups = [
                "product_desc",
                "product_attrs",
                "contributors",
                "media",
                "series",
                "product_extended_attrs",
            ]

        try:
            # Run in executor to avoid blocking async loop with sync library calls
            return await asyncio.to_thread(
                self._get_library_sync, limit, response_groups
            )
        except Exception as e:
            error_msg = f"Failed to fetch library: {e}"
            logger.error(error_msg)
            raise AudibleLibraryError(error_msg) from e

    def _get_library_sync(
        self,
        limit: int | None,
        response_groups: list[str],
    ) -> list[dict[str, Any]]:
        """Synchronous implementation of library fetch."""
        if not self.auth_file.exists():
            raise AudibleAuthError("Auth file not found")

        auth = audible.Authenticator.from_file(self.auth_file)
        client = audible.Client(auth)

        # Format response groups for API
        response_groups_str = ",".join(response_groups)

        def _fetch(sort_by: str, num_results: int) -> list[dict[str, Any]]:
            resp = client.get(
                "1.0/library",
                params={
                    "num_results": num_results,
                    "response_groups": response_groups_str,
                    "sort_by": sort_by,
                },
            )
            batch = resp.get("items", [])
            return batch if isinstance(batch, list) else []

        # Audible enforces `num_results <= 1000` and does not reliably provide a page token in
        # the response (at least for current audible-python responses).
        # Strategy:
        # - Fetch the newest items (sort_by=-PurchaseDate).
        # - If we might be truncated, also fetch the oldest items (sort_by=PurchaseDate) and merge by ASIN.
        max_batch = 1000
        target = min(max(int(limit), 1), max_batch) if limit is not None else max_batch

        newest = _fetch("-PurchaseDate", target)
        items = newest

        # If we hit the cap, do a second pass from the other end to cover libraries > 1000.
        needs_second_pass = False
        if limit is None:
            needs_second_pass = len(newest) >= max_batch
        else:
            needs_second_pass = limit > max_batch and len(newest) >= max_batch

        if needs_second_pass:
            oldest = _fetch("PurchaseDate", max_batch)
            if oldest:
                seen = {it.get("asin") for it in items if isinstance(it, dict)}
                for it in oldest:
                    if not isinstance(it, dict):
                        continue
                    asin = it.get("asin")
                    if asin and asin not in seen:
                        items.append(it)
                        seen.add(asin)

        if limit is not None:
            items = items[: int(limit)]
        
        logger.info("Successfully fetched %d items from library", len(items))
        return items

    async def get_chapters(self, asin: str) -> list[dict[str, Any]]:
        """
        Fetch chapters for a book.

        Args:
            asin: The book ASIN.

        Returns:
            List of chapter dicts with 'title', 'length_ms', 'start_offset_ms'.
        """
        try:
            return await asyncio.to_thread(self._get_chapters_sync, asin)
        except Exception as e:
            logger.error(f"Failed to fetch chapters for {asin}: {e}")
            return []

    def _get_chapters_sync(self, asin: str) -> list[dict[str, Any]]:
        if not self.auth_file.exists():
            raise AudibleAuthError("Auth file not found")

        auth = audible.Authenticator.from_file(self.auth_file)
        client = audible.Client(auth)

        try:
            # Request content metadata with chapter_info
            response = client.get(
                f"1.0/content/{asin}/metadata",
                params={"response_groups": "chapter_info"}
            )

            content_metadata = response.get("content_metadata", {})
            chapter_info = content_metadata.get("chapter_info", {})
            chapters = chapter_info.get("chapters", [])

            return chapters
        except Exception as e:
            logger.warning(f"Audible API error fetching chapters for {asin}: {e}")
            return []

    # ... (keep download, download_batch, etc.) ...

    async def download(
        self,
        asin: str,
        output_dir: Path,
        cover_size: str = "1215",
        quality: str = "high",
        aaxc: bool = True,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """
        Download an audiobook from Audible.

        Supports two progress parsing modes controlled by AUDIBLE_CLI_PROGRESS_FORMAT:
        - 'tqdm' (default): Parse tqdm progress bar output
        - 'ndjson': Use --progress-format ndjson for structured events

        Args:
            asin: Book ASIN to download.
            output_dir: Directory to save files.
            cover_size: Cover image size.
            quality: Audio quality.
            aaxc: Download in AAXC format (required for newer books).
            progress_callback: Optional callback(current_bytes, total_bytes).

        Returns:
            Dictionary with download result info including:
            - success: bool
            - asin: str
            - output_dir: str
            - stdout: str
            - stderr: str
            - files: list[str] (if successful)
            - ndjson_error: dict (if NDJSON mode detected a download_error event)
        """
        progress_format = self.settings.audible_cli_progress_format
        use_ndjson = progress_format == AudibleCliProgressFormat.NDJSON

        logger.info(
            "Starting download for ASIN %s to %s (format=%s, quality=%s, progress_mode=%s)",
            asin,
            output_dir,
            "aaxc" if aaxc else "aax",
            quality,
            progress_format.value,
        )

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "audible",
        ]

        # Add global options (must come before subcommand)
        if self.profile:
            cmd.extend(["--profile", self.profile])

        cmd.extend([
            "download",
            "--asin",
            asin,
            "--output-dir",
            str(output_dir),
            "--cover",
            "--cover-size",
            cover_size,
            "--chapter",
            "--filename-mode",
            "asin_unicode",
            "--quality",
            quality,
            "--no-confirm",
        ])

        if aaxc:
            cmd.append("--aaxc")

        # Add NDJSON progress format flag when enabled
        if use_ndjson:
            cmd.extend(["--progress-format", "ndjson"])

        logger.info("Running download command: %s", " ".join(cmd[:8]) + "...")

        # State for NDJSON error tracking
        ndjson_error_event: NdjsonDownloadEvent | None = None

        def _on_tqdm_progress_line(line: str) -> None:
            """Parse tqdm-style progress output."""
            if not progress_callback:
                return
            parsed = _parse_audible_cli_progress_line(line)
            if not parsed:
                return
            cur_bytes, total_bytes = parsed
            progress_callback(cur_bytes, total_bytes)

        def _on_ndjson_stdout_line(line: str) -> None:
            """Parse NDJSON events from stdout."""
            nonlocal ndjson_error_event

            event = parse_ndjson_download_line(line)
            if not event:
                # Malformed line - already logged by parser, continue
                return

            if event.event_type == "download_progress":
                if progress_callback and event.current_bytes is not None and event.total_bytes is not None:
                    progress_callback(event.current_bytes, event.total_bytes)
            elif event.event_type == "download_start":
                logger.info(
                    "NDJSON download_start: asin=%s, filename=%s, total_bytes=%s, resumed=%s",
                    event.asin, event.filename, event.total_bytes, event.resumed,
                )
                # Initialize progress with total bytes from start event
                if progress_callback and event.total_bytes is not None:
                    progress_callback(0, event.total_bytes)
            elif event.event_type == "download_complete":
                logger.info(
                    "NDJSON download_complete: asin=%s, success=%s, total_bytes=%s",
                    event.asin, event.success, event.total_bytes,
                )
                # Ensure progress shows 100% on completion
                if progress_callback and event.total_bytes is not None and event.success:
                    progress_callback(event.total_bytes, event.total_bytes)
            elif event.event_type == "download_error":
                logger.error(
                    "NDJSON download_error: asin=%s, error_code=%s, message=%s",
                    event.asin, event.error_code, event.message,
                )
                # Store the error event for result processing
                ndjson_error_event = event
            else:
                # Unknown event type - log and continue (MUST NOT crash)
                logger.debug("NDJSON unknown event type '%s': %s", event.event_type, event.raw)

        # Select line handlers based on progress mode
        if use_ndjson:
            # NDJSON mode: stdout has JSON events, stderr may still have human-readable logs
            on_stdout = _on_ndjson_stdout_line
            on_stderr = None  # Don't parse stderr as progress in NDJSON mode
        else:
            # tqdm mode: both stdout and stderr may have tqdm progress bars
            on_stdout = _on_tqdm_progress_line
            on_stderr = _on_tqdm_progress_line

        result = await self._run_command_streaming(
            cmd,
            timeout=1800,
            on_stdout_line=on_stdout,
            on_stderr_line=on_stderr,
        )  # 30 minute timeout
        logger.info("Download command returned: returncode=%s, stderr_preview=%s",
                   result.get("returncode"), result.get("stderr", "")[:200])

        # Determine success - check both return code and NDJSON error events
        success = result["returncode"] == 0 and ndjson_error_event is None

        # Build response
        response: dict[str, Any] = {
            "success": success,
            "asin": asin,
            "output_dir": str(output_dir),
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }

        if success:
            logger.info("Successfully downloaded ASIN %s", asin)
            downloaded_files = self._find_downloaded_files(asin, output_dir)
            logger.debug("Downloaded files: %s", downloaded_files)
            response["files"] = downloaded_files
        else:
            # Include structured error info if we have an NDJSON error event
            if ndjson_error_event:
                response["ndjson_error"] = {
                    "asin": ndjson_error_event.asin,
                    "error_code": ndjson_error_event.error_code,
                    "message": ndjson_error_event.message,
                }
                logger.error(
                    "Download failed for ASIN %s: [%s] %s",
                    asin,
                    ndjson_error_event.error_code,
                    ndjson_error_event.message,
                )
            else:
                logger.error(
                    "Download failed for ASIN %s: %s",
                    asin,
                    result["stderr"],
                )
            response["files"] = []

        return response

    def _find_downloaded_files(self, asin: str, output_dir: Path) -> list[str]:
        """
        Find files downloaded for an ASIN.

        Args:
            asin: The ASIN to search for.
            output_dir: Directory to search in.

        Returns:
            List of file paths found.
        """
        files: list[str] = []
        for pattern in [f"{asin}*", f"*{asin}*"]:
            for match in output_dir.glob(pattern):
                if match.is_file():
                    files.append(str(match))
        return files

    async def download_batch(
        self,
        asins: list[str],
        output_dir: Path,
        cover_size: str = "1215",
        max_parallel: int = 5,
        progress_callback: "Callable[[str, int, int], None] | None" = None,
    ) -> list[dict[str, Any]]:
        """
        Download multiple audiobooks in parallel.

        Args:
            asins: List of ASINs to download.
            output_dir: Directory to save files.
            cover_size: Cover image size.
            max_parallel: Maximum concurrent downloads.
            progress_callback: Optional callback(asin, completed, total).

        Returns:
            List of download results.
        """
        logger.info(
            "Starting batch download: %d ASINs with max_parallel=%d",
            len(asins),
            max_parallel,
        )

        semaphore = asyncio.Semaphore(max_parallel)
        completed_count = 0
        lock = asyncio.Lock()

        async def download_one(asin: str) -> dict[str, Any]:
            nonlocal completed_count
            async with semaphore:
                try:
                    result = await self.download(asin, output_dir, cover_size)
                except Exception as e:
                    logger.exception("Exception downloading ASIN %s", asin)
                    result = {"success": False, "asin": asin, "error": str(e)}

                async with lock:
                    completed_count += 1
                    if progress_callback:
                        progress_callback(asin, completed_count, len(asins))

                return result

        tasks = [download_one(asin) for asin in asins]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and log summary
        successful = 0
        failed = 0
        processed_results: list[dict[str, Any]] = []

        for r in results:
            if isinstance(r, dict):
                processed_results.append(r)
                if r.get("success"):
                    successful += 1
                else:
                    failed += 1
            else:
                processed_results.append({"success": False, "error": str(r)})
                failed += 1

        logger.info(
            "Batch download complete: %d successful, %d failed out of %d total",
            successful,
            failed,
            len(asins),
        )

        return processed_results

    async def get_activation_bytes(self) -> str | None:
        """
        Get activation bytes for AAX decryption.

        Returns:
            The activation bytes string, or None if unavailable.
        """
        logger.debug("Fetching activation bytes")

        cmd = ["audible"]
        if self.profile:
            cmd.extend(["--profile", self.profile])
        cmd.extend(["activation-bytes", "--output-format", "json"])

        result = await self._run_command(cmd)

        if result["returncode"] != 0:
            logger.warning(
                "Failed to get activation bytes: %s",
                result["stderr"],
            )
            return None

        try:
            data = json.loads(result["stdout"])
            activation_bytes = data.get("activation_bytes")
            if activation_bytes:
                logger.debug("Successfully retrieved activation bytes")
            else:
                logger.warning("Activation bytes not found in response")
            return activation_bytes
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to parse activation bytes response: %s", e)
            return None

    async def _run_command(
        self,
        cmd: list[str],
        timeout: int = 300,
    ) -> dict[str, Any]:
        """
        Run an async subprocess command.

        Args:
            cmd: Command and arguments.
            timeout: Timeout in seconds.

        Returns:
            Dictionary with returncode, stdout, stderr.
        """
        cmd_str = " ".join(cmd[:3]) + "..."  # Log first few args only
        logger.info("Executing command: %s (timeout=%ds)", cmd_str, timeout)

        process: asyncio.subprocess.Process | None = None

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            logger.info("Process created with PID: %s", process.pid)

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            result = {
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }

            if process.returncode != 0:
                logger.info(
                    "Command exited with code %d: %s",
                    process.returncode,
                    result["stderr"][:300],
                )

            return result

        except asyncio.CancelledError:
            # Ensure we don't leave orphaned subprocesses when jobs are cancelled.
            if process:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            raise
        except asyncio.TimeoutError:
            logger.error("Command timed out after %ds: %s", timeout, cmd_str)
            if process:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
            }
        except FileNotFoundError as e:
            logger.error("Command not found: %s - %s", cmd[0], e)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command not found: {e}",
            }
        except Exception as e:
            logger.exception("Unexpected error running command: %s", cmd_str)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    async def _run_command_streaming(
        self,
        cmd: list[str],
        timeout: int = 300,
        on_stdout_line: Callable[[str], None] | None = None,
        on_stderr_line: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """
        Run an async subprocess command while streaming output.

        This is primarily used for audible-cli download so we can derive file-level progress.
        """
        cmd_str = " ".join(cmd[:3]) + "..."
        logger.info("Executing command (streaming): %s (timeout=%ds)", cmd_str, timeout)

        process: asyncio.subprocess.Process | None = None
        max_capture = 50_000
        stdout_buf: list[str] = []
        stderr_buf: list[str] = []
        stdout_chars = 0
        stderr_chars = 0

        async def _read_stream(
            stream: asyncio.StreamReader | None,
            sink: list[str],
            cap: str,
            on_line: Callable[[str], None] | None,
        ) -> None:
            nonlocal stdout_chars, stderr_chars
            if stream is None:
                return
            buf = ""
            while True:
                chunk = await stream.read(4096)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                # Capture (bounded)
                if cap == "stdout":
                    if stdout_chars < max_capture:
                        take = text[: max(0, max_capture - stdout_chars)]
                        sink.append(take)
                        stdout_chars += len(take)
                else:
                    if stderr_chars < max_capture:
                        take = text[: max(0, max_capture - stderr_chars)]
                        sink.append(take)
                        stderr_chars += len(take)

                buf += text
                # tqdm writes updates using carriage returns
                while True:
                    split_idx = None
                    for sep in ("\r", "\n"):
                        i = buf.find(sep)
                        if i != -1 and (split_idx is None or i < split_idx):
                            split_idx = i
                    if split_idx is None:
                        break
                    line = buf[:split_idx]
                    buf = buf[split_idx + 1 :]
                    if on_line and line.strip():
                        on_line(line)
            if on_line and buf.strip():
                on_line(buf)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_task = asyncio.create_task(
                _read_stream(process.stdout, stdout_buf, "stdout", on_stdout_line)
            )
            stderr_task = asyncio.create_task(
                _read_stream(process.stderr, stderr_buf, "stderr", on_stderr_line)
            )

            await asyncio.wait_for(process.wait(), timeout=timeout)
            await asyncio.gather(stdout_task, stderr_task)

            return {
                "returncode": process.returncode,
                "stdout": "".join(stdout_buf),
                "stderr": "".join(stderr_buf),
            }

        except asyncio.CancelledError:
            if process:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            raise
        except asyncio.TimeoutError:
            logger.error("Command timed out after %ds: %s", timeout, cmd_str)
            if process:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            return {
                "returncode": -1,
                "stdout": "".join(stdout_buf),
                "stderr": "".join(stderr_buf) or f"Command timed out after {timeout}s",
            }
        except FileNotFoundError as e:
            logger.error("Command not found: %s - %s", cmd[0], e)
            return {
                "returncode": -1,
                "stdout": "".join(stdout_buf),
                "stderr": f"Command not found: {e}",
            }
        except Exception as e:
            logger.exception("Unexpected error running command (streaming): %s", cmd_str)
            return {
                "returncode": -1,
                "stdout": "".join(stdout_buf),
                "stderr": str(e),
            }


_PROGRESS_RE = re.compile(
    r"(?P<pct>\d+)%\|.*?\|\s*(?P<cur>[0-9.]+)(?P<cur_unit>[kMGT]?)\s*/\s*(?P<tot>[0-9.]+)(?P<tot_unit>[kMGT]?)",
    re.IGNORECASE,
)


def _unit_multiplier(unit: str) -> int:
    u = (unit or "").lower()
    if u == "k":
        return 1024
    if u == "m":
        return 1024 ** 2
    if u == "g":
        return 1024 ** 3
    if u == "t":
        return 1024 ** 4
    return 1


def _parse_audible_cli_progress_line(line: str) -> tuple[int, int] | None:
    """
    Parse audible-cli tqdm output like:
      `ASIN_Title-AAX_44_128.aaxc:   1%|          | 9.46M/845M ...`
    """
    if ".aax" not in line and ".aaxc" not in line:
        return None
    m = _PROGRESS_RE.search(line)
    if not m:
        return None
    try:
        cur = float(m.group("cur"))
        tot = float(m.group("tot"))
        cur_b = int(cur * _unit_multiplier(m.group("cur_unit")))
        tot_b = int(tot * _unit_multiplier(m.group("tot_unit")))
        if tot_b <= 0:
            return None
        return cur_b, tot_b
    except Exception:
        return None
