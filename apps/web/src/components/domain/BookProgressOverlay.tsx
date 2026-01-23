/**
 * BookProgressOverlay
 * Displays download/convert progress directly on book cards.
 * Handles PENDING, QUEUED, and RUNNING states with appropriate UI.
 */

"use client";

import * as React from "react";
import { X, Clock, Loader2, Download, FileAudio } from "lucide-react";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/Progress";
import { useBookActiveJobs, useActiveJobs, useCancelJob } from "@/hooks/useJobs";
import { useProgressStats } from "@/hooks/useProgressStats";
import type { JobType, JobStatus } from "@/types";

interface BookProgressOverlayProps {
  asin: string;
  className?: string;
}

// Icons for job types
const JOB_TYPE_ICONS: Record<JobType, React.ElementType> = {
  DOWNLOAD: Download,
  CONVERT: FileAudio,
  SYNC: Loader2,
  REPAIR: Loader2,
};

/**
 * Hook to get dimmed state for a book card based on job status
 */
export function useBookDimmedState(asin: string): boolean {
  const { activeJob } = useBookActiveJobs(asin);
  return activeJob?.status === "PENDING" || activeJob?.status === "QUEUED";
}

/**
 * BookProgressOverlay component
 * Renders an overlay on book cards showing download/convert progress.
 */
export function BookProgressOverlay({ asin, className }: BookProgressOverlayProps) {
  const { activeJob } = useBookActiveJobs(asin);
  const { data: activeJobsData } = useActiveJobs();
  const { mutate: cancelJob, isPending: isCancelling } = useCancelJob();

  // Calculate progress stats only when job is RUNNING
  const isRunning = activeJob?.status === "RUNNING";
  const { speedDisplay, etaDisplay } = useProgressStats(
    activeJob?.progress_percent ?? 0,
    isRunning
  );

  // Calculate queue position for QUEUED jobs
  const queueInfo = React.useMemo(() => {
    if (!activeJob || activeJob.status !== "QUEUED" || !activeJobsData) {
      return null;
    }

    const queuedJobs = activeJobsData.items
      .filter((j) => j.status === "QUEUED" && j.task_type === activeJob.task_type)
      .sort((a, b) => a.created_at.localeCompare(b.created_at));

    const position = queuedJobs.findIndex((j) => j.id === activeJob.id) + 1;
    const total = queuedJobs.length;

    return { position, total };
  }, [activeJob, activeJobsData]);

  // Handle cancel button click
  const handleCancel = React.useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      if (activeJob && !isCancelling) {
        cancelJob(activeJob.id);
      }
    },
    [activeJob, cancelJob, isCancelling]
  );

  // Don't render if no active job
  if (!activeJob) {
    return null;
  }

  const status = activeJob.status;
  const JobIcon = JOB_TYPE_ICONS[activeJob.task_type];

  return (
    <div
      className={cn(
        "absolute inset-x-0 bottom-0 z-10 pointer-events-auto",
        className
      )}
      onClick={(e) => e.stopPropagation()}
    >
      {/* RUNNING State - Full progress display */}
      {status === "RUNNING" && (
        <div className="bg-gradient-to-t from-black/90 via-black/70 to-transparent pt-8 pb-3 px-3">
          {/* Status message */}
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              <JobIcon className="h-3.5 w-3.5 text-primary shrink-0 animate-pulse" />
              <span className="text-[11px] font-medium text-white/90 truncate">
                {activeJob.status_message || `${activeJob.task_type}...`}
              </span>
            </div>
            <button
              onClick={handleCancel}
              disabled={isCancelling}
              className="p-1 rounded-sm hover:bg-white/20 transition-colors shrink-0 ml-1"
              aria-label="Cancel"
            >
              <X className={cn("h-3.5 w-3.5 text-white/70", isCancelling && "animate-pulse")} />
            </button>
          </div>

          {/* Progress bar */}
          <Progress value={activeJob.progress_percent} className="h-1.5 mb-1.5" />

          {/* Stats row */}
          <div className="flex items-center justify-between text-[10px] text-white/70">
            <span className="font-semibold text-white">
              {activeJob.progress_percent}%
            </span>
            {/* Hide speed/ETA on small screens */}
            <div className="hidden sm:flex items-center gap-3">
              {speedDisplay && <span>{speedDisplay}</span>}
              <span>ETA: {etaDisplay}</span>
            </div>
            {/* Show just percentage on mobile */}
            <span className="sm:hidden text-white/50">
              {etaDisplay !== "--:--" ? etaDisplay : ""}
            </span>
          </div>
        </div>
      )}

      {/* QUEUED State - Position indicator */}
      {status === "QUEUED" && (
        <div className="bg-gradient-to-t from-black/80 to-transparent pt-4 pb-2 px-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-blue-400" />
              <span className="text-xs font-medium text-white/90">
                Queued
                {queueInfo && (
                  <span className="text-white/60 ml-1">
                    (#{queueInfo.position} of {queueInfo.total})
                  </span>
                )}
              </span>
            </div>
            <button
              onClick={handleCancel}
              disabled={isCancelling}
              className="p-1 rounded-sm hover:bg-white/20 transition-colors"
              aria-label="Remove from queue"
            >
              <X className={cn("h-4 w-4 text-white/70", isCancelling && "animate-pulse")} />
            </button>
          </div>
        </div>
      )}

      {/* PENDING State - Spinner */}
      {status === "PENDING" && (
        <div className="bg-gradient-to-t from-black/80 to-transparent pt-4 pb-2 px-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 text-yellow-400 animate-spin" />
              <span className="text-xs font-medium text-white/90">Pending...</span>
            </div>
            <button
              onClick={handleCancel}
              disabled={isCancelling}
              className="p-1 rounded-sm hover:bg-white/20 transition-colors"
              aria-label="Cancel"
            >
              <X className={cn("h-4 w-4 text-white/70", isCancelling && "animate-pulse")} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Get active job info for a book
 * Useful for determining card dimming/sorting in parent components
 */
export function useBookJobInfo(asin: string) {
  const { activeJob, hasActiveJob } = useBookActiveJobs(asin);

  return {
    hasActiveJob,
    activeJob,
    isDimmed: activeJob?.status === "PENDING" || activeJob?.status === "QUEUED",
    isRunning: activeJob?.status === "RUNNING",
    status: activeJob?.status as JobStatus | undefined,
  };
}
