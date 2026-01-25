"""Unit tests for WebSocketManager service."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.websocket_manager import WebSocketManager


class TestWebSocketManagerInit:
    """Tests for WebSocketManager initialization."""

    def test_init_creates_empty_collections(self) -> None:
        """Test that manager initializes with empty collections."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                ws_log_buffer_ms=100,
            )

            manager = WebSocketManager()

            assert len(manager._connections) == 0
            assert len(manager._buffers) == 0
            assert len(manager._flush_tasks) == 0

    def test_init_sets_buffer_interval(self) -> None:
        """Test that buffer interval is set from settings."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                ws_log_buffer_ms=200,
            )

            manager = WebSocketManager()

            assert manager._buffer_interval == 0.2  # 200ms in seconds


class TestConnect:
    """Tests for connect method."""

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self) -> None:
        """Test connect accepts the WebSocket connection."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            mock_ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_registers_connection(self) -> None:
        """Test connect registers the connection."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            assert "resource-123" in manager._connections
            assert mock_ws in manager._connections["resource-123"]

    @pytest.mark.asyncio
    async def test_connect_initializes_buffer(self) -> None:
        """Test connect initializes empty buffer for resource."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            assert "resource-123" in manager._buffers
            assert manager._buffers["resource-123"] == []


class TestDisconnect:
    """Tests for disconnect method."""

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self) -> None:
        """Test disconnect removes the connection."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()

            await manager.connect(mock_ws, "resource-123")
            manager.disconnect(mock_ws, "resource-123")

            assert "resource-123" not in manager._connections

    @pytest.mark.asyncio
    async def test_disconnect_removes_buffer(self) -> None:
        """Test disconnect removes the buffer."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()

            await manager.connect(mock_ws, "resource-123")
            manager.disconnect(mock_ws, "resource-123")

            assert "resource-123" not in manager._buffers

    @pytest.mark.asyncio
    async def test_disconnect_cancels_flush_task(self) -> None:
        """Test disconnect cancels pending flush task."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            # Create a mock flush task
            mock_task = MagicMock()
            manager._flush_tasks["resource-123"] = mock_task

            manager.disconnect(mock_ws, "resource-123")

            mock_task.cancel.assert_called_once()
            assert "resource-123" not in manager._flush_tasks

    def test_disconnect_nonexistent_is_safe(self) -> None:
        """Test disconnecting non-existent resource doesn't raise."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            # Should not raise
            manager.disconnect(MagicMock(), "nonexistent")


class TestIsConnected:
    """Tests for is_connected method."""

    @pytest.mark.asyncio
    async def test_is_connected_returns_true(self) -> None:
        """Test is_connected returns True for connected resource."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            assert manager.is_connected("resource-123") is True

    def test_is_connected_returns_false(self) -> None:
        """Test is_connected returns False for non-connected resource."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            assert manager.is_connected("nonexistent") is False


