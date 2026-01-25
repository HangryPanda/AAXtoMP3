"""Unit tests for ConverterEngine service."""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.converter_engine import ConverterEngine


class TestConverterEngineInit:
    """Tests for ConverterEngine initialization."""

    def test_init_loads_settings(self) -> None:
        """Test that engine initializes with settings."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/mock/AAXtoMP3"),
            )

            engine = ConverterEngine()

            assert engine.script_path == Path("/mock/AAXtoMP3")


class TestBuildCommand:
    """Tests for build_command method."""

    def test_build_command_basic(self, tmp_path: Path) -> None:
        """Test building basic command."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            input_file = tmp_path / "test.aaxc"
            output_dir = tmp_path / "output"

            cmd = engine.build_command(
                input_file=input_file,
                output_dir=output_dir,
            )

            assert cmd[0] == "bash"
            assert cmd[1] == "/scripts/AAXtoMP3"
            assert "-e:m4b" in cmd
            assert "-s" in cmd  # single_file default is True
            assert str(output_dir) in cmd
            assert str(input_file) == cmd[-1]

    def test_build_command_mp3_format(self, tmp_path: Path) -> None:
        """Test building command with MP3 format."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            cmd = engine.build_command(
                input_file=tmp_path / "test.aax",
                output_dir=tmp_path,
                format="mp3",
            )

            assert "-e:mp3" in cmd

    def test_build_command_flac_format(self, tmp_path: Path) -> None:
        """Test building command with FLAC format."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            cmd = engine.build_command(
                input_file=tmp_path / "test.aax",
                output_dir=tmp_path,
                format="flac",
            )

            assert "-e:flac" in cmd

    def test_build_command_chaptered_mode(self, tmp_path: Path) -> None:
        """Test building command without single file flag."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            cmd = engine.build_command(
                input_file=tmp_path / "test.aax",
                output_dir=tmp_path,
                single_file=False,
            )

            assert "-s" not in cmd

    def test_build_command_with_authcode(self, tmp_path: Path) -> None:
        """Test building command with authcode."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            cmd = engine.build_command(
                input_file=tmp_path / "test.aax",
                output_dir=tmp_path,
                authcode="abc12345",
            )

            assert "-A" in cmd
            idx = cmd.index("-A")
            assert cmd[idx + 1] == "abc12345"

    def test_build_command_with_voucher(self, tmp_path: Path) -> None:
        """Test building command with voucher file."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            voucher = tmp_path / "test.voucher"
            voucher.write_text("{}")

            cmd = engine.build_command(
                input_file=tmp_path / "test.aaxc",
                output_dir=tmp_path,
                voucher_file=voucher,
            )

            assert "--use-audible-cli-data" in cmd

    def test_build_command_voucher_not_exists(self, tmp_path: Path) -> None:
        """Test voucher file that doesn't exist is ignored."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            cmd = engine.build_command(
                input_file=tmp_path / "test.aaxc",
                output_dir=tmp_path,
                voucher_file=tmp_path / "nonexistent.voucher",
            )

            assert "--use-audible-cli-data" not in cmd

    def test_build_command_with_dir_naming_scheme(self, tmp_path: Path) -> None:
        """Test building command with directory naming scheme."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            cmd = engine.build_command(
                input_file=tmp_path / "test.aax",
                output_dir=tmp_path,
                dir_naming_scheme="$artist/$title",
            )

            assert "--dir-naming-scheme" in cmd
            idx = cmd.index("--dir-naming-scheme")
            assert cmd[idx + 1] == "$artist/$title"

    def test_build_command_with_file_naming_scheme(self, tmp_path: Path) -> None:
        """Test building command with file naming scheme."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            cmd = engine.build_command(
                input_file=tmp_path / "test.aax",
                output_dir=tmp_path,
                file_naming_scheme="$title - $narrator",
            )

            assert "--file-naming-scheme" in cmd
            idx = cmd.index("--file-naming-scheme")
            assert cmd[idx + 1] == "$title - $narrator"

    def test_build_command_with_mp3_compression(self, tmp_path: Path) -> None:
        """Test building command with MP3 compression level."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            cmd = engine.build_command(
                input_file=tmp_path / "test.aax",
                output_dir=tmp_path,
                format="mp3",
                compression=6,
            )

            assert "-l" in cmd
            idx = cmd.index("-l")
            assert cmd[idx + 1] == "6"

    def test_build_command_with_opus_compression(self, tmp_path: Path) -> None:
        """Test building command with Opus compression level."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            cmd = engine.build_command(
                input_file=tmp_path / "test.aax",
                output_dir=tmp_path,
                format="opus",
                compression=8,
            )

            assert "--opus-complexity" in cmd
            idx = cmd.index("--opus-complexity")
            assert cmd[idx + 1] == "8"

    def test_build_command_no_clobber(self, tmp_path: Path) -> None:
        """Test building command with no_clobber flag."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            cmd = engine.build_command(
                input_file=tmp_path / "test.aax",
                output_dir=tmp_path,
                no_clobber=True,
            )

            assert "-n" in cmd

    def test_build_command_input_file_is_last(self, tmp_path: Path) -> None:
        """Test that input file is always last argument."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            input_file = tmp_path / "test.aax"

            cmd = engine.build_command(
                input_file=input_file,
                output_dir=tmp_path,
                format="mp3",
                single_file=True,
                authcode="abc123",
                dir_naming_scheme="$title",
            )

            assert cmd[-1] == str(input_file)


