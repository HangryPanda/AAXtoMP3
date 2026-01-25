/**
 * Global jobs WebSocket feed hook.
 *
 * Subscribes to /jobs/ws and updates React Query caches so the UI can avoid polling.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { WebSocketClient, ConnectionState } from "@/services/websocket";
import { WS_URL } from "@/lib/env";
import type { Job, JobListResponse, WSBatchMessage, WSStatusMessage } from "@/types";
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

  const applyStatusToJob = useCallback(
    (existing: Job | undefined, msg: WSStatusMessage): Job => {
      return {
        id: msg.job_id,
        // Use task_type/book_asin from WebSocket message if provided, otherwise fall back to existing
        task_type: (msg.task_type ?? existing?.task_type ?? "SYNC") as Job["task_type"],
        book_asin: msg.book_asin !== undefined ? msg.book_asin : (existing?.book_asin ?? null),
        status: msg.status as Job["status"],
        progress_percent: msg.progress,
        status_message: msg.message ?? existing?.status_message ?? null,
        download_bytes_current: msg.meta?.download_bytes_current ?? existing?.download_bytes_current,
        download_bytes_total: msg.meta?.download_bytes_total ?? existing?.download_bytes_total,
        download_bytes_per_sec: msg.meta?.download_bytes_per_sec ?? existing?.download_bytes_per_sec,
        log_file_path: existing?.log_file_path ?? null,
        error_message: msg.error ?? existing?.error_message ?? null,
        updated_at: msg.updated_at ?? existing?.updated_at,
        started_at: existing?.started_at ?? null,
        completed_at: existing?.completed_at ?? null,
        created_at: existing?.created_at ?? new Date().toISOString(),
        // Retry tracking fields
        attempt: msg.attempt ?? existing?.attempt ?? 1,
        original_job_id: msg.original_job_id !== undefined ? msg.original_job_id : (existing?.original_job_id ?? null),
      };
    },
    []
  );

  const handleBatch = useCallback(
    (batch: WSBatchMessage) => {
      // Treat batch as an authoritative snapshot of active jobs at connect time.
      const statuses = batch.messages.filter(
        (m): m is WSStatusMessage => m.type === "status"
      );

      queryClient.setQueryData<JobListResponse>(jobKeys.active(), (old) => {
        const existingById = new Map((old?.items ?? []).map((j) => [j.id, j]));
        const nextItems: Job[] = [];

        for (const msg of statuses) {
          const existing = existingById.get(msg.job_id);
          const nextJob = applyStatusToJob(existing, msg);
          if (isJobActive(nextJob)) nextItems.push(nextJob);
        }

        // If the client had cached active jobs that are not in the server snapshot, drop them.
        // This avoids "dead-but-still-running" UI after API restarts or reconnects.
        // (We intentionally do not preserve unknown jobs that are missing from the snapshot.)
        return { items: nextItems, total: nextItems.length };
      });
    },
    [applyStatusToJob, queryClient]
  );

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
                  status_message: msg.message ?? j.status_message,
                  download_bytes_current: msg.meta?.download_bytes_current ?? j.download_bytes_current,
                  download_bytes_total: msg.meta?.download_bytes_total ?? j.download_bytes_total,
                  download_bytes_per_sec: msg.meta?.download_bytes_per_sec ?? j.download_bytes_per_sec,
                  error_message: msg.error ?? j.error_message,
                  updated_at: msg.updated_at ?? j.updated_at,
                  // Update task_type and book_asin if provided in message
                  task_type: (msg.task_type ?? j.task_type) as Job["task_type"],
                  book_asin: msg.book_asin !== undefined ? msg.book_asin : j.book_asin,
                  // Retry tracking fields
                  attempt: msg.attempt ?? j.attempt,
                  original_job_id: msg.original_job_id !== undefined ? msg.original_job_id : j.original_job_id,
                }
              : j
          ),
        };
      });

      // Maintain the active jobs cache so components can use useActiveJobs without polling.
      queryClient.setQueryData<JobListResponse>(jobKeys.active(), (old) => {
        const existing = old?.items.find((j) => j.id === jobId);
        const next = applyStatusToJob(existing, msg);

        if (isJobActive(next)) {
          return upsertJob(old, next);
        }
        return removeJob(old, jobId);
      });
    },
    [applyStatusToJob, queryClient]
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
    ws.subscribe("batch", handleBatch);
    ws.subscribe("status", handleStatus);
    ws.connect();
    wsRef.current = ws;
  }, [handleBatch, handleStatus]);

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
