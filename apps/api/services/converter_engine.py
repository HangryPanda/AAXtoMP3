"""AAXtoMP3 conversion engine wrapper."""

import asyncio
import json
import logging
import re
import shutil
import tempfile
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
    # Time pattern accepts variable decimal places (e.g., .4, .45, .456) or no decimal
    PROGRESS_PATTERN = re.compile(r"size=\s*\d+.*time=(\d+:\d+:\d+(?:\.\d+)?)")
    DURATION_PATTERN = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
    # Additional patterns for robust progress parsing
    # Speed pattern handles N/A and numeric values
    SPEED_PATTERN = re.compile(r"speed=\s*([\d.]+)x")
    # Bitrate pattern handles N/A and numeric values
    BITRATE_PATTERN = re.compile(r"bitrate=\s*([\d.]+)kbits/s")
    # Error detection patterns
    ERROR_PATTERNS = [
        re.compile(r"ERROR[:\s]", re.IGNORECASE),
        re.compile(r"Invalid\s+argument", re.IGNORECASE),
        re.compile(r"Permission\s+denied", re.IGNORECASE),
        re.compile(r"No\s+such\s+file", re.IGNORECASE),
        re.compile(r"Operation\s+not\s+permitted", re.IGNORECASE),
        re.compile(r"Conversion\s+failed!", re.IGNORECASE),
        re.compile(r"File\s+NOT\s+Found", re.IGNORECASE),
    ]

    def __init__(self) -> None:
        """Initialize converter engine."""
        self.settings = get_settings()
        self.script_path = self.settings.aaxtomp3_path.resolve()

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
        cmd.extend(["--target_dir", str(output_dir)])

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

    async def _get_audio_duration(self, file_path: Path) -> float | None:
        """Get audio duration in seconds using ffprobe."""
        try:
            process = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                return float(stdout.decode().strip())
            else:
                logger.warning("ffprobe failed for %s: %s", file_path, stderr.decode())
        except Exception as e:
            logger.warning("Failed to get duration for %s: %s", file_path, e)
        return None

    async def _fix_chapters(self, file_path: Path, chapters_json_path: Path) -> bool:
        """Inject chapter titles from JSON into the MP4/M4B file using FFmpeg metadata."""
        if not chapters_json_path.exists():
            logger.warning("Chapters JSON not found for fixup: %s", chapters_json_path)
            return False
            
        logger.info("Injecting chapter titles from %s into %s", chapters_json_path.name, file_path.name)
        try:
            with open(chapters_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Format depends on JSON structure. audible-cli format:
            # content_metadata -> chapter_info -> chapters [ {title, start_offset_ms, length_ms} ]
            chapters = []
            if 'content_metadata' in data:
                chapters = data['content_metadata'].get('chapter_info', {}).get('chapters', [])
            elif isinstance(data, list):
                chapters = data
            
            if not chapters:
                logger.warning("No chapters found in JSON data")
                return False
            
            # Generate FFMETADATA
            metadata = [";FFMETADATA1"]
            for i, ch in enumerate(chapters):
                # Handle different key names (audible-cli vs direct API)
                start = ch.get('start_offset_ms') or ch.get('start_offset', 0)
                length = ch.get('length_ms') or ch.get('length', 0)
                end = start + length
                title = ch.get('title') or f"Chapter {i+1}"
                metadata.extend([
                    "[CHAPTER]",
                    "TIMEBASE=1/1000",
                    f"START={start}",
                    f"END={end}",
                    f"title={title}"
                ])
            
            # Write to a named temp file
            meta_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
            try:
                meta_file.write("\n".join(metadata))
                meta_file.close()
                meta_path = meta_file.name
                
                temp_output = file_path.with_suffix('.tmp_chapters' + file_path.suffix)
                # Remux with metadata
                # -map 0:a maps all audio streams
                # -map 0:v maps all video streams (cover art)
                # -map_metadata 1 takes global metadata from input 1 (our txt file)
                # -map_chapters 1 takes chapters from input 1
                # -disposition:v attached_pic ensures cover art is treated correctly
                process = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-y", "-i", str(file_path), "-i", meta_path,
                    "-map", "0:a", "-map", "0:v", "-map_metadata", "1", "-map_chapters", "1",
                    "-c", "copy", "-disposition:v", "attached_pic", str(temp_output),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode == 0:
                    shutil.move(str(temp_output), str(file_path))
                    logger.info("Successfully injected %d chapter titles", len(chapters))
                    return True
                else:
                    logger.error("FFmpeg chapter injection failed (code %d): %s", process.returncode, stderr.decode())
            finally:
                if Path(meta_file.name).exists():
                    Path(meta_file.name).unlink()
        except Exception as e:
            logger.error("Failed to fix chapters for %s: %s", file_path, e)
        return False

    async def convert(
        self,
        input_file: Path,
        output_dir: Path,
        format: str = "m4b",
        single_file: bool = True,
        authcode: str | None = None,
        voucher_file: Path | None = None,
        chapters_file: Path | None = None,
        dir_naming_scheme: str | None = None,
        file_naming_scheme: str | None = None,
        compression: int | None = None,
        no_clobber: bool = False,
        progress_callback: Callable[[int, str, dict[str, Any] | None], None] | None = None,
    ) -> dict[str, Any]:
        """
        Execute AAXtoMP3 conversion with atomic writes and verification.

        Args:
            input_file: Path to AAX/AAXC file.
            output_dir: Output directory.
            format: Output format.
            single_file: Single file or chaptered.
            authcode: AAX activation bytes.
            voucher_file: AAXC voucher file.
            chapters_file: AAXC chapters JSON file.
            dir_naming_scheme: Directory naming pattern.
            file_naming_scheme: File naming pattern.
            compression: Compression level.
            no_clobber: Skip if exists.
            progress_callback: Callback for progress updates (percent, line, telemetry).
                - percent: Progress percentage (0-100) or -1 for log-only lines.
                - line: The raw output line.
                - telemetry: Dict with convert_* keys (or None for log-only lines).

        Returns:
            Dictionary with conversion result.
        """
        logger.info(
            "Starting conversion: %s -> %s (format=%s, single=%s)",
            input_file.name,
            output_dir,
            format,
            single_file,
        )

        # Create a temporary directory for atomic write
        # We try to create it on the same filesystem as output_dir for atomic moves
        temp_dir_base = output_dir.parent / ".tmp_conversion"
        temp_dir_base.mkdir(parents=True, exist_ok=True)
        
        with tempfile.TemporaryDirectory(dir=temp_dir_base) as temp_dir_str:
            temp_output_dir = Path(temp_dir_str)
            
            cmd = self.build_command(
                input_file=input_file,
                output_dir=temp_output_dir,
                format=format,
                single_file=single_file,
                authcode=authcode,
                voucher_file=voucher_file,
                dir_naming_scheme=dir_naming_scheme,
                file_naming_scheme=file_naming_scheme,
                compression=compression,
                no_clobber=no_clobber,
            )

            # Get input duration reliably
            total_duration_seconds = await self._get_audio_duration(input_file) or 0.0
            if total_duration_seconds > 0:
                logger.info("Input duration detected: %.2fs", total_duration_seconds)

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
                        else:
                            output_lines.append(line)

                        # Check for error patterns in BOTH streams
                        for pattern in self.ERROR_PATTERNS:
                            if pattern.search(line):
                                detected_errors.append(line)
                                break

                        # Parse progress from ffmpeg output
                        if progress_callback:
                            telemetry = self.parse_ffmpeg_telemetry(line, total_duration_seconds)
                            if telemetry is not None:
                                progress = telemetry.get("convert_percent", 0)
                                # Only update if progress increased (avoid jitter)
                                if progress >= last_progress:
                                    last_progress = progress
                                    progress_callback(progress, line, telemetry)
                            else:
                                progress_callback(-1, line, None)  # Log line without progress

                if process.stdout and process.stderr:
                    await asyncio.gather(
                        read_stream(process.stdout, is_stderr=False),
                        read_stream(process.stderr, is_stderr=True),
                    )

                await process.wait()

                success = process.returncode == 0
                stdout_str = "\n".join(output_lines)
                stderr_str = "\n".join(error_lines)

                final_output_files: list[str] = []

                if success:
                    # Verification Phase
                    logger.info("Conversion successful, starting integrity verification...")
                    temp_files = self._find_output_files(temp_output_dir, format)
                    
                    if not temp_files:
                        success = False
                        detected_errors.append("No output files generated")
                        logger.error("No output files generated in temp dir")
                    else:
                        for temp_file_str in temp_files:
                            temp_file = Path(temp_file_str)
                            
                            # Post-process: Inject Chapter Titles if available
                            if chapters_file and chapters_file.exists():
                                await self._fix_chapters(temp_file, chapters_file)
                            
                            output_duration = await self._get_audio_duration(temp_file)
                            
                            # Tolerance: 1% or 10 seconds, whichever is larger
                            # (AAX vs M4B duration can vary slightly due to container overhead/trimming)
                            tolerance = max(10.0, total_duration_seconds * 0.01)
                            
                            if output_duration is None:
                                success = False
                                msg = f"Failed to verify duration for {temp_file.name}"
                                detected_errors.append(msg)
                                logger.error(msg)
                            elif abs(output_duration - total_duration_seconds) > tolerance:
                                # Only fail if we actually detected a duration from input
                                if total_duration_seconds > 0:
                                    success = False
                                    msg = f"Duration mismatch: Input={total_duration_seconds:.2f}s, Output={output_duration:.2f}s"
                                    detected_errors.append(msg)
                                    logger.error(msg)
                                else:
                                    logger.warning("Could not detect input duration, skipping duration check.")

                    # Atomic Move Phase
                    if success:
                        logger.info("Integrity check passed. Moving files to final destination.")
                        # Ensure final directory exists
                        output_dir.mkdir(parents=True, exist_ok=True)
                        
                        # We need to replicate the directory structure from temp_output_dir to output_dir
                        for temp_file_str in temp_files:
                            temp_file = Path(temp_file_str)
                            # Calculate relative path from temp_output_dir
                            rel_path = temp_file.relative_to(temp_output_dir)
                            dest_path = output_dir / rel_path
                            
                            # Ensure dest parent exists
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            # Move
                            shutil.move(str(temp_file), str(dest_path))
                            final_output_files.append(str(dest_path))
                            logger.info("Moved %s to %s", temp_file.name, dest_path)

                result: dict[str, Any] = {
                    "success": success,
                    "returncode": process.returncode,
                    "input_file": str(input_file),
                    "output_dir": str(output_dir),
                    "format": format,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "duration_seconds": total_duration_seconds,
                    "output_files": final_output_files if success else [],
                }

                if not success:
                    logger.error(
                        "Conversion or verification failed for %s",
                        input_file.name,
                    )
                    if detected_errors:
                        result["detected_errors"] = detected_errors
                    # If stderr is empty but return code is non-zero, use stdout as error info
                    if not stderr_str and stdout_str:
                        result["stderr"] = stdout_str

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

        Handles N/A values safely (returns None).

        Args:
            line: Output line from ffmpeg.

        Returns:
            Speed multiplier or None if not found or N/A.
        """
        # Check for N/A first
        if "speed=N/A" in line or "speed= N/A" in line:
            return None
        match = self.SPEED_PATTERN.search(line)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None

    def _parse_bitrate(self, line: str) -> float | None:
        """
        Parse FFmpeg encoding bitrate from output line.

        Handles N/A values safely (returns None).

        Args:
            line: Output line from ffmpeg.

        Returns:
            Bitrate in kbps or None if not found or N/A.
        """
        # Check for N/A first
        if "bitrate=N/A" in line or "bitrate= N/A" in line:
            return None
        match = self.BITRATE_PATTERN.search(line)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None

    def parse_ffmpeg_telemetry(
        self, line: str, total_duration_seconds: float
    ) -> dict[str, Any] | None:
        """
        Parse full FFmpeg telemetry from a progress line.

        Returns structured telemetry data for status.meta consumption.
        This method is resilient - it does not raise on malformed lines.

        Args:
            line: Output line from ffmpeg.
            total_duration_seconds: Total duration in seconds.

        Returns:
            Dictionary with telemetry keys, or None if not a progress line.
            Keys:
            - convert_current_ms: Current position in milliseconds
            - convert_total_ms: Total duration in milliseconds
            - convert_speed_x: Speed multiplier (if available)
            - convert_bitrate_kbps: Bitrate in kbps (if available)
            - convert_percent: Progress percentage (0-100)
        """
        # Must have total duration to compute progress
        if total_duration_seconds <= 0:
            return None

        # Parse time from progress line
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

            # Use integer math to avoid float precision edge-cases (e.g., 1.4/10.0 -> 13.999999...)
            current_ms = int(round(current_seconds * 1000))
            total_ms = int(round(total_duration_seconds * 1000))
            if total_ms <= 0:
                return None

            progress_percent = (current_ms * 100) // total_ms
            progress_percent = min(100, max(0, int(progress_percent)))

            telemetry: dict[str, Any] = {
                "convert_current_ms": current_ms,
                "convert_total_ms": total_ms,
                "convert_percent": progress_percent,
            }

            # Add speed if available
            speed = self._parse_speed(line)
            if speed is not None:
                telemetry["convert_speed_x"] = speed

            # Add bitrate if available
            bitrate = self._parse_bitrate(line)
            if bitrate is not None:
                telemetry["convert_bitrate_kbps"] = bitrate

            return telemetry

        except (ValueError, ZeroDivisionError):
            # Malformed line - do not crash
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
