/**
 * JobsView
 *
 * Comprehensive view for managing downloads or conversions.
 * Shows Active, Failed, and Completed sections with appropriate actions.
 */

"use client";

import * as React from "react";
import Image from "next/image";
import {
  Download,
  FileAudio,
  X,
  Loader2,
  Play,
  Pause,
  RotateCcw,
  BookOpen,
  CheckCircle2,
  XCircle,
  Trash2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useQueries } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import {
  useActiveJobs,
  useJobsFiltered,
  useCancelJob,
  usePauseJob,
  useResumeJob,
  useRetryJob,
  useClearJobHistory,
} from "@/hooks/useJobs";
import { bookKeys } from "@/hooks/useBooks";
import { getBookDetails } from "@/services/books";
import type { Job, JobType, Book } from "@/types";
import { getCoverUrl, getPrimaryAuthor } from "@/types";
import { useProgressStats } from "@/hooks/useProgressStats";
import { formatMBps } from "@/lib/format";

type ViewType = "downloading" | "converting";

interface JobsViewProps {
  type: ViewType;
  onBackToLibrary?: () => void;
  className?: string;
}

const VIEW_CONFIG: Record<
  ViewType,
  { taskType: JobType; icon: React.ElementType; title: string; singular: string }
> = {
  downloading: {
    taskType: "DOWNLOAD",
    icon: Download,
    title: "Downloads",
    singular: "download",
  },
  converting: {
    taskType: "CONVERT",
    icon: FileAudio,
    title: "Conversions",
    singular: "conversion",
  },
};

// ============================================================================
// Job Card Component - Enterprise-grade visual states
// Based on: Spotify album view / Audible library design principles
// Unified component for both downloads and conversions
// ============================================================================

interface JobCardProps {
  job: Job;
  book: Book | null;
  showActions?: boolean;
}

/**
 * Visual states:
 * - queued: Dashed blue border, desaturated cover, clock badge
 * - processing: Solid blue border with pulsing glow, spinner overlay
 * - completed: Borderless, settled appearance, momentary checkmark
 * - failed: Subtle red accent, retry action available
 *
 * Downloads additionally show: speed and ETA when running
 */
