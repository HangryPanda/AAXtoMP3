import {
  Minus,
  Plus,
  Moon,
  X,
  Info,
  FastForward,
  Keyboard,
  ListMusic,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Book } from "@/types";

// Speed options with 0.1x granularity
export const SPEED_OPTIONS = [
  0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9,
  2.0, 2.25, 2.5, 2.75, 3.0,
];

interface PlayerMetaControlsProps {
  playbackRate: number;
  onPlaybackRateChange: (rate: number) => void;
  sleepTimerMinutes: number | null;
  sleepTimerRemaining: string | null;
  onSleepTimerClick: () => void;
  onSleepTimerCancel: () => void;
  onInfoClick: () => void;
  nextInSeries: Book | null;
  onSeriesClick: () => void;
  onShortcutsClick: () => void;
  onMobileChaptersClick: () => void;
}

export function PlayerMetaControls({
  playbackRate,
  onPlaybackRateChange,
  sleepTimerMinutes,
  sleepTimerRemaining,
  onSleepTimerClick,
  onSleepTimerCancel,
  onInfoClick,
  nextInSeries,
  onSeriesClick,
  onShortcutsClick,
  onMobileChaptersClick,
}: PlayerMetaControlsProps) {
  const handleSpeedChange = (value: string) => {
    onPlaybackRateChange(parseFloat(value));
  };

  const handleSpeedIncrement = (delta: number) => {
    const currentIndex = SPEED_OPTIONS.findIndex(
      (s) => Math.abs(s - playbackRate) < 0.01
    );
    const newIndex = Math.max(
      0,
      Math.min(SPEED_OPTIONS.length - 1, currentIndex + delta)
    );
    onPlaybackRateChange(SPEED_OPTIONS[newIndex]);
  };

  return (
    <>
      {/* Playback Speed with increment buttons */}
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => handleSpeedIncrement(-1)}
          disabled={playbackRate <= SPEED_OPTIONS[0]}
        >
          <Minus className="w-3 h-3" />
        </Button>
        <Select
          value={playbackRate.toString()}
          onValueChange={handleSpeedChange}
        >
          <SelectTrigger className="w-20 h-8 text-sm font-semibold">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SPEED_OPTIONS.map((rate) => (
              <SelectItem key={rate} value={rate.toString()}>
                {rate}x
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => handleSpeedIncrement(1)}
          disabled={playbackRate >= SPEED_OPTIONS[SPEED_OPTIONS.length - 1]}
        >
          <Plus className="w-3 h-3" />
        </Button>
      </div>

      {/* Sleep Timer */}
      <div className="flex items-center gap-1">
        {sleepTimerMinutes !== null ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={onSleepTimerCancel}
            className="gap-1 h-8 text-xs"
          >
            <Moon className="w-3 h-3" />
            {sleepTimerRemaining}
            <X className="w-3 h-3" />
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={onSleepTimerClick}
            title="Sleep Timer"
          >
            <Moon className="w-4 h-4" />
          </Button>
        )}
      </div>

      {/* Book Info */}
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-muted-foreground hover:text-foreground"
        onClick={onInfoClick}
        title="Book Details"
      >
        <Info className="w-4 h-4" />
      </Button>

      {/* Next in Series */}
      {nextInSeries && (
        <Button
          variant="ghost"
          size="sm"
          className="h-8 gap-1 text-muted-foreground hover:text-foreground hidden lg:flex"
          onClick={onSeriesClick}
          title="Next in Series"
        >
          <FastForward className="w-4 h-4" />
          <span className="text-xs">Next</span>
        </Button>
      )}

      {/* Keyboard Shortcuts */}
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-muted-foreground hover:text-foreground hidden lg:flex"
        onClick={onShortcutsClick}
        title="Keyboard Shortcuts"
      >
        <Keyboard className="w-4 h-4" />
      </Button>

      {/* Mobile Chapters Toggle */}
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-muted-foreground hover:text-foreground lg:hidden"
        onClick={onMobileChaptersClick}
      >
        <ListMusic className="w-4 h-4" />
      </Button>
    </>
  );
}
