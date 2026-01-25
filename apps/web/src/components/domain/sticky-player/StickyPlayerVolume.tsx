import * as React from "react";
import { Volume2, VolumeX } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Slider } from "@/components/ui/Slider";

export interface StickyPlayerVolumeProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "onVolumeChange"> {
  volume: number;
  isMuted: boolean;
  onVolumeChange: (volume: number) => void;
  onToggleMute: () => void;
}

export function StickyPlayerVolume({
  volume,
  isMuted,
  onVolumeChange,
  onToggleMute,
  className,
  ...props
}: StickyPlayerVolumeProps) {
  const handleVolumeChange = (value: number[]) => {
    if (value[0] !== undefined) {
      onVolumeChange(value[0] / 100);
    }
  };

  return (
    <div className={cn("hidden lg:flex items-center gap-2 w-32", className)} {...props}>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 shrink-0"
        onClick={onToggleMute}
        aria-label={isMuted ? "Unmute" : "Mute"}
      >
        {isMuted || volume === 0 ? (
          <VolumeX className="h-4 w-4 text-muted-foreground" />
        ) : (
          <Volume2 className="h-4 w-4 text-muted-foreground" />
        )}
      </Button>

      <Slider
        value={[isMuted ? 0 : volume * 100]}
        onValueChange={handleVolumeChange}
        max={100}
        className="flex-1"
        aria-label="Volume"
      />
    </div>
  );
}
