/**
 * LocalItemCard component for grid view (local-only items)
 */
import * as React from "react";
import { Play, BookOpen, HardDrive } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import type { LocalItem } from "@/types";

export function LocalItemCard({
  item,
  onPlay,
  className,
}: {
  item: LocalItem;
  onPlay?: (item: LocalItem) => void;
  className?: string;
}) {
  return (
    <Card
      data-testid="local-item-card"
      tabIndex={0}
      className={cn(
        "group relative overflow-hidden transition-shadow hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        className
      )}
    >
      <div className="relative aspect-square bg-muted flex items-center justify-center">
        <BookOpen className="h-16 w-16 text-muted-foreground/50" />
        <div className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-md border border-border bg-background/80 px-2 py-1 text-xs">
          <HardDrive className="h-3 w-3" />
          Local
        </div>
        <div className="absolute inset-0 flex items-center justify-center bg-black/60 opacity-0 transition-opacity group-hover:opacity-100">
          <Button
            size="icon"
            variant="secondary"
            className="h-14 w-14 rounded-full"
            onClick={(e) => {
              e.stopPropagation();
              onPlay?.(item);
            }}
            aria-label={`Play ${item.title}`}
          >
            <Play className="h-6 w-6" fill="currentColor" />
          </Button>
        </div>
      </div>

      <div className="p-4">
        <h3 className="line-clamp-1 font-semibold" title={item.title}>
          {item.title}
        </h3>
        <p className="line-clamp-1 text-sm text-muted-foreground" title={item.authors ?? undefined}>
          {item.authors || "Unknown Author"}
        </p>
        <div className="mt-3 flex items-center justify-between">
          <div className="text-xs text-muted-foreground">
            {(item.format ?? "audio").toUpperCase()}
          </div>
        </div>
      </div>
    </Card>
  );
}

