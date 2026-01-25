/**
 * ActiveJobsView
 *
 * Dedicated view for displaying active downloads or conversions.
 * Provides a focused, progress-centric UI for monitoring jobs.
 */

"use client";

import * as React from "react";
import Image from "next/image";
import {
  Download,
  FileAudio,
  X,
  Clock,
  Loader2,
  Play,
  Pause,
  BookOpen,
} from "lucide-react";
import { useQueries } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Progress } from "@/components/ui/Progress";
import { Card } from "@/components/ui/Card";
import { useActiveJobs, useCancelJob, usePauseJob, useResumeJob } from "@/hooks/useJobs";
import { bookKeys } from "@/hooks/useBooks";
import { getBookDetails } from "@/services/books";
import { useProgressStats } from "@/hooks/useProgressStats";
import { formatMBps } from "@/lib/format";
import type { Job, JobType, Book } from "@/types";
import { getCoverUrl, getPrimaryAuthor, formatRuntime } from "@/types";

type ViewType = "downloading" | "converting";

interface ActiveJobsViewProps {
  type: ViewType;
  onBackToLibrary?: () => void;
  className?: string;
}

const VIEW_CONFIG: Record<ViewType, { taskType: JobType; icon: React.ElementType; title: string; emptyMessage: string }> = {
  downloading: {
    taskType: "DOWNLOAD",
    icon: Download,
    title: "Downloads",
    emptyMessage: "No active downloads",
  },
  converting: {
    taskType: "CONVERT",
    icon: FileAudio,
    title: "Conversions",
    emptyMessage: "No active conversions",
  },
};

/**
 * Individual job card with detailed progress display
 */
function JobCard({ job, book }: { job: Job; book: Book | null }) {
  const { mutate: cancelJob, isPending: isCancelling } = useCancelJob();
  const { mutate: pauseJob, isPending: isPausing } = usePauseJob();
  const { mutate: resumeJob, isPending: isResuming } = useResumeJob();

  const isRunning = job.status === "RUNNING";
  const isPaused = job.status === "PAUSED";
  const isQueued = job.status === "QUEUED";
  const isPending = job.status === "PENDING";

  const { speedDisplay, etaDisplay } = useProgressStats(
    job.progress_percent,
    isRunning
  );

  const coverUrl = book ? getCoverUrl(book) : null;
  const title = book?.title ?? job.book_asin ?? "Unknown";
  const author = book ? getPrimaryAuthor(book) : "";

  const isDownload = job.task_type === "DOWNLOAD";
  const Icon = job.task_type === "DOWNLOAD" ? Download : FileAudio;

  const handleCancel = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isCancelling) {
      cancelJob(job.id);
    }
  };

  const handlePause = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isPausing) {
      pauseJob(job.id);
    }
  };

  const handleResume = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isResuming) {
      resumeJob(job.id);
    }
  };

  return (
    <Card className="p-4 hover:bg-muted/30 transition-colors">
      <div className="flex gap-4">
        {/* Cover Image */}
        <div className="relative w-20 h-20 rounded-md overflow-hidden bg-muted shrink-0">
          {coverUrl ? (
            <Image
              src={coverUrl}
              alt={title}
              fill
              className="object-cover"
              sizes="80px"
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <BookOpen className="h-8 w-8 text-muted-foreground/50" />
            </div>
          )}

          {/* Status icon overlay */}
          <div className="absolute inset-0 flex items-center justify-center bg-black/40">
            {isRunning && <Icon className="h-6 w-6 text-white animate-pulse" />}
            {isPaused && <Pause className="h-6 w-6 text-yellow-400" />}
            {isQueued && <Clock className="h-6 w-6 text-blue-400" />}
            {isPending && <Loader2 className="h-6 w-6 text-white animate-spin" />}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Title & Author */}
          <div className="mb-2">
            <h3 className="font-semibold text-sm truncate" title={title}>
              {title}
            </h3>
            {author && (
              <p className="text-xs text-muted-foreground truncate">{author}</p>
            )}
          </div>

          {/* Progress Section */}
          {isRunning && (
            <div className="space-y-2">
              <Progress value={job.progress_percent} className="h-2" />
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">
                  {job.progress_percent}%
                </span>
                <div className="flex items-center gap-4">
                  {isDownload ? (
                    <span>{formatMBps(job.download_bytes_per_sec) ?? "— MB/s"}</span>
                  ) : speedDisplay ? (
                    <span>{speedDisplay}</span>
                  ) : null}
                  <span>ETA: {etaDisplay}</span>
                </div>
              </div>
              {job.status_message && (
                <p className="text-xs text-muted-foreground truncate">
                  {job.status_message}
                </p>
              )}
            </div>
          )}

          {/* Queued State */}
          {isQueued && (
            <div className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400">
              <Clock className="h-4 w-4" />
              <span>Queued - waiting to start</span>
            </div>
          )}

          {/* Pending State */}
          {isPending && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Preparing...</span>
            </div>
          )}

          {/* Paused State */}
          {isPaused && (
            <div className="space-y-2">
              <Progress value={job.progress_percent} className="h-2" />
              <div className="flex items-center gap-2 text-sm text-yellow-600 dark:text-yellow-400">
                <Pause className="h-4 w-4" />
                <span>Paused at {job.progress_percent}%</span>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-2 shrink-0">
          {/* Pause/Resume button for running/paused jobs */}
          {(isRunning || isPaused) && (
            <Button
              size="icon"
              variant="outline"
              onClick={isPaused ? handleResume : handlePause}
              disabled={isPausing || isResuming}
              className="h-8 w-8"
              title={isPaused ? "Resume" : "Pause"}
            >
              {isPaused ? (
                <Play className="h-4 w-4" />
              ) : (
                <Pause className="h-4 w-4" />
              )}
            </Button>
          )}

          {/* Cancel button */}
          <Button
            size="icon"
            variant="outline"
            onClick={handleCancel}
            disabled={isCancelling}
            className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
            title="Cancel"
          >
            <X className={cn("h-4 w-4", isCancelling && "animate-pulse")} />
          </Button>
        </div>
      </div>
    </Card>
  );
}

