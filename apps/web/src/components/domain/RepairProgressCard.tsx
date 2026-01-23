/**
 * Displays progress for the latest REPAIR job.
 */

import * as React from "react";
import { AlertTriangle, CheckCircle2, Clock, Wrench } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Progress } from "@/components/ui/Progress";
import { cn } from "@/lib/utils";
import { useJobsFiltered } from "@/hooks/useJobs";
import { useUIStore } from "@/store/uiStore";
import { isJobActive, type Job, type JobStatus } from "@/types";

const STATUS_BADGE_VARIANTS: Record<
  JobStatus,
  "default" | "secondary" | "destructive" | "success" | "warning" | "info"
> = {
  PENDING: "secondary",
  QUEUED: "info",
  RUNNING: "warning",
  PAUSED: "secondary",
  COMPLETED: "success",
  FAILED: "destructive",
  CANCELLED: "secondary",
};

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString();
}

function getSubtitle(job: Job): string {
  if (job.status === "RUNNING") return "Repairing your library index from disk/manifests…";
  if (job.status === "PAUSED") return "Repair paused…";
  if (job.status === "QUEUED" || job.status === "PENDING") return "Repair queued…";
  if (job.status === "COMPLETED") return `Last run: ${formatWhen(job.completed_at ?? job.started_at ?? job.created_at)}`;
  if (job.status === "FAILED") return "Repair failed.";
  return `Last run: ${formatWhen(job.created_at)}`;
}

export function RepairProgressCard({ className }: { className?: string }) {
  const setJobDrawerOpen = useUIStore((s) => s.setJobDrawerOpen);

  const { data } = useJobsFiltered(
    { task_type: "REPAIR", limit: 1 },
    {
      refetchInterval: false,
    }
  );

  const job = data?.items?.[0];
  if (!job) return null;

  const isActive = isJobActive(job);
  const Icon = job.status === "FAILED" ? AlertTriangle : job.status === "COMPLETED" ? CheckCircle2 : Wrench;

  return (
    <Card className={cn("border-border/60", className)}>
      <CardHeader className="py-4">
        <CardTitle className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2 text-sm">
            <Icon className={cn("h-4 w-4", isActive && "animate-pulse")} />
            Repair
          </span>
          <div className="flex items-center gap-2">
            <Badge variant={STATUS_BADGE_VARIANTS[job.status]}>
              {job.status.toLowerCase()}
            </Badge>
            <Button size="sm" variant="outline" onClick={() => setJobDrawerOpen(true)}>
              View Jobs
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0 pb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm text-muted-foreground">{getSubtitle(job)}</p>
            <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground/80">
              <Clock className="h-3 w-3" />
              Created: {formatWhen(job.created_at)}
            </p>
            {job.error_message && (
              <p className="mt-2 text-xs text-destructive line-clamp-3">
                {job.error_message}
              </p>
            )}
          </div>

          {job.status === "RUNNING" && (
            <div className="w-[220px] shrink-0">
              <Progress value={job.progress_percent} className="h-2" />
              <div className="mt-1 text-right text-xs text-muted-foreground">
                {job.progress_percent}%
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
