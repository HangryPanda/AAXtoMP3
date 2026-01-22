"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Terminal } from "@/components/domain/Terminal";
import { useJobWebSocket } from "@/hooks/useJobWebSocket";
import type { Job } from "@/types";

interface JobLogsModalProps {
  job: Job | null;
  open: boolean;
  onClose: () => void;
}

export function JobLogsModal({ job, open, onClose }: JobLogsModalProps) {
  const { logs, isConnected } = useJobWebSocket(job?.id, {
    autoConnect: open && !!job,
  });

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between">
            <span>Logs for Job {job?.id}</span>
            <span className={isConnected ? "text-green-500 text-xs" : "text-red-500 text-xs"}>
              {isConnected ? "Connected" : "Disconnected"}
            </span>
          </DialogTitle>
        </DialogHeader>
        <Terminal
          logs={logs}
          height={400}
          showSearch
          showCopyButton
          showClearButton
        />
      </DialogContent>
    </Dialog>
  );
}