/**
 * Empty state component
 */
function EmptyState({
  type,
  onBackToLibrary,
}: {
  type: ViewType;
  onBackToLibrary?: () => void;
}) {
  const config = VIEW_CONFIG[type];
  const Icon = config.icon;

  return (
    <div className="flex flex-col items-center justify-center h-80 border-2 border-dashed border-border rounded-xl text-muted-foreground bg-muted/20">
      <Icon className="w-16 h-16 mb-4 opacity-20" />
      <p className="text-xl font-semibold text-foreground">{config.emptyMessage}</p>
      <p className="text-sm text-muted-foreground max-w-xs text-center mt-2 mb-6">
        {type === "downloading"
          ? "Select books from your library and click Download to start."
          : "Select downloaded books and click Convert to start."}
      </p>
      {onBackToLibrary && (
        <Button variant="outline" onClick={onBackToLibrary}>
          Back to Library
        </Button>
      )}
    </div>
  );
}

/**
 * Summary header showing queue status
 */
function QueueSummary({ jobs, type }: { jobs: Job[]; type: ViewType }) {
  const runningCount = jobs.filter((j) => j.status === "RUNNING").length;
  const queuedCount = jobs.filter((j) => j.status === "QUEUED" || j.status === "PENDING").length;
  const pausedCount = jobs.filter((j) => j.status === "PAUSED").length;

  const config = VIEW_CONFIG[type];
  const Icon = config.icon;

  return (
    <div className="flex items-center justify-between mb-6 px-1">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-primary/10">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h2 className="text-lg font-semibold">{config.title}</h2>
          <p className="text-sm text-muted-foreground">
            {runningCount > 0 && (
              <span className="text-green-600 dark:text-green-400">
                {runningCount} active
              </span>
            )}
            {runningCount > 0 && queuedCount > 0 && " · "}
            {queuedCount > 0 && (
              <span className="text-blue-600 dark:text-blue-400">
                {queuedCount} queued
              </span>
            )}
            {(runningCount > 0 || queuedCount > 0) && pausedCount > 0 && " · "}
            {pausedCount > 0 && (
              <span className="text-yellow-600 dark:text-yellow-400">
                {pausedCount} paused
              </span>
            )}
            {runningCount === 0 && queuedCount === 0 && pausedCount === 0 && (
              <span>No active jobs</span>
            )}
          </p>
        </div>
      </div>

      {jobs.length > 0 && (
        <div className="text-sm text-muted-foreground">
          {jobs.length} total
        </div>
      )}
    </div>
  );
}

/**
 * Main ActiveJobsView component
 */
export function ActiveJobsView({
  type,
  onBackToLibrary,
  className,
}: ActiveJobsViewProps) {
  const config = VIEW_CONFIG[type];
  const { data: activeJobs, isLoading } = useActiveJobs();

  // Filter jobs by type and sort: running first, then queued/pending, then paused
  const filteredJobs = React.useMemo(() => {
    if (!activeJobs?.items) return [];

    return activeJobs.items
      .filter((j) => j.task_type === config.taskType)
      .sort((a, b) => {
        const statusOrder: Record<string, number> = {
          RUNNING: 0,
          PENDING: 1,
          QUEUED: 2,
          PAUSED: 3,
        };
        const aOrder = statusOrder[a.status] ?? 99;
        const bOrder = statusOrder[b.status] ?? 99;
        if (aOrder !== bOrder) return aOrder - bOrder;
        // Within same status, sort by created_at
        return a.created_at.localeCompare(b.created_at);
      });
  }, [activeJobs, config.taskType]);

  // Get unique book ASINs from jobs
  const jobAsins = React.useMemo(
    () => [...new Set(filteredJobs.map((j) => j.book_asin).filter(Boolean))] as string[],
    [filteredJobs]
  );

  // Fetch book details in parallel for each job
  const bookQueries = useQueries({
    queries: jobAsins.map((asin) => ({
      queryKey: bookKeys.detail(asin),
      queryFn: () => getBookDetails(asin),
      staleTime: 5 * 60 * 1000, // 5 minutes
      enabled: !!asin,
    })),
  });

  // Create a map for quick book lookup
  const booksByAsin = React.useMemo(() => {
    const map = new Map<string, Book>();
    bookQueries.forEach((query, index) => {
      if (query.data) {
        map.set(jobAsins[index], query.data);
      }
    });
    return map;
  }, [bookQueries, jobAsins]);

  if (isLoading) {
    return (
      <div className={cn("flex items-center justify-center h-64", className)}>
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (filteredJobs.length === 0) {
    return (
      <div className={className}>
        <EmptyState type={type} onBackToLibrary={onBackToLibrary} />
      </div>
    );
  }

  return (
    <div className={className}>
      <QueueSummary jobs={filteredJobs} type={type} />

      <div className="space-y-3">
        {filteredJobs.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            book={job.book_asin ? booksByAsin.get(job.book_asin) ?? null : null}
          />
        ))}
      </div>
    </div>
  );
}
