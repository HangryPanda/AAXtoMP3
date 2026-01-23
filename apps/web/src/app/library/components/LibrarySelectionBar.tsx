"use client";

import { CheckSquare, Trash2, Download, FileAudio, Wrench, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

export interface LibrarySelectionBarProps {
  isSelectionMode: boolean;
  selectedCount: number;
  onToggleSelectionMode: () => void;
  onSelectAllPage: () => void;
  onClearSelection: () => void;
  onBatchDelete: () => void;
  onBatchDownload: () => void;
  onBatchConvert: () => void;
  onRepair: () => void;
  isRepairPending: boolean;
  onSync: () => void;
  isSyncing: boolean;
  lastSyncText: string;
  className?: string;
}

export function LibrarySelectionBar({
  isSelectionMode,
  selectedCount,
  onToggleSelectionMode,
  onSelectAllPage,
  onClearSelection,
  onBatchDelete,
  onBatchDownload,
  onBatchConvert,
  onRepair,
  isRepairPending,
  onSync,
  isSyncing,
  lastSyncText,
  className,
}: LibrarySelectionBarProps) {
  return (
    <div className={cn("flex items-center justify-between h-10 px-1", className)}>
      <div className="flex items-center gap-4">
        <Button 
          variant={isSelectionMode ? "default" : "outline"}
          size="sm" 
          onClick={onToggleSelectionMode}
          className={
            isSelectionMode
              ? "gap-2 bg-primary text-primary-foreground"
              : "gap-2 border-primary/60 text-primary hover:bg-primary/10"
          }
        >
          <CheckSquare className="w-4 h-4" />
          {isSelectionMode ? "Exit Selection" : "Select Items"}
        </Button>

        {isSelectionMode && (
          <>
            <span className="text-sm font-medium">{selectedCount} selected</span>
            <Button variant="ghost" size="sm" onClick={onSelectAllPage}>Select All Page</Button>
            <Button variant="ghost" size="sm" onClick={onClearSelection}>Clear</Button>
          </>
        )}
      </div>

      <div className="flex items-center gap-2">
        {isSelectionMode && selectedCount > 0 && (
          <>
            <Button size="sm" variant="destructive" className="gap-2" onClick={onBatchDelete}>
              <Trash2 className="w-4 h-4" />
              Delete Selected
            </Button>
            <Button size="sm" className="gap-2" onClick={onBatchDownload}>
              <Download className="w-4 h-4" />
              Download Selected
            </Button>
            <Button size="sm" className="gap-2" onClick={onBatchConvert}>
              <FileAudio className="w-4 h-4" />
              Convert Selected
            </Button>
          </>
        )}
        
        {!isSelectionMode && (
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={onRepair}
                disabled={isRepairPending}
                className="gap-2"
              >
                <Wrench className={cn("w-4 h-4", isRepairPending && "animate-spin")} />
                Repair
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={onSync}
                disabled={isSyncing}
                className="gap-2"
              >
                <RefreshCw className={cn("w-4 h-4", isSyncing && "animate-spin")} />
                Sync Audible
              </Button>
            </div>
            <div className="text-xs text-muted-foreground">
              {lastSyncText}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
