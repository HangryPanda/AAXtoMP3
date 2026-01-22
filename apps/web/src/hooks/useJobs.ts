/**
 * useJobs Hook
 * React Query hook for managing jobs with optimistic updates
 */

import { useCallback, useMemo } from "react";
import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import {
  getJobs,
  getJobsFiltered,
  getJob,
  createDownloadJob,
  createConvertJob,
  cancelJob,
  getActiveJobs,
} from "@/services/jobs";
import type {
  Job,
  JobStatus,
  JobCreateResponse,
  JobListResponse,
  JobType,
  Settings,
} from "@/types";
import { bookKeys } from "./useBooks";

/**
 * Query keys for jobs
 */
export const jobKeys = {
  all: ["jobs"] as const,
  lists: () => [...jobKeys.all, "list"] as const,
  list: (status?: JobStatus) => [...jobKeys.lists(), { status }] as const,
  filtered: (params?: { status?: JobStatus; task_type?: JobType; limit?: number }) =>
    [...jobKeys.lists(), { ...params }] as const,
  active: () => [...jobKeys.lists(), "active"] as const,
  details: () => [...jobKeys.all, "detail"] as const,
  detail: (id: string) => [...jobKeys.details(), id] as const,
};

/**
 * Hook for fetching jobs list
 */
export function useJobs(
  status?: JobStatus,
  options?: Omit<UseQueryOptions<JobListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: jobKeys.list(status),
    queryFn: () => getJobs(status),
    // Jobs change frequently, shorter stale time
    staleTime: 10 * 1000, // 10 seconds
    ...options,
  });
}

export function useJobsFiltered(
  params?: { status?: JobStatus; task_type?: JobType; limit?: number },
  options?: Omit<UseQueryOptions<JobListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: jobKeys.filtered(params),
    queryFn: () => getJobsFiltered(params),
    staleTime: 5 * 1000,
    ...options,
  });
}

/**
 * Hook for fetching active jobs (running, pending, queued)
 */
export function useActiveJobs(
  options?: Omit<UseQueryOptions<JobListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: jobKeys.active(),
    queryFn: getActiveJobs,
    // We rely on WebSockets for real-time updates
    staleTime: 10000,
    ...options,
  });
}

/**
 * Hook for fetching a single job
 */
export function useJob(
  jobId: string | null | undefined,
  options?: Omit<UseQueryOptions<Job | null>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: jobId ? jobKeys.detail(jobId) : ["disabled"],
    queryFn: async () => {
      if (!jobId) return null;
      return getJob(jobId);
    },
    enabled: !!jobId,
    staleTime: 5000,
    ...options,
  });
}

/**
 * Hook for creating download jobs with optimistic updates
 */
export function useCreateDownloadJob() {
  const queryClient = useQueryClient();

  return useMutation<JobCreateResponse, Error, string | string[], { previousJobs: JobListResponse | undefined }>({
    mutationFn: (asins) => createDownloadJob(asins),
    onMutate: async (asins) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: jobKeys.active() });

      // Snapshot the previous value
      const previousJobs = queryClient.getQueryData<JobListResponse>(
        jobKeys.active()
      );

      // Optimistically add a pending job
      const tempJob: Job = {
        id: `temp-${Date.now()}`,
        task_type: "DOWNLOAD",
        book_asin: Array.isArray(asins) ? asins[0] : asins,
        status: "PENDING",
        progress_percent: 0,
        log_file_path: null,
        error_message: null,
        started_at: null,
        completed_at: null,
        created_at: new Date().toISOString(),
      };

      queryClient.setQueryData<JobListResponse>(jobKeys.active(), (old) => ({
        items: [...(old?.items ?? []), tempJob],
        total: (old?.total ?? 0) + 1,
      }));

      return { previousJobs };
    },
    onError: (_err, _vars, context) => {
      // Rollback on error
      if (context?.previousJobs) {
        queryClient.setQueryData(jobKeys.active(), context.previousJobs);
      }
    },
    onSettled: () => {
      // Refetch to sync with server
      queryClient.invalidateQueries({ queryKey: jobKeys.lists() });
    },
  });
}

/**
 * Hook for creating convert jobs with optimistic updates
 */
