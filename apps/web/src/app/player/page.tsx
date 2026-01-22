"use client";

import { useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Image from "next/image";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  ListMusic,
  Maximize2,
  ChevronLeft,
  Loader2,
  Headphones,
  Settings2,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { useActiveJobs } from "@/hooks/useJobs";
import { useBookDetails, useLocalItemDetails } from "@/hooks/useBooks";
import { usePlayerStore } from "@/store/playerStore";
import { useUIStore } from "@/store/uiStore";
import { API_URL } from "@/lib/env";
import { Button } from "@/components/ui/Button";
import { 
  getCoverUrl, 
  getPrimaryAuthor, 
  formatRuntime, 
  canPlay 
} from "@/types";

function PlayerContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const asin = searchParams.get("asin");
  const localId = searchParams.get("local_id");
  const addToast = useUIStore((state) => state.addToast);
  
  const { data: activeJobs } = useActiveJobs();
  const { data: book, isLoading: isLoadingBook } = useBookDetails(asin, { enabled: !!asin && !localId });
  const { data: localItem, isLoading: isLoadingLocalItem } = useLocalItemDetails(localId, { enabled: !!localId });
  const setJobDrawerOpen = useUIStore((state) => state.setJobDrawerOpen);
  
  // Player Store
  const {
    isPlaying,
    isLoading: isPlayerLoading,
    currentTime,
    duration,
    volume,
    playbackRate,
    loadBook,
    toggle,
    seekRelative,
    seek,
    setVolume,
    setPlaybackRate,
    currentBookId,
    error: playerError
  } = usePlayerStore();

  // Load book into player when asin changes or book details are fetched
  useEffect(() => {
    if (localItem && currentBookId !== `local:${localItem.id}`) {
      const audioUrl = `${API_URL}/stream/local/${localItem.id}`;
      loadBook(`local:${localItem.id}`, audioUrl, localItem.title);
      return;
    }
    if (book && canPlay(book) && currentBookId !== book.asin) {
      const audioUrl = `${API_URL}/stream/${book.asin}`;
      loadBook(book.asin, audioUrl, book.title);
    }
  }, [book, localItem, loadBook, currentBookId]);

  const formatTime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    }
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    seek(parseFloat(e.target.value));
  };

  const handleSettingsClick = () => {
    addToast({
      type: "info",
      title: "Audio Settings",
      message: "Equalizer and advanced audio settings coming soon."
    });
  };

  const isLoadingDetails = isLoadingBook || isLoadingLocalItem;
  const title = localItem?.title ?? book?.title ?? "Select a Book";
  const author = localItem?.authors ?? (book ? getPrimaryAuthor(book) : "Unknown Author");
  const coverUrl = book ? getCoverUrl(book, "1215") : null;

  return (
    <AppShell
      sidebarProps={{ 
        activeJobCount: activeJobs?.total ?? 0, 
        activePath: "/player",
        onJobsClick: () => setJobDrawerOpen(true),
      }}
      headerProps={{
        title: "Now Playing",
        actions: (
          <Button variant="ghost" size="sm" onClick={() => router.push("/library")} className="gap-2">
            <ChevronLeft className="w-4 h-4" />
            Library
          </Button>
        )
      }}
    >
      <div className="flex flex-col lg:flex-row h-full gap-8 max-w-6xl mx-auto">
        {/* Left Side: Cover Art & Chapters (Mobile Order changes) */}
        <aside className="w-full lg:w-80 flex flex-col gap-6 shrink-0">
          {/* Cover Art */}
          <div className="aspect-square relative bg-card border border-border rounded-xl shadow-lg overflow-hidden group">
            {isLoadingDetails ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
              </div>
            ) : coverUrl ? (
              <Image 
                src={coverUrl} 
                alt={book?.title || "Cover"} 
                fill 
                className="object-cover"
                sizes="(max-width: 1024px) 100vw, 320px"
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground bg-muted/20">
                <Headphones className="w-16 h-16 mb-2 opacity-20" />
                <p className="text-sm">No Cover</p>
              </div>
            )}
            
            {isPlayerLoading && (
              <div className="absolute inset-0 bg-background/40 backdrop-blur-sm flex items-center justify-center">
                <Loader2 className="w-10 h-10 animate-spin text-primary" />
              </div>
            )}
          </div>

          {/* Chapter List Card */}
          <div className="bg-card border border-border rounded-xl flex-1 min-h-[300px] flex flex-col overflow-hidden shadow-sm">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <h2 className="font-semibold flex items-center gap-2">
                <ListMusic className="w-4 h-4 text-primary" />
                Chapters
              </h2>
              <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">{book?.chapters?.length || 0}</span>
            </div>
            <div className="flex-1 overflow-auto">
              {book?.chapters && book.chapters.length > 0 ? (
                <div className="divide-y divide-border">
                  {book.chapters.map((chapter, i) => (
                    <button
                      key={i}
                      onClick={() => seek(chapter.start_offset_ms / 1000)}
                      className="w-full px-4 py-3 text-left hover:bg-muted/50 transition-colors flex items-center justify-between group"
                    >
                      <span className="text-sm font-medium line-clamp-1 group-hover:text-primary transition-colors">
                        {chapter.title}
                      </span>
                      <span className="text-xs text-muted-foreground font-mono">
                        {formatTime(chapter.length_ms / 1000)}
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-center text-muted-foreground py-12 px-6">
                  <p className="text-sm font-medium text-foreground/70">No Chapters Available</p>
                  <p className="text-xs mt-1">This book doesn&apos;t have chapter markers or they are still being processed.</p>
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* Right Side: Player Controls */}
        <main className="flex-1 flex flex-col items-center justify-center py-6">
          {playerError && (
            <div className="w-full max-w-xl mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400 text-sm">
              <p className="font-semibold">Playback Error</p>
              <p>{playerError}</p>
            </div>
          )}

          {/* Book Details */}
          <div className="text-center mb-10 w-full">
            <h1 className="text-3xl font-bold tracking-tight mb-2 line-clamp-2">{title}</h1>
            <p className="text-lg text-muted-foreground mb-4">{author}</p>
            <div className="flex items-center justify-center gap-4 text-sm text-muted-foreground font-medium">
               <span className="bg-secondary px-3 py-1 rounded-full">
                {(localItem?.format ?? book?.conversion_format ?? "audio").toUpperCase()}
               </span>
               <span>{book ? formatRuntime(book.runtime_length_min) : "--:--"}</span>
            </div>
          </div>

          {/* Progress Slider */}
          <div className="w-full max-w-2xl mb-8 group">
            <div className="flex justify-between text-sm font-mono text-muted-foreground mb-2 px-1">
              <span className="text-foreground">{formatTime(currentTime)}</span>
              <span>{formatTime(duration)}</span>
            </div>
            <input
              type="range"
              min="0"
              max={duration || 0}
              step="1"
              value={currentTime}
              onChange={handleSliderChange}
              className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary hover:h-3 transition-all"
            />
          </div>

          {/* Main Controls */}
          <div className="flex items-center gap-8 mb-10">
            {/* Skip Back */}
            <Button
              variant="ghost"
              size="icon"
              className="h-12 w-12 rounded-full"
              onClick={() => seekRelative(-10)}
              title="Skip back 10s"
            >
              <SkipBack className="w-7 h-7" />
            </Button>

            {/* Play/Pause */}
            <Button
              onClick={toggle}
              disabled={(!asin && !localId) || isPlayerLoading}
              className="h-20 w-20 rounded-full shadow-xl hover:scale-105 transition-transform"
            >
              {isPlayerLoading ? (
                <Loader2 className="w-10 h-10 animate-spin" />
              ) : isPlaying ? (
                <Pause className="w-10 h-10 fill-current" />
              ) : (
                <Play className="w-10 h-10 ml-1 fill-current" />
              )}
            </Button>

            {/* Skip Forward */}
            <Button
              variant="ghost"
              size="icon"
              className="h-12 w-12 rounded-full"
              onClick={() => seekRelative(30)}
              title="Skip forward 30s"
            >
              <SkipForward className="w-7 h-7" />
            </Button>
          </div>

          {/* Footer Controls */}
          <div className="flex flex-wrap items-center justify-center gap-8 w-full max-w-2xl p-6 bg-card/50 border border-border rounded-2xl backdrop-blur-sm">
            {/* Volume */}
            <div className="flex items-center gap-3 w-40">
              <Volume2 className="w-5 h-5 text-muted-foreground" />
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={volume}
                onChange={(e) => setVolume(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
              />
            </div>

            {/* Playback Speed */}
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Speed</span>
              <select
                value={playbackRate}
                onChange={(e) => setPlaybackRate(parseFloat(e.target.value))}
                className="px-3 py-1.5 text-sm font-semibold bg-background rounded-lg border border-input focus:ring-2 focus:ring-ring focus:outline-none cursor-pointer"
              >
                {[0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3].map(rate => (
                  <option key={rate} value={rate}>{rate}x</option>
                ))}
              </select>
            </div>

            {/* Extra Tools */}
            <div className="flex items-center gap-2">
               <Button 
                 variant="ghost" 
                 size="icon" 
                 onClick={handleSettingsClick}
                 className="text-muted-foreground hover:text-foreground"
                 title="Audio Settings"
               >
                 <Settings2 className="w-5 h-5" />
               </Button>
               <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground lg:hidden">
                 <ListMusic className="w-5 h-5" />
               </Button>
               <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground">
                 <Maximize2 className="w-5 h-5" />
               </Button>
            </div>
          </div>
        </main>
      </div>
    </AppShell>
  );
}

export default function PlayerPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    }>
      <PlayerContent />
    </Suspense>
  );
}
