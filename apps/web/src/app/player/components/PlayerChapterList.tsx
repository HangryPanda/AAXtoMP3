import { ListMusic } from "lucide-react";
import { formatTime } from "@/lib/format";
import { PlayerChapter } from "../types";
import { cn } from "@/lib/utils";

interface PlayerChapterListProps {
  chapters: PlayerChapter[];
  currentChapterIndex: number | null;
  onChapterSelect: (chapter: PlayerChapter) => void;
  isChaptersSynthetic: boolean;
  className?: string;
  id?: string;
}

export function PlayerChapterList({
  chapters,
  currentChapterIndex,
  onChapterSelect,
  isChaptersSynthetic,
  className,
  id,
}: PlayerChapterListProps) {
  return (
    <div
      id={id}
      className={cn(
        "bg-card border border-border rounded-xl overflow-hidden shadow-sm flex flex-col",
        className
      )}
    >
      <div className="p-4 border-b border-border flex items-center justify-between shrink-0">
        <h2 className="font-semibold flex items-center gap-2">
          <ListMusic className="w-4 h-4 text-primary" />
          Chapters
        </h2>
        <div className="flex items-center gap-2">
          {isChaptersSynthetic && (
            <span className="text-xs text-muted-foreground">Loading...</span>
          )}
          <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
            {chapters.length}
          </span>
        </div>
      </div>
      <div className="flex-1 overflow-auto min-h-0">
        {chapters.length > 0 ? (
          <div className="divide-y divide-border">
            {chapters.map((chapter, i) => {
              const isActive = i === currentChapterIndex;
              return (
                <button
                  key={i}
                  onClick={() => onChapterSelect(chapter)}
                  className={cn(
                    "w-full px-4 py-3 text-left hover:bg-muted/50 transition-colors flex items-center justify-between group",
                    isActive && "bg-primary/10"
                  )}
                >
                  <span
                    className={cn(
                      "text-sm font-medium line-clamp-1 group-hover:text-primary transition-colors",
                      isActive && "text-primary"
                    )}
                  >
                    {chapter.title}
                  </span>
                  <span className="text-xs text-muted-foreground font-mono ml-2 shrink-0">
                    {formatTime(chapter.length_ms / 1000)}
                  </span>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="text-center text-muted-foreground py-12 px-6">
            <p className="text-sm font-medium text-foreground/70">
              No Chapters Available
            </p>
            <p className="text-xs mt-1">
              This book doesn&apos;t have chapter markers.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
