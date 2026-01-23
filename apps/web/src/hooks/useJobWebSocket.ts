/**
 * useJobWebSocket Hook
 * React hook for subscribing to job progress and logs via WebSocket
 */

import { useEffect, useRef, useCallback, useState } from "react";
import {
  WebSocketClient,
  ConnectionState,
  type MessageHandler,
} from "@/services/websocket";
import { WS_URL } from "@/lib/env";
import type {
  WSStatusMessage,
  WSProgressMessage,
  WSLogMessage,
} from "@/types";
import { useUpdateJobFromWS } from "./useJobs";

/**
 * Job WebSocket state
 */
export interface JobWebSocketState {
  connectionState: ConnectionState;
  progress: number;
  logs: string[];
  error: string | null;
  isConnected: boolean;
}

/**
 * Job WebSocket options
 */
export interface UseJobWebSocketOptions {
  /** Maximum number of log lines to keep */
  maxLogLines?: number;
  /** Auto-connect on mount */
  autoConnect?: boolean;
  /** Callback for status updates */
  onStatus?: (message: WSStatusMessage) => void;
  /** Callback for progress updates */
  onProgress?: (message: WSProgressMessage) => void;
  /** Callback for log messages */
  onLog?: (message: WSLogMessage) => void;
  /** Callback for errors */
  onError?: (error: Error) => void;
  /** Callback for connection state changes */
  onStateChange?: (state: ConnectionState) => void;
}

/**
 * Hook for subscribing to job progress and logs via WebSocket
 */
