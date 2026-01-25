import { AlertTriangle, Cloud, HardDrive } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/Dialog";
import { formatTime } from "@/lib/format";

export interface PositionConflict {
  localTime: number;
  serverTime: number;
  localLastPlayed: string | null;
  serverLastPlayed: string | null;
}

interface ConflictModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  conflict: PositionConflict | null;
  onUseServer: () => void;
  onUseLocal: () => void;
}

export function ConflictModal({
  open,
  onOpenChange,
  conflict,
  onUseServer,
  onUseLocal,
}: ConflictModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-500" />
            Position Conflict Detected
          </DialogTitle>
          <DialogDescription>
            Your local and server positions are different. Which would you like
            to use?
          </DialogDescription>
        </DialogHeader>

        {conflict && (
          <div className="space-y-4 py-4">
            {/* Server Position Option */}
            <button
              onClick={onUseServer}
              className="w-full p-4 border border-border rounded-lg hover:border-primary hover:bg-primary/5 transition-colors text-left group"
            >
              <div className="flex items-start gap-3">
                <Cloud className="w-5 h-5 text-blue-500 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium group-hover:text-primary transition-colors">
                    Server Position
                  </p>
                  <p className="text-2xl font-mono font-bold text-foreground mt-1">
                    {formatTime(conflict.serverTime)}
                  </p>
                  {conflict.serverLastPlayed && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Last played:{" "}
                      {new Date(conflict.serverLastPlayed).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>
            </button>

            {/* Local Position Option */}
            <button
              onClick={onUseLocal}
              className="w-full p-4 border border-border rounded-lg hover:border-primary hover:bg-primary/5 transition-colors text-left group"
            >
              <div className="flex items-start gap-3">
                <HardDrive className="w-5 h-5 text-green-500 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium group-hover:text-primary transition-colors">
                    Local Position
                  </p>
                  <p className="text-2xl font-mono font-bold text-foreground mt-1">
                    {formatTime(conflict.localTime)}
                  </p>
                  {conflict.localLastPlayed && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Last played:{" "}
                      {new Date(conflict.localLastPlayed).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>
            </button>
          </div>
        )}

        <div className="text-xs text-muted-foreground">
          Tip: If you listened on another device, the server position may be
          more recent.
        </div>
      </DialogContent>
    </Dialog>
  );
}
