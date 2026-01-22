"use client";

import { useState } from "react";
import { JobDrawer } from "@/components/domain/JobDrawer";
import { JobLogsModal } from "@/components/domain/JobLogsModal";
import { useUIStore } from "@/store/uiStore";
import { useJobs, useCancelJob } from "@/hooks/useJobs";
import type { Job } from "@/types";

export function GlobalUI() {
  const isJobDrawerOpen = useUIStore((state) => state.isJobDrawerOpen);
  const setJobDrawerOpen = useUIStore((state) => state.setJobDrawerOpen);
  
  const [logJob, setLogJob] = useState<Job | null>(null);
  
  // Fetch all jobs for the drawer
  const { data: jobsData } = useJobs(undefined, {
    enabled: isJobDrawerOpen,
    refetchInterval: isJobDrawerOpen ? 5000 : false,
  });
  
  const { mutate: cancelJob } = useCancelJob();

  return (
    <>
      <JobDrawer
        open={isJobDrawerOpen}
        jobs={jobsData?.items ?? []}
        onClose={() => setJobDrawerOpen(false)}
        onCancelJob={(job) => cancelJob(job.id)}
        onViewLogs={(job) => setLogJob(job)}
      />
      
      <JobLogsModal 
        job={logJob} 
        open={!!logJob} 
        onClose={() => setLogJob(null)} 
      />
    </>
  );
}
