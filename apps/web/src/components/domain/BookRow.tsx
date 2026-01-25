/**
 * BookRow component for table/list view
 */
import * as React from "react";
import Image from "next/image";
import { Play, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "./StatusBadge";
import { ActionMenu } from "./ActionMenu";
import {
  canPlay,
  getCoverUrl,
  getPrimaryAuthor,
  getPrimaryNarrator,
  formatRuntime,
  type Book,
} from "@/types";
import { formatDate } from "@/lib/format";

export interface BookRowProps {
  book: Book;
  selectable?: boolean;
  selected?: boolean;
  isCurrent?: boolean;
  isPlaying?: boolean;
  onSelect?: (book: Book, selected: boolean) => void;
  onRowClick?: (book: Book) => void;
  onPlay?: (book: Book) => void;
  onDownload?: (book: Book) => void;
  onConvert?: (book: Book) => void;
  onViewDetails?: (book: Book) => void;
  onDelete?: (book: Book) => void;
  className?: string;
}

export function BookRow({
  book,
  selectable = false,
  selected = false,
  isCurrent = false,
  isPlaying = false,
  onSelect,
  onRowClick,
  onPlay,
  onDownload,
  onConvert,
  onViewDetails,
  className,
}: BookRowProps) {
  const coverUrl = getCoverUrl(book);
  const author = getPrimaryAuthor(book);
  const narrator = getPrimaryNarrator(book);
  const duration = formatRuntime(book.runtime_length_min);
  const purchaseDate = formatDate(book.purchase_date);
  const isPlayable = canPlay(book);
  
  const showPlaying = isCurrent && isPlaying;

  const handleRowClick = () => {
    onRowClick?.(book);
  };

  const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation();
    onSelect?.(book, e.target.checked);
  };

  const handlePlayClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onPlay?.(book);
  };

  return (
    <div
      data-testid="book-row"
      role="row"
      onClick={handleRowClick}
      className={cn(
        "flex items-center gap-4 rounded-lg border border-transparent px-4 py-3 transition-colors hover:bg-accent",
        selected && "bg-primary/5 border-primary/20",
        isCurrent && "bg-accent/50",
        onRowClick && "cursor-pointer",
        className
      )}
    >
      {/* Checkbox */}
      {selectable && (
        <input
          type="checkbox"
          checked={selected}
          onChange={handleCheckboxChange}
          className="h-4 w-4 rounded border-input text-primary focus:ring-ring"
          onClick={(e) => e.stopPropagation()}
        />
      )}

      {/* Cover */}
      <div className={cn(
        "h-12 w-12 shrink-0 overflow-hidden rounded bg-muted relative",
        showPlaying && "ring-2 ring-primary ring-offset-1"
      )}>
        {coverUrl ? (
          <Image
            src={coverUrl}
            alt={book.title}
            width={48}
            height={48}
            className="h-12 w-12 object-cover"
          />
        ) : (
          <div
            data-testid="book-cover-placeholder"
            className="flex h-full items-center justify-center"
          >
            <BookOpen className="h-6 w-6 text-muted-foreground/50" />
          </div>
        )}
        
        {/* Playing Overlay */}
        {showPlaying && (
          <div className="absolute inset-0 bg-black/30 flex items-center justify-center">
            <span className="w-1 h-3 bg-white animate-bounce" />
          </div>
        )}
      </div>

      {/* Title & Author */}
      <div className="min-w-0 flex-1">
        <h3 className={cn("truncate font-medium", isCurrent && "text-primary")} title={book.title}>
          {book.title}
        </h3>
        <p className="truncate text-sm text-muted-foreground" title={author}>
          {author}
        </p>
      </div>

      {/* Narrator */}
      <div className="hidden w-32 shrink-0 md:block">
        <p className="truncate text-sm text-muted-foreground" title={narrator}>
          {narrator}
        </p>
      </div>

      {/* Duration */}
      <div className="hidden w-16 shrink-0 text-right text-sm text-muted-foreground sm:block">
        {duration}
      </div>

      {/* Purchase Date */}
      <div className="hidden w-28 shrink-0 text-right text-sm text-muted-foreground lg:block">
        {purchaseDate}
      </div>

      {/* Status */}
      <div className="w-24 shrink-0">
        <StatusBadge status={book.status} showIcon showLabel={false} />
      </div>

      {/* Actions */}
      <div className="flex shrink-0 items-center gap-2">
        <Button
          variant={showPlaying ? "default" : "ghost"}
          size="icon"
          className={cn("h-8 w-8", showPlaying && "h-8 w-8 rounded-full")}
          onClick={handlePlayClick}
          disabled={!isPlayable}
          aria-label={showPlaying ? `Pause ${book.title}` : `Play ${book.title}`}
        >
          {showPlaying ? (
            // Pause icon
            <div className="flex gap-0.5 h-3 items-center">
              <span className="w-1 bg-current h-full" />
              <span className="w-1 bg-current h-full" />
            </div>
          ) : (
            <Play className="h-4 w-4" />
          )}
        </Button>

        <ActionMenu
          book={book}
          onDownload={onDownload}
          onConvert={onConvert}
          onPlay={onPlay}
          onViewDetails={onViewDetails}
        />
      </div>
    </div>
  );
}
