import Image from "next/image";
import { FastForward, Play, Headphones } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/Dialog";
import {
  getCoverUrl,
  getPrimaryAuthor,
  getSeriesInfo,
  formatRuntime,
  Book,
} from "@/types";

interface SeriesModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  nextInSeries: Book | null;
  onPlayNext: () => void;
}

export function SeriesModal({
  open,
  onOpenChange,
  nextInSeries,
  onPlayNext,
}: SeriesModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FastForward className="w-5 h-5 text-primary" />
            Next in Series
          </DialogTitle>
          <DialogDescription>
            You&apos;ve finished this book! Ready for the next one?
          </DialogDescription>
        </DialogHeader>

        {nextInSeries && (
          <div className="flex gap-4 items-start py-4">
            {/* Next book cover */}
            <div className="w-20 h-20 shrink-0 rounded-lg overflow-hidden bg-muted">
              {getCoverUrl(nextInSeries, "500") ? (
                <Image
                  src={getCoverUrl(nextInSeries, "500")!}
                  alt={nextInSeries.title}
                  width={80}
                  height={80}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <Headphones className="w-8 h-8 text-muted-foreground/50" />
                </div>
              )}
            </div>

            {/* Next book info */}
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-base line-clamp-2">
                {nextInSeries.title}
              </h3>
              <p className="text-sm text-muted-foreground mt-1">
                {getPrimaryAuthor(nextInSeries)}
              </p>
              {nextInSeries.series?.[0] && (
                <p className="text-xs text-primary mt-1">
                  {getSeriesInfo(nextInSeries)}
                </p>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                {formatRuntime(nextInSeries.runtime_length_min)}
              </p>
            </div>
          </div>
        )}

        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Not Now
          </Button>
          <Button onClick={onPlayNext}>
            <Play className="w-4 h-4 mr-2" />
            Play Now
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
