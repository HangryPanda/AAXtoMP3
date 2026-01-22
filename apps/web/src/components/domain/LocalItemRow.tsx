/**
 * LocalItemRow component for list view (local-only items)
 */
import * as React from "react";
import { Play, BookOpen, HardDrive } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import type { LocalItem } from "@/types";

export function LocalItemRow({
  item,
  onRowClick,
  onPlay,
  className,
}: {
  item: LocalItem;
  onRowClick?: (item: LocalItem) => void;
  onPlay?: (item: LocalItem) => void;
  className?: string;
}) {
  return (
    <div
      data-testid="local-item-row"
      role="row"
      onClick={() => onRowClick?.(item)}
      className={cn(
        "flex items-center gap-4 rounded-lg border border-transparent px-4 py-3 transition-colors hover:bg-accent",
        onRowClick && "cursor-pointer",
        className
      )}
    >
      <div className="h-12 w-12 shrink-0 overflow-hidden rounded bg-muted flex items-center justify-center">
        <BookOpen className="h-6 w-6 text-muted-foreground/50" />
      </div>

      <div className="min-w-0 flex-1">
        <h3 className="truncate font-medium" title={item.title}>
          {item.title}
        </h3>
        <p className="truncate text-sm text-muted-foreground" title={item.authors ?? undefined}>
          {item.authors || "Unknown Author"}
        </p>
      </div>

      <div className="hidden w-24 shrink-0 md:flex items-center justify-end">
        <span className="inline-flex items-center gap-1 rounded-md border border-border bg-background/80 px-2 py-1 text-xs">
          <HardDrive className="h-3 w-3" />
          Local
        </span>
      </div>

      <div className="w-24 shrink-0 text-right text-sm text-muted-foreground">
        {(item.format ?? "audio").toUpperCase()}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={(e) => {
            e.stopPropagation();
            onPlay?.(item);
          }}
          aria-label={`Play ${item.title}`}
        >
          <Play className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
