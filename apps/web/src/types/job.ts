/**
 * Job-related type definitions
 */

export type JobType = "DOWNLOAD" | "CONVERT" | "SYNC" | "REPAIR";

export type JobStatus =
  | "PENDING"
  | "QUEUED"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export interface Job {
  id: string;
  task_type: JobType;
  book_asin: string | null;
  status: JobStatus;
  progress_percent: number;
  status_message: string | null;
  log_file_path: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface JobLogEntry {
  timestamp: string;
  line: string;
  level?: "info" | "warn" | "error";
}

export interface CreateDownloadJobRequest {
  asin?: string;
  asins?: string[];
}

export interface CreateConvertJobRequest {
  asin: string;
  format?: string;
  naming_scheme?: string;
}

export interface JobCreateResponse {
  job_id: string;
  status: JobStatus;
  message: string;
}

export interface QueuedJobResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface JobListResponse {
  items: Job[];
  total: number;
}

// Job status colors for UI
export const JOB_STATUS_COLORS: Record<JobStatus, string> = {
  PENDING: "gray",
  QUEUED: "blue",
  RUNNING: "yellow",
  COMPLETED: "green",
  FAILED: "red",
  CANCELLED: "gray",
};

// Job type icons
export const JOB_TYPE_ICONS: Record<JobType, string> = {
  DOWNLOAD: "download",
  CONVERT: "file-audio",
  SYNC: "refresh-cw",
  REPAIR: "wrench",
};

// Helper to check if job is active (running or pending)
export function isJobActive(job: Job): boolean {
  return (
    job.status === "PENDING" ||
    job.status === "QUEUED" ||
    job.status === "RUNNING"
  );
}

// Helper to check if job can be cancelled
export function canCancelJob(job: Job): boolean {
  return isJobActive(job);
}

// Helper to format job duration
export function getJobDuration(job: Job): string | null {
  if (!job.started_at) return null;

  const start = new Date(job.started_at);
  const end = job.completed_at ? new Date(job.completed_at) : new Date();
  const durationMs = end.getTime() - start.getTime();

  const seconds = Math.floor(durationMs / 1000);
  if (seconds < 60) return `${seconds}s`;

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}
