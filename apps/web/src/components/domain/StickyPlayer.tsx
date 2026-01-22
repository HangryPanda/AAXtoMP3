/**
 * StickyPlayer component for audio playback controls
 */
import * as React from "react";
import Image from "next/image";
import {
  Play,
  Pause,
  SkipForward,
  SkipBack,
  Volume2,
  VolumeX,
  ListMusic,
  BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Slider } from "@/components/ui/Slider";
import { getCoverUrl, getPrimaryAuthor, type Book } from "@/types";

export interface StickyPlayerProps {
  currentBook?: Book;
  isPlaying?: boolean;
  currentTime?: number;
  duration?: number;
  volume?: number;
  muted?: boolean;
  onPlayPause?: () => void;
  onSkipForward?: () => void;
  onSkipBack?: () => void;
  onSeek?: (time: number) => void;
  onVolumeChange?: (volume: number) => void;
  onMuteToggle?: () => void;
  onChaptersClick?: () => void;
  className?: string;
}

// Format seconds to MM:SS
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function StickyPlayer({
  currentBook,
  isPlaying = false,
  currentTime = 0,
  duration = 0,
  volume = 1,
  muted = false,
  onPlayPause,
  onSkipForward,
  onSkipBack,
  onSeek,
  onVolumeChange,
  onMuteToggle,
  onChaptersClick,
  className,
}: StickyPlayerProps) {
  if (!currentBook) {
    return (
      <div
        className={cn(
          "flex h-20 items-center justify-center text-muted-foreground",
          className
        )}
      >
        No track playing
      </div>
    );
  }

  const coverUrl = getCoverUrl(currentBook);
  const author = getPrimaryAuthor(currentBook);
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  const handleSeek = (value: number[]) => {
    if (duration > 0 && value[0] !== undefined) {
      const newTime = (value[0] / 100) * duration;
      onSeek?.(newTime);
    }
  };

  const handleVolumeChange = (value: number[]) => {
    if (value[0] !== undefined) {
      onVolumeChange?.(value[0] / 100);
    }
  };

  return (
    <div className={cn("flex items-center gap-4 px-4 py-3", className)}>
      {/* Cover */}
      <div className="h-14 w-14 shrink-0 overflow-hidden rounded bg-muted">
        {coverUrl ? (
          <Image
            src={coverUrl}
            alt={currentBook.title}
            width={56}
            height={56}
            className="h-14 w-14 object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <BookOpen className="h-6 w-6 text-muted-foreground/50" />
          </div>
        )}
      </div>

      {/* Book Info */}
      <div className="min-w-0 w-48">
        <h4 className="truncate text-sm font-medium" title={currentBook.title}>
          {currentBook.title}
        </h4>
        <p className="truncate text-xs text-muted-foreground" title={author}>
          {author}
        </p>
      </div>

      {/* Playback Controls */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onSkipBack}
          aria-label="Skip back 30 seconds"
        >
          <SkipBack className="h-4 w-4" />
        </Button>

        <Button
          variant="default"
          size="icon"
          className="h-10 w-10 rounded-full"
          onClick={onPlayPause}
          aria-label={isPlaying ? "Pause" : "Play"}
        >
          {isPlaying ? (
            <Pause className="h-5 w-5" fill="currentColor" />
          ) : (
            <Play className="h-5 w-5" fill="currentColor" />
          )}
        </Button>

        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onSkipForward}
          aria-label="Skip forward 30 seconds"
        >
          <SkipForward className="h-4 w-4" />
        </Button>
      </div>

      {/* Progress */}
      <div className="flex flex-1 items-center gap-3">
        <span className="w-12 text-right text-xs text-muted-foreground">
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

        <span className="w-12 text-xs text-muted-foreground">
          {formatTime(duration)}
        </span>
      </div>

      {/* Volume */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onMuteToggle}
          aria-label={muted ? "Unmute" : "Volume"}
        >
          {muted ? (
            <VolumeX className="h-4 w-4" />
          ) : (
            <Volume2 className="h-4 w-4" />
          )}
        </Button>

        <Slider
          value={[muted ? 0 : volume * 100]}
          onValueChange={handleVolumeChange}
          max={100}
          className="w-24"
          aria-label="Volume"
        />
      </div>

      {/* Chapters */}
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        onClick={onChaptersClick}
        aria-label="Chapters"
      >
        <ListMusic className="h-4 w-4" />
      </Button>
    </div>
  );
}