class TestSendPersonalMessage:
    """Tests for send_personal_message method."""

    @pytest.mark.asyncio
    async def test_send_personal_message_success(self) -> None:
        """Test sending message to connected resource."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            message = {"type": "test", "data": "hello"}
            result = await manager.send_personal_message(message, "resource-123")

            assert result is True
            mock_ws.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_personal_message_not_connected(self) -> None:
        """Test sending message to non-connected resource returns False."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            result = await manager.send_personal_message(
                {"type": "test"}, "nonexistent"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_send_personal_message_exception_disconnects(self) -> None:
        """Test send failure disconnects the client."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock(side_effect=Exception("Connection lost"))

            await manager.connect(mock_ws, "resource-123")

            result = await manager.send_personal_message(
                {"type": "test"}, "resource-123"
            )

            assert result is False
            assert "resource-123" not in manager._connections


class TestBroadcast:
    """Tests for broadcast method."""

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self) -> None:
        """Test broadcast sends message to all connected clients."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            # Connect multiple clients
            for i in range(3):
                mock_ws = MagicMock()
                mock_ws.accept = AsyncMock()
                mock_ws.send_json = AsyncMock()
                await manager.connect(mock_ws, f"resource-{i}")

            message = {"type": "broadcast", "data": "hello all"}
            await manager.broadcast(message)

            # Verify all received the message
            for _resource_id, websockets in manager._connections.items():
                for ws in websockets:
                    ws.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_connections(self) -> None:
        """Test broadcast removes connections that fail."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            # Connect good client
            good_ws = MagicMock()
            good_ws.accept = AsyncMock()
            good_ws.send_json = AsyncMock()
            await manager.connect(good_ws, "good-client")

            # Connect bad client
            bad_ws = MagicMock()
            bad_ws.accept = AsyncMock()
            bad_ws.send_json = AsyncMock(side_effect=Exception("Failed"))
            await manager.connect(bad_ws, "bad-client")

            await manager.broadcast({"type": "test"})

            assert "good-client" in manager._connections
            assert "bad-client" not in manager._connections


class TestBufferMessage:
    """Tests for buffer_message method."""

    @pytest.mark.asyncio
    async def test_buffer_message_adds_to_buffer(self) -> None:
        """Test buffering a message adds it to the buffer."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            message = {"type": "log", "line": "test output"}
            manager.buffer_message(message, "resource-123")

            assert len(manager._buffers["resource-123"]) == 1
            assert manager._buffers["resource-123"][0] == message

    @pytest.mark.asyncio
    async def test_buffer_message_multiple(self) -> None:
        """Test buffering multiple messages."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            for i in range(5):
                manager.buffer_message({"line": f"message {i}"}, "resource-123")

            assert len(manager._buffers["resource-123"]) == 5

    def test_buffer_message_not_connected_ignored(self) -> None:
        """Test buffering for non-connected resource is ignored."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            # Should not raise
            manager.buffer_message({"type": "test"}, "nonexistent")

    @pytest.mark.asyncio
    async def test_buffer_message_creates_flush_task(self) -> None:
        """Test buffering a message creates flush task."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            manager.buffer_message({"type": "log"}, "resource-123")

            # Flush task should be created
            assert "resource-123" in manager._flush_tasks

            # Clean up
            manager._flush_tasks["resource-123"].cancel()
            try:
                await manager._flush_tasks["resource-123"]
            except asyncio.CancelledError:
                pass


class TestFlushBuffer:
    """Tests for _flush_buffer method."""

    @pytest.mark.asyncio
    async def test_flush_buffer_sends_batch(self) -> None:
        """Test flushing sends buffered messages as batch."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=10)  # 10ms

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            # Add messages to buffer
            manager._buffers["resource-123"] = [
                {"line": "msg1"},
                {"line": "msg2"},
                {"line": "msg3"},
            ]

            await manager._flush_buffer("resource-123")

            # Verify batch was sent
            mock_ws.send_json.assert_called_once()
            call_arg = mock_ws.send_json.call_args[0][0]

            assert call_arg["type"] == "batch"
            assert call_arg["count"] == 3
            assert len(call_arg["messages"]) == 3

    @pytest.mark.asyncio
    async def test_flush_buffer_clears_buffer(self) -> None:
        """Test flushing clears the buffer."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=10)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()

            await manager.connect(mock_ws, "resource-123")
            manager._buffers["resource-123"] = [{"line": "msg1"}]

            await manager._flush_buffer("resource-123")

            assert manager._buffers["resource-123"] == []

    @pytest.mark.asyncio
    async def test_flush_buffer_empty_buffer_no_send(self) -> None:
        """Test flushing empty buffer doesn't send."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=10)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            await manager._flush_buffer("resource-123")

            mock_ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_buffer_disconnects_on_error(self) -> None:
        """Test flush disconnects client on send error."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=10)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock(side_effect=Exception("Send failed"))

            await manager.connect(mock_ws, "resource-123")
            manager._buffers["resource-123"] = [{"line": "msg"}]

            await manager._flush_buffer("resource-123")

            assert "resource-123" not in manager._connections


class TestCreateProgressCallback:
    """Tests for create_progress_callback method."""

    @pytest.mark.asyncio
    async def test_create_progress_callback_positive_percent(self) -> None:
        """Test callback sends progress immediately for positive percent."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            callback = manager.create_progress_callback("resource-123")

            # Call with positive percent (should send immediately)
            callback(50, "Processing...")

            # Give async task time to run
            await asyncio.sleep(0.01)

            # Verify message was sent
            mock_ws.send_json.assert_called()
            call_arg = mock_ws.send_json.call_args[0][0]
            assert call_arg["type"] == "progress"
            assert call_arg["percent"] == 50

    @pytest.mark.asyncio
    async def test_create_progress_callback_negative_percent_buffers(self) -> None:
        """Test callback buffers log lines (negative percent)."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=1000)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            callback = manager.create_progress_callback("resource-123")

            # Call with negative percent (should buffer)
            callback(-1, "Log output line")

            # Check buffer has the message
            assert len(manager._buffers["resource-123"]) == 1
            assert manager._buffers["resource-123"][0]["type"] == "log"

            # Clean up flush task
            if "resource-123" in manager._flush_tasks:
                manager._flush_tasks["resource-123"].cancel()

    @pytest.mark.asyncio
    async def test_create_progress_callback_custom_type(self) -> None:
        """Test callback with custom message type."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            callback = manager.create_progress_callback(
                "resource-123", message_type="download_progress"
            )

            callback(75, "Downloading...")
            await asyncio.sleep(0.01)

            call_arg = mock_ws.send_json.call_args[0][0]
            assert call_arg["type"] == "download_progress"


