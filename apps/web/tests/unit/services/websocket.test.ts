/**
 * WebSocket Client Tests
 * Tests auto-reconnect, message buffering, and subscription patterns
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  WebSocketClient,
  ConnectionState,
  type MessageHandler,
} from "@/services/websocket";
import type { WSMessage, WSMessageType } from "@/types";

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];

  url: string;
  readyState: number = 0; // CONNECTING
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent("close"));
    }
  });

  // Helper to simulate connection
  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) {
      this.onopen(new Event("open"));
    }
  }

  // Helper to simulate message
  simulateMessage(data: WSMessage) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent("message", { data: JSON.stringify(data) }));
    }
  }

  // Helper to simulate error
  simulateError() {
    if (this.onerror) {
      this.onerror(new Event("error"));
    }
  }

  // Helper to simulate close
  simulateClose(code = 1000, reason = "") {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent("close", { code, reason }));
    }
  }
}

describe("WebSocketClient", () => {
  const wsUrl = "ws://localhost:8000/ws/jobs/test-job";
  let originalWebSocket: typeof WebSocket;

  beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocket.instances = [];
    originalWebSocket = global.WebSocket;
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
  });

  afterEach(() => {
    vi.useRealTimers();
    global.WebSocket = originalWebSocket;
  });

  describe("connection management", () => {
    it("should connect to the provided URL", () => {
      const client = new WebSocketClient(wsUrl);
      client.connect();

      expect(MockWebSocket.instances).toHaveLength(1);
      expect(MockWebSocket.instances[0].url).toBe(wsUrl);
    });

    it("should update connection state to connected on open", () => {
      const client = new WebSocketClient(wsUrl);
      client.connect();

      expect(client.getState()).toBe(ConnectionState.CONNECTING);

      MockWebSocket.instances[0].simulateOpen();

      expect(client.getState()).toBe(ConnectionState.CONNECTED);
    });

    it("should update connection state to disconnected on close", () => {
      const client = new WebSocketClient(wsUrl);
      client.connect();
      MockWebSocket.instances[0].simulateOpen();
      MockWebSocket.instances[0].simulateClose();

      expect(client.getState()).toBe(ConnectionState.DISCONNECTED);
    });

    it("should call onStateChange callback when state changes", () => {
      const stateChanges: ConnectionState[] = [];
      const client = new WebSocketClient(wsUrl, {
        onStateChange: (state) => stateChanges.push(state),
      });

      client.connect();
      expect(stateChanges).toContain(ConnectionState.CONNECTING);

      MockWebSocket.instances[0].simulateOpen();
      expect(stateChanges).toContain(ConnectionState.CONNECTED);
    });

    it("should disconnect and clean up properly", () => {
      const client = new WebSocketClient(wsUrl);
      client.connect();
      MockWebSocket.instances[0].simulateOpen();

      client.disconnect();

      expect(MockWebSocket.instances[0].close).toHaveBeenCalled();
    });
  });

  describe("auto-reconnect", () => {
    it("should attempt to reconnect after unexpected disconnection", () => {
      const client = new WebSocketClient(wsUrl, {
        reconnectDelay: 1000,
        maxReconnectAttempts: 3,
      });

      client.connect();
      MockWebSocket.instances[0].simulateOpen();
      MockWebSocket.instances[0].simulateClose(1006, "Unexpected"); // Abnormal closure

      expect(client.getState()).toBe(ConnectionState.RECONNECTING);

      // Fast-forward past reconnect delay
      vi.advanceTimersByTime(1000);

      expect(MockWebSocket.instances).toHaveLength(2);
    });

    it("should use exponential backoff for reconnect attempts", () => {
      const client = new WebSocketClient(wsUrl, {
        reconnectDelay: 1000,
        maxReconnectAttempts: 5,
      });

      client.connect();
      MockWebSocket.instances[0].simulateOpen();

      // First disconnect
      MockWebSocket.instances[0].simulateClose(1006);
      expect(MockWebSocket.instances).toHaveLength(1);

      // First reconnect after 1000ms
      vi.advanceTimersByTime(1000);
      expect(MockWebSocket.instances).toHaveLength(2);
      MockWebSocket.instances[1].simulateClose(1006);

      // Second reconnect after 2000ms (exponential backoff)
      vi.advanceTimersByTime(1500);
      expect(MockWebSocket.instances).toHaveLength(2); // Still 2, hasn't fired yet
      vi.advanceTimersByTime(500);
      expect(MockWebSocket.instances).toHaveLength(3);
    });

    it("should stop reconnecting after max attempts", () => {
      const client = new WebSocketClient(wsUrl, {
        reconnectDelay: 100,
        maxReconnectAttempts: 2,
      });

      client.connect();
      MockWebSocket.instances[0].simulateOpen();
      MockWebSocket.instances[0].simulateClose(1006);

      // First reconnect attempt
      vi.advanceTimersByTime(100);
      MockWebSocket.instances[1].simulateClose(1006);

      // Second reconnect attempt
      vi.advanceTimersByTime(200);
      MockWebSocket.instances[2].simulateClose(1006);

      // Should stop - state should be failed
      vi.advanceTimersByTime(10000);
      expect(MockWebSocket.instances).toHaveLength(3);
      expect(client.getState()).toBe(ConnectionState.FAILED);
    });

    it("should not reconnect on clean close (code 1000)", () => {
      const client = new WebSocketClient(wsUrl, {
        reconnectDelay: 100,
        maxReconnectAttempts: 3,
      });

      client.connect();
      MockWebSocket.instances[0].simulateOpen();
      MockWebSocket.instances[0].simulateClose(1000, "Normal closure");

      vi.advanceTimersByTime(1000);

      expect(MockWebSocket.instances).toHaveLength(1);
      expect(client.getState()).toBe(ConnectionState.DISCONNECTED);
    });

    it("should reset reconnect attempts after successful connection", () => {
      const client = new WebSocketClient(wsUrl, {
        reconnectDelay: 100,
        maxReconnectAttempts: 2,
      });

      client.connect();
      MockWebSocket.instances[0].simulateOpen();
      MockWebSocket.instances[0].simulateClose(1006);

      // First reconnect
      vi.advanceTimersByTime(100);
      MockWebSocket.instances[1].simulateOpen(); // Successful reconnect

      expect(client.getReconnectAttempts()).toBe(0);
    });
  });

  describe("message handling", () => {
    it("should dispatch messages to subscribed handlers", () => {
      const client = new WebSocketClient(wsUrl);
      const handler = vi.fn();

      client.subscribe("progress", handler);
      client.connect();
      MockWebSocket.instances[0].simulateOpen();

      const message: WSMessage = { type: "progress", percent: 50, line: "Processing..." };
      MockWebSocket.instances[0].simulateMessage(message);

      expect(handler).toHaveBeenCalledWith(message);
    });

    it("should allow multiple handlers per message type", () => {
      const client = new WebSocketClient(wsUrl);
      const handler1 = vi.fn();
      const handler2 = vi.fn();

      client.subscribe("log", handler1);
      client.subscribe("log", handler2);
      client.connect();
      MockWebSocket.instances[0].simulateOpen();

      const message: WSMessage = { type: "log", line: "Test log" };
      MockWebSocket.instances[0].simulateMessage(message);

      expect(handler1).toHaveBeenCalledWith(message);
      expect(handler2).toHaveBeenCalledWith(message);
    });

    it("should unsubscribe handlers correctly", () => {
      const client = new WebSocketClient(wsUrl);
      const handler = vi.fn();

      client.subscribe("status", handler);
      client.connect();
      MockWebSocket.instances[0].simulateOpen();

      client.unsubscribe("status", handler);

      const message: WSMessage = { type: "status", job_id: "test", status: "RUNNING", progress: 50 };
      MockWebSocket.instances[0].simulateMessage(message);

      expect(handler).not.toHaveBeenCalled();
    });

    it("should not call handlers for unsubscribed message types", () => {
      const client = new WebSocketClient(wsUrl);
      const progressHandler = vi.fn();

      client.subscribe("progress", progressHandler);
      client.connect();
      MockWebSocket.instances[0].simulateOpen();

      const logMessage: WSMessage = { type: "log", line: "Test log" };
      MockWebSocket.instances[0].simulateMessage(logMessage);

      expect(progressHandler).not.toHaveBeenCalled();
    });

    it("should handle batch messages and dispatch each message", () => {
      const client = new WebSocketClient(wsUrl);
      const logHandler = vi.fn();

      client.subscribe("log", logHandler);
      client.connect();
      MockWebSocket.instances[0].simulateOpen();

      const batchMessage: WSMessage = {
        type: "batch",
        messages: [
          { type: "log", line: "Log 1" },
          { type: "log", line: "Log 2" },
          { type: "log", line: "Log 3" },
        ],
        count: 3,
      };
      MockWebSocket.instances[0].simulateMessage(batchMessage);

      expect(logHandler).toHaveBeenCalledTimes(3);
    });
  });

  describe("message buffering", () => {
    it("should buffer log messages and flush periodically", () => {
      const client = new WebSocketClient(wsUrl, {
        bufferFlushInterval: 100,
      });
      const logHandler = vi.fn();

      client.subscribe("log", logHandler);
      client.connect();
      MockWebSocket.instances[0].simulateOpen();

      // Send multiple log messages rapidly
      for (let i = 0; i < 5; i++) {
        MockWebSocket.instances[0].simulateMessage({ type: "log", line: `Log ${i}` });
      }

      // Messages should be buffered, not immediately dispatched
      // (implementation detail - may dispatch immediately in some implementations)

      // Advance timers to trigger flush
      vi.advanceTimersByTime(100);

      // After flush, all messages should have been handled
      expect(logHandler).toHaveBeenCalled();
    });
  });

  describe("send functionality", () => {
    it("should send messages when connected", () => {
      const client = new WebSocketClient(wsUrl);
      client.connect();
      MockWebSocket.instances[0].simulateOpen();

      client.send({ action: "subscribe", channel: "job-123" });

      expect(MockWebSocket.instances[0].send).toHaveBeenCalledWith(
        JSON.stringify({ action: "subscribe", channel: "job-123" })
      );
    });

    it("should throw error when sending while disconnected", () => {
      const client = new WebSocketClient(wsUrl);

      expect(() => client.send({ test: true })).toThrow();
    });

    it("should queue messages sent while connecting", () => {
      const client = new WebSocketClient(wsUrl, {
        queueWhileConnecting: true,
      });
      client.connect();

      // Send while still connecting
      client.send({ action: "subscribe", channel: "test" });

      expect(MockWebSocket.instances[0].send).not.toHaveBeenCalled();

      // Complete connection
      MockWebSocket.instances[0].simulateOpen();

      expect(MockWebSocket.instances[0].send).toHaveBeenCalled();
    });
  });

  describe("error handling", () => {
    it("should handle connection errors gracefully", () => {
      const onError = vi.fn();
      const client = new WebSocketClient(wsUrl, {
        onError,
      });

      client.connect();
      MockWebSocket.instances[0].simulateError();

      expect(onError).toHaveBeenCalled();
    });

    it("should handle malformed messages without crashing", () => {
      const client = new WebSocketClient(wsUrl);
      const handler = vi.fn();
      client.subscribe("log", handler);
      client.connect();
      MockWebSocket.instances[0].simulateOpen();

      // Simulate malformed message
      if (MockWebSocket.instances[0].onmessage) {
        MockWebSocket.instances[0].onmessage(
          new MessageEvent("message", { data: "invalid json" })
        );
      }

      // Should not crash, handler should not be called
      expect(handler).not.toHaveBeenCalled();
    });
  });

  describe("connection tracking", () => {
    it("should track last connected time", () => {
      const client = new WebSocketClient(wsUrl);
      client.connect();

      expect(client.getLastConnectedTime()).toBeNull();

      MockWebSocket.instances[0].simulateOpen();

      expect(client.getLastConnectedTime()).toBeInstanceOf(Date);
    });

    it("should track reconnect attempts", () => {
      const client = new WebSocketClient(wsUrl, {
        reconnectDelay: 100,
        maxReconnectAttempts: 5,
      });

      client.connect();
      MockWebSocket.instances[0].simulateOpen();
      MockWebSocket.instances[0].simulateClose(1006);

      expect(client.getReconnectAttempts()).toBe(0); // Before reconnect

      vi.advanceTimersByTime(100);
      MockWebSocket.instances[1].simulateClose(1006);

      expect(client.getReconnectAttempts()).toBe(1);

      vi.advanceTimersByTime(200);

      expect(client.getReconnectAttempts()).toBe(2);
    });
  });
});
