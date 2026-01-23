"""Just-In-Time audio streaming with on-the-fly transcoding."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from core.config import get_settings
from db.models import Book
from services.audible_client import AudibleClient

logger = logging.getLogger(__name__)


class JITStreamingError(Exception):
    """Base exception for JIT streaming operations."""
    pass


class VoucherParseError(JITStreamingError):
    """Failed to parse voucher file."""
    pass


class DecryptionParamsError(JITStreamingError):
    """Failed to get decryption parameters."""
    pass


class JITStreamingService:
    """Just-In-Time audio streaming with on-the-fly transcoding."""

    def __init__(
        self,
        max_concurrent: int | None = None,
        bitrate: str | None = None,
        output_format: str | None = None,
    ):
        """
        Initialize JIT streaming service.

        Args:
            max_concurrent: Max concurrent JIT streams (defaults to config).
            bitrate: Output bitrate (defaults to config).
            output_format: Output format (defaults to config).
        """
        settings = get_settings()
        self.max_concurrent = max_concurrent or settings.max_jit_streams
        self.bitrate = bitrate or settings.jit_stream_bitrate
        self.output_format = output_format or settings.jit_stream_format

        self.streaming_semaphore = asyncio.Semaphore(self.max_concurrent)
        self.active_processes: dict[str, asyncio.subprocess.Process] = {}
        self._audible_client: AudibleClient | None = None

    @property
    def audible_client(self) -> AudibleClient:
        """Lazy-load AudibleClient."""
        if self._audible_client is None:
            self._audible_client = AudibleClient()
        return self._audible_client

    def parse_voucher(self, voucher_path: Path) -> tuple[str, str] | None:
        """
        Extract audible_key and audible_iv from voucher file.

        Args:
            voucher_path: Path to the .voucher file.

        Returns:
            Tuple of (key, iv) if successful, None otherwise.

        Raises:
            VoucherParseError: If voucher parsing fails.
        """
        if not voucher_path.exists():
            logger.warning("Voucher file not found: %s", voucher_path)
            return None

        try:
            with open(voucher_path, "r") as f:
                voucher_data = json.load(f)

            # The voucher structure contains license_response with key/iv
            license_response = voucher_data.get("content_license", {}).get(
                "license_response", {}
            )

            key = license_response.get("key")
            iv = license_response.get("iv")

            if not key or not iv:
                logger.warning(
                    "Voucher missing key or iv: key=%s, iv=%s",
                    bool(key),
                    bool(iv),
                )
                return None

            logger.debug("Successfully parsed voucher: key_len=%d, iv_len=%d", len(key), len(iv))
            return (key, iv)

        except json.JSONDecodeError as e:
            raise VoucherParseError(f"Invalid JSON in voucher file: {e}") from e
        except Exception as e:
            raise VoucherParseError(f"Failed to parse voucher: {e}") from e

    async def get_decryption_params(
        self, book: Book
    ) -> tuple[list[str], Path] | None:
        """
        Get FFmpeg decryption args and source path for a book.

        For AAXC files: Uses audible_key and audible_iv from voucher.
        For AAX files: Uses activation_bytes from audible-cli.

        Args:
            book: Book model with local paths.

        Returns:
            Tuple of (ffmpeg_decrypt_args, source_path) or None if unavailable.

        Raises:
            DecryptionParamsError: If decryption params cannot be obtained.
        """
        if not book.local_path_aax:
            logger.debug("Book %s has no local_path_aax", book.asin)
            return None

        source_path = Path(book.local_path_aax)
        if not source_path.exists():
            logger.debug("Source file not found: %s", source_path)
            return None

        # Determine if AAXC or AAX based on extension
        is_aaxc = source_path.suffix.lower() == ".aaxc"

        if is_aaxc:
            # AAXC requires voucher-based decryption
            if not book.local_path_voucher:
                logger.warning(
                    "Book %s is AAXC but has no voucher path", book.asin
                )
                return None

            voucher_path = Path(book.local_path_voucher)
            parsed = self.parse_voucher(voucher_path)
            if not parsed:
                return None

            key, iv = parsed
            decrypt_args = ["-audible_key", key, "-audible_iv", iv]
            logger.debug("Using AAXC decryption for %s", book.asin)

        else:
            # AAX uses activation_bytes
            activation_bytes = await self.audible_client.get_activation_bytes()
            if not activation_bytes:
                raise DecryptionParamsError(
                    f"Could not get activation bytes for AAX file: {book.asin}"
                )

            decrypt_args = ["-activation_bytes", activation_bytes]
            logger.debug("Using AAX decryption for %s", book.asin)

        return (decrypt_args, source_path)

    def build_stream_command(
        self,
        source: Path,
        decrypt_args: list[str],
        output_format: str | None = None,
        bitrate: str | None = None,
        start_time: float | None = None,
    ) -> list[str]:
        """
        Build FFmpeg command for stdout streaming.

        Args:
            source: Path to source AAX/AAXC file.
            decrypt_args: Decryption arguments (key/iv or activation_bytes).
            output_format: Output format (mp3, aac, etc.). Defaults to instance config.
            bitrate: Output bitrate. Defaults to instance config.
            start_time: Optional start position in seconds for seeking.

        Returns:
            Command list for asyncio.create_subprocess_exec.
        """
        fmt = output_format or self.output_format
        br = bitrate or self.bitrate

        cmd = ["ffmpeg"]

        # Add decryption parameters before input
        cmd.extend(decrypt_args)

        # Seek position MUST come before -i for fast input seeking
        # (FFmpeg seeks in the input stream rather than decoding everything first)
        if start_time is not None and start_time > 0:
            cmd.extend(["-ss", str(start_time)])

        # Input file
        cmd.extend(["-i", str(source)])

        # Output options: no video, audio codec based on format
        cmd.append("-vn")

        if fmt == "mp3":
            cmd.extend(["-codec:a", "libmp3lame", "-ab", br])
        elif fmt == "aac":
            cmd.extend(["-codec:a", "aac", "-ab", br])
        elif fmt == "opus":
            cmd.extend(["-codec:a", "libopus", "-ab", br])
        elif fmt == "flac":
            cmd.extend(["-codec:a", "flac"])
        else:
            # Default to mp3
            cmd.extend(["-codec:a", "libmp3lame", "-ab", br])
            fmt = "mp3"

        # Output to stdout
        cmd.extend(["-f", fmt, "pipe:1"])

        return cmd

    async def stream_audio(
        self,
        book: Book,
        start_time: float | None = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream transcoded audio from source file.

        Manages FFmpeg process lifecycle and handles client disconnection gracefully.

        Args:
            book: Book to stream.
            start_time: Optional start position in seconds.

        Yields:
            Audio data chunks.

        Raises:
            JITStreamingError: If streaming fails.
        """
        async with self.streaming_semaphore:
            logger.info("Starting JIT stream for %s (start_time=%s)", book.asin, start_time)

            params = await self.get_decryption_params(book)
            if not params:
                raise JITStreamingError(
                    f"Could not get decryption params for book {book.asin}"
                )

            decrypt_args, source_path = params
            cmd = self.build_stream_command(
                source_path,
                decrypt_args,
                start_time=start_time,
            )

            process: asyncio.subprocess.Process | None = None

            try:
                logger.debug("Launching FFmpeg: %s", " ".join(cmd[:5]) + "...")
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                self.active_processes[book.asin] = process

                chunk_size = 8192
                while True:
                    if process.stdout is None:
                        break

                    chunk = await process.stdout.read(chunk_size)
                    if not chunk:
                        break

                    yield chunk

                # Check for errors
                await process.wait()
                if process.returncode != 0:
                    stderr = ""
                    if process.stderr:
                        stderr_bytes = await process.stderr.read()
                        stderr = stderr_bytes.decode("utf-8", errors="replace")
                    logger.error(
                        "FFmpeg exited with code %d for %s: %s",
                        process.returncode,
                        book.asin,
                        stderr[:500],
                    )

                logger.info("Completed JIT stream for %s", book.asin)

            except asyncio.CancelledError:
                logger.info(
                    "Client disconnected, terminating FFmpeg for %s", book.asin
                )
                raise

            finally:
                if process and process.returncode is None:
                    logger.debug("Terminating FFmpeg process for %s", book.asin)
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        logger.warning(
                            "FFmpeg did not terminate, killing for %s", book.asin
                        )
                        process.kill()
                        await process.wait()

                self.active_processes.pop(book.asin, None)

    def get_active_streams(self) -> list[str]:
        """Get list of ASINs with active JIT streams."""
        return list(self.active_processes.keys())

    def get_stream_count(self) -> int:
        """Get number of active JIT streams."""
        return len(self.active_processes)

    async def cancel_stream(self, asin: str) -> bool:
        """
        Cancel an active JIT stream.

        Args:
            asin: Book ASIN to cancel.

        Returns:
            True if stream was cancelled, False if not found.
        """
        process = self.active_processes.get(asin)
        if not process:
            return False

        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

        self.active_processes.pop(asin, None)
        logger.info("Cancelled JIT stream for %s", asin)
        return True
