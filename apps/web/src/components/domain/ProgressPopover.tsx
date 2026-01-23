"use client";

import * as React from "react";
import { 
  X, 
  Minus, 
  Download, 
  FileAudio, 
  RefreshCw, 
  Wrench,
  AlertCircle,
  GripHorizontal,
  RotateCcw,
  CheckCircle2,
  History,
  FileText,
  XCircle,
  Pause,
  Play
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Progress } from "@/components/ui/Progress";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { useUIStore } from "@/store/uiStore";
import {
  useActiveJobs,
  useJobs,
  useJobsFiltered,
  useRetryJob,
  usePauseJob,
  useResumeJob,
  useClearJobHistory,
} from "@/hooks/useJobs";
import { Job, JobStatus, JobType, isJobActive } from "@/types";
import { ConnectionState } from "@/services/websocket";

// Icons for job types
const JOB_TYPE_ICONS: Record<JobType, React.ElementType> = {
  DOWNLOAD: Download,
  CONVERT: FileAudio,
  SYNC: RefreshCw,
  REPAIR: Wrench,
};

// Helper to format remaining time
function formatDuration(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return "--:--";
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

function formatAge(iso: string | undefined): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h`;
}

function ageSeconds(iso: string | undefined): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return null;
  return Math.max(0, Math.floor((Date.now() - t) / 1000));
}

interface JobStat {
  speed: number;
  etr: number;
  lastProgress: number;
  lastTime: number;
}

export interface ProgressPopoverProps {
  jobsFeedConnectionState: ConnectionState;
  onOpenJobs: () => void;
  onViewLogs: (job: Job) => void;
  onCancelJob: (jobId: string) => void;
}

const STATUS_LABEL: Record<JobStatus, string> = {
  PENDING: "Pending",
  QUEUED: "Queued",
  RUNNING: "Running",
  PAUSED: "Paused",
  COMPLETED: "Completed",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

export function ProgressPopover({
  jobsFeedConnectionState,
  onOpenJobs,
  onViewLogs,
  onCancelJob,
}: ProgressPopoverProps) {
  const { 
    progressPopover, 
    closeProgressPopover, 
    minimizeProgressPopover, 
    maximizeProgressPopover,
    updateProgressPopoverPosition 
  } = useUIStore();

  const [activeTab, setActiveTab] = React.useState<"active" | "failed" | "history">("active");
  const shouldPoll = progressPopover.isOpen && !progressPopover.isMinimized;
  
  const { data: activeJobsData } = useActiveJobs({
    enabled: progressPopover.isOpen,
    refetchInterval: false,
  });
  const { data: failedCountData } = useJobsFiltered(
    { status: "FAILED" as JobStatus, limit: 1 },
    { enabled: progressPopover.isOpen, refetchInterval: 30000, staleTime: 15000 }
  );
  const failedCount = failedCountData?.total ?? 0;

  const { data: failedJobsData } = useJobs("FAILED", {
    enabled: shouldPoll && activeTab === "failed",
    refetchInterval: false,
  });
  const { data: historyJobsData } = useJobsFiltered(
    { limit: 50 },
    {
      enabled: shouldPoll && activeTab === "history",
      refetchInterval: false,
      staleTime: 15000,
    }
  );
  
  const { mutate: retryJobById } = useRetryJob();
  const { mutate: pauseJobById } = usePauseJob();
  const { mutate: resumeJobById } = useResumeJob();
  const { mutate: clearHistory } = useClearJobHistory();

  const activeJobs = React.useMemo(() => 
    activeJobsData?.items.filter(isJobActive) || [], 
    [activeJobsData]
  );
  const failedJobs = failedJobsData?.items || [];
  const historyJobs = React.useMemo(() => {
    const items = historyJobsData?.items ?? [];
    const statuses: JobStatus[] = ["COMPLETED", "FAILED", "CANCELLED"];
    return items
      .filter((j) => statuses.includes(j.status))
      .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
  }, [historyJobsData]);

  // Refs for performance optimizations
  const cardRef = React.useRef<HTMLDivElement>(null);
  const dragStartRef = React.useRef<{ x: number; y: number } | null>(null);
  const jobStatsRef = React.useRef<Record<string, JobStat>>({});
  
  // State for the calculated stats to display
  const [displayStats, setDisplayStats] = React.useState<Record<string, JobStat>>({});
  const [isDragging, setIsDragging] = React.useState(false);
  const [dragPosition, setDragPosition] = React.useState<{ x: number; y: number } | null>(null);

  // Calculate stats in an effect to handle impurity (Date.now) correctly
  React.useEffect(() => {
    const updateStats = () => {
      const now = Date.now();
      const stats: Record<string, JobStat> = {};
      const prevStats = jobStatsRef.current;

      activeJobs.forEach(job => {
        const prev = prevStats[job.id];
        
        if (!prev) {
          stats[job.id] = {
            speed: 0,
            etr: 0,
            lastProgress: job.progress_percent,
            lastTime: now
          };
        } else {
          const timeDiff = (now - prev.lastTime) / 1000;
          
          if (timeDiff >= 1) {
            const progressDiff = job.progress_percent - prev.lastProgress;
            const currentSpeed = timeDiff > 0 ? Math.max(0, progressDiff / timeDiff) : 0;
            const smoothedSpeed = (currentSpeed * 0.3) + (prev.speed * 0.7);
            const remaining = 100 - job.progress_percent;
            const etr = smoothedSpeed > 0 ? remaining / smoothedSpeed : 0;

            stats[job.id] = {
              speed: smoothedSpeed,
              etr,
              lastProgress: job.progress_percent,
              lastTime: now
            };
          } else {
            stats[job.id] = prev;
          }
        }
      });
      
      jobStatsRef.current = stats;
      setDisplayStats(stats);
    };

    updateStats();
    
    if (activeJobs.length > 0) {
      const interval = setInterval(updateStats, 1000);
      return () => clearInterval(interval);
    }
  }, [activeJobs]);

  // Drag logic
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (cardRef.current) {
      const rect = cardRef.current.getBoundingClientRect();
      dragStartRef.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      };
      setDragPosition({ x: rect.left, y: rect.top });
      setIsDragging(true);
    }
  };

  const clampToViewport = React.useCallback((x: number, y: number) => {
    const el = cardRef.current;
    const w = el?.offsetWidth ?? 0;
    const h = el?.offsetHeight ?? 0;
    const maxX = Math.max(0, window.innerWidth - w);
    const maxY = Math.max(0, window.innerHeight - h);
    return {
      x: Math.min(Math.max(0, x), maxX),
      y: Math.min(Math.max(0, y), maxY),
    };
  }, []);

  React.useEffect(() => {
    if (!isDragging) return;

    const onMouseMove = (e: MouseEvent) => {
      if (!dragStartRef.current || !cardRef.current) return;
      
      const newX = e.clientX - dragStartRef.current.x;
      const newY = e.clientY - dragStartRef.current.y;
      setDragPosition({ x: newX, y: newY });
    };

    const onMouseUp = (e: MouseEvent) => {
      if (dragStartRef.current && cardRef.current) {
        const newX = e.clientX - dragStartRef.current.x;
        const newY = e.clientY - dragStartRef.current.y;
        const clamped = clampToViewport(newX, newY);
        updateProgressPopoverPosition(clamped.x, clamped.y);
      }
      setIsDragging(false);
      setDragPosition(null);
      dragStartRef.current = null;
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [clampToViewport, isDragging, updateProgressPopoverPosition]);

  // Clamp position on resize to avoid the popover going off-screen.
  React.useEffect(() => {
    if (!progressPopover.isOpen) return;
    const onResize = () => {
      const clamped = clampToViewport(progressPopover.position.x, progressPopover.position.y);
      if (clamped.x !== progressPopover.position.x || clamped.y !== progressPopover.position.y) {
        updateProgressPopoverPosition(clamped.x, clamped.y);
      }
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [clampToViewport, progressPopover.isOpen, progressPopover.position.x, progressPopover.position.y, updateProgressPopoverPosition]);

  const handleRetry = (job: Job) => {
    if (job.task_type !== "DOWNLOAD" && job.task_type !== "CONVERT") return;
    retryJobById(job.id);
  };

  if (!progressPopover.isOpen) return null;

  const isRealtimeConnected = jobsFeedConnectionState === ConnectionState.CONNECTED;

  // Render Minimized View
  if (progressPopover.isMinimized) {
    return (
      <div 
        ref={cardRef}
        className="fixed z-50 shadow-lg cursor-pointer bg-primary text-primary-foreground rounded-full px-3 py-1.5 flex items-center gap-2 animate-in fade-in zoom-in duration-200 hover:scale-105 transition-transform"
        style={{
          left: (dragPosition?.x ?? progressPopover.position.x),
          top: (dragPosition?.y ?? progressPopover.position.y),
        }}
        onClick={maximizeProgressPopover}
        onMouseDown={handleMouseDown}
      >
        <div className="flex -space-x-2">
           {activeJobs.length > 0 ? (
             <div className="relative">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
             </div>
           ) : failedCount > 0 ? (
             <AlertCircle className="w-4 h-4 text-destructive-foreground" />
           ) : (
             <CheckCircle2 className="w-4 h-4" />
          )}
        </div>
        <span className="text-xs font-medium whitespace-nowrap">
          {activeJobs.length} Active {failedCount > 0 && `• ${failedCount} Failed`}
        </span>
      </div>
    );
  }

  // Render Full View
  return (
    <Card 
      ref={cardRef}
      className="fixed z-50 w-[min(92vw,520px)] shadow-2xl flex flex-col max-h-[80vh] animate-in fade-in zoom-in duration-200 border-primary/20 bg-background/95 backdrop-blur-sm"
      style={{
        left: (dragPosition?.x ?? progressPopover.position.x),
        top: (dragPosition?.y ?? progressPopover.position.y),
      }}
    >
      <CardHeader 
        className="p-2 border-b bg-muted/30 cursor-grab active:cursor-grabbing flex flex-row items-center justify-between space-y-0"
        onMouseDown={handleMouseDown}
      >
        <CardTitle className="text-xs font-medium flex items-center gap-2 select-none">
          <GripHorizontal className="w-3.5 h-3.5 text-muted-foreground" />
          Tasks
          <span
            className={cn(
              "inline-flex items-center gap-1 text-[10px] font-medium",
              isRealtimeConnected ? "text-emerald-600" : "text-muted-foreground"
            )}
            title={
              isRealtimeConnected
                ? "Realtime connected"
                : "Realtime disconnected (UI may be stale)"
            }
          >
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                isRealtimeConnected ? "bg-emerald-600" : "bg-muted-foreground"
              )}
            />
            {isRealtimeConnected ? "Live" : "Stale"}
          </span>
        </CardTitle>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[11px]"
            onClick={(e) => {
              e.stopPropagation();
              onOpenJobs();
            }}
            title="View jobs"
          >
            Jobs
          </Button>
          {activeJobs.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-[11px] text-destructive hover:text-destructive"
              onClick={(e) => {
                e.stopPropagation();
                if (!window.confirm(`Cancel ${activeJobs.length} active job(s)?`)) return;
                for (const job of activeJobs) onCancelJob(job.id);
              }}
              title="Cancel all active jobs"
            >
              Cancel all
            </Button>
          )}
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); minimizeProgressPopover(); }}>
            <Minus className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); closeProgressPopover(); }}>
            <X className="h-3 w-3" />
          </Button>
        </div>
      </CardHeader>
      
      {/* Tabs / Toggle */}
      <div className="flex p-1 bg-muted/30 border-b" role="tablist" aria-label="Tasks tabs">
        <button
          className={cn(
            "flex-1 text-[11px] font-medium py-1 px-2 rounded-sm transition-colors",
            activeTab === "active" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:bg-background/50"
          )}
          onClick={() => setActiveTab("active")}
          role="tab"
          aria-selected={activeTab === "active"}
        >
          Active ({activeJobs.length})
        </button>
        <button
          className={cn(
            "flex-1 text-[11px] font-medium py-1 px-2 rounded-sm transition-colors",
            activeTab === "failed" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:bg-background/50"
          )}
          onClick={() => setActiveTab("failed")}
          role="tab"
          aria-selected={activeTab === "failed"}
        >
          Failed ({failedCount})
        </button>
        <button
          className={cn(
            "flex-1 text-[11px] font-medium py-1 px-2 rounded-sm transition-colors",
            activeTab === "history" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:bg-background/50"
          )}
          onClick={() => setActiveTab("history")}
          role="tab"
          aria-selected={activeTab === "history"}
        >
          History
        </button>
      </div>

      {!isRealtimeConnected && (
        <div className="px-3 py-2 border-b bg-muted/20 text-[11px] text-muted-foreground">
          Realtime disconnected — data may be stale. Open <span className="font-medium">Jobs</span> to verify status.
        </div>
      )}
      
      <CardContent className="p-0 overflow-y-auto flex-1 custom-scrollbar">
        {activeTab === "active" ? (
          activeJobs.length === 0 ? (
            <div className="p-5 text-center text-muted-foreground text-xs flex flex-col items-center gap-2">
              <CheckCircle2 className="w-6 h-6 opacity-20" />
              <p>No active tasks.</p>
            </div>
          ) : (
            <div className="divide-y">
              {activeJobs.map(job => {
                const Icon = JOB_TYPE_ICONS[job.task_type];
                const stats = displayStats[job.id];
                const etr = stats ? formatDuration(stats.etr) : "--:--";
                const speed = stats ? `${stats.speed.toFixed(1)}%/s` : "";
                const secondsSinceUpdate = ageSeconds(job.updated_at);
                const isStalled = (secondsSinceUpdate ?? 0) > 90 && job.status === "RUNNING" && !isDragging;

                const statusText =
                  job.status_message || `${STATUS_LABEL[job.status]}…`;

                return (
                  <div key={job.id} className="p-2.5 hover:bg-muted/50 transition-colors">
                    <div className="flex items-start gap-2 mb-2">
                      <div className="p-1.5 bg-primary/10 rounded-sm shrink-0 mt-0.5">
                        <Icon className="w-3.5 h-3.5 text-primary animate-pulse" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex justify-between items-start gap-2">
                          <p className="text-[11px] font-medium text-muted-foreground">
                            {job.task_type} • {STATUS_LABEL[job.status]}
                          </p>
                          <span className="text-xs font-semibold text-primary shrink-0">
                            {job.progress_percent}%
                          </span>
                        </div>
                        <p
                          className="text-xs font-medium mt-0.5 line-clamp-2 leading-snug"
                          title={statusText}
                        >
                          {statusText}
                        </p>
                        <p className="text-[11px] text-muted-foreground truncate mt-0.5" title={job.book_asin || job.id}>
                          {job.book_asin || job.id}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        {job.status === "PAUSED" ? (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => resumeJobById(job.id)}
                            title="Resume"
                          >
                            <Play className="h-3.5 w-3.5" />
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => pauseJobById(job.id)}
                            title="Pause"
                          >
                            <Pause className="h-3.5 w-3.5" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => onViewLogs(job)}
                          title="View logs"
                        >
                          <FileText className="h-3.5 w-3.5" />
                        </Button>
                        {isJobActive(job) && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-destructive hover:text-destructive"
                            onClick={() => onCancelJob(job.id)}
                            title="Cancel"
                          >
                            <XCircle className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    </div>

                    <Progress value={job.progress_percent} className="h-1.5 mb-1.5" />

                    <div className="flex justify-between text-[10px] text-muted-foreground">
                      <span className="flex items-center gap-2">
                        <span>{speed || "—"}</span>
                        <span title={job.updated_at ? `Updated at ${job.updated_at}` : ""}>
                          Updated: {formatAge(job.updated_at)}
                        </span>
                        {isStalled && (
                          <span className="text-destructive font-medium" title="No updates recently">
                            Stalled
                          </span>
                        )}
                      </span>
                      <span>ETA: {etr}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )
        ) : activeTab === "failed" ? (
          failedJobs.length === 0 ? (
            <div className="p-5 text-center text-muted-foreground text-xs flex flex-col items-center gap-2">
              <CheckCircle2 className="w-6 h-6 opacity-20" />
              <p>No failed tasks.</p>
            </div>
          ) : (
            <div className="divide-y">
              {failedJobs.map(job => {
                const Icon = JOB_TYPE_ICONS[job.task_type];
                return (
                  <div key={job.id} className="p-2 hover:bg-destructive/5 transition-colors group">
                    <div className="flex items-start gap-2">
                      <div className="p-1.5 bg-destructive/10 rounded-sm shrink-0">
                        <Icon className="w-3.5 h-3.5 text-destructive" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex justify-between items-start">
                          <p className="text-xs font-medium truncate text-destructive">
                            {job.task_type} Failed
                          </p>
                          <div className="flex items-center gap-1 -mt-1 -mr-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6"
                              onClick={() => onViewLogs(job)}
                              title="View logs"
                            >
                              <FileText className="h-3.5 w-3.5" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="h-6 w-6"
                              onClick={() => handleRetry(job)}
                              title="Retry"
                              disabled={job.task_type !== "DOWNLOAD" && job.task_type !== "CONVERT"}
                            >
                              <RotateCcw className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </div>
                        <p className="text-[10px] text-muted-foreground truncate" title={job.book_asin || job.id}>
                          {job.book_asin || job.id}
                        </p>
                        <p className="text-[10px] text-destructive/80 mt-1 line-clamp-2" title={job.error_message || ""}>
                          {job.error_message || "Failed (no error message recorded)."}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )
        ) : historyJobs.length === 0 ? (
          <div className="p-5 text-center text-muted-foreground text-xs flex flex-col items-center gap-2">
            <History className="w-6 h-6 opacity-20" />
            <p>No recent history.</p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (!window.confirm("Clear job history (completed/failed/cancelled)?")) return;
                clearHistory({ delete_logs: false });
              }}
              className="text-[11px]"
              title="Clear completed/failed/cancelled jobs"
            >
              Clear history
            </Button>
          </div>
        ) : (
          <div className="divide-y">
            <div className="p-2 flex items-center justify-between bg-muted/20">
              <span className="text-[11px] text-muted-foreground">
                Showing {historyJobs.length} most recent
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-[11px]"
                onClick={() => {
                  if (!window.confirm("Clear job history (completed/failed/cancelled)?")) return;
                  clearHistory({ delete_logs: false });
                }}
                title="Clear completed/failed/cancelled jobs"
              >
                Clear history
              </Button>
            </div>
            {historyJobs.map((job) => {
              const Icon = JOB_TYPE_ICONS[job.task_type];
              const isFailed = job.status === "FAILED";
              return (
                <div
                  key={job.id}
                  className={cn(
                    "p-2 transition-colors group",
                    isFailed ? "hover:bg-destructive/5" : "hover:bg-muted/50"
                  )}
                >
                  <div className="flex items-start gap-2">
                    <div
                      className={cn(
                        "p-1.5 rounded-sm shrink-0",
                        isFailed ? "bg-destructive/10" : "bg-muted"
                      )}
                    >
                      <Icon className={cn("w-3.5 h-3.5", isFailed ? "text-destructive" : "text-foreground/70")} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <p className={cn("text-xs font-medium truncate", isFailed && "text-destructive")}>
                          {job.task_type}
                        </p>
                        <span className={cn("text-[10px] font-medium", isFailed ? "text-destructive" : "text-muted-foreground")}>
                          {job.status.toLowerCase()}
                        </span>
                      </div>
                      <p className="text-[10px] text-muted-foreground truncate" title={job.book_asin || job.id}>
                        {job.book_asin || job.id}
                      </p>
                      <p className="text-[10px] text-muted-foreground truncate" title={job.updated_at || job.created_at}>
                        Updated: {formatAge(job.updated_at || job.created_at)}
                      </p>
                      {job.error_message && (
                        <p className="text-[10px] text-destructive/80 mt-1 line-clamp-2" title={job.error_message}>
                          {job.error_message}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => onViewLogs(job)}
                        title="View logs"
                      >
                        <FileText className="h-3.5 w-3.5" />
                      </Button>
                      {(job.status === "FAILED" || job.status === "CANCELLED") &&
                        (job.task_type === "DOWNLOAD" || job.task_type === "CONVERT") && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => handleRetry(job)}
                            title="Retry"
                          >
                            <RotateCcw className="h-3.5 w-3.5" />
                          </Button>
                        )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