export function useJobWebSocket(
  jobId: string | null | undefined,
  options: UseJobWebSocketOptions = {}
) {
  const {
    maxLogLines = 1000,
    autoConnect = true,
    onStatus,
    onProgress,
    onLog,
    onError,
    onStateChange,
  } = options;

  const wsRef = useRef<WebSocketClient | null>(null);
  const currentJobIdRef = useRef<string | null>(jobId ?? null);
  const { updateJob, markCompleted } = useUpdateJobFromWS();

  const [state, setState] = useState<JobWebSocketState>({
    connectionState: ConnectionState.DISCONNECTED,
    progress: 0,
    logs: [],
    error: null,
    isConnected: false,
  });

  useEffect(() => {
    currentJobIdRef.current = jobId ?? null;
  }, [jobId]);

  // Handle status messages
  const handleStatus: MessageHandler<WSStatusMessage> = useCallback(
    (message) => {
      setState((prev) => ({
        ...prev,
        progress: message.progress,
        error: message.error ?? null,
      }));

      // Update job in React Query cache
      if (jobId) {
        updateJob(jobId, {
          status: message.status as "RUNNING" | "COMPLETED" | "FAILED",
          progress_percent: message.progress,
          status_message: message.message ?? null,
          error_message: message.error ?? null,
        });

        // Trigger refetch if job completed
        if (message.status === "COMPLETED" || message.status === "FAILED") {
          markCompleted(jobId);
        }
      }

      onStatus?.(message);
    },
    [jobId, updateJob, markCompleted, onStatus]
  );

  // Handle progress messages
  const handleProgress: MessageHandler<WSProgressMessage> = useCallback(
    (message) => {
      if (
        message.job_id &&
        currentJobIdRef.current &&
        message.job_id !== currentJobIdRef.current
      ) {
        return;
      }
      setState((prev) => ({
        ...prev,
        progress: message.percent,
      }));

      // Update job in React Query cache
      if (jobId) {
        updateJob(jobId, {
          progress_percent: message.percent,
        });
      }

      onProgress?.(message);
    },
    [jobId, updateJob, onProgress]
  );

  // Handle log messages
  const handleLog: MessageHandler<WSLogMessage> = useCallback(
    (message) => {
      if (
        message.job_id &&
        currentJobIdRef.current &&
        message.job_id !== currentJobIdRef.current
      ) {
        return;
      }
      setState((prev) => {
        const newLogs = [...prev.logs, message.line];
        // Keep only last maxLogLines
        if (newLogs.length > maxLogLines) {
          newLogs.splice(0, newLogs.length - maxLogLines);
        }
        return { ...prev, logs: newLogs };
      });

      onLog?.(message);
    },
    [maxLogLines, onLog]
  );

  const handleConnected: MessageHandler<{ type: "connected"; job_id: string }> =
    useCallback((message) => {
      // Reset logs on (re)connect so server tail replay doesn't duplicate in the UI.
      if (currentJobIdRef.current && message.job_id !== currentJobIdRef.current) {
        return;
      }
      setState((prev) => ({
        ...prev,
        logs: [],
        error: null,
        progress: 0,
      }));
    }, []);

  // Handle connection state changes
  const handleStateChange = useCallback(
    (connectionState: ConnectionState) => {
      setState((prev) => ({
        ...prev,
        connectionState,
        isConnected: connectionState === ConnectionState.CONNECTED,
      }));

      onStateChange?.(connectionState);
    },
    [onStateChange]
  );

  // Handle errors
  const handleError = useCallback(
    (error: Error) => {
      setState((prev) => ({
        ...prev,
        error: error.message,
      }));

      onError?.(error);
    },
    [onError]
  );

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!jobId || wsRef.current) return;

    const wsUrl = `${WS_URL}/jobs/ws/${jobId}`;
    const ws = new WebSocketClient(wsUrl, {
      reconnectDelay: 1000,
      maxReconnectAttempts: 10,
      bufferFlushInterval: 100,
      onStateChange: handleStateChange,
      onError: handleError,
    });

    // Subscribe to message types
    ws.subscribe("connected", handleConnected);
    ws.subscribe("status", handleStatus);
    ws.subscribe("progress", handleProgress);
    ws.subscribe("log", handleLog);

    ws.connect();
    wsRef.current = ws;
  }, [
    jobId,
    handleStateChange,
    handleError,
    handleConnected,
    handleStatus,
    handleProgress,
    handleLog,
  ]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.disconnect();
      wsRef.current = null;
    }
  }, []);

  // Clear logs
  const clearLogs = useCallback(() => {
    setState((prev) => ({ ...prev, logs: [] }));
  }, []);

  // Effect for auto-connect and cleanup
  useEffect(() => {
    if (jobId && autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [jobId, autoConnect, connect, disconnect]);

  return {
    ...state,
    connect,
    disconnect,
    clearLogs,
  };
}

/**
 * Hook for subscribing to multiple jobs
 */
export function useMultiJobWebSocket(
  jobIds: string[],
  options: Omit<UseJobWebSocketOptions, "onStatus" | "onProgress" | "onLog"> & {
    onJobStatus?: (jobId: string, message: WSStatusMessage) => void;
    onJobProgress?: (jobId: string, message: WSProgressMessage) => void;
    onJobLog?: (jobId: string, message: WSLogMessage) => void;
  } = {}
) {
  const wsMap = useRef<Map<string, WebSocketClient>>(new Map());
  const { updateJob, markCompleted } = useUpdateJobFromWS();

  const [jobStates, setJobStates] = useState<
    Map<string, { progress: number; status: string | null; message: string | null }>
  >(new Map());

  // Connect to a specific job
  const connectToJob = useCallback(
    (jobId: string) => {
      if (wsMap.current.has(jobId)) return;

      const wsUrl = `${WS_URL}/jobs/ws/${jobId}`;
      const ws = new WebSocketClient(wsUrl, {
        reconnectDelay: 1000,
        maxReconnectAttempts: 5,
      });

      ws.subscribe("status", (msg: WSStatusMessage) => {
        setJobStates((prev) => {
          const newMap = new Map(prev);
          newMap.set(jobId, { progress: msg.progress, status: msg.status, message: msg.message ?? null });
          return newMap;
        });

        updateJob(jobId, {
          status: msg.status as "RUNNING" | "COMPLETED" | "FAILED",
          progress_percent: msg.progress,
          status_message: msg.message ?? null,
        });

        if (msg.status === "COMPLETED" || msg.status === "FAILED") {
          markCompleted(jobId);
        }

        options.onJobStatus?.(jobId, msg);
      });

      ws.subscribe("progress", (msg: WSProgressMessage) => {
        setJobStates((prev) => {
          const newMap = new Map(prev);
          const current = prev.get(jobId) ?? { progress: 0, status: null, message: null };
          newMap.set(jobId, { ...current, progress: msg.percent });
          return newMap;
        });

        updateJob(jobId, { progress_percent: msg.percent });
        options.onJobProgress?.(jobId, msg);
      });

      ws.subscribe("log", (msg: WSLogMessage) => {
        options.onJobLog?.(jobId, msg);
      });

      ws.connect();
      wsMap.current.set(jobId, ws);
    },
    [updateJob, markCompleted, options]
  );

  // Disconnect from a specific job
  const disconnectFromJob = useCallback((jobId: string) => {
    const ws = wsMap.current.get(jobId);
    if (ws) {
      ws.disconnect();
      wsMap.current.delete(jobId);
    }
  }, []);

  // Disconnect from all jobs
  const disconnectAll = useCallback(() => {
    wsMap.current.forEach((ws) => ws.disconnect());
    wsMap.current.clear();
  }, []);

  // Effect to manage connections based on jobIds
  useEffect(() => {
    // Connect to new jobs
    for (const jobId of jobIds) {
      connectToJob(jobId);
    }

    // Disconnect from removed jobs
    wsMap.current.forEach((_, existingId) => {
      if (!jobIds.includes(existingId)) {
        disconnectFromJob(existingId);
      }
    });

    return () => {
      disconnectAll();
    };
  }, [jobIds, connectToJob, disconnectFromJob, disconnectAll]);

  return {
    jobStates,
    connectToJob,
    disconnectFromJob,
    disconnectAll,
  };
}
