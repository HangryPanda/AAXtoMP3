/**
 * BookCard component for grid view
 */
import * as React from "react";
import Image from "next/image";
import { Play, Clock, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "./StatusBadge";
import { ActionMenu } from "./ActionMenu";
import { BookProgressOverlay, useBookDimmedState } from "./BookProgressOverlay";
import {
  canPlay,
  getCoverUrl,
  getPrimaryAuthor,
  getSeriesInfo,
  formatRuntime,
  type Book,
} from "@/types";

export interface BookCardProps {
  book: Book;
  selectable?: boolean;
  selected?: boolean;
  isCurrent?: boolean;
  isPlaying?: boolean;
  onSelect?: (book: Book, selected: boolean) => void;
  onPlay?: (book: Book) => void;
  onAction?: (action: string, book: Book) => void;
  onDownload?: (book: Book) => void;
  onConvert?: (book: Book) => void;
  onViewDetails?: (book: Book) => void;
  className?: string;
}

export function BookCard({
  book,
  selectable = false,
  selected = false,
  isCurrent = false,
  isPlaying = false,
  onSelect,
  onPlay,
  onAction,
  onDownload,
  onConvert,
  onViewDetails,
  className,
}: BookCardProps) {
  const coverUrl = getCoverUrl(book);
  const author = getPrimaryAuthor(book);
  const seriesInfo = getSeriesInfo(book);
  const duration = formatRuntime(book.runtime_length_min);
  const isPlayable = canPlay(book);
  const isDimmed = useBookDimmedState(book.asin);
  
  // Show playing state if this is the current book
  const showPlaying = isCurrent && isPlaying;

  const handlePlay = (e: React.MouseEvent) => {
    e.stopPropagation();
    onPlay?.(book);
  };

  const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation();
    onSelect?.(book, e.target.checked);
  };

  return (
    <Card
      data-testid="book-card"
      tabIndex={0}
      className={cn(
        "group relative overflow-hidden transition-shadow hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        selected && "ring-2 ring-primary",
        isDimmed && "opacity-60",
        className
      )}
    >
      {/* Selection Checkbox */}
      {selectable && (
        <div className="absolute left-2 top-2 z-20">
          <input
            type="checkbox"
            checked={selected}
            onChange={handleCheckboxChange}
            className="h-5 w-5 rounded border-input bg-background/80 text-primary shadow-sm focus:ring-ring"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}

      {/* Cover Image */}
      <div className={cn(
        "relative aspect-square bg-muted transition-all",
        showPlaying && "ring-4 ring-primary ring-offset-2 ring-offset-background"
      )}>
        {coverUrl ? (
          <Image
            src={coverUrl}
            alt={book.title}
            fill
            className="object-cover"
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
          />
        ) : (
          <div
            data-testid="book-cover-placeholder"
            className="flex h-full items-center justify-center"
          >
            <BookOpen className="h-16 w-16 text-muted-foreground/50" />
          </div>
        )}

        {/* Overlay with play button - always show if playing, otherwise hover */}
        <div className={cn(
          "absolute inset-0 flex items-center justify-center bg-black/40 transition-opacity",
          showPlaying || isCurrent ? "opacity-100" : "opacity-0 group-hover:opacity-100"
        )}>
          <Button
            size="icon"
            variant="secondary"
            className={cn("h-14 w-14 rounded-full shadow-lg", showPlaying && "scale-110")}
            onClick={handlePlay}
            disabled={!isPlayable}
            aria-label={showPlaying ? `Pause ${book.title}` : `Play ${book.title}`}
          >
            {showPlaying ? (
              // Simple equalizer-like animation or pause icon
              <div className="flex gap-1 items-end h-6 pb-1">
                <span className="w-1 bg-current animate-[bounce_1s_infinite] h-3"></span>
                <span className="w-1 bg-current animate-[bounce_1.2s_infinite] h-5"></span>
                <span className="w-1 bg-current animate-[bounce_0.8s_infinite] h-4"></span>
              </div>
            ) : (
              <Play className="h-6 w-6 ml-1" fill="currentColor" />
            )}
          </Button>
        </div>

        {/* Progress Overlay for active jobs */}
        <BookProgressOverlay asin={book.asin} />

        {/* Status Badge */}
        <div className="absolute right-2 top-2">
          <StatusBadge status={book.status} showIcon showLabel={false} />
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Title */}
        <h3 className="line-clamp-1 font-semibold" title={book.title}>
          {book.title}
        </h3>

        {/* Author */}
        <p className="line-clamp-1 text-sm text-muted-foreground" title={author}>
          {author}
        </p>

        {/* Series */}
        {seriesInfo && (
          <p
            className="mt-1 line-clamp-1 text-xs text-muted-foreground/70"
            title={seriesInfo}
          >
            {seriesInfo}
          </p>
        )}

        {/* Footer */}
        <div className="mt-3 flex items-center justify-between">
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            <span>{duration}</span>
          </div>

          <ActionMenu
            book={book}
            onDownload={onDownload}
            onConvert={onConvert}
            onPlay={onPlay}
            onViewDetails={onViewDetails}
            onDelete={() => onAction?.("delete", book)}
          />
        </div>
      </div>
    </Card>
  );
}
