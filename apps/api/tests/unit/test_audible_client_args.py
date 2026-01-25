"""Unit tests for AudibleClient argument generation."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from services.audible_client import AudibleClient

class TestAudibleClientArguments:
    """Tests for verifying command line arguments passed to audible-cli."""

    @pytest.fixture
    def client(self):
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="test_profile",
            )
            yield AudibleClient()

    @pytest.mark.asyncio
    async def test_download_command_structure(self, client, tmp_path):
        """Verify the exact structure of the download command."""
        output_dir = tmp_path / "downloads"
        
        with patch.object(client, "_run_command_streaming", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
            
            await client.download(
                asin="B001234567",
                output_dir=output_dir,
                cover_size="1215",
                aaxc=True
            )
            
            # Get the command arguments passed to _run_command
            cmd = mock_run.call_args[0][0]
            
            # Verify base command
            assert cmd[0] == "audible"

            # audible-cli does not support --config-dir (config is derived from HOME/.audible)
            assert "--config-dir" not in cmd

            # Check for profile flag (order might vary)
            assert "--profile" in cmd
            assert cmd[cmd.index("--profile") + 1] == "test_profile"
            
            # Verify subcommand
            assert "download" in cmd
            
            # Verify arguments
            assert "--asin" in cmd
            assert cmd[cmd.index("--asin") + 1] == "B001234567"
            
            assert "--output-dir" in cmd
            assert cmd[cmd.index("--output-dir") + 1] == str(output_dir)
            
            assert "--cover-size" in cmd
            assert cmd[cmd.index("--cover-size") + 1] == "1215"
            
            assert "--aaxc" in cmd

    @pytest.mark.asyncio
    async def test_download_without_aaxc(self, client, tmp_path):
        """Verify download command without AAXC flag."""
        with patch.object(client, "_run_command_streaming", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
            
            await client.download(
                asin="B001",
                output_dir=tmp_path,
                aaxc=False
            )
            
            cmd = mock_run.call_args[0][0]
            assert "--aaxc" not in cmd
            assert "--no-aaxc" not in cmd

    @pytest.mark.asyncio
    async def test_get_activation_bytes_command(self, client):
        """Verify activation bytes command structure."""
        with patch.object(client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {"returncode": 0, "stdout": "{\"activation_bytes\":\"1234\"}", "stderr": ""}
            
            await client.get_activation_bytes()
            
            cmd = mock_run.call_args[0][0]
            
            assert cmd[0] == "audible"
            assert "activation-bytes" in cmd
            assert "--profile" in cmd
