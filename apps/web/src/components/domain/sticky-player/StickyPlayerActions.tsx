import * as React from "react";
import { cn } from "@/lib/utils";
import { Button, ButtonProps } from "@/components/ui/Button";
import { Moon, ListMusic, ChevronUp, X } from "lucide-react";

export function StickyPlayerActionsGroup({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex items-center gap-1 md:gap-2 shrink-0", className)} {...props}>
      {children}
    </div>
  );
}

export interface StickyPlayerSleepButtonProps extends ButtonProps {
  timeLeft: number | null;
}

export const StickyPlayerSleepButton = React.forwardRef<HTMLButtonElement, StickyPlayerSleepButtonProps>(
  ({ timeLeft, className, ...props }, ref) => {
    return (
      <Button
        ref={ref}
        variant="ghost"
        size="icon"
        className={cn("h-9 w-9 relative", timeLeft && "text-primary", className)}
        aria-label="Sleep timer"
        {...props}
      >
        <Moon className={cn("h-5 w-5", timeLeft && "fill-current")} />
        {timeLeft && (
          <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[8px] text-primary-foreground font-bold">
            {Math.ceil(timeLeft / 60000)}
          </span>
        )}
      </Button>
    );
  }
);
StickyPlayerSleepButton.displayName = "StickyPlayerSleepButton";

export interface StickyPlayerSpeedButtonProps extends ButtonProps {
  playbackRate: number;
}

export const StickyPlayerSpeedButton = React.forwardRef<HTMLButtonElement, StickyPlayerSpeedButtonProps>(
  ({ playbackRate, className, ...props }, ref) => {
    return (
      <Button
        ref={ref}
        variant="ghost"
        className={cn("h-9 px-2 text-[11px] font-bold hover:bg-muted", className)}
        aria-label="Playback speed"
        {...props}
      >
        {playbackRate}x
      </Button>
    );
  }
);
StickyPlayerSpeedButton.displayName = "StickyPlayerSpeedButton";

export const StickyPlayerChaptersButton = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, ...props }, ref) => {
    return (
      <Button
        ref={ref}
        variant="ghost"
        size="icon"
        className={cn("h-9 w-9", className)}
        aria-label="Chapters"
        {...props}
      >
        <ListMusic className="h-5 w-5" />
      </Button>
    );
  }
);
StickyPlayerChaptersButton.displayName = "StickyPlayerChaptersButton";

export const StickyPlayerExpandButton = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, ...props }, ref) => {
    return (
      <Button
        ref={ref}
        variant="ghost"
        size="icon"
        className={cn("h-9 w-9 lg:hidden", className)}
        aria-label="Expand player"
        {...props}
      >
        <ChevronUp className="h-5 w-5" />
      </Button>
    );
  }
);
StickyPlayerExpandButton.displayName = "StickyPlayerExpandButton";

export const StickyPlayerCloseButton = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, ...props }, ref) => {
    return (
      <Button
        ref={ref}
        variant="ghost"
        size="icon"
        className={cn("h-9 w-9 text-muted-foreground hover:text-destructive hidden lg:inline-flex", className)}
        aria-label="Close player"
        {...props}
      >
        <X className="h-5 w-5" />
      </Button>
    );
  }
);
StickyPlayerCloseButton.displayName = "StickyPlayerCloseButton";
