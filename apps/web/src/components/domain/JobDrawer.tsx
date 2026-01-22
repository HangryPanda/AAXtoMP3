/**
 * JobDrawer component for displaying active and recent jobs
 */
import * as React from "react";
import {
  Download,
  FileAudio,
  RefreshCw,
  Wrench,
  X,
  FileText,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Progress } from "@/components/ui/Progress";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import {
  type Job,
  type JobStatus,
  type JobType,
  isJobActive,
  canCancelJob,
  getJobDuration,
} from "@/types";

const JOB_TYPE_ICONS: Record<JobType, React.ElementType> = {
  DOWNLOAD: Download,
  CONVERT: FileAudio,
  SYNC: RefreshCw,
  REPAIR: Wrench,
};

const STATUS_BADGE_VARIANTS: Record<JobStatus, "default" | "secondary" | "destructive" | "success" | "warning" | "info"> = {
  PENDING: "secondary",
  QUEUED: "info",
  RUNNING: "warning",
  COMPLETED: "success",
  FAILED: "destructive",
  CANCELLED: "secondary",
};

export interface JobDrawerProps {
  open: boolean;
  jobs: Job[];
  onClose?: () => void;
  onCancelJob?: (job: Job) => void;
  onViewLogs?: (job: Job) => void;
  className?: string;
}

export function JobDrawer({
  open,
  jobs,
  onClose,
  onCancelJob,
  onViewLogs,
  className,
}: JobDrawerProps) {
  const handleEscapeKey = React.useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose?.();
      }
    },
    [onClose]
  );

  React.useEffect(() => {
    if (open) {
      document.addEventListener("keydown", handleEscapeKey);
      return () => document.removeEventListener("keydown", handleEscapeKey);
    }
  }, [open, handleEscapeKey]);

  if (!open) return null;

  const activeJobs = jobs.filter(isJobActive);
  const completedJobs = jobs.filter((job) => !isJobActive(job));

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose?.()}>
      <DialogContent className={cn("max-w-md", className)}>
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between">
            <span>Jobs</span>
            {activeJobs.length > 0 && (
              <Badge variant="info">{activeJobs.length} active</Badge>
            )}
          </DialogTitle>
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-4 top-4"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </DialogHeader>

        <div className="max-h-[60vh] overflow-y-auto">
          {jobs.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-muted-foreground">
              No jobs
            </div>
          ) : (
            <div className="space-y-4">
              {/* Active Jobs */}
              {activeJobs.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                    Active
                  </h3>
                  <div className="space-y-2">
                    {activeJobs.map((job) => (
                      <JobItem
                        key={job.id}
                        job={job}
                        onCancel={onCancelJob}
                        onViewLogs={onViewLogs}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Completed Jobs */}
              {completedJobs.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                    Completed
                  </h3>
                  <div className="space-y-2">
                    {completedJobs.map((job) => (
                      <JobItem
                        key={job.id}
                        job={job}
                        onCancel={onCancelJob}
                        onViewLogs={onViewLogs}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface JobItemProps {
  job: Job;
  onCancel?: (job: Job) => void;
  onViewLogs?: (job: Job) => void;
}

function JobItem({ job, onCancel, onViewLogs }: JobItemProps) {
  const Icon = JOB_TYPE_ICONS[job.task_type];
  const isActive = isJobActive(job);
  const canCancel = canCancelJob(job);
  const duration = getJobDuration(job);

  return (
    <div className="rounded-lg border p-3">
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
            isActive ? "bg-primary/10" : "bg-muted"
          )}
        >
          <Icon
            className={cn(
              "h-4 w-4",
              isActive && "animate-pulse text-primary"
            )}
          />
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-sm font-medium">
              {job.task_type}
            </span>
            <Badge variant={STATUS_BADGE_VARIANTS[job.status]} className="shrink-0">
              {job.status.toLowerCase()}
            </Badge>
          </div>

          <p className="truncate text-xs text-muted-foreground">
            {job.id}
          </p>

          {/* Progress for running jobs */}
          {job.status === "RUNNING" && (
            <div className="mt-2">
              <Progress value={job.progress_percent} className="h-1" />
              <span className="text-xs text-muted-foreground">
                {job.progress_percent}%
              </span>
            </div>
          )}

          {/* Duration for completed jobs */}
          {duration && !isActive && (
            <p className="mt-1 text-xs text-muted-foreground">
              Duration: {duration}
            </p>
          )}

          {/* Error message */}
          {job.error_message && (
            <p className="mt-1 text-xs text-destructive">
              {job.error_message}
            </p>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="mt-2 flex justify-end gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onViewLogs?.(job)}
          aria-label="View logs"
        >
          <FileText className="mr-1 h-3 w-3" />
          Logs
        </Button>

        {canCancel && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onCancel?.(job)}
            aria-label="Cancel job"
            className="text-destructive hover:text-destructive"
          >
            <XCircle className="mr-1 h-3 w-3" />
            Cancel
          </Button>
        )}
      </div>
    </div>
  );
}
