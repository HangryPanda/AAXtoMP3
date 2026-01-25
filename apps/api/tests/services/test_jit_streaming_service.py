"""Unit tests for JITStreamingService logic."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from db.models import Book, BookStatus
from services.jit_streaming import (
    JITStreamingError,
    JITStreamingService,
    VoucherParseError,
)


class TestJITStreamingServiceUnit:
    """Unit tests for JITStreamingService."""

    @pytest.fixture
    def service(self):
        """Create a service instance."""
        return JITStreamingService()

    def test_parse_voucher_success(self, service, tmp_path):
        """Test successful voucher parsing."""
        voucher_file = tmp_path / "valid.voucher"
        data = {
            "content_license": {
                "license_response": {"key": "mykey", "iv": "myiv"}
            }
        }
        voucher_file.write_text(json.dumps(data))

        key, iv = service.parse_voucher(voucher_file)
        assert key == "mykey"
        assert iv == "myiv"

    def test_parse_voucher_file_not_found(self, service, tmp_path):
        """Test parsing missing voucher file."""
        result = service.parse_voucher(tmp_path / "nonexistent.voucher")
        assert result is None

    def test_parse_voucher_invalid_json(self, service, tmp_path):
        """Test parsing invalid JSON voucher."""
        voucher_file = tmp_path / "invalid.voucher"
        voucher_file.write_text("{invalid_json")

        with pytest.raises(VoucherParseError, match="Invalid JSON"):
            service.parse_voucher(voucher_file)

    def test_parse_voucher_missing_keys(self, service, tmp_path):
        """Test parsing voucher with missing keys."""
        voucher_file = tmp_path / "missing.voucher"
        data = {
            "content_license": {
                "license_response": {"other": "data"}
            }
        }
        voucher_file.write_text(json.dumps(data))

        result = service.parse_voucher(voucher_file)
        assert result is None

    def test_build_stream_command_aax_mp3(self, service):
        """Test building FFmpeg command for AAX to MP3."""
        source = Path("/tmp/book.aax")
        decrypt_args = ["-activation_bytes", "deadbeef"]
        
        cmd = service.build_stream_command(
            source=source,
            decrypt_args=decrypt_args,
            output_format="mp3",
            bitrate="64k",
        )

        assert cmd[0] == "ffmpeg"
        assert "-activation_bytes" in cmd
        assert "deadbeef" in cmd
        assert "-i" in cmd
        assert str(source) in cmd
        assert "-codec:a" in cmd
        assert "libmp3lame" in cmd
        assert "-ab" in cmd
        assert "64k" in cmd
        assert "pipe:1" in cmd

    def test_build_stream_command_with_seek(self, service):
        """Test building FFmpeg command with seek."""
        source = Path("/tmp/book.aax")
        decrypt_args = ["-activation_bytes", "deadbeef"]
        
        cmd = service.build_stream_command(
            source=source,
            decrypt_args=decrypt_args,
            start_time=120.5,
        )

        assert "-ss" in cmd
        assert "120.5" in cmd
        
        # Ensure seek is before input
        ss_idx = cmd.index("-ss")
        i_idx = cmd.index("-i")
        assert ss_idx < i_idx

    def test_build_stream_command_formats(self, service):
        """Test building FFmpeg command for different formats."""
        source = Path("/tmp/book.aax")
        decrypt_args = []

        # FLAC
        cmd = service.build_stream_command(source, decrypt_args, output_format="flac")
        assert "flac" in cmd
        assert "-codec:a" in cmd
        assert "flac" in cmd

        # Opus
        cmd = service.build_stream_command(source, decrypt_args, output_format="opus")
        assert "libopus" in cmd

        # AAC
        cmd = service.build_stream_command(source, decrypt_args, output_format="aac")
        assert "aac" in cmd

    @pytest.mark.asyncio
    async def test_get_decryption_params_aax(self, service):
        """Test getting params for AAX file."""
        book = MagicMock(spec=Book)
        book.asin = "TESTAAX"
        book.local_path_aax = "/tmp/book.aax"
        book.local_path_voucher = None

        with patch.object(Path, "exists", return_value=True), \
             patch("services.jit_streaming.AudibleClient") as MockClient:
            
            mock_client = MockClient.return_value
            mock_client.get_activation_bytes = AsyncMock(return_value="deadbeef")
            service._audible_client = mock_client

            args, path = await service.get_decryption_params(book)
            
            assert str(path) == "/tmp/book.aax"
            assert args == ["-activation_bytes", "deadbeef"]

    @pytest.mark.asyncio
    async def test_get_decryption_params_aaxc(self, service, tmp_path):
        """Test getting params for AAXC file."""
        voucher_path = tmp_path / "test.voucher"
        voucher_data = {
            "content_license": {
                "license_response": {"key": "k", "iv": "i"}
            }
        }
        voucher_path.write_text(json.dumps(voucher_data))

        book = MagicMock(spec=Book)
        book.asin = "TESTAAXC"
        book.local_path_aax = "/tmp/book.aaxc"
        book.local_path_voucher = str(voucher_path)

        with patch.object(Path, "exists", return_value=True):
            # Patch suffix indirectly or just ensure mocked Path behaves
            # Wait, Path("/tmp/book.aaxc").suffix is ".aaxc" without mocking
            # But get_decryption_params uses Path(book.local_path_aax)
            
            args, path = await service.get_decryption_params(book)
            
            assert str(path) == "/tmp/book.aaxc"
            assert args == ["-audible_key", "k", "-audible_iv", "i"]
