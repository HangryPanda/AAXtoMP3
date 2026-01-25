"""Unit tests for audible-cli progress parsing."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.audible_client import AudibleClient, NdjsonDownloadEvent, parse_ndjson_download_line
from services.audible_client import _parse_audible_cli_progress_line


def test_parse_audible_cli_progress_line_parses_aaxc() -> None:
    line = "0063137321_Dark Rise-AAX_44_128.aaxc:   1%|          | 9.46M/845M [00:04<05:21, 2.73MB/s]"
    parsed = _parse_audible_cli_progress_line(line)
    assert parsed is not None
    cur_b, tot_b = parsed
    assert cur_b > 0
    assert tot_b > cur_b


def test_parse_audible_cli_progress_line_ignores_non_aax_lines() -> None:
    assert _parse_audible_cli_progress_line("File cover.jpg downloaded") is None


class TestParseNdjsonDownloadLine:
    def test_download_start(self) -> None:
        line = json.dumps(
            {
                "event_type": "download_start",
                "asin": "1774241404",
                "filename": "1774241404_Title.aaxc",
                "total_bytes": 1000,
                "resumed": False,
                "timestamp": "2026-01-25T00:00:00Z",
            }
        )
        event = parse_ndjson_download_line(line)
        assert isinstance(event, NdjsonDownloadEvent)
        assert event.event_type == "download_start"
        assert event.asin == "1774241404"
        assert event.filename == "1774241404_Title.aaxc"
        assert event.total_bytes == 1000
        assert event.resumed is False
        assert event.timestamp == "2026-01-25T00:00:00Z"

    def test_download_progress_with_type_coercion(self) -> None:
        line = json.dumps(
            {
                "event_type": "download_progress",
                "asin": "1774241404",
                "filename": "1774241404_Title.aaxc",
                "current_bytes": "500",
                "total_bytes": "1000",
                "bytes_per_sec": "123.45",
                "resumed": True,
                "timestamp": "2026-01-25T00:00:01Z",
            }
        )
        event = parse_ndjson_download_line(line)
        assert isinstance(event, NdjsonDownloadEvent)
        assert event.event_type == "download_progress"
        assert event.current_bytes == 500
        assert event.total_bytes == 1000
        assert event.bytes_per_sec == pytest.approx(123.45)
        assert event.resumed is True

    def test_download_complete(self) -> None:
        line = json.dumps(
            {
                "event_type": "download_complete",
                "asin": "1774241404",
                "filename": "1774241404_Title.aaxc",
                "total_bytes": 1000,
                "success": True,
                "timestamp": "2026-01-25T00:00:02Z",
            }
        )
        event = parse_ndjson_download_line(line)
        assert isinstance(event, NdjsonDownloadEvent)
        assert event.event_type == "download_complete"
        assert event.success is True
        assert event.total_bytes == 1000

    def test_download_error(self) -> None:
        line = json.dumps(
            {
                "event_type": "download_error",
                "asin": "0123456789",
                "success": False,
                "error_code": "NotFound",
                "message": "ASIN not found",
            }
        )
        event = parse_ndjson_download_line(line)
        assert isinstance(event, NdjsonDownloadEvent)
        assert event.event_type == "download_error"
        assert event.asin == "0123456789"
        assert event.success is False
        assert event.error_code == "NotFound"
        assert event.message == "ASIN not found"

    def test_malformed_lines_return_none(self) -> None:
        assert parse_ndjson_download_line("") is None
        assert parse_ndjson_download_line("not json") is None
        assert parse_ndjson_download_line('{"event_type":') is None

    def test_non_dict_json_is_ignored(self) -> None:
        assert parse_ndjson_download_line('["download_progress"]') is None

    def test_unknown_event_type_defaults_to_unknown(self) -> None:
        line = json.dumps({"asin": "1774241404"})
        event = parse_ndjson_download_line(line)
        assert isinstance(event, NdjsonDownloadEvent)
        assert event.event_type == "unknown"
        assert event.asin == "1774241404"


class _FakeStream:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self._idx = 0

    async def read(self, _n: int) -> bytes:
        if self._idx >= len(self._chunks):
            return b""
        chunk = self._chunks[self._idx]
        self._idx += 1
        await asyncio.sleep(0)
        return chunk


class _FakeProcess:
    def __init__(self, stdout_chunks: list[bytes], stderr_chunks: list[bytes]) -> None:
        self.stdout = _FakeStream(stdout_chunks)
        self.stderr = _FakeStream(stderr_chunks)
        self.returncode: int | None = None

    async def wait(self) -> int:
        await asyncio.sleep(0)
        self.returncode = 0
        return 0

    def kill(self) -> None:  # pragma: no cover
        return


@pytest.mark.asyncio
async def test_run_command_streaming_can_consume_ndjson_stdout() -> None:
    """
    Integration-style test: stub subprocess stdout stream with NDJSON lines.

    This ensures our streaming splitter forwards complete lines (\\n and \\r),
    and that NDJSON parsing can be applied line-by-line with malformed lines ignored.
    """
    ndjson_lines = [
        json.dumps({"event_type": "download_start", "asin": "1774241404", "total_bytes": 10}),
        "not json",
        json.dumps({"event_type": "download_progress", "asin": "1774241404", "current_bytes": 5, "total_bytes": 10}),
        json.dumps({"event_type": "download_complete", "asin": "1774241404", "success": True, "total_bytes": 10}),
        json.dumps({"event_type": "download_error", "asin": "0123456789", "success": False, "error_code": "NotFound"}),
    ]

    payload = ("\n".join(ndjson_lines[:2]) + "\r" + "\n".join(ndjson_lines[2:]) + "\n").encode("utf-8")
    stdout_chunks = [payload[:25], payload[25:60], payload[60:]]
    stderr_chunks: list[bytes] = []

    fake_proc = _FakeProcess(stdout_chunks=stdout_chunks, stderr_chunks=stderr_chunks)

    captured_events: list[NdjsonDownloadEvent] = []

    def on_stdout_line(line: str) -> None:
        event = parse_ndjson_download_line(line)
        if event is not None:
            captured_events.append(event)

    with patch("services.audible_client.get_settings") as mock_settings, patch(
        "services.audible_client.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=fake_proc),
    ):
        mock_settings.return_value = MagicMock(
            audible_auth_file=Path("/tmp/auth.json"),
            audible_profile="default",
        )
        client = AudibleClient()
        result = await client._run_command_streaming(
            ["audible", "download", "--asin", "1774241404"],
            timeout=1,
            on_stdout_line=on_stdout_line,
        )

    assert result["returncode"] == 0
    assert [e.event_type for e in captured_events] == [
        "download_start",
        "download_progress",
        "download_complete",
        "download_error",
    ]
