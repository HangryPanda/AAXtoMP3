/**
 * StatusBadge component for displaying book status
 */
import * as React from "react";
import {
  Cloud,
  Download,
  AlertCircle,
  Loader2,
  FileCheck,
  FileAudio,
  Book,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { STATUS_LABELS, type BookStatus } from "@/types";

const STATUS_STYLES: Record<BookStatus, string> = {
  NEW: "bg-gray-500 text-white",
  DOWNLOADING: "bg-blue-500 text-white",
  DOWNLOADED: "bg-cyan-500 text-white",
  VALIDATING: "bg-purple-500 text-white",
  VALIDATED: "bg-indigo-500 text-white",
  CONVERTING: "bg-yellow-500 text-white",
  COMPLETED: "bg-green-500 text-white",
  FAILED: "bg-red-500 text-white",
};

const STATUS_ICONS: Record<BookStatus, React.ElementType> = {
  NEW: Cloud,
  DOWNLOADING: Download,
  DOWNLOADED: FileCheck,
  VALIDATING: Loader2,
  VALIDATED: FileCheck,
  CONVERTING: FileAudio,
  COMPLETED: Book,
  FAILED: AlertCircle,
};

export interface StatusBadgeProps {
  status: BookStatus;
  showIcon?: boolean;
  showLabel?: boolean;
  className?: string;
}

export function StatusBadge({
  status,
  showIcon = false,
  showLabel = true,
  className,
}: StatusBadgeProps) {
  const Icon = STATUS_ICONS[status];
  const isAnimating = status === "DOWNLOADING" || status === "VALIDATING" || status === "CONVERTING";
  const iconOnly = showIcon && !showLabel;
  const iconOnlyCircle = iconOnly && status === "COMPLETED";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold",
        STATUS_STYLES[status],
        iconOnlyCircle && "h-6 w-6 justify-center rounded-full p-0",
        iconOnly && !iconOnlyCircle && "px-1.5",
        className
      )}
    >
      {showIcon && (
        <Icon
          className={cn(
            iconOnlyCircle ? "h-3.5 w-3.5" : iconOnly ? "h-3 w-3" : "h-3 w-3",
            isAnimating && "animate-spin"
          )}
          data-testid="status-icon"
        />
      )}
      {showLabel ? (
        STATUS_LABELS[status]
      ) : (
        <span className="sr-only">{STATUS_LABELS[status]}</span>
      )}
    </span>
  );
}
