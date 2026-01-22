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
  CheckCircle2
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Progress } from "@/components/ui/Progress";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { useUIStore } from "@/store/uiStore";
import { useActiveJobs, useJobs, useCreateDownloadJob, useCreateConvertJob } from "@/hooks/useJobs";
import { Job, JobType, isJobActive } from "@/types";

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

interface JobStat {
  speed: number;
  etr: number;
  lastProgress: number;
  lastTime: number;
}

export function ProgressPopover() {
  const { 
    progressPopover, 
    closeProgressPopover, 
    minimizeProgressPopover, 
    maximizeProgressPopover,
    updateProgressPopoverPosition 
  } = useUIStore();
  
  const { data: activeJobsData } = useActiveJobs({ refetchInterval: 1000 });
  const { data: failedJobsData } = useJobs("FAILED", { refetchInterval: 5000 });
  
  const { mutate: retryDownload } = useCreateDownloadJob();
  const { mutate: retryConvert } = useCreateConvertJob();

  const [activeTab, setActiveTab] = React.useState<"active" | "failed">("active");

  const activeJobs = React.useMemo(() => 
    activeJobsData?.items.filter(isJobActive) || [], 
    [activeJobsData]
  );
  const failedJobs = failedJobsData?.items || [];

  // Refs for performance optimizations
  const cardRef = React.useRef<HTMLDivElement>(null);
  const dragStartRef = React.useRef<{ x: number; y: number } | null>(null);
  const jobStatsRef = React.useRef<Record<string, JobStat>>({});
  
  // State for the calculated stats to display
  const [displayStats, setDisplayStats] = React.useState<Record<string, JobStat>>({});
  const [isDragging, setIsDragging] = React.useState(false);

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
      setIsDragging(true);
    }
  };

  React.useEffect(() => {
    if (!isDragging) return;

    const onMouseMove = (e: MouseEvent) => {
      if (!dragStartRef.current || !cardRef.current) return;
      
      // Direct DOM update for performance (60fps)
      const newX = e.clientX - dragStartRef.current.x;
      const newY = e.clientY - dragStartRef.current.y;
      
      cardRef.current.style.left = `${newX}px`;
      cardRef.current.style.top = `${newY}px`;
    };

    const onMouseUp = (e: MouseEvent) => {
      if (dragStartRef.current && cardRef.current) {
        const newX = e.clientX - dragStartRef.current.x;
        const newY = e.clientY - dragStartRef.current.y;
        updateProgressPopoverPosition(newX, newY);
      }
      setIsDragging(false);
      dragStartRef.current = null;
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [isDragging, updateProgressPopoverPosition]);

  const handleRetry = (job: Job) => {
    if (!job.book_asin) return;
    
    if (job.task_type === 'DOWNLOAD') {
      retryDownload(job.book_asin);
    } else if (job.task_type === 'CONVERT') {
      retryConvert({ asin: job.book_asin });
    }
  };

  if (!progressPopover.isOpen) return null;

  // Render Minimized View
  if (progressPopover.isMinimized) {
    return (
      <div 
        ref={cardRef}
        className="fixed z-50 shadow-lg cursor-pointer bg-primary text-primary-foreground rounded-full px-4 py-2 flex items-center gap-2 animate-in fade-in zoom-in duration-200 hover:scale-105 transition-transform"
        style={{ left: progressPopover.position.x, top: progressPopover.position.y }}
        onClick={maximizeProgressPopover}
        onMouseDown={handleMouseDown}
      >
        <div className="flex -space-x-2">
           {activeJobs.length > 0 ? (
             <div className="relative">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
             </div>
           ) : failedJobs.length > 0 ? (
             <AlertCircle className="w-4 h-4 text-destructive-foreground" />
           ) : (
             <CheckCircle2 className="w-4 h-4" />
           )}
        </div>
        <span className="text-sm font-medium whitespace-nowrap">
          {activeJobs.length} Active {failedJobs.length > 0 && `• ${failedJobs.length} Failed`}
        </span>
      </div>
    );
  }

  // Render Full View
  return (
    <Card 
      ref={cardRef}
      className="fixed z-50 w-80 shadow-2xl flex flex-col max-h-[80vh] animate-in fade-in zoom-in duration-200 border-primary/20 bg-background/95 backdrop-blur-sm"
      style={{ left: progressPopover.position.x, top: progressPopover.position.y }}
    >
      <CardHeader 
        className="p-3 border-b bg-muted/30 cursor-grab active:cursor-grabbing flex flex-row items-center justify-between space-y-0"
        onMouseDown={handleMouseDown}
      >
        <CardTitle className="text-sm font-medium flex items-center gap-2 select-none">
          <GripHorizontal className="w-4 h-4 text-muted-foreground" />
          Task Manager
        </CardTitle>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); minimizeProgressPopover(); }}>
            <Minus className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); closeProgressPopover(); }}>
            <X className="h-3 w-3" />
          </Button>
        </div>
      </CardHeader>
      
      {/* Tabs / Toggle */}
      <div className="flex p-1 bg-muted/30 border-b">
        <button
          className={cn(
            "flex-1 text-xs font-medium py-1.5 px-2 rounded-sm transition-colors",
            activeTab === "active" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:bg-background/50"
          )}
          onClick={() => setActiveTab("active")}
        >
          Active ({activeJobs.length})
        </button>
        <button
          className={cn(
            "flex-1 text-xs font-medium py-1.5 px-2 rounded-sm transition-colors",
            activeTab === "failed" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:bg-background/50"
          )}
          onClick={() => setActiveTab("failed")}
        >
          Failed ({failedJobs.length})
        </button>
      </div>
      
      <CardContent className="p-0 overflow-y-auto flex-1 custom-scrollbar">
        {activeTab === "active" ? (
          activeJobs.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm flex flex-col items-center gap-2">
              <CheckCircle2 className="w-8 h-8 opacity-20" />
              <p>No active tasks</p>
            </div>
          ) : (
            <div className="divide-y">
              {activeJobs.map(job => {
                const Icon = JOB_TYPE_ICONS[job.task_type];
                const stats = displayStats[job.id];
                const etr = stats ? formatDuration(stats.etr) : "--:--";
                const speed = stats ? `${stats.speed.toFixed(1)}%/s` : "";

                return (
                  <div key={job.id} className="p-3 hover:bg-muted/50 transition-colors">
                    <div className="flex items-start gap-3 mb-2">
                      <div className="p-2 bg-primary/10 rounded-md shrink-0">
                        <Icon className="w-4 h-4 text-primary animate-pulse" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex justify-between items-start">
                          <p className="text-sm font-medium truncate">
                            {job.task_type}
                          </p>
                          <span className="text-xs text-muted-foreground font-mono">
                            {job.progress_percent}%
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground truncate" title={job.book_asin || "Unknown Book"}>
                          {job.book_asin || "Processing..."}
                        </p>
                      </div>
                    </div>
                    
                    <Progress value={job.progress_percent} className="h-1.5 mb-1" />
                    
                    <div className="flex justify-between text-[10px] text-muted-foreground font-medium uppercase tracking-wider">
                      <span>{speed}</span>
                      <span>{etr} remaining</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )
        ) : (
          failedJobs.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm flex flex-col items-center gap-2">
              <CheckCircle2 className="w-8 h-8 opacity-20" />
              <p>No failed tasks</p>
            </div>
          ) : (
            <div className="divide-y">
              {failedJobs.map(job => {
                const Icon = JOB_TYPE_ICONS[job.task_type];
                return (
                  <div key={job.id} className="p-3 hover:bg-destructive/5 transition-colors group">
                    <div className="flex items-start gap-3">
                      <div className="p-2 bg-destructive/10 rounded-md shrink-0">
                        <Icon className="w-4 h-4 text-destructive" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex justify-between items-start">
                          <p className="text-sm font-medium truncate text-destructive">
                            {job.task_type} Failed
                          </p>
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity -mt-1 -mr-1"
                            onClick={() => handleRetry(job)}
                            title="Retry"
                          >
                            <RotateCcw className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                        <p className="text-xs text-muted-foreground truncate" title={job.book_asin || ""}>
                          {job.book_asin}
                        </p>
                        <p className="text-xs text-destructive/80 mt-1 line-clamp-2" title={job.error_message || ""}>
                          {job.error_message || "Unknown error"}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )
        )}
      </CardContent>
    </Card>
  );
}