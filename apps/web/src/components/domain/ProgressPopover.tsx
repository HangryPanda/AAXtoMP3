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

  // State for ETR calculation
  const [jobStats, setJobStats] = React.useState<Record<string, { speed: number; etr: number; lastProgress: number; lastTime: number }>>({});
  
  // State for dragging
  const [isDragging, setIsDragging] = React.useState(false);
  const [dragOffset, setDragOffset] = React.useState({ x: 0, y: 0 });

  const activeJobs = React.useMemo(() => 
    activeJobsData?.items.filter(isJobActive) || [], 
    [activeJobsData]
  );
  const failedJobs = failedJobsData?.items || [];
  
  // Calculate Speed and ETR
  React.useEffect(() => {
    const now = Date.now();
    
    setJobStats(prev => {
      const next = { ...prev };
      
      activeJobs.forEach(job => {
        const prevStat = prev[job.id];
        
        if (!prevStat) {
          // Initialize
          next[job.id] = {
            speed: 0,
            etr: 0,
            lastProgress: job.progress_percent,
            lastTime: now
          };
        } else {
          // Update
          const timeDiff = (now - prevStat.lastTime) / 1000; // seconds
          if (timeDiff >= 1) { // Update every second roughly
            const progressDiff = job.progress_percent - prevStat.lastProgress;
            
            // Simple moving average for speed to smooth it out slightly
            const currentSpeed = timeDiff > 0 ? Math.max(0, progressDiff / timeDiff) : 0;
            
            // Smooth speed: 30% new, 70% old
            const smoothedSpeed = (currentSpeed * 0.3) + (prevStat.speed * 0.7);
            
            // Calculate ETR
            const remaining = 100 - job.progress_percent;
            const etr = smoothedSpeed > 0 ? remaining / smoothedSpeed : 0;
            
            next[job.id] = {
              speed: smoothedSpeed,
              etr,
              lastProgress: job.progress_percent,
              lastTime: now
            };
          }
        }
      });
      
      return next;
    });
  }, [activeJobs]);

  // Drag handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    // Only allow dragging from header
    setIsDragging(true);
    setDragOffset({
      x: e.clientX - progressPopover.position.x,
      y: e.clientY - progressPopover.position.y
    });
  };

  const handleMouseMove = React.useCallback((e: MouseEvent) => {
    if (isDragging) {
      updateProgressPopoverPosition(
        e.clientX - dragOffset.x,
        e.clientY - dragOffset.y
      );
    }
  }, [isDragging, dragOffset, updateProgressPopoverPosition]);

  const handleMouseUp = React.useCallback(() => {
    setIsDragging(false);
  }, []);

  React.useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

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
                const stats = jobStats[job.id];
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