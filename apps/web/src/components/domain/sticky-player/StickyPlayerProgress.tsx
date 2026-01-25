import * as React from "react";
import { cn } from "@/lib/utils";
import { Slider } from "@/components/ui/Slider";

export interface StickyPlayerProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  currentTime: number;
  duration: number;
  onSeek: (time: number) => void;
}

// Format seconds to H:MM:SS or MM:SS
function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function StickyPlayerProgress({
  currentTime,
  duration,
  onSeek,
  className,
  ...props
}: StickyPlayerProgressProps) {
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  const handleSeek = (value: number[]) => {
    if (duration > 0 && value[0] !== undefined) {
      const newTime = (value[0] / 100) * duration;
      onSeek(newTime);
    }
  };

  return (
    <div className={cn("flex flex-1 items-center gap-3 min-w-[100px]", className)} {...props}>
      <span className="hidden lg:inline-block w-12 text-right text-[11px] font-mono text-muted-foreground">
        {formatTime(currentTime)}
      </span>

      <div className="relative flex-1 group py-2">
        <Slider
          value={[progress]}
          onValueChange={handleSeek}
          max={100}
          step={0.01}
          className="flex-1 cursor-pointer"
          aria-label="Seek"
        />
      </div>

      <span className="hidden lg:inline-block w-12 text-[11px] font-mono text-muted-foreground">
        {formatTime(duration)}
      </span>
    </div>
  );
}
