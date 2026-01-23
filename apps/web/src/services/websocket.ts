/**
 * WebSocket Client
 * Handles WebSocket connections with auto-reconnect, message buffering, and subscriptions
 */

import type {
  WSMessage,
  WSMessageType,
  WSBatchMessage,
} from "@/types";

/**
 * Connection states
 */
export enum ConnectionState {
  DISCONNECTED = "disconnected",
  CONNECTING = "connecting",
  CONNECTED = "connected",
  RECONNECTING = "reconnecting",
  FAILED = "failed",
}

/**
 * Message handler type
 */
export type MessageHandler<T extends WSMessage = WSMessage> = (message: T) => void;

/**
 * WebSocket client options
 */
export interface WebSocketClientOptions {
  /** Delay between reconnect attempts in ms */
  reconnectDelay?: number;
  /** Maximum number of reconnect attempts */
  maxReconnectAttempts?: number;
  /** Interval for flushing buffered messages in ms */
  bufferFlushInterval?: number;
  /** Queue messages while connecting */
  queueWhileConnecting?: boolean;
  /** Called when connection state changes */
  onStateChange?: (state: ConnectionState) => void;
  /** Called when an error occurs */
  onError?: (error: Error) => void;
}

/**
 * WebSocket client with auto-reconnect, message buffering, and subscription pattern
 */
export class WebSocketClient {
  private url: string;
  private ws: WebSocket | null = null;
  private state: ConnectionState = ConnectionState.DISCONNECTED;
  private reconnectAttempts = 0;
  private lastConnectedTime: Date | null = null;
  private reconnectTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private flushIntervalId: ReturnType<typeof setInterval> | null = null;
  private intentionalClose = false;

  // Options
  private readonly reconnectDelay: number;
  private readonly maxReconnectAttempts: number;
  private readonly bufferFlushInterval: number;
  private readonly queueWhileConnecting: boolean;
  private readonly onStateChange?: (state: ConnectionState) => void;
  private readonly onError?: (error: Error) => void;

  // Subscriptions
  private handlers: Map<WSMessageType, Set<MessageHandler>> = new Map();

  // Message buffer for logs
  private messageBuffer: WSMessage[] = [];

  // Queue for messages sent while connecting
  private messageQueue: unknown[] = [];

  constructor(url: string, options: WebSocketClientOptions = {}) {
    this.url = url;
    this.reconnectDelay = options.reconnectDelay ?? 1000;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 10;
    this.bufferFlushInterval = options.bufferFlushInterval ?? 100;
    this.queueWhileConnecting = options.queueWhileConnecting ?? false;
    this.onStateChange = options.onStateChange;
    this.onError = options.onError;
  }

