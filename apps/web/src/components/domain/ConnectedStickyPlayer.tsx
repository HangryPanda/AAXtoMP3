/**
 * ConnectedStickyPlayer - StickyPlayer wired to usePlayerStore
 *
 * This component provides a global mini-player that syncs with the main player state.
 * It appears at the bottom of all pages and allows quick playback control.
 * Features smooth entrance animation and view transition support.
 */
"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui";
import { usePlayerStore } from "@/store/playerStore";
import { useBookDetails } from "@/hooks/useBooks";
import { getCoverUrl, getPrimaryAuthor } from "@/types";
import { cn } from "@/lib/utils";
import { ChapterList } from "./ChapterList";
import {
  StickyPlayerRoot,
  StickyPlayerCover,
  StickyPlayerInfo,
  StickyPlayerControls,
  StickyPlayerProgress,
  StickyPlayerActionsGroup,
  StickyPlayerSleepButton,
  StickyPlayerSpeedButton,
  StickyPlayerChaptersButton,
  StickyPlayerExpandButton,
  StickyPlayerVolume,
  StickyPlayerCloseButton,
} from "./sticky-player";

export interface ConnectedStickyPlayerProps {
  className?: string;
}

export function ConnectedStickyPlayer({
  className,
}: ConnectedStickyPlayerProps) {
  const router = useRouter();
  const [isAnimating, setIsAnimating] = React.useState(false);
  const [isChapterDialogOpen, setIsChapterDialogOpen] = React.useState(false);
  const prevBookIdRef = React.useRef<string | null>(null);

  // Player state from store
  const {
    isPlaying,
    isLoading,
    currentTime,
    duration,
    playbackRate,
    volume,
    isMuted,
    currentBookId,
    currentBookTitle,
    currentAudioUrl,
    chapters,
    currentChapterIndex,
    sleepTimer,
    toggle,
    seekRelative,
    seek,
    nextChapter,
    prevChapter,
    seekToChapter,
    setPlaybackRate,
    setVolume,
    toggleMute,
    setSleepTimer,
    loadBook,
    unloadBook,
    smartResumeMessage,
    clearSmartResumeMessage,
  } = usePlayerStore();

  // Re-initialize player on mount if state persists but instance is lost (e.g. refresh)
  React.useEffect(() => {
    if (currentBookId && currentAudioUrl && currentBookTitle) {
      loadBook(currentBookId, currentAudioUrl, currentBookTitle);
    }
  }, [currentBookId, currentAudioUrl, currentBookTitle, loadBook]);

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
    return null;
  }

  const currentChapter = currentChapterIndex !== null ? chapters[currentChapterIndex] : undefined;
  const coverUrl = book ? getCoverUrl(book, "500") : null;
  const author = book ? getPrimaryAuthor(book) : null;
  
  const handleNavigateToPlayer = () => {
    const navigate = () => {
      if (isLocalItem) {
        router.push(`/player?local_id=${currentBookId.replace("local:", "")}`);
      } else if (currentBookId) {
        router.push(`/player?asin=${currentBookId}`);
      }
    };

    const doc = document as Document & {
      startViewTransition?: (callback: () => void) => void;
    };
    if (doc.startViewTransition) {
      doc.startViewTransition(navigate);
      return;
    }
    navigate();
  };

  // Map chapters to ChapterList format
  const mappedChapters = chapters.map((c, i) => ({
    id: `chapter-${i}`,
    title: c.title,
    startTime: c.start_offset_ms / 1000,
    duration: c.length_ms / 1000,
  }));

  // Playback speeds
  const speeds = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3];

  // Sleep timer presets (in minutes)
  const sleepPresets = [15, 30, 45, 60];

  return (
    <>
      <StickyPlayerRoot
        className={className}
        isAnimating={isAnimating}
        // Custom style for view transition
        style={{ viewTransitionName: "mini-player" } as React.CSSProperties}
      >
        {/* Smart Resume Toast Overlay */}
        {smartResumeMessage && (
          <div className="absolute -top-12 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground px-4 py-2 rounded-full text-sm font-medium shadow-lg animate-in fade-in slide-in-from-bottom-2 z-10 whitespace-nowrap">
            {smartResumeMessage}
          </div>
        )}

        {/* 1. Cover */}
        <StickyPlayerCover
          src={coverUrl}
          alt={currentBookTitle || "Book Cover"}
          onClick={handleNavigateToPlayer}
          style={{ viewTransitionName: "player-cover" } as React.CSSProperties}
        />

        {/* 2. Info */}
        <StickyPlayerInfo
          title={currentBookTitle || "Unknown Title"}
          subtitle={currentChapter?.title || author || "Unknown Author"}
          onClick={handleNavigateToPlayer}
        />

        {/* 3. Controls */}
        <StickyPlayerControls
          isPlaying={isPlaying}
          isLoading={isLoading}
          onPlayPause={toggle}
          onSkipBack={() => seekRelative(-15)}
          onSkipForward={() => seekRelative(15)}
          onPrevChapter={prevChapter}
          onNextChapter={nextChapter}
        />

        {/* 4. Progress */}
        <StickyPlayerProgress
          currentTime={currentTime}
          duration={duration}
          onSeek={seek}
        />

        {/* 5. Volume */}
        <StickyPlayerVolume
          volume={volume}
          isMuted={isMuted}
          onVolumeChange={setVolume}
          onToggleMute={toggleMute}
        />

        {/* 6. Actions */}
        <StickyPlayerActionsGroup>
          {/* Sleep Timer */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <StickyPlayerSleepButton timeLeft={sleepTimer.timeLeft} />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Sleep Timer</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {sleepPresets.map((min) => (
                <DropdownMenuItem key={min} onClick={() => setSleepTimer(min)}>
                  {min} Minutes
                </DropdownMenuItem>
              ))}
              <DropdownMenuItem onClick={() => setSleepTimer(null)}>
                Off
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Playback Speed */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <StickyPlayerSpeedButton playbackRate={playbackRate} />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Playback Speed</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {speeds.map((speed) => (
                <DropdownMenuItem 
                  key={speed} 
                  onClick={() => setPlaybackRate(speed)}
                  className={cn(playbackRate === speed && "bg-accent")}
                >
                  {speed}x
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Chapters */}
          <StickyPlayerChaptersButton onClick={() => setIsChapterDialogOpen(true)} />

          {/* Expand (Mobile) */}
          <StickyPlayerExpandButton onClick={handleNavigateToPlayer} />

          {/* Close */}
          <StickyPlayerCloseButton onClick={unloadBook} />
        </StickyPlayerActionsGroup>
      </StickyPlayerRoot>

      {/* Chapter List Dialog */}
      <Dialog open={isChapterDialogOpen} onOpenChange={setIsChapterDialogOpen}>
        <DialogContent className="max-w-md h-[80vh] flex flex-col p-0 overflow-hidden">
          <DialogHeader className="p-6 border-b">
            <DialogTitle>Chapters</DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto">
            <ChapterList
              chapters={mappedChapters}
              currentChapterId={currentChapterIndex !== null ? `chapter-${currentChapterIndex}` : undefined}
              onChapterSelect={(c) => {
                const index = mappedChapters.indexOf(c);
                seekToChapter(index);
                setIsChapterDialogOpen(false);
              }}
            />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