export function useCreateConvertJob() {
  const queryClient = useQueryClient();

  return useMutation<
    JobCreateResponse,
    Error,
    {
      asin: string;
      settings?: Partial<Pick<Settings, "output_format" | "dir_naming_scheme" | "file_naming_scheme">>;
    },
    { previousJobs: JobListResponse | undefined }
  >({
    mutationFn: ({ asin, settings }) => createConvertJob(asin, settings),
    onMutate: async ({ asin }) => {
      await queryClient.cancelQueries({ queryKey: jobKeys.active() });

      const previousJobs = queryClient.getQueryData<JobListResponse>(
        jobKeys.active()
      );

      // Optimistically add a pending job
      const tempJob: Job = {
        id: `temp-${Date.now()}`,
        task_type: "CONVERT",
        book_asin: asin,
        status: "PENDING",
        progress_percent: 0,
        log_file_path: null,
        error_message: null,
        started_at: null,
        completed_at: null,
        created_at: new Date().toISOString(),
      };

      queryClient.setQueryData<JobListResponse>(jobKeys.active(), (old) => ({
        items: [...(old?.items ?? []), tempJob],
        total: (old?.total ?? 0) + 1,
      }));

      return { previousJobs };
    },
    onError: (_err, _vars, context) => {
      if (context?.previousJobs) {
        queryClient.setQueryData(jobKeys.active(), context.previousJobs);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: jobKeys.lists() });
    },
  });
}

/**
 * Hook for cancelling jobs with optimistic updates
 */
export function useCancelJob() {
  const queryClient = useQueryClient();

  return useMutation<{ message: string }, Error, string, { previousJobs: JobListResponse | undefined }>({
    mutationFn: (jobId) => cancelJob(jobId),
    onMutate: async (jobId) => {
      await queryClient.cancelQueries({ queryKey: jobKeys.active() });

      const previousJobs = queryClient.getQueryData<JobListResponse>(
        jobKeys.active()
      );

      // Optimistically update job status to CANCELLED
      queryClient.setQueryData<JobListResponse>(jobKeys.active(), (old) => ({
        items:
          old?.items.map((job) =>
            job.id === jobId ? { ...job, status: "CANCELLED" as JobStatus } : job
          ) ?? [],
        total: old?.total ?? 0,
      }));

      return { previousJobs };
    },
    onError: (_err, _vars, context) => {
      if (context?.previousJobs) {
        queryClient.setQueryData(jobKeys.active(), context.previousJobs);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: jobKeys.lists() });
      // Also invalidate books since job completion may change book status
      queryClient.invalidateQueries({ queryKey: bookKeys.all });
    },
  });
}

/**
 * Hook to update job in cache from WebSocket updates
 */
export function useUpdateJobFromWS() {
  const queryClient = useQueryClient();

  const updateJob = useCallback((jobId: string, updates: Partial<Job>) => {
    // Update in lists
    queryClient.setQueriesData<JobListResponse>(
      { queryKey: jobKeys.lists() },
      (old) => {
        if (!old) return old;
        return {
          ...old,
          items: old.items.map((job) =>
            job.id === jobId ? { ...job, ...updates } : job
          ),
        };
      }
    );

    // Update in detail cache
    queryClient.setQueryData<Job>(jobKeys.detail(jobId), (old) => {
      if (!old) return old;
      return { ...old, ...updates };
    });
  }, [queryClient]);

  const markCompleted = useCallback((jobId: string) => {
    queryClient.invalidateQueries({ queryKey: jobKeys.detail(jobId) });
    queryClient.invalidateQueries({ queryKey: jobKeys.lists() });
    queryClient.invalidateQueries({ queryKey: bookKeys.all });
  }, [queryClient]);

  return useMemo(() => ({ updateJob, markCompleted }), [updateJob, markCompleted]);
}

/**
 * Hook to check if there are any active jobs for a book
 */
export function useBookActiveJobs(asin: string | null | undefined) {
  const { data } = useActiveJobs();

  if (!asin || !data) {
    return { hasActiveJob: false, activeJob: null };
  }

  const activeJob = data.items.find((job) => job.book_asin === asin);

  return {
    hasActiveJob: !!activeJob,
    activeJob: activeJob ?? null,
  };
}