  /**
   * Connect to the WebSocket server
   */
  connect(): void {
    if (this.ws && (this.state === ConnectionState.CONNECTED || this.state === ConnectionState.CONNECTING)) {
      return;
    }

    this.intentionalClose = false;
    this.setState(ConnectionState.CONNECTING);

    try {
      this.ws = new WebSocket(this.url);
      this.setupEventHandlers();
    } catch (error) {
      this.handleError(error instanceof Error ? error : new Error("Failed to create WebSocket"));
    }
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect(): void {
    this.intentionalClose = true;
    this.clearReconnectTimeout();
    this.clearFlushInterval();

    if (this.ws) {
      this.ws.close(1000, "Client disconnect");
    }

    this.setState(ConnectionState.DISCONNECTED);
  }

  /**
   * Subscribe to a message type
   */
  subscribe<T extends WSMessage>(type: WSMessageType, handler: MessageHandler<T>): void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)!.add(handler as MessageHandler);
  }

  /**
   * Unsubscribe from a message type
   */
  unsubscribe<T extends WSMessage>(type: WSMessageType, handler: MessageHandler<T>): void {
    const handlersSet = this.handlers.get(type);
    if (handlersSet) {
      handlersSet.delete(handler as MessageHandler);
    }
  }

  /**
   * Send a message through the WebSocket
   */
  send(data: unknown): void {
    if (this.state === ConnectionState.CONNECTING && this.queueWhileConnecting) {
      this.messageQueue.push(data);
      return;
    }

    if (this.state !== ConnectionState.CONNECTED || !this.ws) {
      throw new Error("WebSocket is not connected");
    }

    this.ws.send(JSON.stringify(data));
  }

  /**
   * Get the current connection state
   */
  getState(): ConnectionState {
    return this.state;
  }

  /**
   * Get the last connected time
   */
  getLastConnectedTime(): Date | null {
    return this.lastConnectedTime;
  }

  /**
   * Get the current reconnect attempts
   */
  getReconnectAttempts(): number {
    return this.reconnectAttempts;
  }

  /**
   * Set up WebSocket event handlers
   */
  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      this.lastConnectedTime = new Date();
      this.reconnectAttempts = 0;
      this.setState(ConnectionState.CONNECTED);
      this.startFlushInterval();
      this.flushMessageQueue();
    };

    this.ws.onclose = (event) => {
      this.clearFlushInterval();

      if (this.intentionalClose || event.code === 1000) {
        this.setState(ConnectionState.DISCONNECTED);
        return;
      }

      // Unexpected close - attempt reconnect
      this.attemptReconnect();
    };

    this.ws.onerror = () => {
      this.handleError(new Error("WebSocket error"));
    };

    this.ws.onmessage = (event) => {
      this.handleMessage(event);
    };
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data as string) as WSMessage;
      this.dispatchMessage(data);
    } catch {
      // Malformed message - ignore
      console.warn("Failed to parse WebSocket message:", event.data);
    }
  }

  /**
   * Dispatch a message to subscribed handlers
   */
  private dispatchMessage(message: WSMessage): void {
    // Handle batch messages
    if (message.type === "batch") {
      const batchMsg = message as WSBatchMessage;
      // Allow consumers to treat the batch as an authoritative snapshot.
      const batchHandlers = this.handlers.get("batch");
      if (batchHandlers) {
        for (const handler of batchHandlers) {
          try {
            handler(batchMsg);
          } catch (error) {
            console.error("Error in batch message handler:", error);
          }
        }
      }
      for (const msg of batchMsg.messages) {
        this.dispatchMessage(msg);
      }
      return;
    }

    // Buffer log messages for batched processing
    if (message.type === "log") {
      this.messageBuffer.push(message);
      return;
    }

    // Dispatch to handlers
    const handlersSet = this.handlers.get(message.type);
    if (handlersSet) {
      for (const handler of handlersSet) {
        try {
          handler(message);
        } catch (error) {
          console.error("Error in message handler:", error);
        }
      }
    }
  }

  /**
   * Flush buffered messages to handlers
   */
  private flushBuffer(): void {
    if (this.messageBuffer.length === 0) return;

    const messages = [...this.messageBuffer];
    this.messageBuffer = [];

    for (const message of messages) {
      const handlersSet = this.handlers.get(message.type);
      if (handlersSet) {
        for (const handler of handlersSet) {
          try {
            handler(message);
          } catch (error) {
            console.error("Error in message handler:", error);
          }
        }
      }
    }
  }

  /**
   * Flush queued messages sent while connecting
   */
  private flushMessageQueue(): void {
    if (!this.queueWhileConnecting || this.messageQueue.length === 0) return;

    const queue = [...this.messageQueue];
    this.messageQueue = [];

    for (const data of queue) {
      this.send(data);
    }
  }

  /**
   * Start the flush interval for buffered messages
   */
  private startFlushInterval(): void {
    this.clearFlushInterval();
    this.flushIntervalId = setInterval(() => {
      this.flushBuffer();
    }, this.bufferFlushInterval);
  }

  /**
   * Clear the flush interval
   */
  private clearFlushInterval(): void {
    if (this.flushIntervalId) {
      clearInterval(this.flushIntervalId);
      this.flushIntervalId = null;
    }
  }

  /**
   * Attempt to reconnect to the WebSocket server
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.setState(ConnectionState.FAILED);
      return;
    }

    this.setState(ConnectionState.RECONNECTING);

    // Calculate delay with exponential backoff
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;

    this.reconnectTimeoutId = setTimeout(() => {
      this.connect();
    }, delay);
  }

  /**
   * Clear the reconnect timeout
   */
  private clearReconnectTimeout(): void {
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
  }

  /**
   * Update the connection state
   */
  private setState(state: ConnectionState): void {
    if (this.state === state) return;
    this.state = state;
    this.onStateChange?.(state);
  }

  /**
   * Handle errors
   */
  private handleError(error: Error): void {
    this.onError?.(error);
  }
}

/**
 * Create a WebSocket client for job monitoring
 */
export function createJobWebSocket(
  jobId: string,
  options?: WebSocketClientOptions
): WebSocketClient {
  // Import WS_URL from env - this will be available at runtime
  const wsUrl = typeof window !== "undefined"
    ? `${process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"}/jobs/ws/${jobId}`
    : `ws://localhost:8000/jobs/ws/${jobId}`;

  return new WebSocketClient(wsUrl, options);
}
