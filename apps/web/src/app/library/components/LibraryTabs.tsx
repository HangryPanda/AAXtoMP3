"use client";

import { cn } from "@/lib/utils";

export interface LibraryTabsProps {
  contentType: "audiobook" | "podcast";
  onContentTypeChange: (type: "audiobook" | "podcast") => void;
  className?: string;
}

export function LibraryTabs({
  contentType,
  onContentTypeChange,
  className,
}: LibraryTabsProps) {
  return (
    <div className={cn("flex items-center gap-2 px-1", className)}>
      <div className="inline-flex items-center rounded-md border border-border bg-muted/30 p-1">
        <button
          type="button"
          onClick={() => onContentTypeChange("audiobook")}
          className={cn(
            "px-3 py-1.5 text-sm font-medium rounded-sm transition-colors",
            contentType === "audiobook"
              ? "bg-background shadow-sm text-foreground"
              : "text-muted-foreground hover:bg-background/50"
          )}
          aria-pressed={contentType === "audiobook"}
        >
          Audiobooks
        </button>
        <button
          type="button"
          onClick={() => onContentTypeChange("podcast")}
          className={cn(
            "px-3 py-1.5 text-sm font-medium rounded-sm transition-colors",
            contentType === "podcast"
              ? "bg-background shadow-sm text-foreground"
              : "text-muted-foreground hover:bg-background/50"
          )}
          aria-pressed={contentType === "podcast"}
        >
          Podcasts
        </button>
      </div>
    </div>
  );
}
