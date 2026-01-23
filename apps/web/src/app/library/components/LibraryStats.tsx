"use client";

import { AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { RepairPreview } from "@/types";

export interface LibraryStatsProps {
  totalBooks: number;
  downloadedCount: number;
  convertedCount: number;
  downloadQueueCount: number;
  convertQueueCount: number;
  inProgressCount: number;
  failedCount: number;
  downloadingTotal: number;
  convertingTotal: number;
  onOpenProgressPopover: () => void;
  repairPreview?: RepairPreview;
}

export function LibraryStats({
  totalBooks,
  downloadedCount,
  convertedCount,
  downloadQueueCount,
  convertQueueCount,
  inProgressCount,
  failedCount,
  downloadingTotal,
  convertingTotal,
  onOpenProgressPopover,
  repairPreview,
}: LibraryStatsProps) {
  return (
    <div className="flex gap-4 mb-6 overflow-x-auto pb-2">
      {/* Total Books */}
      <div className="bg-card border border-border rounded-lg px-4 py-3 min-w-[140px] shadow-sm">
        <div className="text-2xl font-bold">{totalBooks}</div>
        <div className="text-sm text-muted-foreground">Total Books</div>
      </div>

      {/* Downloaded */}
      <div className="bg-card border border-border rounded-lg px-4 py-3 min-w-[160px] shadow-sm">
        <div className="text-2xl font-bold text-cyan-600 dark:text-cyan-500">
          {downloadedCount}
        </div>
        <div className="text-sm text-muted-foreground">Downloaded</div>
        <div className="text-xs text-muted-foreground/80">
          Download queue: {downloadQueueCount}
        </div>
        {repairPreview?.downloaded_on_disk_total !== undefined && (
          <div className="text-[11px] text-muted-foreground/80">
            On disk: {repairPreview.downloaded_on_disk_total} (orphans: {repairPreview.orphan_downloads})
          </div>
        )}
      </div>

      {/* Converted */}
      <div className="bg-card border border-border rounded-lg px-4 py-3 min-w-[140px] shadow-sm">
        <div className="text-2xl font-bold text-green-600 dark:text-green-500">
          {convertedCount}
        </div>
        <div className="text-sm text-muted-foreground">Converted</div>
        <div className="text-xs text-muted-foreground/80">
          Convert queue: {convertQueueCount}
        </div>
        {repairPreview?.converted_m4b_files_on_disk_total !== undefined && (
          <div className="text-[11px] text-muted-foreground/80">
            M4B files: {repairPreview.converted_m4b_files_on_disk_total} (local: {repairPreview.orphan_conversions})
          </div>
        )}
        {repairPreview?.misplaced_files_count !== undefined && repairPreview.misplaced_files_count > 0 && (
          <div className="text-[11px] text-amber-600 dark:text-amber-500">
            Misplaced: {repairPreview.misplaced_files_count}
          </div>
        )}
        {repairPreview && (
          <div className="text-xs text-muted-foreground/80">
            Of downloaded: {repairPreview.converted_of_downloaded}
          </div>
        )}
      </div>

      {/* In Progress */}
      <div 
        className="bg-card border border-border rounded-lg px-4 py-3 min-w-[160px] shadow-sm cursor-pointer hover:bg-muted/50 transition-colors relative"
        onClick={onOpenProgressPopover}
      >
        {inProgressCount > 0 && (
          <span className="absolute top-3 right-3 flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-500"></span>
          </span>
        )}
        {failedCount > 0 && (
           <span className="absolute top-3 right-3 flex h-3 w-3 items-center justify-center">
             <AlertCircle className="h-3 w-3 text-destructive animate-pulse" />
           </span>
        )}
        <div className="text-2xl font-bold text-blue-600 dark:text-blue-500 flex items-center gap-2">
          {inProgressCount}
          {failedCount > 0 && <span className="text-sm font-normal text-destructive ml-1">({failedCount} failed)</span>}
        </div>
        <div className="text-sm text-muted-foreground">In Progress</div>
        <div className="text-xs text-muted-foreground/80">
          Downloading: {downloadingTotal}
        </div>
        <div className="text-xs text-muted-foreground/80">
          Converting: {convertingTotal}
        </div>
      </div>
    </div>
  );
}
