/**
 * ConnectedStickyPlayer - StickyPlayer wired to usePlayerStore
 *
 * This component provides a global mini-player that syncs with the main player state.
 * It appears at the bottom of all pages and allows quick playback control.
 * Features smooth entrance animation and view transition support.
 */
"use client";

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";
import Image from "next/image";
import {
  Play,
  Pause,
  SkipForward,
  SkipBack,
  Volume2,
  VolumeX,
  BookOpen,
  ChevronUp,
  X,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Slider } from "@/components/ui/Slider";
import { usePlayerStore } from "@/store/playerStore";
import { useBookDetails } from "@/hooks/useBooks";
import { getCoverUrl, getPrimaryAuthor } from "@/types";

export interface ConnectedStickyPlayerProps {
  className?: string;
  onExpandClick?: () => void;
}

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function ConnectedStickyPlayer({
  className,
  onExpandClick,
}: ConnectedStickyPlayerProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [isAnimating, setIsAnimating] = React.useState(false);
  const [isVisible, setIsVisible] = React.useState(true);
  const prevBookIdRef = React.useRef<string | null>(null);

  // Player state from store
  const {
    isPlaying,
    isLoading,
    currentTime,
    duration,
    volume,
    isMuted,
    currentBookId,
    currentBookTitle,
    toggle,
    seekRelative,
    seek,
    setVolume,
    toggleMute,
    unloadBook,
    smartResumeMessage,
    clearSmartResumeMessage,
  } = usePlayerStore();

  // Fetch book details if we have an ASIN (not a local item)
  const isLocalItem = currentBookId?.startsWith("local:");
  const asin = !isLocalItem ? currentBookId : null;
  const { data: book } = useBookDetails(asin, { enabled: !!asin });

  // Show smart resume toast
  React.useEffect(() => {
    if (smartResumeMessage) {
      // Auto-dismiss after 5 seconds
      const timer = setTimeout(() => {
        clearSmartResumeMessage();
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [smartResumeMessage, clearSmartResumeMessage]);

  // Animate when a new book is loaded
  React.useEffect(() => {
    if (currentBookId && currentBookId !== prevBookIdRef.current) {
      setIsAnimating(true);
      setIsVisible(true);
      const timer = setTimeout(() => setIsAnimating(false), 500);
      prevBookIdRef.current = currentBookId;
      return () => clearTimeout(timer);
    }
    if (!currentBookId) {
      prevBookIdRef.current = null;
    }
  }, [currentBookId]);

  // Don't render if no book is loaded
  if (!currentBookId) {
    return (
      <div
        className={cn(
          "flex h-20 items-center justify-center text-muted-foreground text-sm",
          className
        )}
      >
        No audiobook playing
      </div>
    );
  }

  const coverUrl = book ? getCoverUrl(book, "500") : null;
  const author = book ? getPrimaryAuthor(book) : null;
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  const handleSeek = (value: number[]) => {
    if (duration > 0 && value[0] !== undefined) {
      const newTime = (value[0] / 100) * duration;
      seek(newTime);
    }
  };

  const handleVolumeChange = (value: number[]) => {
    if (value[0] !== undefined) {
      setVolume(value[0] / 100);
    }
  };

  const handleNavigateToPlayer = () => {
    // Add a brief animation before navigating
    setIsAnimating(true);

    // Use View Transitions API if available for smooth page transitions
    const navigate = () => {
      if (isLocalItem) {
        router.push(`/player?local_id=${currentBookId.replace("local:", "")}`);
      } else if (currentBookId) {
        router.push(`/player?asin=${currentBookId}`);
      }
    };

    // Check if View Transitions API is supported
    if (typeof document !== "undefined" && "startViewTransition" in document) {
      (document as any).startViewTransition(() => {
        navigate();
      });
    } else {
      navigate();
    }
  };

  return (
    <div
      className={cn(
        "relative transition-all duration-300 ease-out",
        isAnimating && "animate-in fade-in slide-in-from-bottom-4",
        className
      )}
      style={{
        // Use view-transition-name for browsers that support it
        viewTransitionName: "mini-player",
      }}
    >
      {/* Smart Resume Toast */}
      {smartResumeMessage && (
        <div className="absolute -top-12 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground px-4 py-2 rounded-full text-sm font-medium shadow-lg animate-in fade-in slide-in-from-bottom-2 z-10">
          {smartResumeMessage}
        </div>
      )}

      <div className="flex items-center gap-3 px-4 py-3">
        {/* Cover - clickable to open player with view transition */}
        <button
          onClick={handleNavigateToPlayer}
          className={cn(
            "h-14 w-14 shrink-0 overflow-hidden rounded bg-muted hover:ring-2 hover:ring-primary transition-all",
            isAnimating && "animate-in zoom-in-95 duration-300"
          )}
          style={{
            viewTransitionName: "player-cover",
          }}
        >
          {coverUrl ? (
            <Image
              src={coverUrl}
              alt={currentBookTitle || "Cover"}
              width={56}
              height={56}
              className="h-14 w-14 object-cover"
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <BookOpen className="h-6 w-6 text-muted-foreground/50" />
            </div>
          )}
        </button>

        {/* Book Info - clickable to open player */}
        <button
          onClick={handleNavigateToPlayer}
          className="min-w-0 w-40 text-left hover:text-primary transition-colors"
        >
          <h4
            className="truncate text-sm font-medium"
            title={currentBookTitle || "Unknown"}
          >
            {currentBookTitle || "Unknown Title"}
          </h4>
          <p
            className="truncate text-xs text-muted-foreground"
            title={author || ""}
          >
            {author || "Unknown Author"}
          </p>
        </button>

        {/* Playback Controls */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => seekRelative(-15)}
            aria-label="Skip back 15 seconds"
          >
            <SkipBack className="h-4 w-4" />
          </Button>

          <Button
            variant="default"
            size="icon"
            className="h-10 w-10 rounded-full"
            onClick={toggle}
            disabled={isLoading}
            aria-label={isPlaying ? "Pause" : "Play"}
          >
            {isPlaying ? (
              <Pause className="h-5 w-5" fill="currentColor" />
            ) : (
              <Play className="h-5 w-5 ml-0.5" fill="currentColor" />
            )}
          </Button>

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => seekRelative(30)}
            aria-label="Skip forward 30 seconds"
          >
            <SkipForward className="h-4 w-4" />
          </Button>
        </div>

        {/* Progress */}
        <div className="flex flex-1 items-center gap-3">
          <span className="w-14 text-right text-xs text-muted-foreground font-mono">
            {formatTime(currentTime)}
          </span>

          <Slider
            value={[progress]}
            onValueChange={handleSeek}
            max={100}
            step={0.1}
            className="flex-1"
            aria-label="Seek"
          />

          <span className="w-14 text-xs text-muted-foreground font-mono">
            {formatTime(duration)}
          </span>
        </div>

        {/* Volume */}
        <div className="flex items-center gap-2 w-32">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={toggleMute}
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

        {/* Expand to full player */}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onExpandClick || handleNavigateToPlayer}
          aria-label="Open full player"
        >
          <ChevronUp className="h-4 w-4" />
        </Button>

        {/* Close */}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground hover:text-destructive"
          onClick={unloadBook}
          aria-label="Close player"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
