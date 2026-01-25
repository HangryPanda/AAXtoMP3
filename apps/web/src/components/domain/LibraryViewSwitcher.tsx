/**
 * LibraryViewSwitcher
 *
 * Segmented control for switching between Library, Downloading, and Converting views.
 * Shows badge counts for active jobs in each category.
 */

"use client";

import * as React from "react";
import { Library, Download, FileAudio } from "lucide-react";
import { cn } from "@/lib/utils";
import { useActiveJobs } from "@/hooks/useJobs";

export type LibraryViewType = "library" | "downloading" | "converting";

interface LibraryViewSwitcherProps {
  activeView: LibraryViewType;
  onViewChange: (view: LibraryViewType) => void;
  totalBooks?: number;
  className?: string;
}

interface ViewTab {
  id: LibraryViewType;
  label: string;
  icon: React.ElementType;
  getCount: (data: { downloadCount: number; convertCount: number; totalBooks: number }) => number;
  showBadge: boolean;
}

const VIEW_TABS: ViewTab[] = [
  {
    id: "library",
    label: "Library",
    icon: Library,
    getCount: ({ totalBooks }) => totalBooks,
    showBadge: false,
  },
  {
    id: "downloading",
    label: "Downloading",
    icon: Download,
    getCount: ({ downloadCount }) => downloadCount,
    showBadge: true,
  },
  {
    id: "converting",
    label: "Converting",
    icon: FileAudio,
    getCount: ({ convertCount }) => convertCount,
    showBadge: true,
  },
];

export function LibraryViewSwitcher({
  activeView,
  onViewChange,
  totalBooks = 0,
  className,
}: LibraryViewSwitcherProps) {
  const { data: activeJobs } = useActiveJobs();

  const downloadCount = React.useMemo(
    () => activeJobs?.items.filter((j) => j.task_type === "DOWNLOAD").length ?? 0,
    [activeJobs]
  );

  const convertCount = React.useMemo(
    () => activeJobs?.items.filter((j) => j.task_type === "CONVERT").length ?? 0,
    [activeJobs]
  );

  const counts = { downloadCount, convertCount, totalBooks };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-lg border border-border bg-muted/30 p-1",
        className
      )}
      role="tablist"
      aria-label="Library views"
    >
      {VIEW_TABS.map((tab) => {
        const isActive = activeView === tab.id;
        const count = tab.getCount(counts);
        const Icon = tab.icon;
        const hasActiveItems = tab.showBadge && count > 0;

        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            aria-controls={`${tab.id}-panel`}
            onClick={() => onViewChange(tab.id)}
            className={cn(
              "relative flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-all",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              isActive
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground hover:bg-background/50"
            )}
          >
            <Icon className={cn("h-4 w-4", hasActiveItems && !isActive && "text-primary")} />
            <span>{tab.label}</span>

            {/* Count badge */}
            {count > 0 && (
              <span
                className={cn(
                  "inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 text-xs font-semibold rounded-full",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : hasActiveItems
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {count}
              </span>
            )}

            {/* Animated indicator for active jobs */}
            {hasActiveItems && !isActive && (
              <span className="absolute top-1 right-1 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