function JobCard({ job, book, showActions = true }: JobCardProps) {
  const { mutate: cancelJob, isPending: isCancelling } = useCancelJob();
  const { mutate: pauseJob, isPending: isPausing } = usePauseJob();
  const { mutate: resumeJob, isPending: isResuming } = useResumeJob();
  const { mutate: retryJob, isPending: isRetrying } = useRetryJob();

  const isRunning = job.status === "RUNNING";
  const isPaused = job.status === "PAUSED";
  const isQueued = job.status === "QUEUED";
  const isPending = job.status === "PENDING";
  const isFailed = job.status === "FAILED";
  const isCompleted = job.status === "COMPLETED";
  const isDownload = job.task_type === "DOWNLOAD";

  // Combined states for styling
  const isWaiting = isQueued || isPending;
  const isProcessing = isRunning || isPaused;

  const { speedDisplay, etaDisplay } = useProgressStats(job.progress_percent, isRunning && !isDownload);
  const downloadSpeed = isDownload ? formatMBps(job.download_bytes_per_sec) : null;

  const coverUrl = book ? getCoverUrl(book) : null;
  const title = book?.title ?? job.book_asin ?? "Unknown";
  const author = book ? getPrimaryAuthor(book) : "";
  const duration = book?.runtime_length_min
    ? `${Math.floor(book.runtime_length_min / 60)}h ${book.runtime_length_min % 60}m`
    : null;

  // Card container classes based on state
  const cardClasses = cn(
    "group relative flex flex-col rounded-lg transition-all duration-300",
    // Queued: dashed blue border
    isWaiting && "border-2 border-dashed border-blue-300",
    // Processing: solid blue border with pulsing glow
    isProcessing && "ring-2 ring-blue-500 animate-pulse-glow",
    // Failed: subtle red ring
    isFailed && "ring-1 ring-destructive/40",
    // Completed: no border, settled
    isCompleted && "ring-0",
    // Default hover for non-active states
    !isProcessing && !isWaiting && "hover:-translate-y-0.5 hover:shadow-lg"
  );

  // Cover filter classes
  const coverClasses = cn(
    "relative aspect-[3/4] rounded-lg overflow-hidden bg-gradient-to-br from-slate-200 to-slate-300 shadow-md transition-all duration-300",
    // Desaturate queued items
    isWaiting && "saturate-[0.7]",
    // Normal for others
    !isWaiting && "saturate-100"
  );

  return (
    <div className={cardClasses}>
      {/* Book Cover Container */}
      <div className={coverClasses}>
        {coverUrl ? (
          <Image
            src={coverUrl}
            alt={title}
            fill
            className="object-cover"
            sizes="(max-width: 640px) 33vw, (max-width: 1024px) 20vw, 180px"
          />
        ) : (
          // Auto-generated gradient placeholder with title
          <div className="flex h-full items-center justify-center p-4 bg-gradient-to-br from-slate-400 to-slate-600">
            <span className="text-white/80 text-sm font-medium text-center line-clamp-3">
              {title}
            </span>
          </div>
        )}


        {/* Retry attempt badge - only show on failed or in-progress jobs */}
        {(job.attempt ?? 1) > 1 && !isCompleted && (
          <div className="absolute top-2 right-2 px-1.5 py-0.5 rounded text-[10px] font-medium bg-orange-500 text-white shadow-sm">
            Attempt {job.attempt}
          </div>
        )}

        {/* QUEUED STATE: Semi-transparent overlay with badge */}
        {isWaiting && (
          <div className="absolute inset-0 bg-white/40 flex items-center justify-center">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-blue-500 text-white text-xs font-medium shadow-lg">
              {isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : isDownload ? (
                <Download className="h-3 w-3" />
              ) : (
                <FileAudio className="h-3 w-3" />
              )}
              <span>{isPending ? "Preparing" : "Queued"}</span>
            </div>
          </div>
        )}

        {/* PROCESSING STATE: Spinner overlay with stats */}
        {isProcessing && (
          <div className="absolute inset-0 bg-black/30 flex flex-col items-center justify-center gap-1.5">
            {/* CSS Spinner */}
            <div className="relative">
              <div className="w-10 h-10 rounded-full border-3 border-white/30 border-t-white animate-spin" />
            </div>
            {/* Progress percentage */}
            <div className="text-white text-sm font-semibold">
              {job.progress_percent}%
            </div>
            {/* Download-specific stats: Speed and ETA */}
            {isDownload && isRunning && (downloadSpeed || etaDisplay !== "--:--") && (
              <div className="flex flex-col items-center text-white/80 text-[10px] font-medium">
                <span>{downloadSpeed ?? "— MB/s"}</span>
                {etaDisplay !== "--:--" && <span>{etaDisplay}</span>}
              </div>
            )}
            {isPaused && (
              <div className="flex items-center gap-1 text-yellow-300 text-xs">
                <Pause className="h-3 w-3" />
                <span>Paused</span>
              </div>
            )}
          </div>
        )}

        {/* COMPLETED STATE: Checkmark that fades */}
        {isCompleted && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="animate-completion-check">
              <div className="w-12 h-12 rounded-full bg-green-500 flex items-center justify-center shadow-lg">
                <CheckCircle2 className="h-6 w-6 text-white" />
              </div>
            </div>
          </div>
        )}

        {/* FAILED STATE: Subtle indicator */}
        {isFailed && (
          <div className="absolute bottom-2 right-2">
            <div className="p-1.5 rounded-full bg-destructive/90 shadow-sm">
              <XCircle className="h-3.5 w-3.5 text-white" />
            </div>
          </div>
        )}

        {/* Hover Actions Overlay */}
        {showActions && (
          <div className="absolute inset-0 flex items-center justify-center gap-2 bg-black/0 opacity-0 group-hover:bg-black/50 group-hover:opacity-100 transition-all duration-200">
            {isFailed && (
              <Button
                size="sm"
                onClick={() => retryJob(job.id)}
                disabled={isRetrying}
                className="h-9 gap-2 bg-white text-slate-900 hover:bg-slate-100 shadow-lg"
              >
                <RotateCcw className={cn("h-4 w-4", isRetrying && "animate-spin")} />
                Retry
              </Button>
            )}
            {isProcessing && (
              <>
                <Button
                  size="icon"
                  onClick={() => (isPaused ? resumeJob(job.id) : pauseJob(job.id))}
                  disabled={isPausing || isResuming}
                  className="h-9 w-9 bg-white text-slate-900 hover:bg-slate-100 shadow-lg"
                  title={isPaused ? "Resume" : "Pause"}
                >
                  {isPaused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
                </Button>
                <Button
                  size="icon"
                  onClick={() => cancelJob(job.id)}
                  disabled={isCancelling}
                  className="h-9 w-9 bg-white text-destructive hover:bg-red-50 shadow-lg"
                  title="Cancel"
                >
                  <X className={cn("h-4 w-4", isCancelling && "animate-pulse")} />
                </Button>
              </>
            )}
            {isWaiting && (
              <Button
                size="icon"
                onClick={() => cancelJob(job.id)}
                disabled={isCancelling}
                className="h-9 w-9 bg-white text-slate-600 hover:bg-slate-100 shadow-lg"
                title="Remove from queue"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Book Info */}
      <div className="mt-2.5 px-1 pb-2">
        <h3
          className="font-medium text-[13px] leading-tight line-clamp-2 text-foreground min-h-[2.5em]"
          title={title}
        >
          {title}
        </h3>
        <div className="mt-1 flex items-center justify-between gap-2">
          {author ? (
            <p className="text-[11px] text-muted-foreground truncate">{author}</p>
          ) : (
            <span />
          )}
          {duration && (
            <span className="text-[10px] text-muted-foreground/60 whitespace-nowrap">{duration}</span>
          )}
        </div>

        {/* Error message for failed - muted, not aggressive */}
        {isFailed && job.error_message && (
          <p
            className="mt-1 text-[10px] text-muted-foreground/70 line-clamp-1"
            title={job.error_message}
          >
            {job.error_message}
          </p>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Section Components
// ============================================================================

interface SectionProps {
  title: string;
  count: number;
  children: React.ReactNode;
  defaultExpanded?: boolean;
  actions?: React.ReactNode;
}

function Section({
  title,
  count,
  children,
  defaultExpanded = true,
  actions,
}: SectionProps) {
  const [expanded, setExpanded] = React.useState(defaultExpanded);

  if (count === 0) return null;

  return (
    <div className="mb-10">
      {/* Section Header */}
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronUp className="h-4 w-4" />
          )}
          <span>{title}</span>
          <span className="text-xs bg-muted px-2 py-0.5 rounded-full">{count}</span>
        </button>
        {actions && expanded && (
          <div onClick={(e) => e.stopPropagation()}>{actions}</div>
        )}
      </div>

      {/* Responsive Grid - auto-fill with minmax for natural reflow */}
      {expanded && (
        <div
          className="grid gap-x-6 gap-y-8"
          style={{
            gridTemplateColumns: "repeat(auto-fill, minmax(160px, 200px))",
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Empty State
// ============================================================================

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
    <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
      <div className="p-4 rounded-full bg-muted/50 mb-4">
        <Icon className="w-8 h-8 opacity-40" />
      </div>
      <p className="text-lg font-medium text-foreground">No {config.title.toLowerCase()}</p>
      <p className="text-sm text-muted-foreground max-w-xs text-center mt-1 mb-6">
        {type === "downloading"
          ? "Select books from your library to start downloading."
          : "Downloaded books will appear here for conversion."}
      </p>
      {onBackToLibrary && (
        <Button variant="outline" onClick={onBackToLibrary} className="gap-2">
          <BookOpen className="h-4 w-4" />
          Browse Library
        </Button>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * Get the latest job per book_asin from a list of jobs.
 * This ensures we show only ONE entry per book, not a list of all attempts.
 */
function getLatestJobPerBook(jobs: Job[]): Job[] {
  const latestByAsin = new Map<string, Job>();
  const noAsinJobs: Job[] = [];

  for (const job of jobs) {
    if (!job.book_asin) {
      noAsinJobs.push(job);
      continue;
    }

    const existing = latestByAsin.get(job.book_asin);
    if (!existing || job.created_at > existing.created_at) {
      latestByAsin.set(job.book_asin, job);
    }
  }

  return [...latestByAsin.values(), ...noAsinJobs];
}

/**
 * Filter failed jobs to show only actionable failures:
 * - Only the latest attempt per book
 * - Hide if there's an active or completed retry for that book
 */
function getActionableFailures(
  failedJobs: Job[],
  activeJobs: Job[],
  completedJobs: Job[]
): Job[] {
  // Books that have active or completed jobs don't need to show in failed
  const handledAsins = new Set<string>();
  for (const job of [...activeJobs, ...completedJobs]) {
    if (job.book_asin) {
      handledAsins.add(job.book_asin);
    }
  }

  // Get latest failure per book, excluding those being handled
  const latestFailures = getLatestJobPerBook(failedJobs);
  return latestFailures.filter((job) => {
    if (!job.book_asin) return true;
    return !handledAsins.has(job.book_asin);
  });
}

export function JobsView({ type, onBackToLibrary, className }: JobsViewProps) {
  const config = VIEW_CONFIG[type];

  // Fetch jobs by status and type with real-time updates
  const { data: activeJobs, isLoading: isLoadingActive } = useActiveJobs();
  const { data: failedJobs, isLoading: isLoadingFailed } = useJobsFiltered(
    { status: "FAILED", task_type: config.taskType, limit: 50 },
    { staleTime: 2000, refetchInterval: 5000 }
  );
  const { data: completedJobs, isLoading: isLoadingCompleted } = useJobsFiltered(
    { status: "COMPLETED", task_type: config.taskType, limit: 50 },
    { staleTime: 2000, refetchInterval: 5000 }
  );

  const { mutate: retryJob, isPending: isRetryingBatch } = useRetryJob();
  const { mutate: clearHistory, isPending: isClearingHistory } = useClearJobHistory();

  // Filter active jobs by type (active jobs are already unique per book)
  const activeFiltered = React.useMemo(() => {
    if (!activeJobs?.items) return [];
    return activeJobs.items
      .filter((j) => j.task_type === config.taskType)
      .sort((a, b) => {
        // Running first, then queued/pending by created_at
        const statusOrder: Record<string, number> = {
          RUNNING: 0,
          PENDING: 1,
          QUEUED: 2,
          PAUSED: 3,
        };
        const aOrder = statusOrder[a.status] ?? 99;
        const bOrder = statusOrder[b.status] ?? 99;
        if (aOrder !== bOrder) return aOrder - bOrder;
        return a.created_at.localeCompare(b.created_at);
      });
  }, [activeJobs, config.taskType]);

  // Failed: Show only ONE entry per book (latest attempt), hide if being retried
  const failedFiltered = React.useMemo(() => {
    const rawFailed = failedJobs?.items ?? [];
    const rawCompleted = completedJobs?.items ?? [];
    return getActionableFailures(rawFailed, activeFiltered, rawCompleted)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [failedJobs, activeFiltered, completedJobs]);

  // Completed: Show only ONE entry per book (latest successful attempt)
  const completedFiltered = React.useMemo(() => {
    const rawCompleted = completedJobs?.items ?? [];
    return getLatestJobPerBook(rawCompleted)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [completedJobs]);

  // Collect all unique ASINs for book lookup
  const allAsins = React.useMemo(() => {
    const asins = new Set<string>();
    [...activeFiltered, ...failedFiltered, ...completedFiltered].forEach((j) => {
      if (j.book_asin) asins.add(j.book_asin);
    });
    return Array.from(asins);
  }, [activeFiltered, failedFiltered, completedFiltered]);

  // Fetch book details in parallel
  const bookQueries = useQueries({
    queries: allAsins.map((asin) => ({
      queryKey: bookKeys.detail(asin),
      queryFn: () => getBookDetails(asin),
      staleTime: 5 * 60 * 1000,
    })),
  });

  const booksByAsin = React.useMemo(() => {
    const map = new Map<string, Book>();
    bookQueries.forEach((query, index) => {
      if (query.data) {
        map.set(allAsins[index], query.data);
      }
    });
    return map;
  }, [bookQueries, allAsins]);

  // Handlers
  const handleRetryAllFailed = () => {
    failedFiltered.forEach((job) => {
      retryJob(job.id);
    });
  };

  const handleClearCompleted = () => {
    clearHistory({ delete_logs: false });
  };

  const isLoading = isLoadingActive || isLoadingFailed || isLoadingCompleted;
  const hasAnyJobs =
    activeFiltered.length > 0 || failedFiltered.length > 0 || completedFiltered.length > 0;

  if (isLoading) {
    return (
      <div className={cn("w-full px-6 py-6 flex items-center justify-center h-64", className)}>
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!hasAnyJobs) {
    return (
      <div className={cn("w-full px-6 py-6", className)}>
        <EmptyState type={type} onBackToLibrary={onBackToLibrary} />
      </div>
    );
  }

  return (
    <div className={cn("w-full px-6 py-6", className)}>
      {/* Minimal Header */}
      {onBackToLibrary && (
        <div className="flex items-center justify-end mb-6">
          <Button variant="ghost" onClick={onBackToLibrary} size="sm" className="gap-2 text-muted-foreground hover:text-foreground">
            <BookOpen className="h-4 w-4" />
            Library
          </Button>
        </div>
      )}

      {/* Active Jobs Section */}
      <Section
        title="In Progress"
        count={activeFiltered.length}
        defaultExpanded={true}
      >
        {activeFiltered.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            book={job.book_asin ? booksByAsin.get(job.book_asin) ?? null : null}
          />
        ))}
      </Section>

      {/* Failed Jobs Section */}
      <Section
        title="Needs Attention"
        count={failedFiltered.length}
        defaultExpanded={true}
        actions={
          failedFiltered.length > 1 && (
            <Button
              size="sm"
              variant="ghost"
              onClick={handleRetryAllFailed}
              disabled={isRetryingBatch}
              className="h-7 text-xs gap-1.5 text-muted-foreground hover:text-foreground"
            >
              <RotateCcw className={cn("h-3 w-3", isRetryingBatch && "animate-spin")} />
              Retry All
            </Button>
          )
        }
      >
        {failedFiltered.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            book={job.book_asin ? booksByAsin.get(job.book_asin) ?? null : null}
          />
        ))}
      </Section>

      {/* Completed Jobs Section */}
      <Section
        title="Recently Completed"
        count={completedFiltered.length}
        defaultExpanded={false}
        actions={
          <Button
            size="sm"
            variant="ghost"
            onClick={handleClearCompleted}
            disabled={isClearingHistory}
            className="h-7 text-xs gap-1.5 text-muted-foreground hover:text-foreground"
          >
            <Trash2 className={cn("h-3 w-3", isClearingHistory && "animate-spin")} />
            Clear
          </Button>
        }
      >
        {completedFiltered.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            book={job.book_asin ? booksByAsin.get(job.book_asin) ?? null : null}
            showActions={false}
          />
        ))}
      </Section>
    </div>
  );
}
