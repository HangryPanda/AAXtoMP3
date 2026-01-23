"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { JobDrawer } from "@/components/domain/JobDrawer";
import { JobLogsModal } from "@/components/domain/JobLogsModal";
import { ProgressPopover } from "@/components/domain/ProgressPopover";
import { useUIStore } from "@/store/uiStore";
import { useActiveJobs, useJobs, useCancelJob, usePauseJob, useResumeJob } from "@/hooks/useJobs";
import { useJobsFeedWebSocket } from "@/hooks/useJobsFeedWebSocket";
import { isJobActive } from "@/types";
import type { Job } from "@/types";

export function GlobalUI() {
  const jobsFeed = useJobsFeedWebSocket();

  const isJobDrawerOpen = useUIStore((state) => state.isJobDrawerOpen);
  const setJobDrawerOpen = useUIStore((state) => state.setJobDrawerOpen);
  const progressPopover = useUIStore((s) => s.progressPopover);
  const openProgressPopover = useUIStore((s) => s.openProgressPopover);
  
  const [logJob, setLogJob] = useState<Job | null>(null);

  // Global active jobs polling (drives the progress popover + cues)
  const { data: activeJobsData } = useActiveJobs({
    // Fetch once; subsequent updates come from the global jobs websocket feed.
    refetchInterval: false,
  });
  const activeCount = useMemo(
    () => activeJobsData?.items.filter(isJobActive).length ?? 0,
    [activeJobsData]
  );
  const dismissedRef = useRef(false);
  const prevActiveCountRef = useRef(0);
  useEffect(() => {
    const prev = prevActiveCountRef.current;
    prevActiveCountRef.current = activeCount;

    if (activeCount === 0) {
      dismissedRef.current = false;
      return;
    }

    // If new work appears, show the progress UI (but don't fight the user after they close it).
    const becameActive = prev === 0 && activeCount > 0;
    if (becameActive) dismissedRef.current = false;

    if (!progressPopover.isOpen && !dismissedRef.current) {
      openProgressPopover();
    }
  }, [activeCount, openProgressPopover, progressPopover.isOpen]);

  // Track user dismissing the popover while work is still ongoing.
  useEffect(() => {
    if (activeCount > 0 && !progressPopover.isOpen) {
      dismissedRef.current = true;
    }
  }, [activeCount, progressPopover.isOpen]);
  
  // Fetch all jobs for the drawer
  const { data: jobsData } = useJobs(undefined, {
    enabled: isJobDrawerOpen,
    refetchInterval: false,
  });
  
  const { mutate: cancelJob } = useCancelJob();
  const { mutate: pauseJob } = usePauseJob();
  const { mutate: resumeJob } = useResumeJob();

  return (
    <>
      <JobDrawer
        open={isJobDrawerOpen}
        jobs={jobsData?.items ?? []}
        onClose={() => setJobDrawerOpen(false)}
        onCancelJob={(job) => cancelJob(job.id)}
        onPauseJob={(job) => pauseJob(job.id)}
        onResumeJob={(job) => resumeJob(job.id)}
        onViewLogs={(job) => setLogJob(job)}
      />
      <ProgressPopover
        jobsFeedConnectionState={jobsFeed.connectionState}
        onOpenJobs={() => setJobDrawerOpen(true)}
        onViewLogs={(job) => setLogJob(job)}
        onCancelJob={(jobId) => cancelJob(jobId)}
      />
      
      <JobLogsModal 
        job={logJob} 
        open={!!logJob} 
        onClose={() => setLogJob(null)} 
      />
    </>
  );
}
