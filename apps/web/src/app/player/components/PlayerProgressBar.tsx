import { formatTime } from "@/lib/format";
import { PlayerChapter } from "../types";

interface PlayerProgressBarProps {
  currentTime: number;
  duration: number;
  chapters: PlayerChapter[];
  onSeek: (time: number) => void;
}

export function PlayerProgressBar({
  currentTime,
  duration,
  chapters,
  onSeek,
}: PlayerProgressBarProps) {
  // Calculate chapter progress percentages for segmented progress bar
  const chapterSegments = chapters.map((ch) => ({
    start: duration > 0 ? (ch.start_offset_ms / 1000 / duration) * 100 : 0,
    width:
      duration > 0
        ? (ch.length_ms / 1000 / duration) * 100
        : 100 / chapters.length,
    title: ch.title,
  }));

  return (
    <div className="w-full max-w-2xl mb-6 group">
      <div className="flex justify-between text-sm font-mono text-muted-foreground mb-2 px-1">
        <span className="text-foreground">{formatTime(currentTime)}</span>
        <span>{formatTime(duration)}</span>
      </div>

      {/* Chapter-segmented timeline */}
      <div className="relative h-3 w-full">
        {/* Background track with chapter segments */}
        <div className="absolute inset-0 flex gap-0.5 rounded-full overflow-hidden">
          {chapterSegments.length > 0 ? (
            chapterSegments.map((seg, i) => (
              <div
                key={i}
                className="h-full bg-secondary hover:bg-secondary/80 transition-colors relative group/seg"
                style={{ width: `${seg.width}%` }}
                title={seg.title}
              >
                {/* Tooltip on hover */}
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-popover text-popover-foreground text-xs rounded shadow-lg opacity-0 group-hover/seg:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                  {seg.title}
                </div>
              </div>
            ))
          ) : (
            <div className="h-full w-full bg-secondary rounded-full" />
          )}
        </div>

        {/* Progress overlay */}
        <div
          className="absolute inset-y-0 left-0 bg-primary rounded-full pointer-events-none"
          style={{
            width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%`,
          }}
        />

        {/* Interactive slider overlay */}
        <input
          type="range"
          min="0"
          max={duration || 1}
          step="1"
          value={currentTime}
          onChange={(e) => onSeek(parseFloat(e.target.value))}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />

        {/* Thumb indicator */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-primary rounded-full shadow-lg pointer-events-none transition-transform group-hover:scale-125"
          style={{
            left: `calc(${
              duration > 0 ? (currentTime / duration) * 100 : 0
            }% - 8px)`,
          }}
        />
      </div>
    </div>
  );
}