class TestSendStatusUpdate:
    """Tests for send_status_update method."""

    @pytest.mark.asyncio
    async def test_send_status_update_basic(self) -> None:
        """Test sending basic status update."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            result = await manager.send_status_update(
                "resource-123", status="RUNNING", progress=25
            )

            assert result is True

            call_arg = mock_ws.send_json.call_args[0][0]
            assert call_arg["type"] == "status"
            assert call_arg["status"] == "RUNNING"
            assert call_arg["progress"] == 25

    @pytest.mark.asyncio
    async def test_send_status_update_with_error(self) -> None:
        """Test sending status update with error message."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            result = await manager.send_status_update(
                "resource-123",
                status="FAILED",
                progress=0,
                error="File not found",
            )

            assert result is True

            call_arg = mock_ws.send_json.call_args[0][0]
            assert call_arg["status"] == "FAILED"
            assert call_arg["error"] == "File not found"

    @pytest.mark.asyncio
    async def test_send_status_update_not_connected(self) -> None:
        """Test sending status update to non-connected resource."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=100)

            manager = WebSocketManager()

            result = await manager.send_status_update("nonexistent", "RUNNING")

            assert result is False


class TestMessageBufferingIntegration:
    """Integration tests for message buffering behavior."""

    @pytest.mark.asyncio
    async def test_rapid_messages_are_batched(self) -> None:
        """Test that rapid messages are batched together."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=50)  # 50ms

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            # Send many messages rapidly
            for i in range(10):
                manager.buffer_message({"line": f"msg{i}"}, "resource-123")

            # Wait for flush
            await asyncio.sleep(0.1)

            # Should have sent one batch
            assert mock_ws.send_json.call_count == 1

            call_arg = mock_ws.send_json.call_args[0][0]
            assert call_arg["type"] == "batch"
            assert call_arg["count"] == 10

    @pytest.mark.asyncio
    async def test_progress_and_logs_separate(self) -> None:
        """Test that progress updates are immediate while logs are buffered."""
        with patch("services.websocket_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ws_log_buffer_ms=200)

            manager = WebSocketManager()

            mock_ws = MagicMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()

            await manager.connect(mock_ws, "resource-123")

            callback = manager.create_progress_callback("resource-123")

            # Send progress (immediate)
            callback(50, "50% complete")
            await asyncio.sleep(0.01)

            # Send log (buffered)
            callback(-1, "Log line 1")
            callback(-1, "Log line 2")

            # Progress should have been sent immediately
            first_call = mock_ws.send_json.call_args_list[0][0][0]
            assert first_call["type"] == "progress"
            assert first_call["percent"] == 50

            # Logs should be in buffer
            assert len(manager._buffers["resource-123"]) == 2

            # Clean up
            if "resource-123" in manager._flush_tasks:
                manager._flush_tasks["resource-123"].cancel()
