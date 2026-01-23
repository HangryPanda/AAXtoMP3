/**
 * Global jobs WebSocket feed hook.
 *
 * Subscribes to /jobs/ws and updates React Query caches so the UI can avoid polling.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { WebSocketClient, ConnectionState } from "@/services/websocket";
import { WS_URL } from "@/lib/env";
import type { Job, JobListResponse, WSStatusMessage } from "@/types";
import { isJobActive } from "@/types";
import { jobKeys } from "./useJobs";

function upsertJob(list: JobListResponse | undefined, job: Job): JobListResponse {
  const items = list?.items ?? [];
  const existingIdx = items.findIndex((j) => j.id === job.id);
  const nextItems =
    existingIdx >= 0
      ? items.map((j) => (j.id === job.id ? { ...j, ...job } : j))
      : [job, ...items];
  return { items: nextItems, total: nextItems.length };
}

function removeJob(list: JobListResponse | undefined, jobId: string): JobListResponse | undefined {
  if (!list) return list;
  const nextItems = list.items.filter((j) => j.id !== jobId);
  return { items: nextItems, total: nextItems.length };
}

export function useJobsFeedWebSocket() {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocketClient | null>(null);
  const [state, setState] = useState<ConnectionState>(ConnectionState.DISCONNECTED);

  const handleStatus = useCallback(
    (msg: WSStatusMessage) => {
      const jobId = msg.job_id;

      // Update any list/detail caches that already contain the job.
      queryClient.setQueriesData<JobListResponse>({ queryKey: jobKeys.lists() }, (old) => {
        if (!old) return old;
        return {
          ...old,
          items: old.items.map((j) =>
            j.id === jobId
              ? {
                  ...j,
                  status: msg.status as Job["status"],
                  progress_percent: msg.progress,
                  error_message: msg.error ?? j.error_message,
                }
              : j
          ),
        };
      });

      // Maintain the active jobs cache so components can use useActiveJobs without polling.
      queryClient.setQueryData<JobListResponse>(jobKeys.active(), (old) => {
        const existing = old?.items.find((j) => j.id === jobId);
        const next: Job = {
          id: jobId,
          task_type: (existing?.task_type ?? "SYNC") as Job["task_type"],
          book_asin: existing?.book_asin ?? null,
          status: msg.status as Job["status"],
          progress_percent: msg.progress,
          log_file_path: existing?.log_file_path ?? null,
          error_message: msg.error ?? existing?.error_message ?? null,
          started_at: existing?.started_at ?? null,
          completed_at: existing?.completed_at ?? null,
          created_at: existing?.created_at ?? new Date().toISOString(),
        } as Job;

        if (isJobActive(next)) {
          return upsertJob(old, next);
        }
        return removeJob(old, jobId);
      });
    },
    [queryClient]
  );

  const connect = useCallback(() => {
    if (wsRef.current) return;
    const ws = new WebSocketClient(`${WS_URL}/jobs/ws`, {
      reconnectDelay: 1000,
      maxReconnectAttempts: 10,
      bufferFlushInterval: 100,
      onStateChange: setState,
      onError: () => setState(ConnectionState.FAILED),
    });
    ws.subscribe("status", handleStatus);
    ws.connect();
    wsRef.current = ws;
  }, [handleStatus]);

  const disconnect = useCallback(() => {
    wsRef.current?.disconnect();
    wsRef.current = null;
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { connectionState: state, isConnected: state === ConnectionState.CONNECTED };
}
