/**
 * ChapterList component for chapter navigation
 */
import * as React from "react";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/Progress";

export interface Chapter {
  id: string;
  title: string;
  startTime: number; // in seconds
  duration: number; // in seconds
}

export interface ChapterListProps {
  chapters: Chapter[];
  currentChapterId?: string;
  currentTimeInChapter?: number;
  showNumbers?: boolean;
  onChapterSelect?: (chapter: Chapter) => void;
  className?: string;
}

// Format seconds to MM:SS
function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function ChapterList({
  chapters,
  currentChapterId,
  currentTimeInChapter = 0,
  showNumbers = false,
  onChapterSelect,
  className,
}: ChapterListProps) {
  if (chapters.length === 0) {
    return (
      <div
        data-testid="chapter-list"
        className={cn(
          "flex h-full items-center justify-center text-muted-foreground",
          className
        )}
      >
        No chapters available
      </div>
    );
  }

  const handleKeyDown = (e: React.KeyboardEvent, chapter: Chapter) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onChapterSelect?.(chapter);
    }
  };

  return (
    <div
      data-testid="chapter-list"
      className={cn("overflow-y-auto", className)}
    >
      <ul role="list" className="divide-y divide-border">
        {chapters.map((chapter, index) => {
          const isActive = chapter.id === currentChapterId;
          const progressPercent = isActive && chapter.duration > 0
            ? (currentTimeInChapter / chapter.duration) * 100
            : 0;

          return (
            <li
              key={chapter.id}
              role="listitem"
              data-testid={`chapter-item-${chapter.id}`}
              tabIndex={0}
              onClick={() => onChapterSelect?.(chapter)}
              onKeyDown={(e) => handleKeyDown(e, chapter)}
              className={cn(
                "relative flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors hover:bg-accent",
                isActive && "bg-primary/10"
              )}
            >
              {/* Chapter Number */}
              {showNumbers && (
                <span className="w-6 shrink-0 text-center text-sm font-medium text-muted-foreground">
                  {index + 1}
                </span>
              )}

              {/* Chapter Info */}
              <div className="min-w-0 flex-1">
                <h4
                  className={cn(
                    "truncate text-sm",
                    isActive && "font-medium text-primary"
                  )}
                  title={chapter.title}
                >
                  {chapter.title}
                </h4>

                {/* Progress bar for current chapter */}
                {isActive && (
                  <div className="mt-1">
                    <Progress
                      value={progressPercent}
                      className="h-1"
                      data-testid="chapter-progress"
                    />
                  </div>
                )}
              </div>

              {/* Duration */}
              <span className="shrink-0 text-xs text-muted-foreground">
                {formatDuration(chapter.duration)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
