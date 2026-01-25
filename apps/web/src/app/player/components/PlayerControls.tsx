import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  RotateCw,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

interface PlayerControlsProps {
  isPlaying: boolean;
  isLoading: boolean;
  canPlay: boolean;
  hasChapters: boolean;
  isLastChapter: boolean;
  onToggle: () => void;
  onSeekRelative: (seconds: number) => void;
  onNextChapter: () => void;
  onPrevChapter: () => void;
}

export function PlayerControls({
  isPlaying,
  isLoading,
  canPlay,
  hasChapters,
  isLastChapter,
  onToggle,
  onSeekRelative,
  onNextChapter,
  onPrevChapter,
}: PlayerControlsProps) {
  return (
    <div className="flex items-center gap-4 lg:gap-8 mb-8">
      {/* Previous Chapter */}
      <Button
        variant="ghost"
        size="icon"
        className="h-10 w-10 lg:h-12 lg:w-12 rounded-full"
        onClick={onPrevChapter}
        disabled={!hasChapters}
        title="Previous Chapter (Shift+P)"
      >
        <SkipBack className="w-5 h-5 lg:w-6 lg:h-6" />
      </Button>

      {/* Skip Back */}
      <Button
        variant="ghost"
        size="icon"
        className="h-10 w-10 lg:h-12 lg:w-12 rounded-full"
        onClick={() => onSeekRelative(-15)}
        title="Skip back 15s (←)"
      >
        <div className="relative flex items-center justify-center">
          <RotateCcw className="!w-7 !h-7 lg:!w-9 lg:!h-9" strokeWidth={0.75} />
          <span className="absolute text-[6px] lg:text-xs font-semibold">
            15
          </span>
        </div>
      </Button>

      {/* Play/Pause */}
      <Button
        onClick={onToggle}
        disabled={!canPlay || isLoading}
        className="h-16 w-16 lg:h-20 lg:w-20 rounded-full shadow-xl hover:scale-105 transition-transform"
        title="Play/Pause (Space)"
      >
        {isLoading ? (
          <Loader2 className="w-8 h-8 lg:w-10 lg:h-10 animate-spin" />
        ) : isPlaying ? (
          <Pause className="w-8 h-8 lg:w-10 lg:h-10 fill-current" />
        ) : (
          <Play className="w-8 h-8 lg:w-10 lg:h-10 ml-1 fill-current" />
        )}
      </Button>

      {/* Skip Forward */}
      <Button
        variant="ghost"
        size="icon"
        className="h-10 w-10 lg:h-12 lg:w-12 rounded-full"
        onClick={() => onSeekRelative(30)}
        title="Skip forward 30s (→)"
      >
        <div className="relative flex items-center justify-center">
          <RotateCw className="!w-7 !h-7 lg:!w-9 lg:!h-9" strokeWidth={0.75} />
          <span className="absolute text-[8px] lg:text-xs font-semibold">
            30
          </span>
        </div>
      </Button>

      {/* Next Chapter */}
      <Button
        variant="ghost"
        size="icon"
        className="h-10 w-10 lg:h-12 lg:w-12 rounded-full"
        onClick={onNextChapter}
        disabled={!hasChapters || isLastChapter}
        title="Next Chapter (Shift+N)"
      >
        <SkipForward className="w-5 h-5 lg:w-6 lg:h-6" />
      </Button>
    </div>
  );
}