class TestConvert:
    """Tests for convert method."""

    @pytest.mark.asyncio
    async def test_convert_success(self, tmp_path: Path) -> None:
        """Test successful conversion."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            input_file = tmp_path / "test.aax"
            input_file.write_bytes(b"fake aax content")

            with patch("asyncio.create_subprocess_exec") as mock_exec, \
                 patch.object(engine, "_find_output_files", side_effect=lambda d, f: [str(Path(d) / "output.m4b")]), \
                 patch.object(engine, "_get_audio_duration", return_value=0.0), \
                 patch("shutil.move") as mock_move:
                
                mock_process = AsyncMock()
                # Mock readline to return empty bytes (end of stream)
                mock_process.stdout.readline = AsyncMock(return_value=b"")
                mock_process.stderr.readline = AsyncMock(return_value=b"")
                mock_process.wait = AsyncMock(return_value=0)
                mock_process.returncode = 0
                mock_exec.return_value = mock_process

                result = await engine.convert(
                    input_file=input_file,
                    output_dir=tmp_path,
                )

            assert result["success"] is True
            assert result["returncode"] == 0
            assert result["format"] == "m4b"

    @pytest.mark.asyncio
    async def test_convert_failure(self, tmp_path: Path) -> None:
        """Test conversion failure."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            input_file = tmp_path / "test.aax"
            input_file.write_bytes(b"fake aax content")

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = AsyncMock()
                # Mock readline to return empty bytes (end of stream)
                mock_process.stdout.readline = AsyncMock(return_value=b"")
                mock_process.stderr.readline = AsyncMock(return_value=b"")
                mock_process.wait = AsyncMock(return_value=1)
                mock_process.returncode = 1
                mock_exec.return_value = mock_process

                result = await engine.convert(
                    input_file=input_file,
                    output_dir=tmp_path,
                )

            assert result["success"] is False
            assert result["returncode"] == 1

    @pytest.mark.asyncio
    async def test_convert_with_progress_callback(self, tmp_path: Path) -> None:
        """Test conversion with progress callback."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            input_file = tmp_path / "test.aax"
            input_file.write_bytes(b"fake content")

            progress_calls: list[tuple[int, str, dict | None]] = []

            def progress_callback(
                percent: int, line: str, telemetry: dict | None = None
            ) -> None:
                progress_calls.append((percent, line, telemetry))

            # Mock the stream reading with ffmpeg-like output
            async def mock_read_lines(stream: Any) -> Any:
                lines = [
                    "Duration: 01:00:00.00",
                    "size=    5000kB time=00:30:00.00",
                ]
                for line in lines:
                    yield line

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = MagicMock()
                mock_process.stdout = MagicMock()
                mock_process.stderr = MagicMock()
                mock_process.wait = AsyncMock(return_value=None)
                mock_process.returncode = 0
                mock_exec.return_value = mock_process

                with patch.object(engine, "_read_lines", side_effect=mock_read_lines):
                    await engine.convert(
                        input_file=input_file,
                        output_dir=tmp_path,
                        progress_callback=progress_callback,
                    )

            # Verify callback was called
            assert len(progress_calls) > 0

    @pytest.mark.asyncio
    async def test_convert_exception_handling(self, tmp_path: Path) -> None:
        """Test conversion handles exceptions gracefully."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            input_file = tmp_path / "test.aax"
            input_file.write_bytes(b"content")

            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=Exception("Process error"),
            ):
                result = await engine.convert(
                    input_file=input_file,
                    output_dir=tmp_path,
                )

            assert result["success"] is False
            assert result["returncode"] == -1
            assert "error" in result


class TestParseProgress:
    """Tests for _parse_progress method."""

    def test_parse_progress_valid_line(self) -> None:
        """Test parsing valid ffmpeg progress line."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()

            # 1 hour total duration, 30 minutes elapsed = 50%
            total_duration = 3600.0  # 1 hour in seconds
            line = "size=    5000kB time=00:30:00.00 bitrate= 128.0kbits/s"

            progress = engine._parse_progress(line, total_duration)

            assert progress == 50

    def test_parse_progress_no_match(self) -> None:
        """Test parsing line without time info."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            line = "Random log output"

            progress = engine._parse_progress(line, 3600.0)

            assert progress is None

    def test_parse_progress_zero_duration(self) -> None:
        """Test parsing with zero duration returns None."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            line = "size=    5000kB time=00:30:00.00"

            progress = engine._parse_progress(line, 0)

            assert progress is None

    def test_parse_progress_negative_duration(self) -> None:
        """Test parsing with negative duration returns None."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            line = "size=    5000kB time=00:30:00.00"

            progress = engine._parse_progress(line, -1)

            assert progress is None

    def test_parse_progress_clamped_to_100(self) -> None:
        """Test progress is clamped to max 100."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            # Time is greater than duration (edge case)
            line = "size=    5000kB time=02:00:00.00"

            progress = engine._parse_progress(line, 3600.0)  # 1 hour total

            assert progress == 100

    def test_parse_progress_at_start(self) -> None:
        """Test progress at start of conversion."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            line = "size=    100kB time=00:00:36.00"  # 36 seconds

            progress = engine._parse_progress(line, 3600.0)  # 1 hour total

            assert progress == 1


