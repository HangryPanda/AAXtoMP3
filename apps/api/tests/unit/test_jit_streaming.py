"""Unit tests for JIT streaming service."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from db.models import Book, BookStatus
from services.jit_streaming import (
    DecryptionParamsError,
    JITStreamingError,
    JITStreamingService,
    VoucherParseError,
)


class TestParseVoucher:
    """Tests for voucher parsing."""

    def test_parse_voucher_valid(self, tmp_path: Path) -> None:
        """Test parsing a valid voucher file."""
        voucher_data = {
            "content_license": {
                "license_response": {
                    "key": "abcdef1234567890abcdef1234567890",
                    "iv": "1234567890abcdef1234567890abcdef",
                }
            }
        }
        voucher_path = tmp_path / "test.voucher"
        voucher_path.write_text(json.dumps(voucher_data))

        service = JITStreamingService()
        result = service.parse_voucher(voucher_path)

        assert result is not None
        key, iv = result
        assert key == "abcdef1234567890abcdef1234567890"
        assert iv == "1234567890abcdef1234567890abcdef"

    def test_parse_voucher_missing_file(self, tmp_path: Path) -> None:
        """Test parsing returns None for missing file."""
        voucher_path = tmp_path / "nonexistent.voucher"

        service = JITStreamingService()
        result = service.parse_voucher(voucher_path)

        assert result is None

    def test_parse_voucher_missing_key(self, tmp_path: Path) -> None:
        """Test parsing returns None when key is missing."""
        voucher_data = {
            "content_license": {
                "license_response": {
                    "iv": "1234567890abcdef1234567890abcdef",
                }
            }
        }
        voucher_path = tmp_path / "test.voucher"
        voucher_path.write_text(json.dumps(voucher_data))

        service = JITStreamingService()
        result = service.parse_voucher(voucher_path)

        assert result is None

    def test_parse_voucher_missing_iv(self, tmp_path: Path) -> None:
        """Test parsing returns None when iv is missing."""
        voucher_data = {
            "content_license": {
                "license_response": {
                    "key": "abcdef1234567890abcdef1234567890",
                }
            }
        }
        voucher_path = tmp_path / "test.voucher"
        voucher_path.write_text(json.dumps(voucher_data))

        service = JITStreamingService()
        result = service.parse_voucher(voucher_path)

        assert result is None

    def test_parse_voucher_invalid_json(self, tmp_path: Path) -> None:
        """Test parsing raises error for invalid JSON."""
        voucher_path = tmp_path / "test.voucher"
        voucher_path.write_text("not valid json {{{")

        service = JITStreamingService()

        with pytest.raises(VoucherParseError) as exc_info:
            service.parse_voucher(voucher_path)

        assert "Invalid JSON" in str(exc_info.value)

    def test_parse_voucher_empty_structure(self, tmp_path: Path) -> None:
        """Test parsing returns None for empty structure."""
        voucher_path = tmp_path / "test.voucher"
        voucher_path.write_text("{}")

        service = JITStreamingService()
        result = service.parse_voucher(voucher_path)

        assert result is None


class TestBuildStreamCommand:
    """Tests for FFmpeg command building."""

    def test_build_command_aaxc_mp3(self, tmp_path: Path) -> None:
        """Test AAXC command construction for MP3 output."""
        source = tmp_path / "test.aaxc"
        source.touch()

        service = JITStreamingService()
        decrypt_args = ["-audible_key", "testkey", "-audible_iv", "testiv"]

        cmd = service.build_stream_command(
            source=source,
            decrypt_args=decrypt_args,
            output_format="mp3",
            bitrate="128k",
        )

        assert cmd[0] == "ffmpeg"
        assert "-audible_key" in cmd
        assert "testkey" in cmd
        assert "-audible_iv" in cmd
        assert "testiv" in cmd
        assert "-i" in cmd
        assert str(source) in cmd
        assert "-vn" in cmd
        assert "-codec:a" in cmd
        assert "libmp3lame" in cmd
        assert "-ab" in cmd
        assert "128k" in cmd
        assert "-f" in cmd
        assert "mp3" in cmd
        assert "pipe:1" in cmd

    def test_build_command_aax(self, tmp_path: Path) -> None:
        """Test AAX command construction."""
        source = tmp_path / "test.aax"
        source.touch()

        service = JITStreamingService()
        decrypt_args = ["-activation_bytes", "deadbeef"]

        cmd = service.build_stream_command(
            source=source,
            decrypt_args=decrypt_args,
            output_format="mp3",
            bitrate="192k",
        )

        assert "-activation_bytes" in cmd
        assert "deadbeef" in cmd
        assert "192k" in cmd

    def test_build_command_with_start_time(self, tmp_path: Path) -> None:
        """Test command with seek position - must be before -i for fast seeking."""
        source = tmp_path / "test.aaxc"
        source.touch()

        service = JITStreamingService()
        decrypt_args = ["-audible_key", "key", "-audible_iv", "iv"]

        cmd = service.build_stream_command(
            source=source,
            decrypt_args=decrypt_args,
            start_time=120.5,
        )

        assert "-ss" in cmd
        ss_index = cmd.index("-ss")
        i_index = cmd.index("-i")
        # -ss must come BEFORE -i for fast input seeking
        assert ss_index < i_index, "-ss should come before -i for efficient seeking"
        assert cmd[ss_index + 1] == "120.5"

    def test_build_command_aac_format(self, tmp_path: Path) -> None:
        """Test AAC output format."""
        source = tmp_path / "test.aaxc"
        source.touch()

        service = JITStreamingService()
        decrypt_args = ["-audible_key", "key", "-audible_iv", "iv"]

        cmd = service.build_stream_command(
            source=source,
            decrypt_args=decrypt_args,
            output_format="aac",
        )

        assert "aac" in cmd
        codec_index = cmd.index("-codec:a")
        assert cmd[codec_index + 1] == "aac"

    def test_build_command_opus_format(self, tmp_path: Path) -> None:
        """Test Opus output format."""
        source = tmp_path / "test.aaxc"
        source.touch()

        service = JITStreamingService()
        decrypt_args = ["-audible_key", "key", "-audible_iv", "iv"]

        cmd = service.build_stream_command(
            source=source,
            decrypt_args=decrypt_args,
            output_format="opus",
        )

        assert "libopus" in cmd
        assert "opus" in cmd

    def test_build_command_flac_format(self, tmp_path: Path) -> None:
        """Test FLAC output format (no bitrate)."""
        source = tmp_path / "test.aaxc"
        source.touch()

        service = JITStreamingService()
        decrypt_args = ["-audible_key", "key", "-audible_iv", "iv"]

        cmd = service.build_stream_command(
            source=source,
            decrypt_args=decrypt_args,
            output_format="flac",
        )

        assert "flac" in cmd
        # FLAC shouldn't have -ab since it's lossless
        codec_index = cmd.index("-codec:a")
        assert cmd[codec_index + 1] == "flac"


class TestGetDecryptionParams:
    """Tests for decryption parameter retrieval."""

    @pytest.mark.asyncio
    async def test_get_decryption_params_aaxc(self, tmp_path: Path) -> None:
        """Test getting decryption params for AAXC file."""
        # Create AAXC and voucher files
        aaxc_path = tmp_path / "test.aaxc"
        aaxc_path.touch()

        voucher_path = tmp_path / "test.voucher"
        voucher_data = {
            "content_license": {
                "license_response": {
                    "key": "testkey123",
                    "iv": "testiv456",
                }
            }
        }
        voucher_path.write_text(json.dumps(voucher_data))

        book = Book(
            asin="B00TEST",
            title="Test Book",
            local_path_aax=str(aaxc_path),
            local_path_voucher=str(voucher_path),
        )

        service = JITStreamingService()
        result = await service.get_decryption_params(book)

        assert result is not None
        decrypt_args, source = result
        assert "-audible_key" in decrypt_args
        assert "testkey123" in decrypt_args
        assert "-audible_iv" in decrypt_args
        assert "testiv456" in decrypt_args
        assert source == aaxc_path

    @pytest.mark.asyncio
    async def test_get_decryption_params_aax(self, tmp_path: Path) -> None:
        """Test getting decryption params for AAX file."""
        aax_path = tmp_path / "test.aax"
        aax_path.touch()

        book = Book(
            asin="B00TEST",
            title="Test Book",
            local_path_aax=str(aax_path),
        )

        service = JITStreamingService()

        # Mock the audible client
        with patch.object(
            service.audible_client,
            "get_activation_bytes",
            new_callable=AsyncMock,
            return_value="abcd1234",
        ):
            result = await service.get_decryption_params(book)

        assert result is not None
        decrypt_args, source = result
        assert "-activation_bytes" in decrypt_args
        assert "abcd1234" in decrypt_args
        assert source == aax_path

    @pytest.mark.asyncio
    async def test_get_decryption_params_no_path(self) -> None:
        """Test returns None when no local path."""
        book = Book(
            asin="B00TEST",
            title="Test Book",
            local_path_aax=None,
        )

        service = JITStreamingService()
        result = await service.get_decryption_params(book)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_decryption_params_file_not_found(self, tmp_path: Path) -> None:
        """Test returns None when file doesn't exist."""
        book = Book(
            asin="B00TEST",
            title="Test Book",
            local_path_aax=str(tmp_path / "nonexistent.aaxc"),
        )

        service = JITStreamingService()
        result = await service.get_decryption_params(book)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_decryption_params_aaxc_no_voucher(self, tmp_path: Path) -> None:
        """Test returns None for AAXC without voucher."""
        aaxc_path = tmp_path / "test.aaxc"
        aaxc_path.touch()

        book = Book(
            asin="B00TEST",
            title="Test Book",
            local_path_aax=str(aaxc_path),
            local_path_voucher=None,
        )

        service = JITStreamingService()
        result = await service.get_decryption_params(book)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_decryption_params_aax_no_activation_bytes(
        self, tmp_path: Path
    ) -> None:
        """Test raises error when activation bytes unavailable."""
        aax_path = tmp_path / "test.aax"
        aax_path.touch()

        book = Book(
            asin="B00TEST",
            title="Test Book",
            local_path_aax=str(aax_path),
        )

        service = JITStreamingService()

        with patch.object(
            service.audible_client,
            "get_activation_bytes",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with pytest.raises(DecryptionParamsError):
                await service.get_decryption_params(book)


class TestConcurrencyControl:
    """Tests for semaphore and concurrency limits."""

    def test_semaphore_initialization(self) -> None:
        """Test semaphore is initialized with correct limit."""
        service = JITStreamingService(max_concurrent=3)
        # Semaphore internal value check
        assert service.streaming_semaphore._value == 3

    def test_default_semaphore_from_config(self) -> None:
        """Test semaphore uses config default."""
        with patch("services.jit_streaming.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                max_jit_streams=4,
                jit_stream_bitrate="192k",
                jit_stream_format="aac",
            )
            service = JITStreamingService()
            assert service.max_concurrent == 4
            assert service.bitrate == "192k"
            assert service.output_format == "aac"

    def test_get_active_streams_empty(self) -> None:
        """Test getting active streams when none active."""
        service = JITStreamingService()
        assert service.get_active_streams() == []
        assert service.get_stream_count() == 0


class TestServiceLifecycle:
    """Tests for service lifecycle management."""

    @pytest.mark.asyncio
    async def test_cancel_stream_not_found(self) -> None:
        """Test cancelling non-existent stream."""
        service = JITStreamingService()
        result = await service.cancel_stream("NONEXISTENT")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_stream_active(self) -> None:
        """Test cancelling an active stream."""
        service = JITStreamingService()

        # Create a mock process
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()

        # Make wait() return immediately
        async def mock_wait():
            mock_process.returncode = -15  # SIGTERM
            return -15

        mock_process.wait = mock_wait

        service.active_processes["B00TEST"] = mock_process

        result = await service.cancel_stream("B00TEST")

        assert result is True
        assert "B00TEST" not in service.active_processes
        mock_process.terminate.assert_called_once()


class TestStreamAudio:
    """Tests for the main stream_audio method."""

    @pytest.mark.asyncio
    async def test_stream_audio_no_decryption_params(self) -> None:
        """Test stream_audio raises error when decryption params unavailable."""
        book = Book(
            asin="B00TEST",
            title="Test Book",
            local_path_aax=None,
        )

        service = JITStreamingService()

        with pytest.raises(JITStreamingError) as exc_info:
            async for _ in service.stream_audio(book):
                pass

        assert "Could not get decryption params" in str(exc_info.value)
