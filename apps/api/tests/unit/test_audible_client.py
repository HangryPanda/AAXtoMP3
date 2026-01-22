"""Unit tests for AudibleClient service."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.audible_client import AudibleClient, AudibleLibraryError


class TestAudibleClientInit:
    """Tests for AudibleClient initialization."""

    def test_init_loads_settings(self) -> None:
        """Test that client initializes with settings."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="test_profile",
            )

            client = AudibleClient()

            assert client.auth_file == Path("/mock/auth.json")
            assert client.profile == "test_profile"


class TestIsAuthenticated:
    """Tests for is_authenticated method."""

    @pytest.mark.asyncio
    async def test_is_authenticated_returns_false_when_auth_file_missing(
        self,
    ) -> None:
        """Test returns False when auth file doesn't exist."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/nonexistent/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()
            result = await client.is_authenticated()

            assert result is False

    @pytest.mark.asyncio
    async def test_is_authenticated_returns_true_on_success(
        self,
        tmp_path: Path,
    ) -> None:
        """Test returns True when auth check succeeds."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text("{}")

        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=auth_file,
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                return_value={"returncode": 0, "stdout": "", "stderr": ""},
            ):
                result = await client.is_authenticated()

            assert result is True

    @pytest.mark.asyncio
    async def test_is_authenticated_returns_false_on_command_failure(
        self,
        tmp_path: Path,
    ) -> None:
        """Test returns False when audible command fails."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text("{}")

        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=auth_file,
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                return_value={"returncode": 1, "stdout": "", "stderr": "Auth failed"},
            ):
                result = await client.is_authenticated()

            assert result is False

    @pytest.mark.asyncio
    async def test_is_authenticated_handles_exception(
        self,
        tmp_path: Path,
    ) -> None:
        """Test returns False when exception occurs."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text("{}")

        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=auth_file,
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                side_effect=Exception("Connection error"),
            ):
                result = await client.is_authenticated()

            assert result is False


class TestGetLibrary:
    """Tests for get_library method."""

    @pytest.mark.asyncio
    async def test_get_library_success(self) -> None:
        """Test successfully fetching library."""
        library_data = [
            {"asin": "B001", "title": "Book 1"},
            {"asin": "B002", "title": "Book 2"},
        ]

        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                return_value={
                    "returncode": 0,
                    "stdout": json.dumps(library_data),
                    "stderr": "",
                },
            ):
                result = await client.get_library()

            assert result == library_data

    @pytest.mark.asyncio
    async def test_get_library_with_limit(self) -> None:
        """Test fetching library with limit parameter (applied post-fetch)."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()
            mock_run = AsyncMock(
                return_value={
                    "returncode": 0,
                    "stdout": "[]",
                    "stderr": "",
                }
            )

            with patch.object(client, "_run_command", mock_run):
                await client.get_library(limit=10)

            # Verify library export command is used (limit is applied post-fetch)
            call_args = mock_run.call_args[0][0]
            assert "library" in call_args
            assert "export" in call_args
            assert "--format" in call_args

    @pytest.mark.asyncio
    async def test_get_library_with_response_groups(self) -> None:
        """Test fetching library with response groups (not supported by CLI export)."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()
            mock_run = AsyncMock(
                return_value={
                    "returncode": 0,
                    "stdout": "[]",
                    "stderr": "",
                }
            )

            with patch.object(client, "_run_command", mock_run):
                # response_groups parameter is accepted but not passed to CLI
                await client.get_library(response_groups=["product_desc", "media"])

            # Verify library export command is used
            call_args = mock_run.call_args[0][0]
            assert "library" in call_args
            assert "export" in call_args

    @pytest.mark.asyncio
    async def test_get_library_raises_on_failure(self) -> None:
        """Test raises RuntimeError when command fails."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                return_value={
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "Authentication failed",
                },
            ):
                with pytest.raises(AudibleLibraryError, match="Failed to fetch library"):
                    await client.get_library()

    @pytest.mark.asyncio
    async def test_get_library_raises_on_invalid_json(self) -> None:
        """Test raises RuntimeError when response is not valid JSON."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                return_value={
                    "returncode": 0,
                    "stdout": "not valid json{",
                    "stderr": "",
                },
            ):
                with pytest.raises(AudibleLibraryError, match="Failed to parse library"):
                    await client.get_library()


