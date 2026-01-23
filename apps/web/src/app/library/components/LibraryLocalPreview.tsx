"use client";

import { Button } from "@/components/ui/Button";
import { LocalItemCard } from "@/components/domain/LocalItemCard";
import { LocalItemRow } from "@/components/domain/LocalItemRow";
import { cn } from "@/lib/utils";
import type { LocalItem } from "@/types";

export interface LibraryLocalPreviewProps {
  items: LocalItem[];
  total: number;
  viewMode: "grid" | "list";
  onViewLocal: () => void;
  onPlay: (id: string) => void;
}

export function LibraryLocalPreview({
  items,
  total,
  viewMode,
  onViewLocal,
  onPlay,
}: LibraryLocalPreviewProps) {
  if (!items.length) return null;

  return (
    <section className="mb-8">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-muted-foreground">
          Local-only ({total})
        </h2>
        <Button
          size="sm"
          variant="outline"
          onClick={onViewLocal}
        >
          View Local
        </Button>
      </div>
      <div
        className={cn(
          viewMode === "grid"
            ? "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6"
            : "space-y-1"
        )}
      >
        {items.map((it) =>
          viewMode === "grid" ? (
            <LocalItemCard
              key={it.id}
              item={it}
              onPlay={() => onPlay(it.id)}
            />
          ) : (
            <LocalItemRow
              key={it.id}
              item={it}
              onRowClick={() => onPlay(it.id)}
              onPlay={() => onPlay(it.id)}
            />
          )
        )}
      </div>
    </section>
  );
}
