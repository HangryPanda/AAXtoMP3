import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { PlayerCover } from "../components/PlayerCover";
import { PlayerChapterList } from "../components/PlayerChapterList";
import { PlayerHeader } from "../components/PlayerHeader";
import { PlayerProgressBar } from "../components/PlayerProgressBar";
import { PlayerControls } from "../components/PlayerControls";
import { PlayerVolume } from "../components/PlayerVolume";
import { PlayerMetaControls } from "../components/PlayerMetaControls";
import { usePlayerLogic } from "../hooks/usePlayerLogic";

type PlayerLogic = ReturnType<typeof usePlayerLogic>;

interface DesktopPlayerLayoutProps {
  logic: PlayerLogic;
  onBack: () => void;
  coverUrl: string | null;
  title: string;
  author: string;
  showModals: {
    metadata: () => void;
    sleepTimer: () => void;
    shortcuts: () => void;
    series: () => void;
    cancelSleepTimer: () => void;
  };
}

export function DesktopPlayerLayout({
  logic,
  onBack,
  coverUrl,
  title,
  author,
  showModals,
}: DesktopPlayerLayoutProps) {
  const {
    book,
    localItem,
    isLoadingDetails,
    isLoading: isPlayerLoading,
    chapters,
    currentChapterIndex,
    isChaptersSynthetic,
    seek,
    play,
    currentChapter,
    duration,
    currentTime,
    isPlaying,
    toggle,
    seekRelative,
    goToNextChapter,
    goToPrevChapter,
    volume,
    isMuted,
    setVolume,
    toggleMute,
    playbackRate,
    setPlaybackRate,
    sleepTimerMinutes,
    sleepTimerRemaining,
    nextInSeries,
    error: playerError,
  } = logic;

  return (
    <div className="flex flex-col lg:flex-row h-full gap-8 max-w-6xl mx-auto">
      {/* Left Side: Cover Art & Chapters */}
      <aside className="w-full lg:w-80 flex flex-col gap-6 shrink-0 order-1 lg:order-1">
        {/* Back to Library */}
        <Button
          variant="ghost"
          size="sm"
          onClick={onBack}
          className="self-start gap-2 -mt-2"
        >
          <ChevronLeft className="w-4 h-4" />
          Back to Library
        </Button>

        {/* Cover Art */}
        <PlayerCover
          book={book}
          coverUrl={coverUrl}
          isLoadingDetails={isLoadingDetails}
          isPlayerLoading={isPlayerLoading}
        />

        {/* Chapter List Card */}
        <PlayerChapterList
          chapters={chapters}
          currentChapterIndex={currentChapterIndex}
          onChapterSelect={(chapter) => {
            seek(chapter.start_offset_ms / 1000);
            play();
          }}
          isChaptersSynthetic={isChaptersSynthetic}
          className="hidden lg:flex flex-1 min-h-[200px] lg:min-h-[300px]"
        />
      </aside>

      {/* Right Side: Player Controls */}
      <main className="flex-1 flex flex-col items-center justify-center py-4 lg:py-6 order-2 lg:order-2">
        {playerError && (
          <div className="w-full max-w-xl mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400 text-sm">
            <p className="font-semibold">Playback Error</p>
            <p>{playerError}</p>
          </div>
        )}

        {/* Book Details */}
        <PlayerHeader
          title={title}
          author={author}
          book={book}
          localItem={localItem}
          currentChapter={currentChapter}
          duration={duration}
        />

        {/* Segmented Progress Bar */}
        <PlayerProgressBar
          currentTime={currentTime}
          duration={duration}
          chapters={chapters}
          onSeek={seek}
        />

        {/* Main Controls */}
        <PlayerControls
          isPlaying={isPlaying}
          isLoading={isPlayerLoading}
          canPlay={!!((book || localItem) && !isPlayerLoading)}
          hasChapters={chapters.length > 0}
          isLastChapter={
            currentChapterIndex !== null &&
            currentChapterIndex >= chapters.length - 1
          }
          onToggle={toggle}
          onSeekRelative={seekRelative}
          onNextChapter={goToNextChapter}
          onPrevChapter={goToPrevChapter}
        />

        {/* Footer Controls */}
        <div className="flex flex-wrap items-center justify-center gap-4 lg:gap-6 w-full max-w-2xl p-4 lg:p-6 bg-card/50 border border-border rounded-2xl backdrop-blur-sm">
          {/* Volume */}
          <PlayerVolume
            volume={volume}
            isMuted={isMuted}
            onVolumeChange={setVolume}
            onToggleMute={toggleMute}
          />

          <PlayerMetaControls
            playbackRate={playbackRate}
            onPlaybackRateChange={setPlaybackRate} // Using setPlaybackRate from store directly, logic hook exposes handleSpeedIncrement separately
            // Wait, looking at MetaControls, it handles the select change but increments need the logic function
            // Actually MetaControls calls onPlaybackRateChange for both Select and +/- buttons?
            // Let's check PlayerMetaControls implementation.
            // It calls handleSpeedIncrement locally which calls onPlaybackRateChange with the NEW value.
            // So passing setPlaybackRate is correct.
            sleepTimerMinutes={sleepTimerMinutes}
            sleepTimerRemaining={sleepTimerRemaining}
            onSleepTimerClick={showModals.sleepTimer}
            onSleepTimerCancel={showModals.cancelSleepTimer}
            onInfoClick={showModals.metadata}
            nextInSeries={nextInSeries}
            onSeriesClick={showModals.series}
            onShortcutsClick={showModals.shortcuts}
            onMobileChaptersClick={() => {
              document
                .getElementById("mobile-chapters")
                ?.scrollIntoView({ behavior: "smooth" });
            }}
          />
        </div>
      </main>

      {/* Mobile Chapters Section (Hidden on desktop via CSS class in component, but good to have here for structure) */}
      <PlayerChapterList
        id="mobile-chapters"
        chapters={chapters}
        currentChapterIndex={currentChapterIndex}
        onChapterSelect={(chapter) => {
          seek(chapter.start_offset_ms / 1000);
          play();
        }}
        isChaptersSynthetic={isChaptersSynthetic}
        className="w-full lg:hidden order-3 max-h-[400px]"
      />
    </div>
  );
}
