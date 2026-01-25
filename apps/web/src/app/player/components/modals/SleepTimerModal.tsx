import { Moon } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/Dialog";

// Sleep timer options
const SLEEP_TIMER_OPTIONS = [
  { label: "15 minutes", value: 15 },
  { label: "30 minutes", value: 30 },
  { label: "45 minutes", value: 45 },
  { label: "60 minutes", value: 60 },
  { label: "90 minutes", value: 90 },
  { label: "End of chapter", value: -1 },
];

interface SleepTimerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSetTimer: (minutes: number) => void;
}

export function SleepTimerModal({
  open,
  onOpenChange,
  onSetTimer,
}: SleepTimerModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Moon className="w-5 h-5" />
            Sleep Timer
          </DialogTitle>
          <DialogDescription>
            Playback will gradually fade out and pause
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          {SLEEP_TIMER_OPTIONS.map((option) => (
            <Button
              key={option.value}
              variant="outline"
              className="justify-start h-12"
              onClick={() => onSetTimer(option.value)}
            >
              {option.label}
            </Button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
