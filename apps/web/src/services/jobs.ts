/**
 * Jobs Service
 * API functions for managing download and conversion jobs
 */

import { apiRequest } from "./api";
import type {
  Job,
  JobType,
  JobStatus,
  JobCreateResponse,
  BatchJobCreateResponse,
  JobListResponse,
  CreateDownloadJobRequest,
  CreateConvertJobRequest,
  Settings,
} from "@/types";

/**
 * Get list of jobs with optional status filtering
 */
export async function getJobs(status?: JobStatus): Promise<JobListResponse> {
  return apiRequest<JobListResponse>({
    method: "GET",
    url: "/jobs",
    params: status ? { status } : undefined,
  });
}

export async function getJobsFiltered(params?: {
  status?: JobStatus;
  task_type?: JobType;
  limit?: number;
}): Promise<JobListResponse> {
  return apiRequest<JobListResponse>({
    method: "GET",
    url: "/jobs",
    params: params && Object.keys(params).length > 0 ? params : undefined,
  });
}

/**
 * Get a single job by ID
 */
export async function getJob(jobId: string): Promise<Job> {
  return apiRequest<Job>({
    method: "GET",
    url: `/jobs/${jobId}`,
  });
}

/**
 * Create a download job for one or more books
 */
export async function createDownloadJob(
  asins: string | string[]
): Promise<JobCreateResponse | BatchJobCreateResponse> {
  const request: CreateDownloadJobRequest = Array.isArray(asins)
    ? { asins }
    : { asin: asins };

  return apiRequest<JobCreateResponse | BatchJobCreateResponse>({
    method: "POST",
    url: "/jobs/download",
    data: request,
  });
}

/**
 * Create a conversion job for a book
 */
export async function createConvertJob(
  asin: string,
  settings?: Partial<Pick<Settings, "output_format" | "dir_naming_scheme" | "file_naming_scheme">>
): Promise<JobCreateResponse> {
  const request: CreateConvertJobRequest = {
    asin,
    format: settings?.output_format,
    naming_scheme: settings?.dir_naming_scheme,
  };

  return apiRequest<JobCreateResponse>({
    method: "POST",
    url: "/jobs/convert",
    data: request,
  });
}

/**
 * Cancel an active job
 */
export async function cancelJob(jobId: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>({
    method: "DELETE",
    url: `/jobs/${jobId}`,
  });
}

/**
 * Retry a job by id (supports batch download jobs)
 */
export async function retryJob(jobId: string): Promise<{ job_id: string; status: string; message: string }> {
  return apiRequest<{ job_id: string; status: string; message: string }>({
    method: "POST",
    url: `/jobs/${jobId}/retry`,
  });
}

export async function pauseJob(jobId: string): Promise<{ status: string; message: string }> {
  return apiRequest<{ status: string; message: string }>({
    method: "POST",
    url: `/jobs/${jobId}/pause`,
  });
}

export async function resumeJob(jobId: string): Promise<{ status: string; message: string }> {
  return apiRequest<{ status: string; message: string }>({
    method: "POST",
    url: `/jobs/${jobId}/resume`,
  });
}

/**
 * Clear job history (completed/failed/cancelled) with optional log deletion.
 */
export async function clearJobHistory(params?: {
  status?: string;
  older_than?: string;
  delete_logs?: boolean;
}): Promise<{ deleted: number; message: string }> {
  return apiRequest<{ deleted: number; message: string }>({
    method: "DELETE",
    url: "/jobs/history",
    params: params && Object.keys(params).length > 0 ? params : undefined,
  });
}

/**
 * Get all active jobs (running, pending, queued)
 */
export async function getActiveJobs(): Promise<JobListResponse> {
  return getJobs("RUNNING,PENDING,QUEUED,PAUSED" as JobStatus);
}

/**
 * Get completed jobs
 */
export async function getCompletedJobs(): Promise<JobListResponse> {
  return getJobs("COMPLETED");
}

/**
 * Get failed jobs
 */
export async function getFailedJobs(): Promise<JobListResponse> {
  return getJobs("FAILED");
}
