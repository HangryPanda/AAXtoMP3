import { Volume2, VolumeX } from "lucide-react";
import { Slider } from "@/components/ui/Slider";
import { Button } from "@/components/ui/Button";

interface PlayerVolumeProps {
  volume: number;
  isMuted: boolean;
  onVolumeChange: (volume: number) => void;
  onToggleMute: () => void;
}

export function PlayerVolume({
  volume,
  isMuted,
  onVolumeChange,
  onToggleMute,
}: PlayerVolumeProps) {
  const handleVolumeChange = (value: number[]) => {
    if (value[0] !== undefined) {
      onVolumeChange(value[0] / 100);
    }
  };

  return (
    <div className="flex items-center gap-2 w-32 lg:w-40">
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 shrink-0"
        onClick={onToggleMute}
        title="Mute (M)"
      >
        {isMuted || volume === 0 ? (
          <VolumeX className="w-4 h-4 text-muted-foreground" />
        ) : (
          <Volume2 className="w-4 h-4 text-muted-foreground" />
        )}
      </Button>
      <Slider
        value={[isMuted ? 0 : volume * 100]}
        onValueChange={handleVolumeChange}
        max={100}
        step={1}
        className="flex-1"
        aria-label="Volume"
      />
    </div>
  );
}