class TestValidateAax:
    """Tests for validate_aax method."""

    @pytest.mark.asyncio
    async def test_validate_aax_valid(self, tmp_path: Path) -> None:
        """Test validating valid AAX file."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            input_file = tmp_path / "test.aax"
            input_file.write_bytes(b"fake content")

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = MagicMock()
                mock_process.communicate = AsyncMock(
                    return_value=(b"Valid AAX file", b"")
                )
                mock_process.returncode = 0
                mock_exec.return_value = mock_process

                result = await engine.validate_aax(
                    input_file=input_file,
                    authcode="abc123",
                )

            assert result["valid"] is True
            assert result["returncode"] == 0

    @pytest.mark.asyncio
    async def test_validate_aax_invalid(self, tmp_path: Path) -> None:
        """Test validating invalid AAX file."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            input_file = tmp_path / "test.aax"
            input_file.write_bytes(b"fake content")

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = MagicMock()
                mock_process.communicate = AsyncMock(
                    return_value=(b"", b"Invalid authcode")
                )
                mock_process.returncode = 1
                mock_exec.return_value = mock_process

                result = await engine.validate_aax(input_file=input_file)

            assert result["valid"] is False
            assert result["returncode"] == 1

    @pytest.mark.asyncio
    async def test_validate_aax_includes_authcode(self, tmp_path: Path) -> None:
        """Test validation command includes authcode when provided."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            input_file = tmp_path / "test.aax"
            input_file.write_bytes(b"content")

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = MagicMock()
                mock_process.communicate = AsyncMock(return_value=(b"", b""))
                mock_process.returncode = 0
                mock_exec.return_value = mock_process

                await engine.validate_aax(
                    input_file=input_file,
                    authcode="testcode123",
                )

            # Check command args
            call_args = mock_exec.call_args[0]
            assert "-A" in call_args
            assert "testcode123" in call_args
            assert "-V" in call_args


class TestDurationPattern:
    """Tests for duration pattern matching."""

    def test_duration_pattern_matches(self) -> None:
        """Test duration pattern matches ffmpeg output."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            line = "  Duration: 02:30:45.67, start: 0.000000"

            match = engine.DURATION_PATTERN.search(line)

            assert match is not None
            assert match.group(1) == "02"  # hours
            assert match.group(2) == "30"  # minutes
            assert match.group(3) == "45.67"  # seconds

    def test_progress_pattern_matches(self) -> None:
        """Test progress pattern matches ffmpeg output."""
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )

            engine = ConverterEngine()
            line = "size=  123456kB time=01:15:30.50 bitrate= 128.0kbits/s speed=1.5x"

            match = engine.PROGRESS_PATTERN.search(line)

            assert match is not None
            assert match.group(1) == "01:15:30.50"


class TestParseFfmpegTelemetry:
    """Tests for ConverterEngine.parse_ffmpeg_telemetry robustness."""

    def test_parse_ffmpeg_telemetry_parses_time_with_variable_decimals(self) -> None:
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(aaxtomp3_path=Path("/scripts/AAXtoMP3"))
            engine = ConverterEngine()

        total = 10.0  # seconds
        line = "size=    1234kB time=00:00:01.4 bitrate=128.0kbits/s speed=2.5x"
        telemetry = engine.parse_ffmpeg_telemetry(line, total)
        assert telemetry is not None
        assert telemetry["convert_total_ms"] == 10_000
        assert telemetry["convert_current_ms"] == 1_400
        assert telemetry["convert_percent"] == 14
        assert telemetry["convert_speed_x"] == pytest.approx(2.5)
        assert telemetry["convert_bitrate_kbps"] == pytest.approx(128.0)

    def test_parse_ffmpeg_telemetry_handles_na_values_safely(self) -> None:
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(aaxtomp3_path=Path("/scripts/AAXtoMP3"))
            engine = ConverterEngine()

        total = 10.0
        line = "size=    1234kB time=00:00:01.45 bitrate=N/A speed=N/A"
        telemetry = engine.parse_ffmpeg_telemetry(line, total)
        assert telemetry is not None
        assert telemetry["convert_current_ms"] == 1_450
        assert "convert_speed_x" not in telemetry
        assert "convert_bitrate_kbps" not in telemetry

    def test_parse_ffmpeg_telemetry_returns_none_on_non_progress_lines(self) -> None:
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(aaxtomp3_path=Path("/scripts/AAXtoMP3"))
            engine = ConverterEngine()

        assert engine.parse_ffmpeg_telemetry("not ffmpeg", 10.0) is None
