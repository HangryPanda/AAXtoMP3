import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/Dialog";
import {
  formatRuntime,
  getSeriesInfo,
  Book,
  LocalItem,
  BookDetailsResponse,
} from "@/types";
import { formatTime, formatBytes } from "@/lib/format";

interface MetadataModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  book?: Book | null;
  localItem?: LocalItem | null;
  bookDetails?: BookDetailsResponse | null;
  duration: number;
}

export function MetadataModal({
  open,
  onOpenChange,
  book,
  localItem,
  bookDetails,
  duration,
}: MetadataModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Book Details</DialogTitle>
          <DialogDescription>
            Extended information about this audiobook
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 text-sm">
          <div className="grid grid-cols-[120px_1fr] gap-2">
            <span className="text-muted-foreground">Title</span>
            <span className="font-medium">
              {book?.title || localItem?.title || "N/A"}
            </span>
          </div>
          {book?.subtitle && (
            <div className="grid grid-cols-[120px_1fr] gap-2">
              <span className="text-muted-foreground">Subtitle</span>
              <span>{book.subtitle}</span>
            </div>
          )}
          <div className="grid grid-cols-[120px_1fr] gap-2">
            <span className="text-muted-foreground">Author(s)</span>
            <span>
              {book?.authors?.map((a) => a.name).join(", ") ||
                localItem?.authors ||
                "N/A"}
            </span>
          </div>
          <div className="grid grid-cols-[120px_1fr] gap-2">
            <span className="text-muted-foreground">Narrator(s)</span>
            <span>
              {book?.narrators?.map((n) => n.name).join(", ") || "N/A"}
            </span>
          </div>
          {book?.series && book.series.length > 0 && (
            <div className="grid grid-cols-[120px_1fr] gap-2">
              <span className="text-muted-foreground">Series</span>
              <span>{getSeriesInfo(book)}</span>
            </div>
          )}
          {book?.publisher && (
            <div className="grid grid-cols-[120px_1fr] gap-2">
              <span className="text-muted-foreground">Publisher</span>
              <span>{book.publisher}</span>
            </div>
          )}
          {book?.language && (
            <div className="grid grid-cols-[120px_1fr] gap-2">
              <span className="text-muted-foreground">Language</span>
              <span className="capitalize">{book.language}</span>
            </div>
          )}
          <div className="grid grid-cols-[120px_1fr] gap-2">
            <span className="text-muted-foreground">Duration</span>
            <span>
              {book
                ? formatRuntime(book.runtime_length_min)
                : formatTime(duration)}
            </span>
          </div>
          <div className="grid grid-cols-[120px_1fr] gap-2">
            <span className="text-muted-foreground">Format</span>
            <span className="uppercase">
              {localItem?.format || book?.conversion_format || "N/A"}
            </span>
          </div>
          {bookDetails?.technical?.file_size && (
            <div className="grid grid-cols-[120px_1fr] gap-2">
              <span className="text-muted-foreground">File Size</span>
              <span>{formatBytes(bookDetails.technical.file_size)}</span>
            </div>
          )}
          {book?.asin && (
            <div className="grid grid-cols-[120px_1fr] gap-2">
              <span className="text-muted-foreground">ASIN</span>
              <span className="font-mono text-xs">{book.asin}</span>
            </div>
          )}
          {book?.local_path_converted && (
            <div className="grid grid-cols-[120px_1fr] gap-2">
              <span className="text-muted-foreground">File Path</span>
              <span className="font-mono text-xs break-all">
                {book.local_path_converted}
              </span>
            </div>
          )}
          {bookDetails?.description && (
            <div className="pt-4 border-t">
              <span className="text-muted-foreground block mb-2">
                Description
              </span>
              <p className="text-sm leading-relaxed">
                {bookDetails.description}
              </p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