class TestDownload:
    """Tests for download method."""

    @pytest.mark.asyncio
    async def test_download_success(self, tmp_path: Path) -> None:
        """Test successful download."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                return_value={
                    "returncode": 0,
                    "stdout": "Download complete",
                    "stderr": "",
                },
            ) as mock_run:
                result = await client.download(
                    asin="B00TEST123",
                    output_dir=tmp_path,
                )

            assert result["success"] is True
            assert result["asin"] == "B00TEST123"
            assert result["output_dir"] == str(tmp_path)

            # Verify command includes required args
            call_args = mock_run.call_args[0][0]
            assert "--asin" in call_args
            assert "B00TEST123" in call_args
            assert "--output-dir" in call_args
            assert "--aaxc" in call_args  # Default is AAXC

    @pytest.mark.asyncio
    async def test_download_without_aaxc(self, tmp_path: Path) -> None:
        """Test download with aaxc=False."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                return_value={
                    "returncode": 0,
                    "stdout": "",
                    "stderr": "",
                },
            ) as mock_run:
                await client.download(
                    asin="B00TEST123",
                    output_dir=tmp_path,
                    aaxc=False,
                )

            call_args = mock_run.call_args[0][0]
            assert "--aaxc" not in call_args

    @pytest.mark.asyncio
    async def test_download_with_custom_cover_size(self, tmp_path: Path) -> None:
        """Test download with custom cover size."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                return_value={
                    "returncode": 0,
                    "stdout": "",
                    "stderr": "",
                },
            ) as mock_run:
                await client.download(
                    asin="B00TEST123",
                    output_dir=tmp_path,
                    cover_size="500",
                )

            call_args = mock_run.call_args[0][0]
            assert "--cover-size" in call_args
            idx = call_args.index("--cover-size")
            assert call_args[idx + 1] == "500"

    @pytest.mark.asyncio
    async def test_download_failure(self, tmp_path: Path) -> None:
        """Test download returns failure result on error."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                return_value={
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "Download failed: not found",
                },
            ):
                result = await client.download(
                    asin="B00INVALID",
                    output_dir=tmp_path,
                )

            assert result["success"] is False
            assert "not found" in result["stderr"]


class TestDownloadBatch:
    """Tests for download_batch method."""

    @pytest.mark.asyncio
    async def test_download_batch_all_success(self, tmp_path: Path) -> None:
        """Test batch download with all successful."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "download",
                new_callable=AsyncMock,
                return_value={"success": True},
            ):
                results = await client.download_batch(
                    asins=["B001", "B002", "B003"],
                    output_dir=tmp_path,
                )

            assert len(results) == 3
            assert all(r["success"] for r in results)

    @pytest.mark.asyncio
    async def test_download_batch_partial_failure(self, tmp_path: Path) -> None:
        """Test batch download with some failures."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            async def download_side_effect(
                asin: str, output_dir: Path, cover_size: str
            ) -> dict[str, Any]:
                if asin == "B002":
                    return {"success": False, "error": "Not found"}
                return {"success": True, "asin": asin}

            with patch.object(
                client,
                "download",
                side_effect=download_side_effect,
            ):
                results = await client.download_batch(
                    asins=["B001", "B002", "B003"],
                    output_dir=tmp_path,
                )

            assert len(results) == 3
            assert results[0]["success"] is True
            assert results[1]["success"] is False
            assert results[2]["success"] is True

    @pytest.mark.asyncio
    async def test_download_batch_respects_max_parallel(self, tmp_path: Path) -> None:
        """Test batch download respects max_parallel limit."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()
            concurrent_count = 0
            max_concurrent = 0

            async def track_concurrent(
                asin: str, output_dir: Path, cover_size: str
            ) -> dict[str, Any]:
                nonlocal concurrent_count, max_concurrent
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.01)
                concurrent_count -= 1
                return {"success": True}

            with patch.object(client, "download", side_effect=track_concurrent):
                await client.download_batch(
                    asins=[f"B{i:03d}" for i in range(10)],
                    output_dir=tmp_path,
                    max_parallel=3,
                )

            assert max_concurrent <= 3

    @pytest.mark.asyncio
    async def test_download_batch_handles_exceptions(self, tmp_path: Path) -> None:
        """Test batch download handles exceptions gracefully."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            async def download_with_error(
                asin: str, output_dir: Path, cover_size: str
            ) -> dict[str, Any]:
                if asin == "B002":
                    raise Exception("Network error")
                return {"success": True}

            with patch.object(client, "download", side_effect=download_with_error):
                results = await client.download_batch(
                    asins=["B001", "B002", "B003"],
                    output_dir=tmp_path,
                )

            assert len(results) == 3
            assert results[0]["success"] is True
            assert results[1]["success"] is False
            assert "Network error" in str(results[1].get("error", ""))
            assert results[2]["success"] is True


