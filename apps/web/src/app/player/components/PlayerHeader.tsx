import { formatRuntime, Book, LocalItem } from "@/types";
import { PlayerChapter } from "../types";
import { formatTime } from "@/lib/format";

interface PlayerHeaderProps {
  title: string;
  author: string;
  book?: Book | null;
  localItem?: LocalItem | null;
  currentChapter?: PlayerChapter | null;
  duration: number;
}

export function PlayerHeader({
  title,
  author,
  book,
  localItem,
  currentChapter,
  duration,
}: PlayerHeaderProps) {
  return (
    <div className="text-center mb-8 w-full">
      <h1 className="text-2xl lg:text-3xl font-bold tracking-tight mb-2 line-clamp-2">
        {title}
      </h1>
      <p className="text-base lg:text-lg text-muted-foreground mb-3">
        {author}
      </p>
      <div className="flex items-center justify-center gap-3 text-sm text-muted-foreground font-medium flex-wrap">
        <span className="bg-secondary px-3 py-1 rounded-full">
          {(
            localItem?.format ??
            book?.conversion_format ??
            "audio"
          ).toUpperCase()}
        </span>
        <span>
          {book
            ? formatRuntime(book.runtime_length_min)
            : formatTime(duration)}
        </span>
        {currentChapter && (
          <span className="text-primary">{currentChapter.title}</span>
        )}
      </div>
    </div>
  );
}
