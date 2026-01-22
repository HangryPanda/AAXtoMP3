"""AAXtoMP3 conversion engine wrapper."""

import asyncio
import logging
import re
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)


class ConverterError(Exception):
    """Base exception for converter errors."""

    pass


class ConversionError(ConverterError):
    """Raised when a conversion operation fails."""

    pass


class ValidationError(ConverterError):
    """Raised when file validation fails."""

    pass


class ConverterEngine:
    """Wrapper for AAXtoMP3 bash script execution."""

    # FFmpeg progress patterns
    PROGRESS_PATTERN = re.compile(r"size=\s*\d+.*time=(\d+:\d+:\d+\.\d+)")
    DURATION_PATTERN = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)")
    # Additional patterns for robust progress parsing
    SPEED_PATTERN = re.compile(r"speed=\s*([\d.]+)x")
    BITRATE_PATTERN = re.compile(r"bitrate=\s*([\d.]+)kbits/s")
    # Error detection patterns
    ERROR_PATTERNS = [
        re.compile(r"Error|ERROR|error", re.IGNORECASE),
        re.compile(r"Invalid|invalid", re.IGNORECASE),
        re.compile(r"failed|Failed|FAILED"),
        re.compile(r"Permission denied"),
        re.compile(r"No such file"),
    ]

    def __init__(self) -> None:
        """Initialize converter engine."""
        self.settings = get_settings()
        self.script_path = self.settings.aaxtomp3_path

        if not self.script_path.exists():
            logger.warning(
                "AAXtoMP3 script not found at %s",
                self.script_path,
            )

    def build_command(
        self,
        input_file: Path,
        output_dir: Path,
        format: str = "m4b",
        single_file: bool = True,
        authcode: str | None = None,
        voucher_file: Path | None = None,
        dir_naming_scheme: str | None = None,
        file_naming_scheme: str | None = None,
        compression: int | None = None,
        no_clobber: bool = False,
    ) -> list[str]:
        """
        Build the AAXtoMP3 command with arguments.

        Args:
            input_file: Path to AAX/AAXC file
            output_dir: Output directory
            format: Output format (mp3, m4a, m4b, flac, opus)
            single_file: Single file or chaptered output
            authcode: AAX activation bytes
            voucher_file: AAXC voucher file path
            dir_naming_scheme: Directory naming pattern
            file_naming_scheme: File naming pattern
            compression: Compression level
            no_clobber: Skip if output exists

        Returns:
            List of command arguments
        """
        cmd = ["bash", str(self.script_path)]

        # Output format
        cmd.extend([f"-e:{format}"])

        # Single file or chaptered
        if single_file:
            cmd.append("-s")

        # Authentication
        if voucher_file and voucher_file.exists():
            cmd.append("--use-audible-cli-data")
        elif authcode:
            cmd.extend(["-A", authcode])

        # Output directory
        cmd.extend(["-d", str(output_dir)])

        # Naming schemes
        if dir_naming_scheme:
            cmd.extend(["--dir-naming-scheme", dir_naming_scheme])

        if file_naming_scheme:
            cmd.extend(["--file-naming-scheme", file_naming_scheme])

        # Compression
        if compression is not None:
            if format == "mp3":
                cmd.extend(["-l", str(compression)])
            elif format == "opus":
                cmd.extend(["--opus-complexity", str(compression)])

        # No clobber
        if no_clobber:
            cmd.append("-n")

        # Input file (must be last)
        cmd.append(str(input_file))

        return cmd

    async def convert(
        self,
        input_file: Path,
        output_dir: Path,
        format: str = "m4b",
        single_file: bool = True,
        authcode: str | None = None,
        voucher_file: Path | None = None,
        dir_naming_scheme: str | None = None,
        file_naming_scheme: str | None = None,
        compression: int | None = None,
        no_clobber: bool = False,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> dict[str, Any]:
        """
        Execute AAXtoMP3 conversion.

        Args:
            input_file: Path to AAX/AAXC file.
            output_dir: Output directory.
            format: Output format.
            single_file: Single file or chaptered.
            authcode: AAX activation bytes.
            voucher_file: AAXC voucher file.
            dir_naming_scheme: Directory naming pattern.
            file_naming_scheme: File naming pattern.
            compression: Compression level.
            no_clobber: Skip if exists.
            progress_callback: Callback for progress updates (percent, line).

        Returns:
            Dictionary with conversion result including:
            - success: bool
            - returncode: int
            - input_file: str
            - output_dir: str
            - format: str
            - stdout: str
            - stderr: str
            - duration_seconds: float (if detected)
            - output_files: list[str] (if successful)
            - error: str (if failed)
        """
        logger.info(
            "Starting conversion: %s -> %s (format=%s, single=%s)",
            input_file.name,
            output_dir,
            format,
            single_file,
        )

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = self.build_command(
            input_file=input_file,
            output_dir=output_dir,
            format=format,
            single_file=single_file,
            authcode=authcode,
            voucher_file=voucher_file,
            dir_naming_scheme=dir_naming_scheme,
            file_naming_scheme=file_naming_scheme,
            compression=compression,
            no_clobber=no_clobber,
        )

        total_duration_seconds = 0.0
        output_lines: list[str] = []
        error_lines: list[str] = []
        detected_errors: list[str] = []
        last_progress = 0

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(input_file.parent),
            )

            async def read_stream(
                stream: asyncio.StreamReader,
                is_stderr: bool = False,
            ) -> None:
                nonlocal total_duration_seconds, last_progress

                async for line in self._read_lines(stream):
                    if is_stderr:
                        error_lines.append(line)
                        # Parse duration from ffmpeg stderr
                        duration_match = self.DURATION_PATTERN.search(line)
                        if duration_match:
                            hours = int(duration_match.group(1))
                            minutes = int(duration_match.group(2))
                            seconds = float(duration_match.group(3))
                            total_duration_seconds = hours * 3600 + minutes * 60 + seconds
                            logger.debug("Detected duration: %.2fs", total_duration_seconds)

                        # Check for error patterns
                        for pattern in self.ERROR_PATTERNS:
                            if pattern.search(line):
                                detected_errors.append(line)
                                logger.warning("Potential error detected: %s", line[:100])
                                break
                    else:
                        output_lines.append(line)

                    # Parse progress from ffmpeg output
                    if progress_callback:
                        progress = self._parse_progress(line, total_duration_seconds)
                        if progress is not None:
                            # Only update if progress increased (avoid jitter)
                            if progress >= last_progress:
                                last_progress = progress
                                progress_callback(progress, line)
                        else:
                            progress_callback(-1, line)  # Log line without progress

            if process.stdout and process.stderr:
                await asyncio.gather(
                    read_stream(process.stdout, is_stderr=False),
                    read_stream(process.stderr, is_stderr=True),
                )

            await process.wait()

            success = process.returncode == 0
            result: dict[str, Any] = {
                "success": success,
                "returncode": process.returncode,
                "input_file": str(input_file),
                "output_dir": str(output_dir),
                "format": format,
                "stdout": "\n".join(output_lines),
                "stderr": "\n".join(error_lines),
                "duration_seconds": total_duration_seconds,
            }

            if success:
                logger.info("Conversion completed successfully for %s", input_file.name)
                result["output_files"] = self._find_output_files(output_dir, format)
            else:
                logger.error(
                    "Conversion failed for %s with code %d",
                    input_file.name,
                    process.returncode,
                )
                if detected_errors:
                    result["detected_errors"] = detected_errors

            return result

        except Exception as e:
            logger.exception("Exception during conversion of %s", input_file.name)
            return {
                "success": False,
                "returncode": -1,
                "input_file": str(input_file),
                "output_dir": str(output_dir),
                "format": format,
                "error": str(e),
            }

    def _find_output_files(self, output_dir: Path, format: str) -> list[str]:
        """
        Find output files created by conversion.

        Args:
            output_dir: Directory to search.
            format: Expected output format.

        Returns:
            List of output file paths.
        """
        extensions = {
            "mp3": [".mp3"],
            "m4a": [".m4a"],
            "m4b": [".m4b"],
            "flac": [".flac"],
            "opus": [".opus", ".ogg"],
            "ogg": [".ogg"],
        }

        exts = extensions.get(format, [f".{format}"])
        files: list[str] = []

        for ext in exts:
            for match in output_dir.rglob(f"*{ext}"):
                if match.is_file():
                    files.append(str(match))

        return files

    async def _read_lines(
        self, stream: asyncio.StreamReader
    ) -> AsyncGenerator[str, None]:
        """Read lines from async stream."""
        while True:
            line = await stream.readline()
            if not line:
                break
            yield line.decode("utf-8", errors="replace").rstrip()

    def _parse_progress(self, line: str, total_duration: float) -> int | None:
        """
        Parse FFmpeg progress from output line.

        Args:
            line: Output line from ffmpeg.
            total_duration: Total duration in seconds.

        Returns:
            Progress percentage (0-100) or None if not a progress line.
        """
        if total_duration <= 0:
            return None

        match = self.PROGRESS_PATTERN.search(line)
        if not match:
            return None

        time_str = match.group(1)
        parts = time_str.split(":")
        if len(parts) != 3:
            return None

        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            current_seconds = hours * 3600 + minutes * 60 + seconds

            progress = int((current_seconds / total_duration) * 100)
            return min(100, max(0, progress))
        except (ValueError, ZeroDivisionError):
            return None

    def _parse_speed(self, line: str) -> float | None:
        """
        Parse FFmpeg encoding speed from output line.

        Args:
            line: Output line from ffmpeg.

        Returns:
            Speed multiplier or None if not found.
        """
        match = self.SPEED_PATTERN.search(line)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None

    def estimate_remaining_time(
        self,
        progress: int,
        total_duration: float,
        speed: float | None,
    ) -> float | None:
        """
        Estimate remaining conversion time.

        Args:
            progress: Current progress percentage (0-100).
            total_duration: Total audio duration in seconds.
            speed: Current encoding speed multiplier.

        Returns:
            Estimated remaining seconds, or None if cannot estimate.
        """
        if progress <= 0 or progress >= 100 or not speed or speed <= 0:
            return None

        remaining_audio = total_duration * (100 - progress) / 100
        return remaining_audio / speed

    async def validate_aax(
        self,
        input_file: Path,
        authcode: str | None = None,
    ) -> dict[str, Any]:
        """
        Validate an AAX file without converting.

        Args:
            input_file: Path to AAX file.
            authcode: AAX activation bytes.

        Returns:
            Dictionary with validation result including:
            - valid: bool
            - returncode: int
            - input_file: str
            - stdout: str
            - stderr: str
            - error: str (if validation failed)
        """
        logger.info("Validating AAX file: %s", input_file.name)

        if not input_file.exists():
            logger.error("Input file does not exist: %s", input_file)
            return {
                "valid": False,
                "returncode": -1,
                "input_file": str(input_file),
                "stdout": "",
                "stderr": "",
                "error": "Input file does not exist",
            }

        cmd = ["bash", str(self.script_path), "-V"]

        if authcode:
            cmd.extend(["-A", authcode])

        cmd.append(str(input_file))

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            result = {
                "valid": process.returncode == 0,
                "returncode": process.returncode,
                "input_file": str(input_file),
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }

            if result["valid"]:
                logger.info("Validation passed for %s", input_file.name)
            else:
                logger.warning(
                    "Validation failed for %s: %s",
                    input_file.name,
                    result["stderr"][:200],
                )

            return result

        except Exception as e:
            logger.exception("Exception during validation of %s", input_file.name)
            return {
                "valid": False,
                "returncode": -1,
                "input_file": str(input_file),
                "stdout": "",
                "stderr": "",
                "error": str(e),
            }
