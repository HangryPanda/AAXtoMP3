import * as React from "react";
import {
  Play,
  Pause,
  SkipForward,
  SkipBack,
  RotateCcw,
  RotateCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";

export interface StickyPlayerControlsProps extends React.HTMLAttributes<HTMLDivElement> {
  isPlaying: boolean;
  isLoading?: boolean;
  onPlayPause: () => void;
  onSkipBack: () => void;
  onSkipForward: () => void;
  onPrevChapter?: () => void;
  onNextChapter?: () => void;
}

export function StickyPlayerControls({
  isPlaying,
  isLoading,
  onPlayPause,
  onSkipBack,
  onSkipForward,
  onPrevChapter,
  onNextChapter,
  className,
  ...props
}: StickyPlayerControlsProps) {
  return (
    <div className={cn("flex items-center gap-1 md:gap-3 shrink-0", className)} {...props}>
      {/* Skip Back 15s */}
      <Button
        variant="ghost"
        size="icon"
        className="relative h-9 w-9"
        onClick={onSkipBack}
        aria-label="Skip back 15 seconds"
      >
        <RotateCcw className="h-5 w-5" />
        <span className="absolute text-[8px] font-bold top-[13px]">15</span>
      </Button>

      {/* Prev Chapter */}
      {onPrevChapter && (
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 hidden md:flex"
          onClick={onPrevChapter}
          aria-label="Previous chapter"
        >
          <SkipBack className="h-5 w-5" />
        </Button>
      )}

      {/* Play/Pause */}
      <Button
        variant="default"
        size="icon"
        className="h-12 w-12 rounded-full shadow-md bg-primary hover:scale-105 transition-transform"
        onClick={onPlayPause}
        disabled={isLoading}
        aria-label={isPlaying ? "Pause" : "Play"}
      >
        {isPlaying ? (
          <Pause className="h-6 w-6" fill="currentColor" />
        ) : (
          <Play className="h-6 w-6 ml-1" fill="currentColor" />
        )}
      </Button>

      {/* Next Chapter */}
      {onNextChapter && (
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 hidden md:flex"
          onClick={onNextChapter}
          aria-label="Next chapter"
        >
          <SkipForward className="h-5 w-5" />
        </Button>
      )}

      {/* Skip Forward 15s */}
      <Button
        variant="ghost"
        size="icon"
        className="relative h-9 w-9"
        onClick={onSkipForward}
        aria-label="Skip forward 15 seconds"
      >
        <RotateCw className="h-5 w-5" />
        <span className="absolute text-[8px] font-bold top-[13px]">15</span>
      </Button>
    </div>
  );
}