class TestGetActivationBytes:
    """Tests for get_activation_bytes method."""

    @pytest.mark.asyncio
    async def test_get_activation_bytes_success(self) -> None:
        """Test successfully getting activation bytes."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                return_value={
                    "returncode": 0,
                    "stdout": json.dumps({"activation_bytes": "abc12345"}),
                    "stderr": "",
                },
            ):
                result = await client.get_activation_bytes()

            assert result == "abc12345"

    @pytest.mark.asyncio
    async def test_get_activation_bytes_returns_none_on_failure(self) -> None:
        """Test returns None when command fails."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                return_value={
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "Error",
                },
            ):
                result = await client.get_activation_bytes()

            assert result is None

    @pytest.mark.asyncio
    async def test_get_activation_bytes_returns_none_on_invalid_json(self) -> None:
        """Test returns None when response is invalid JSON."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch.object(
                client,
                "_run_command",
                new_callable=AsyncMock,
                return_value={
                    "returncode": 0,
                    "stdout": "not json",
                    "stderr": "",
                },
            ):
                result = await client.get_activation_bytes()

            assert result is None


class TestRunCommand:
    """Tests for _run_command method."""

    @pytest.mark.asyncio
    async def test_run_command_success(self) -> None:
        """Test running command successfully."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = MagicMock()
                mock_process.communicate = AsyncMock(
                    return_value=(b"output", b"errors")
                )
                mock_process.returncode = 0
                mock_exec.return_value = mock_process

                result = await client._run_command(["echo", "test"])

            assert result["returncode"] == 0
            assert result["stdout"] == "output"
            assert result["stderr"] == "errors"

    @pytest.mark.asyncio
    async def test_run_command_timeout(self) -> None:
        """Test command timeout handling."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = MagicMock()
                mock_process.communicate = AsyncMock(
                    side_effect=asyncio.TimeoutError()
                )
                mock_process.kill = MagicMock()
                mock_exec.return_value = mock_process

                result = await client._run_command(["slow", "command"], timeout=1)

            assert result["returncode"] == -1
            assert "timed out" in result["stderr"].lower()

    @pytest.mark.asyncio
    async def test_run_command_exception(self) -> None:
        """Test exception handling."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=FileNotFoundError("Command not found"),
            ):
                result = await client._run_command(["nonexistent"])

            assert result["returncode"] == -1
            assert "not found" in result["stderr"].lower()

    @pytest.mark.asyncio
    async def test_run_command_decodes_utf8(self) -> None:
        """Test command output is decoded as UTF-8."""
        with patch("services.audible_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                audible_auth_file=Path("/mock/auth.json"),
                audible_profile="default",
            )

            client = AudibleClient()

            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = MagicMock()
                # Unicode string as bytes
                mock_process.communicate = AsyncMock(
                    return_value=("Unicode: \u00e9".encode("utf-8"), b"")
                )
                mock_process.returncode = 0
                mock_exec.return_value = mock_process

                result = await client._run_command(["test"])

            assert result["stdout"] == "Unicode: \u00e9"
