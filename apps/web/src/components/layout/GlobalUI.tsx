"use client";

import { useState } from "react";
import { JobDrawer } from "@/components/domain/JobDrawer";
import { JobLogsModal } from "@/components/domain/JobLogsModal";
import { ProgressPopover } from "@/components/domain/ProgressPopover";
import { useUIStore } from "@/store/uiStore";
import { useJobs, useCancelJob, usePauseJob, useResumeJob } from "@/hooks/useJobs";
import { useJobsFeedWebSocket } from "@/hooks/useJobsFeedWebSocket";
import type { Job } from "@/types";

export function GlobalUI() {
  const jobsFeed = useJobsFeedWebSocket();

  const isJobDrawerOpen = useUIStore((state) => state.isJobDrawerOpen);
  const setJobDrawerOpen = useUIStore((state) => state.setJobDrawerOpen);
  
  const [logJob, setLogJob] = useState<Job | null>(null);

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
