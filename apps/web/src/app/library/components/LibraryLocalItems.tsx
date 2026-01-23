"use client";

import { useRouter } from "next/navigation";
import { LocalItemCard } from "@/components/domain/LocalItemCard";
import { LocalItemRow } from "@/components/domain/LocalItemRow";
import { cn } from "@/lib/utils";
import type { LocalItem } from "@/types";

export interface LibraryLocalItemsProps {
  items: LocalItem[];
  viewMode: "grid" | "list";
  className?: string;
}

export function LibraryLocalItems({
  items,
  viewMode,
  className,
}: LibraryLocalItemsProps) {
  const router = useRouter();

  return (
    <div
      className={cn(
        "pb-10",
        viewMode === "grid"
          ? "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6"
          : "space-y-1",
        className
      )}
    >
      {items.map((it) =>
        viewMode === "grid" ? (
          <LocalItemCard
            key={it.id}
            item={it}
            onPlay={() => router.push(`/player?local_id=${it.id}`)}
          />
        ) : (
          <LocalItemRow
            key={it.id}
            item={it}
            onRowClick={() => router.push(`/player?local_id=${it.id}`)}
            onPlay={() => router.push(`/player?local_id=${it.id}`)}
          />
        )
      )}
    </div>
  );
}
