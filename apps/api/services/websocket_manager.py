"""WebSocket connection manager for real-time updates."""

import asyncio
import json
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket

from core.config import get_settings


class WebSocketManager:
    """
    Manages WebSocket connections and broadcasts.

    Features:
    - Connection tracking per job/resource ID
    - Message buffering to prevent render thrashing
    - Broadcast to all subscribers
    """

    def __init__(self) -> None:
        """Initialize WebSocket manager."""
        self.settings = get_settings()
        self._connections: dict[str, WebSocket] = {}
        self._buffers: dict[str, list[dict[str, Any]]] = {}
        self._flush_tasks: dict[str, asyncio.Task[None]] = {}
        self._buffer_interval = self.settings.ws_log_buffer_ms / 1000.0

    async def connect(self, websocket: WebSocket, resource_id: str) -> None:
        """
        Accept and register a WebSocket connection.

        Args:
            websocket: The WebSocket connection
            resource_id: Identifier for the resource (e.g., job_id)
        """
        await websocket.accept()
        self._connections[resource_id] = websocket
        self._buffers[resource_id] = []

    def disconnect(self, resource_id: str) -> None:
        """
        Remove a WebSocket connection.

        Args:
            resource_id: Identifier for the resource
        """
        if resource_id in self._connections:
            del self._connections[resource_id]

        if resource_id in self._buffers:
            del self._buffers[resource_id]

        if resource_id in self._flush_tasks:
            self._flush_tasks[resource_id].cancel()
            del self._flush_tasks[resource_id]

    def is_connected(self, resource_id: str) -> bool:
        """Check if a resource has an active connection."""
        return resource_id in self._connections

    async def send_personal_message(
        self,
        message: dict[str, Any],
        resource_id: str,
    ) -> bool:
        """
        Send a message to a specific connection.

        Args:
            message: Message to send
            resource_id: Target resource ID

        Returns:
            True if sent successfully, False otherwise
        """
        if resource_id not in self._connections:
            return False

        try:
            await self._connections[resource_id].send_json(message)
            return True
        except Exception:
            self.disconnect(resource_id)
            return False

    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Broadcast a message to all connected clients.

        Args:
            message: Message to broadcast
        """
        disconnected: list[str] = []

        for resource_id, websocket in self._connections.items():
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(resource_id)

        # Clean up disconnected clients
        for resource_id in disconnected:
            self.disconnect(resource_id)

    def buffer_message(self, message: dict[str, Any], resource_id: str) -> None:
        """
        Buffer a message for batched sending.

        Messages are collected and flushed at regular intervals to prevent
        overwhelming the client with rapid updates (e.g., FFmpeg log output).

        Args:
            message: Message to buffer
            resource_id: Target resource ID
        """
        if resource_id not in self._connections:
            return

        if resource_id not in self._buffers:
            self._buffers[resource_id] = []

        self._buffers[resource_id].append(message)

        # Start flush task if not already running
        if resource_id not in self._flush_tasks or self._flush_tasks[resource_id].done():
            self._flush_tasks[resource_id] = asyncio.create_task(
                self._flush_buffer(resource_id)
            )

    async def _flush_buffer(self, resource_id: str) -> None:
        """
        Flush buffered messages after interval.

        Args:
            resource_id: Resource ID to flush
        """
        await asyncio.sleep(self._buffer_interval)

        if resource_id not in self._buffers or resource_id not in self._connections:
            return

        messages = self._buffers[resource_id]
        if not messages:
            return

        self._buffers[resource_id] = []

        try:
            # Send all buffered messages as a batch
            await self._connections[resource_id].send_json({
                "type": "batch",
                "messages": messages,
                "count": len(messages),
            })
        except Exception:
            self.disconnect(resource_id)

    def create_progress_callback(
        self,
        resource_id: str,
        message_type: str = "progress",
    ) -> Callable[[int, str], None]:
        """
        Create a progress callback for job execution.

        Args:
            resource_id: Resource ID to send updates to
            message_type: Type field for messages

        Returns:
            Callback function that buffers progress updates
        """
        def callback(percent: int, line: str) -> None:
            message = {
                "type": message_type,
                "percent": percent,
                "line": line,
            }

            if percent >= 0:
                # Progress update - send immediately
                asyncio.create_task(
                    self.send_personal_message(message, resource_id)
                )
            else:
                # Log line - buffer it
                self.buffer_message({"type": "log", "line": line}, resource_id)

        return callback

    async def send_status_update(
        self,
        resource_id: str,
        status: str,
        progress: int = 0,
        error: str | None = None,
    ) -> bool:
        """
        Send a status update message.

        Args:
            resource_id: Target resource ID
            status: Current status
            progress: Progress percentage
            error: Optional error message

        Returns:
            True if sent successfully
        """
        message = {
            "type": "status",
            "status": status,
            "progress": progress,
        }

        if error:
            message["error"] = error

        return await self.send_personal_message(message, resource_id)
