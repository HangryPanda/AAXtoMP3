"""Audible API client wrapper for audible-cli integration."""

import asyncio
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import audible
from core.config import get_settings

logger = logging.getLogger(__name__)


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
    ) -> dict[str, Any]:
        """
        Download an audiobook from Audible.

        Args:
            asin: Book ASIN to download.
            output_dir: Directory to save files.
            cover_size: Cover image size.
            quality: Audio quality.
            aaxc: Download in AAXC format (required for newer books).

        Returns:
            Dictionary with download result info including:
            - success: bool
            - asin: str
            - output_dir: str
            - stdout: str
            - stderr: str
            - files: list[str] (if successful)
        """
        logger.info(
            "Starting download for ASIN %s to %s (format=%s, quality=%s)",
            asin,
            output_dir,
            "aaxc" if aaxc else "aax",
            quality,
        )

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "audible",
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
        ]

        if aaxc:
            cmd.append("--aaxc")

        result = await self._run_command(cmd, timeout=1800)  # 30 minute timeout

        success = result["returncode"] == 0

        if success:
            logger.info("Successfully downloaded ASIN %s", asin)
            # Find downloaded files
            downloaded_files = self._find_downloaded_files(asin, output_dir)
            logger.debug("Downloaded files: %s", downloaded_files)
        else:
            logger.error(
                "Download failed for ASIN %s: %s",
                asin,
                result["stderr"],
            )
            downloaded_files: list[str] = []

        return {
            "success": success,
            "asin": asin,
            "output_dir": str(output_dir),
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "files": downloaded_files,
        }

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

        result = await self._run_command(
            ["audible", "activation-bytes", "--output-format", "json"]
        )

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
        logger.debug("Executing command: %s (timeout=%ds)", cmd_str, timeout)

        process: asyncio.subprocess.Process | None = None

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            result = {
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }

            if process.returncode != 0:
                logger.debug(
                    "Command exited with code %d: %s",
                    process.returncode,
                    result["stderr"][:200],
                )

            return result

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
            logger.error("Command not found: %s", cmd[0])
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
