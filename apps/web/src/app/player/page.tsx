"use client";

import { useEffect, useState, useCallback, useRef, useMemo, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Image from "next/image";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  ListMusic,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Headphones,
  Info,
  Moon,
  Minus,
  Plus,
  Settings2,
  Maximize2,
  X,
  Keyboard,
  FastForward,
  Cloud,
  HardDrive,
  AlertTriangle,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { getBooks, getPlaybackProgress } from "@/services/books";
import { getProgress as getLocalProgress } from "@/lib/db";
import { AppShell } from "@/components/layout/AppShell";
import { useActiveJobs } from "@/hooks/useJobs";
import {
  useBookDetails,
  useBookDetailsEnriched,
  useLocalItemDetails,
} from "@/hooks/useBooks";
import { usePlayerStore } from "@/store/playerStore";
import { useUIStore } from "@/store/uiStore";
import { API_URL } from "@/lib/env";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/Dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Slider } from "@/components/ui/Slider";
import {
  getCoverUrl,
  getPrimaryAuthor,
  getPrimaryNarrator,
  getSeriesInfo,
  formatRuntime,
  canPlay,
  type Book,
  type Series,
} from "@/types";

type PlayerChapter = {
  title: string;
  start_offset_ms: number;
  length_ms: number;
  index?: number;
  end_offset_ms?: number;
};

/**
 * Find the next book in a series given the current book
 */
function findNextInSeries(
  currentBook: Book,
  seriesBooks: Book[]
): Book | null {
  if (!currentBook.series || currentBook.series.length === 0) return null;

  const primarySeries = currentBook.series[0];
  const currentSequence = parseFloat(primarySeries.sequence || "0");

  // Sort books by sequence number
  const sortedBooks = seriesBooks
    .filter((b) => {
      if (!b.series) return false;
      const matchingSeries = b.series.find(
        (s) => s.title === primarySeries.title
      );
      return matchingSeries && matchingSeries.sequence;
    })
    .map((b) => {
      const matchingSeries = b.series!.find(
        (s) => s.title === primarySeries.title
      )!;
      return {
        book: b,
        sequence: parseFloat(matchingSeries.sequence || "0"),
      };
    })
    .sort((a, b) => a.sequence - b.sequence);

  // Find the next book after current sequence
  const nextBook = sortedBooks.find(
    (item) =>
      item.sequence > currentSequence &&
      item.book.asin !== currentBook.asin &&
      canPlay(item.book)
  );

  return nextBook?.book || null;
}

// Speed options with 0.1x granularity
const SPEED_OPTIONS = [
  0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9,
  2.0, 2.25, 2.5, 2.75, 3.0,
];

// Sleep timer options
const SLEEP_TIMER_OPTIONS = [
  { label: "15 minutes", value: 15 },
  { label: "30 minutes", value: 30 },
  { label: "45 minutes", value: 45 },
  { label: "60 minutes", value: 60 },
  { label: "90 minutes", value: 90 },
  { label: "End of chapter", value: -1 },
];

// Keyboard shortcuts info
const KEYBOARD_SHORTCUTS = [
  { key: "Space", action: "Play / Pause" },
  { key: "←", action: "Rewind 15s" },
  { key: "→", action: "Forward 30s" },
  { key: "↑", action: "Volume Up" },
  { key: "↓", action: "Volume Down" },
  { key: "M", action: "Mute / Unmute" },
  { key: "Shift + N", action: "Next Chapter" },
  { key: "Shift + P", action: "Previous Chapter" },
];

function PlayerContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const asin = searchParams.get("asin");
  const localId = searchParams.get("local_id");
  const addToast = useUIStore((state) => state.addToast);

  // Local UI state
  const [showMetadataModal, setShowMetadataModal] = useState(false);
  const [showSleepTimerModal, setShowSleepTimerModal] = useState(false);
  const [showKeyboardShortcuts, setShowKeyboardShortcuts] = useState(false);
  const [showSeriesModal, setShowSeriesModal] = useState(false);
  const [nextInSeries, setNextInSeries] = useState<Book | null>(null);
  const [showPositionConflictModal, setShowPositionConflictModal] =
    useState(false);
  const [positionConflict, setPositionConflict] = useState<{
    localTime: number;
    serverTime: number;
    localLastPlayed: string | null;
    serverLastPlayed: string | null;
  } | null>(null);
  const [sleepTimerMinutes, setSleepTimerMinutes] = useState<number | null>(
    null
  );
  const [sleepTimerEndTime, setSleepTimerEndTime] = useState<number | null>(
    null
  );
  const [sleepTimerChapterEnd, setSleepTimerChapterEnd] = useState(false);
  const [sleepTimerRemaining, setSleepTimerRemaining] = useState<string | null>(
    null
  );
  const originalVolumeRef = useRef<number>(1);
  const hasShownSeriesModalRef = useRef(false);

  const { data: activeJobs } = useActiveJobs();
  const { data: book, isLoading: isLoadingBook } = useBookDetails(asin, {
    enabled: !!asin && !localId,
  });
  const { data: bookDetails } = useBookDetailsEnriched(asin, {
    enabled: !!asin && !localId,
  });
  const { data: localItem, isLoading: isLoadingLocalItem } =
    useLocalItemDetails(localId, { enabled: !!localId });
  const setJobDrawerOpen = useUIStore((state) => state.setJobDrawerOpen);

  // Fetch books in the same series for seamless transition
  const seriesTitle = book?.series?.[0]?.title;
  const { data: seriesBooksData } = useQuery({
    queryKey: ["seriesBooks", seriesTitle],
    queryFn: () =>
      getBooks({
        series_title: seriesTitle!,
        status: "COMPLETED",
        page_size: 50,
      }),
    enabled: !!seriesTitle && !!book,
  });

  // Player Store
  const {
    isPlaying,
    isLoading: isPlayerLoading,
    currentTime,
    duration,
    volume,
    isMuted,
    playbackRate,
    loadBook,
    play,
    pause,
    toggle,
    seekRelative,
    seek,
    setVolume,
    setPlaybackRate,
    toggleMute,
    currentBookId,
    error: playerError,
  } = usePlayerStore();

  // Load book into player when asin changes or book details are fetched
  useEffect(() => {
    if (localItem && currentBookId !== `local:${localItem.id}`) {
      const audioUrl = `${API_URL}/stream/local/${localItem.id}`;
      loadBook(`local:${localItem.id}`, audioUrl, localItem.title);
      // Reset series modal state for new book
      hasShownSeriesModalRef.current = false;
      setNextInSeries(null);
      return;
    }
    if (book && canPlay(book) && currentBookId !== book.asin) {
      const audioUrl = `${API_URL}/stream/${book.asin}`;
      loadBook(book.asin, audioUrl, book.title);
      // Reset series modal state for new book
      hasShownSeriesModalRef.current = false;
      setNextInSeries(null);
    }
  }, [book, localItem, loadBook, currentBookId]);

  // Find next book in series when series data is loaded
  useEffect(() => {
    if (book && seriesBooksData?.items) {
      const next = findNextInSeries(book, seriesBooksData.items);
      setNextInSeries(next);
    }
  }, [book, seriesBooksData]);

  // Detect book completion and show series transition prompt
  useEffect(() => {
    if (!book || !nextInSeries || hasShownSeriesModalRef.current) return;

    // Check if we're at 99% or more of the book
    const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

    if (progressPercent >= 99 && !isPlaying) {
      hasShownSeriesModalRef.current = true;
      setShowSeriesModal(true);
    }
  }, [book, nextInSeries, currentTime, duration, isPlaying]);

  // Position conflict detection - check server vs local progress
  const hasCheckedConflictRef = useRef<string | null>(null);
  useEffect(() => {
    // Only check for ASIN-based books (not local items)
    if (!asin || !book || !duration || duration === 0) return;
    // Only check once per book load
    if (hasCheckedConflictRef.current === asin) return;

    const checkPositionConflict = async () => {
      hasCheckedConflictRef.current = asin;

      try {
        // Fetch local progress first (always available)
        const localProgress = await getLocalProgress(asin).catch(() => null);

        // Try to fetch server progress - gracefully handle if endpoint not available
        let serverProgress = null;
        try {
          serverProgress = await getPlaybackProgress(asin);
        } catch {
          // Server endpoint may not be available - this is fine, skip conflict check
          return;
        }

        // If neither has progress, no conflict
        if (!localProgress && !serverProgress) {
          return;
        }

        const localTimeSeconds = localProgress?.currentTime ?? 0;
        const serverTimeSeconds = serverProgress
          ? serverProgress.position_ms / 1000
          : 0;

        // Calculate difference in seconds
        const timeDiff = Math.abs(localTimeSeconds - serverTimeSeconds);

        // Only show conflict if difference is > 30 seconds and both have progress
        const CONFLICT_THRESHOLD_SECONDS = 30;
        if (
          timeDiff > CONFLICT_THRESHOLD_SECONDS &&
          localTimeSeconds > 0 &&
          serverTimeSeconds > 0
        ) {
          setPositionConflict({
            localTime: localTimeSeconds,
            serverTime: serverTimeSeconds,
            localLastPlayed: localProgress?.lastPlayedAt ?? null,
            serverLastPlayed: serverProgress?.last_played_at ?? null,
          });
          setShowPositionConflictModal(true);
        }
      } catch (err) {
        // Silently fail - position conflict check is non-critical
      }
    };

    checkPositionConflict();
  }, [asin, book, duration]);

  // Derived data
  const chapters = useMemo(() => {
    const enriched = bookDetails?.chapters?.length ? bookDetails.chapters : null;
    const basic = book?.chapters?.length ? book.chapters : null;

    const fromApi = enriched ?? basic;
    if (fromApi && fromApi.length > 0) return fromApi;

    // UI fallback: if we have audio duration but no chapter metadata yet,
    // synthesize a single full-length chapter so navigation/UI never breaks.
    // Use API's duration_total_ms first, then fall back to audio element duration.
    const fallbackDurationMs = bookDetails?.duration_total_ms ?? (duration > 0 ? Math.floor(duration * 1000) : 0);
    if (fallbackDurationMs > 0) {
      return [
        {
          index: 0,
          title: "Full Duration",
          start_offset_ms: 0,
          length_ms: fallbackDurationMs,
          end_offset_ms: fallbackDurationMs,
        },
      ] satisfies PlayerChapter[];
    }

    return [];
  }, [bookDetails?.chapters, bookDetails?.duration_total_ms, book?.chapters, duration]);

  const isChaptersSynthetic =
    !!bookDetails?.chapters_synthetic ||
    (!bookDetails?.chapters?.length && !book?.chapters?.length && (duration > 0 || (bookDetails?.duration_total_ms ?? 0) > 0));

  // Find current chapter based on currentTime
  const getCurrentChapter = useCallback((): {
    chapter: PlayerChapter | null;
    index: number;
  } => {
    if (!chapters.length) return { chapter: null, index: -1 };
    const currentMs = currentTime * 1000;
    for (let i = chapters.length - 1; i >= 0; i--) {
      if (currentMs >= chapters[i].start_offset_ms) {
        return { chapter: chapters[i], index: i };
      }
    }
    return { chapter: chapters[0], index: 0 };
  }, [chapters, currentTime]);

  const { chapter: currentChapter, index: currentChapterIndex } =
    getCurrentChapter();

  // Sleep timer countdown display
  useEffect(() => {
    if (sleepTimerEndTime === null && !sleepTimerChapterEnd) {
      setSleepTimerRemaining(null);
      return;
    }

    if (sleepTimerChapterEnd) {
      setSleepTimerRemaining("End of chapter");
      return;
    }

    const updateRemaining = () => {
      if (sleepTimerEndTime === null) return;
      const remaining = Math.max(0, sleepTimerEndTime - Date.now());
      const mins = Math.floor(remaining / 60000);
      const secs = Math.floor((remaining % 60000) / 1000);
      setSleepTimerRemaining(`${mins}:${secs.toString().padStart(2, "0")}`);
    };

    updateRemaining();
    const interval = setInterval(updateRemaining, 1000);
    return () => clearInterval(interval);
  }, [sleepTimerEndTime, sleepTimerChapterEnd]);

  // Sleep timer logic
  useEffect(() => {
    if (!isPlaying || sleepTimerMinutes === null) return;

    // Handle "End of chapter" mode
    if (sleepTimerChapterEnd && currentChapter) {
      const chapterEndMs =
        currentChapter.start_offset_ms + currentChapter.length_ms;
      const chapterEndSec = chapterEndMs / 1000;
      // If we're within 2 seconds of chapter end, trigger sleep
      if (currentTime >= chapterEndSec - 2) {
        // Gradual fade out
        let fadeVolume = volume;
        const fadeInterval = setInterval(() => {
          fadeVolume = Math.max(0, fadeVolume - 0.1);
          setVolume(fadeVolume);
          if (fadeVolume <= 0) {
            clearInterval(fadeInterval);
            pause();
            setSleepTimerMinutes(null);
            setSleepTimerEndTime(null);
            setSleepTimerChapterEnd(false);
            setVolume(originalVolumeRef.current);
            addToast({
              type: "info",
              title: "Sleep Timer",
              message: "Playback paused at end of chapter",
            });
          }
        }, 100);
        return () => clearInterval(fadeInterval);
      }
      return;
    }

    // Handle time-based sleep timer
    if (sleepTimerEndTime !== null) {
      const now = Date.now();
      const remaining = sleepTimerEndTime - now;

      if (remaining <= 0) {
        pause();
        setSleepTimerMinutes(null);
        setSleepTimerEndTime(null);
        setVolume(originalVolumeRef.current);
        addToast({
          type: "info",
          title: "Sleep Timer",
          message: "Playback paused",
        });
        return;
      }

      // Start fade-out in the last 60 seconds
      if (remaining <= 60000 && remaining > 0) {
        const fadePercent = remaining / 60000;
        const targetVolume = Math.max(
          0.05,
          originalVolumeRef.current * fadePercent
        );
        if (volume > targetVolume) {
          setVolume(targetVolume);
        }
      }
    }
  }, [
    isPlaying,
    currentTime,
    sleepTimerMinutes,
    sleepTimerEndTime,
    sleepTimerChapterEnd,
    currentChapter,
    pause,
    setVolume,
    volume,
    addToast,
  ]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in inputs or when modals are open
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }

      switch (e.code) {
        case "Space":
          e.preventDefault();
          toggle();
          break;
        case "ArrowLeft":
          e.preventDefault();
          seekRelative(-15);
          break;
        case "ArrowRight":
          e.preventDefault();
          seekRelative(30);
          break;
        case "ArrowUp":
          e.preventDefault();
          setVolume(Math.min(1, volume + 0.1));
          break;
        case "ArrowDown":
          e.preventDefault();
          setVolume(Math.max(0, volume - 0.1));
          break;
        case "KeyM":
          e.preventDefault();
          toggleMute();
          break;
        case "KeyN":
          if (e.shiftKey && chapters.length > 0) {
            e.preventDefault();
            const currentMs = currentTime * 1000;
            const nextChapter = chapters.find(
              (ch) => ch.start_offset_ms > currentMs
            );
            if (nextChapter) {
              seek(nextChapter.start_offset_ms / 1000);
            }
          }
          break;
        case "KeyP":
          if (e.shiftKey && chapters.length > 0) {
            e.preventDefault();
            const currentMs = currentTime * 1000;
            let prevChapter: PlayerChapter | null = null;
            for (const ch of chapters) {
              if (ch.start_offset_ms >= currentMs - 3000) break;
              prevChapter = ch;
            }
            if (prevChapter) {
              seek(prevChapter.start_offset_ms / 1000);
            }
          }
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    toggle,
    seekRelative,
    setVolume,
    toggleMute,
    volume,
    seek,
    chapters,
    currentTime,
  ]);

  // Media Session API integration
  useEffect(() => {
    if (!("mediaSession" in navigator)) return;

    const mediaTitle = localItem?.title ?? book?.title ?? "Audiobook";
    const artist =
      localItem?.authors ?? (book ? getPrimaryAuthor(book) : "Unknown Author");
    const mediaCoverUrl = book ? getCoverUrl(book, "500") : undefined;

    navigator.mediaSession.metadata = new MediaMetadata({
      title: mediaTitle,
      artist,
      album: book?.series?.[0]?.title || "Audiobook",
      artwork: mediaCoverUrl
        ? [
            { src: mediaCoverUrl, sizes: "96x96", type: "image/jpeg" },
            { src: mediaCoverUrl, sizes: "128x128", type: "image/jpeg" },
            { src: mediaCoverUrl, sizes: "192x192", type: "image/jpeg" },
            { src: mediaCoverUrl, sizes: "256x256", type: "image/jpeg" },
            { src: mediaCoverUrl, sizes: "384x384", type: "image/jpeg" },
            { src: mediaCoverUrl, sizes: "512x512", type: "image/jpeg" },
          ]
        : [],
    });

    navigator.mediaSession.setActionHandler("play", () => play());
    navigator.mediaSession.setActionHandler("pause", () => pause());
    navigator.mediaSession.setActionHandler("seekbackward", () =>
      seekRelative(-15)
    );
    navigator.mediaSession.setActionHandler("seekforward", () =>
      seekRelative(30)
    );
    navigator.mediaSession.setActionHandler("previoustrack", () => {
      if (chapters.length > 0) {
        const currentMs = currentTime * 1000;
        let prevChapter: PlayerChapter | null = null;
        for (const ch of chapters) {
          if (ch.start_offset_ms >= currentMs - 3000) break;
          prevChapter = ch;
        }
        if (prevChapter) {
          seek(prevChapter.start_offset_ms / 1000);
        }
      }
    });
    navigator.mediaSession.setActionHandler("nexttrack", () => {
      if (chapters.length > 0) {
        const currentMs = currentTime * 1000;
        const nextChapter = chapters.find(
          (ch) => ch.start_offset_ms > currentMs
        );
        if (nextChapter) {
          seek(nextChapter.start_offset_ms / 1000);
        }
      }
    });

    // Update playback state
    navigator.mediaSession.playbackState = isPlaying ? "playing" : "paused";

    // Update position state
    if (duration > 0) {
      navigator.mediaSession.setPositionState({
        duration,
        playbackRate,
        position: currentTime,
      });
    }

    return () => {
      navigator.mediaSession.setActionHandler("play", null);
      navigator.mediaSession.setActionHandler("pause", null);
      navigator.mediaSession.setActionHandler("seekbackward", null);
      navigator.mediaSession.setActionHandler("seekforward", null);
      navigator.mediaSession.setActionHandler("previoustrack", null);
      navigator.mediaSession.setActionHandler("nexttrack", null);
    };
  }, [
    book,
    localItem,
    isPlaying,
    currentTime,
    duration,
    playbackRate,
    play,
    pause,
    seek,
    seekRelative,
    chapters,
  ]);

  const formatTime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, "0")}:${s
        .toString()
        .padStart(2, "0")}`;
    }
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const handleProgressChange = (value: number[]) => {
    if (value[0] !== undefined) {
      seek(value[0]);
    }
  };

  const handleVolumeChange = (value: number[]) => {
    if (value[0] !== undefined) {
      setVolume(value[0] / 100);
    }
  };

  const handleSpeedChange = (value: string) => {
    setPlaybackRate(parseFloat(value));
  };

  const handleSpeedIncrement = (delta: number) => {
    const currentIndex = SPEED_OPTIONS.findIndex(
      (s) => Math.abs(s - playbackRate) < 0.01
    );
    const newIndex = Math.max(
      0,
      Math.min(SPEED_OPTIONS.length - 1, currentIndex + delta)
    );
    setPlaybackRate(SPEED_OPTIONS[newIndex]);
  };

  const handleSleepTimer = (minutes: number) => {
    originalVolumeRef.current = volume;
    if (minutes === -1) {
      setSleepTimerMinutes(-1);
      setSleepTimerChapterEnd(true);
      setSleepTimerEndTime(null);
      addToast({
        type: "info",
        title: "Sleep Timer Set",
        message: "Playback will pause at end of current chapter",
      });
    } else {
      setSleepTimerMinutes(minutes);
      setSleepTimerEndTime(Date.now() + minutes * 60 * 1000);
      setSleepTimerChapterEnd(false);
      addToast({
        type: "info",
        title: "Sleep Timer Set",
        message: `Playback will pause in ${minutes} minutes`,
      });
    }
    setShowSleepTimerModal(false);
  };

  const cancelSleepTimer = () => {
    setSleepTimerMinutes(null);
    setSleepTimerEndTime(null);
    setSleepTimerChapterEnd(false);
    setVolume(originalVolumeRef.current);
    addToast({
      type: "info",
      title: "Sleep Timer Cancelled",
      message: "Sleep timer has been cancelled",
    });
  };

  // Play next book in series
  const handlePlayNextInSeries = () => {
    if (nextInSeries) {
      setShowSeriesModal(false);
      router.push(`/player?asin=${nextInSeries.asin}`);
    }
  };

  // Handle position conflict resolution
  const handleUseServerPosition = () => {
    if (positionConflict) {
      seek(positionConflict.serverTime);
      addToast({
        type: "info",
        title: "Position Updated",
        message: "Using server position",
      });
    }
    setShowPositionConflictModal(false);
    setPositionConflict(null);
  };

  const handleUseLocalPosition = () => {
    if (positionConflict) {
      seek(positionConflict.localTime);
      addToast({
        type: "info",
        title: "Position Updated",
        message: "Using local position",
      });
    }
    setShowPositionConflictModal(false);
    setPositionConflict(null);
  };

  // Navigate to next/previous chapter
  const goToNextChapter = () => {
    if (currentChapterIndex < chapters.length - 1) {
      seek(chapters[currentChapterIndex + 1].start_offset_ms / 1000);
    }
  };

  const goToPrevChapter = () => {
    // If more than 3 seconds into chapter, restart chapter; otherwise go to previous
    const chapterStartSec = currentChapter
      ? currentChapter.start_offset_ms / 1000
      : 0;
    if (currentTime - chapterStartSec > 3 && currentChapter) {
      seek(chapterStartSec);
    } else if (currentChapterIndex > 0) {
      seek(chapters[currentChapterIndex - 1].start_offset_ms / 1000);
    }
  };

  const isLoadingDetails = isLoadingBook || isLoadingLocalItem;
  const title = localItem?.title ?? book?.title ?? "Select a Book";
  const author =
    localItem?.authors ?? (book ? getPrimaryAuthor(book) : "Unknown Author");
  const coverUrl = book ? getCoverUrl(book, "1215") : null;

  // Calculate chapter progress percentages for segmented progress bar
  const chapterSegments = chapters.map((ch) => ({
    start: duration > 0 ? (ch.start_offset_ms / 1000 / duration) * 100 : 0,
    width:
      duration > 0 ? (ch.length_ms / 1000 / duration) * 100 : 100 / chapters.length,
    title: ch.title,
  }));

  return (
    <AppShell
      sidebarProps={{
        activeJobCount: activeJobs?.total ?? 0,
        activePath: "/player",
        onJobsClick: () => setJobDrawerOpen(true),
      }}
      headerProps={{
        title: "Now Playing",
      }}
      hidePlayer
    >
      <div className="flex flex-col lg:flex-row h-full gap-8 max-w-6xl mx-auto">
        {/* Left Side: Cover Art & Chapters */}
        <aside className="w-full lg:w-80 flex flex-col gap-6 shrink-0 order-1 lg:order-1">
          {/* Back to Library - Local to player */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push("/library")}
            className="self-start gap-2 -mt-2"
          >
            <ChevronLeft className="w-4 h-4" />
            Back to Library
          </Button>

          {/* Cover Art */}
          <div
            className="aspect-square relative bg-card border border-border rounded-xl shadow-lg overflow-hidden group"
            style={{ viewTransitionName: "player-cover" }}
          >
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
                priority
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

          {/* Chapter List Card - Hidden on mobile, shown on desktop */}
          <div className="bg-card border border-border rounded-xl flex-1 min-h-[200px] lg:min-h-[300px] flex flex-col overflow-hidden shadow-sm hidden lg:flex">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <h2 className="font-semibold flex items-center gap-2">
                <ListMusic className="w-4 h-4 text-primary" />
                Chapters
              </h2>
              <div className="flex items-center gap-2">
                {isChaptersSynthetic && (
                  <span className="text-xs text-muted-foreground">
                    Loading...
                  </span>
                )}
                <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                  {chapters.length}
                </span>
              </div>
            </div>
            <div className="flex-1 overflow-auto">
              {chapters.length > 0 ? (
                <div className="divide-y divide-border">
                  {chapters.map((chapter, i) => {
                    const isActive = i === currentChapterIndex;
                    return (
                      <button
                        key={i}
                        onClick={() => seek(chapter.start_offset_ms / 1000)}
                        className={`w-full px-4 py-3 text-left hover:bg-muted/50 transition-colors flex items-center justify-between group ${
                          isActive ? "bg-primary/10" : ""
                        }`}
                      >
                        <span
                          className={`text-sm font-medium line-clamp-1 group-hover:text-primary transition-colors ${
                            isActive ? "text-primary" : ""
                          }`}
                        >
                          {chapter.title}
                        </span>
                        <span className="text-xs text-muted-foreground font-mono ml-2 shrink-0">
                          {formatTime(chapter.length_ms / 1000)}
                        </span>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center text-muted-foreground py-12 px-6">
                  <p className="text-sm font-medium text-foreground/70">
                    No Chapters Available
                  </p>
                  <p className="text-xs mt-1">
                    This book doesn&apos;t have chapter markers.
                  </p>
                </div>
              )}
            </div>
          </div>
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
          <div className="text-center mb-8 w-full">
            <h1 className="text-2xl lg:text-3xl font-bold tracking-tight mb-2 line-clamp-2">
              {title}
            </h1>
            <p className="text-base lg:text-lg text-muted-foreground mb-3">
              {author}
            </p>
            <div className="flex items-center justify-center gap-3 text-sm text-muted-foreground font-medium flex-wrap">
              <span className="bg-secondary px-3 py-1 rounded-full">
                {(
                  localItem?.format ??
                  book?.conversion_format ??
                  "audio"
                ).toUpperCase()}
              </span>
              <span>{book ? formatRuntime(book.runtime_length_min) : "--:--"}</span>
              {currentChapter && (
                <span className="text-primary">{currentChapter.title}</span>
              )}
            </div>
          </div>

          {/* Segmented Progress Bar */}
          <div className="w-full max-w-2xl mb-6 group">
            <div className="flex justify-between text-sm font-mono text-muted-foreground mb-2 px-1">
              <span className="text-foreground">{formatTime(currentTime)}</span>
              <span>{formatTime(duration)}</span>
            </div>

            {/* Chapter-segmented timeline */}
            <div className="relative h-3 w-full">
              {/* Background track with chapter segments */}
              <div className="absolute inset-0 flex gap-0.5 rounded-full overflow-hidden">
                {chapterSegments.length > 0 ? (
                  chapterSegments.map((seg, i) => (
                    <div
                      key={i}
                      className="h-full bg-secondary hover:bg-secondary/80 transition-colors relative group/seg"
                      style={{ width: `${seg.width}%` }}
                      title={seg.title}
                    >
                      {/* Tooltip on hover */}
                      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-popover text-popover-foreground text-xs rounded shadow-lg opacity-0 group-hover/seg:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                        {seg.title}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="h-full w-full bg-secondary rounded-full" />
                )}
              </div>

              {/* Progress overlay */}
              <div
                className="absolute inset-y-0 left-0 bg-primary rounded-full pointer-events-none"
                style={{
                  width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%`,
                }}
              />

              {/* Interactive slider overlay */}
              <input
                type="range"
                min="0"
                max={duration || 1}
                step="1"
                value={currentTime}
                onChange={(e) => seek(parseFloat(e.target.value))}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />

              {/* Thumb indicator */}
              <div
                className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-primary rounded-full shadow-lg pointer-events-none transition-transform group-hover:scale-125"
                style={{
                  left: `calc(${duration > 0 ? (currentTime / duration) * 100 : 0}% - 8px)`,
                }}
              />
            </div>
          </div>

          {/* Main Controls */}
          <div className="flex items-center gap-4 lg:gap-8 mb-8">
            {/* Previous Chapter */}
            <Button
              variant="ghost"
              size="icon"
              className="h-10 w-10 lg:h-12 lg:w-12 rounded-full"
              onClick={goToPrevChapter}
              disabled={chapters.length === 0}
              title="Previous Chapter (Shift+P)"
            >
              <ChevronLeft className="w-5 h-5 lg:w-6 lg:h-6" />
            </Button>

            {/* Skip Back */}
            <Button
              variant="ghost"
              size="icon"
              className="h-10 w-10 lg:h-12 lg:w-12 rounded-full"
              onClick={() => seekRelative(-15)}
              title="Skip back 15s (←)"
            >
              <SkipBack className="w-5 h-5 lg:w-7 lg:h-7" />
            </Button>

            {/* Play/Pause */}
            <Button
              onClick={toggle}
              disabled={(!asin && !localId) || isPlayerLoading}
              className="h-16 w-16 lg:h-20 lg:w-20 rounded-full shadow-xl hover:scale-105 transition-transform"
              title="Play/Pause (Space)"
            >
              {isPlayerLoading ? (
                <Loader2 className="w-8 h-8 lg:w-10 lg:h-10 animate-spin" />
              ) : isPlaying ? (
                <Pause className="w-8 h-8 lg:w-10 lg:h-10 fill-current" />
              ) : (
                <Play className="w-8 h-8 lg:w-10 lg:h-10 ml-1 fill-current" />
              )}
            </Button>

            {/* Skip Forward */}
            <Button
              variant="ghost"
              size="icon"
              className="h-10 w-10 lg:h-12 lg:w-12 rounded-full"
              onClick={() => seekRelative(30)}
              title="Skip forward 30s (→)"
            >
              <SkipForward className="w-5 h-5 lg:w-7 lg:h-7" />
            </Button>

            {/* Next Chapter */}
            <Button
              variant="ghost"
              size="icon"
              className="h-10 w-10 lg:h-12 lg:w-12 rounded-full"
              onClick={goToNextChapter}
              disabled={
                chapters.length === 0 ||
                currentChapterIndex >= chapters.length - 1
              }
              title="Next Chapter (Shift+N)"
            >
              <ChevronRight className="w-5 h-5 lg:w-6 lg:h-6" />
            </Button>
          </div>

          {/* Footer Controls */}
          <div className="flex flex-wrap items-center justify-center gap-4 lg:gap-6 w-full max-w-2xl p-4 lg:p-6 bg-card/50 border border-border rounded-2xl backdrop-blur-sm">
            {/* Volume */}
            <div className="flex items-center gap-2 w-32 lg:w-40">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0"
                onClick={toggleMute}
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

            {/* Playback Speed with increment buttons */}
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => handleSpeedIncrement(-1)}
                disabled={playbackRate <= SPEED_OPTIONS[0]}
              >
                <Minus className="w-3 h-3" />
              </Button>
              <Select
                value={playbackRate.toString()}
                onValueChange={handleSpeedChange}
              >
                <SelectTrigger className="w-20 h-8 text-sm font-semibold">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SPEED_OPTIONS.map((rate) => (
                    <SelectItem key={rate} value={rate.toString()}>
                      {rate}x
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => handleSpeedIncrement(1)}
                disabled={
                  playbackRate >= SPEED_OPTIONS[SPEED_OPTIONS.length - 1]
                }
              >
                <Plus className="w-3 h-3" />
              </Button>
            </div>

            {/* Sleep Timer */}
            <div className="flex items-center gap-1">
              {sleepTimerMinutes !== null ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={cancelSleepTimer}
                  className="gap-1 h-8 text-xs"
                >
                  <Moon className="w-3 h-3" />
                  {sleepTimerRemaining}
                  <X className="w-3 h-3" />
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowSleepTimerModal(true)}
                  title="Sleep Timer"
                >
                  <Moon className="w-4 h-4" />
                </Button>
              )}
            </div>

            {/* Book Info */}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={() => setShowMetadataModal(true)}
              title="Book Details"
            >
              <Info className="w-4 h-4" />
            </Button>

            {/* Next in Series */}
            {nextInSeries && (
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-1 text-muted-foreground hover:text-foreground hidden lg:flex"
                onClick={() => setShowSeriesModal(true)}
                title="Next in Series"
              >
                <FastForward className="w-4 h-4" />
                <span className="text-xs">Next</span>
              </Button>
            )}

            {/* Keyboard Shortcuts */}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground hidden lg:flex"
              onClick={() => setShowKeyboardShortcuts(true)}
              title="Keyboard Shortcuts"
            >
              <Keyboard className="w-4 h-4" />
            </Button>

            {/* Mobile Chapters Toggle */}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground lg:hidden"
              onClick={() => {
                // Scroll to chapters or show modal
                document
                  .getElementById("mobile-chapters")
                  ?.scrollIntoView({ behavior: "smooth" });
              }}
            >
              <ListMusic className="w-4 h-4" />
            </Button>
          </div>
        </main>

        {/* Mobile Chapters Section */}
        <div
          id="mobile-chapters"
          className="w-full lg:hidden order-3 bg-card border border-border rounded-xl overflow-hidden shadow-sm"
        >
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h2 className="font-semibold flex items-center gap-2">
              <ListMusic className="w-4 h-4 text-primary" />
              Chapters
            </h2>
            <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
              {chapters.length}
            </span>
          </div>
          <div className="max-h-[400px] overflow-auto">
            {chapters.length > 0 ? (
              <div className="divide-y divide-border">
                {chapters.map((chapter, i) => {
                  const isActive = i === currentChapterIndex;
                  return (
                    <button
                      key={i}
                      onClick={() => seek(chapter.start_offset_ms / 1000)}
                      className={`w-full px-4 py-3 text-left hover:bg-muted/50 transition-colors flex items-center justify-between ${
                        isActive ? "bg-primary/10" : ""
                      }`}
                    >
                      <span
                        className={`text-sm font-medium line-clamp-1 ${
                          isActive ? "text-primary" : ""
                        }`}
                      >
                        {chapter.title}
                      </span>
                      <span className="text-xs text-muted-foreground font-mono ml-2 shrink-0">
                        {formatTime(chapter.length_ms / 1000)}
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="text-center text-muted-foreground py-12 px-6">
                <p className="text-sm font-medium text-foreground/70">
                  No Chapters
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Metadata Modal */}
      <Dialog open={showMetadataModal} onOpenChange={setShowMetadataModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Book Details</DialogTitle>
            <DialogDescription>
              Extended information about this audiobook
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-[120px_1fr] gap-2">
              <span className="text-muted-foreground">Title</span>
              <span className="font-medium">{book?.title || localItem?.title || "N/A"}</span>
            </div>
            {book?.subtitle && (
              <div className="grid grid-cols-[120px_1fr] gap-2">
                <span className="text-muted-foreground">Subtitle</span>
                <span>{book.subtitle}</span>
              </div>
            )}
            <div className="grid grid-cols-[120px_1fr] gap-2">
              <span className="text-muted-foreground">Author(s)</span>
              <span>
                {book?.authors?.map((a) => a.name).join(", ") ||
                  localItem?.authors ||
                  "N/A"}
              </span>
            </div>
            <div className="grid grid-cols-[120px_1fr] gap-2">
              <span className="text-muted-foreground">Narrator(s)</span>
              <span>
                {book?.narrators?.map((n) => n.name).join(", ") || "N/A"}
              </span>
            </div>
            {book?.series && book.series.length > 0 && (
              <div className="grid grid-cols-[120px_1fr] gap-2">
                <span className="text-muted-foreground">Series</span>
                <span>{getSeriesInfo(book)}</span>
              </div>
            )}
            {book?.publisher && (
              <div className="grid grid-cols-[120px_1fr] gap-2">
                <span className="text-muted-foreground">Publisher</span>
                <span>{book.publisher}</span>
              </div>
            )}
            {book?.language && (
              <div className="grid grid-cols-[120px_1fr] gap-2">
                <span className="text-muted-foreground">Language</span>
                <span className="capitalize">{book.language}</span>
              </div>
            )}
            <div className="grid grid-cols-[120px_1fr] gap-2">
              <span className="text-muted-foreground">Duration</span>
              <span>
                {book
                  ? formatRuntime(book.runtime_length_min)
                  : formatTime(duration)}
              </span>
            </div>
            <div className="grid grid-cols-[120px_1fr] gap-2">
              <span className="text-muted-foreground">Format</span>
              <span className="uppercase">
                {localItem?.format || book?.conversion_format || "N/A"}
              </span>
            </div>
            {book?.asin && (
              <div className="grid grid-cols-[120px_1fr] gap-2">
                <span className="text-muted-foreground">ASIN</span>
                <span className="font-mono text-xs">{book.asin}</span>
              </div>
            )}
            {book?.local_path_converted && (
              <div className="grid grid-cols-[120px_1fr] gap-2">
                <span className="text-muted-foreground">File Path</span>
                <span className="font-mono text-xs break-all">
                  {book.local_path_converted}
                </span>
              </div>
            )}
            {bookDetails?.description && (
              <div className="pt-4 border-t">
                <span className="text-muted-foreground block mb-2">
                  Description
                </span>
                <p className="text-sm leading-relaxed">
                  {bookDetails.description}
                </p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Sleep Timer Modal */}
      <Dialog open={showSleepTimerModal} onOpenChange={setShowSleepTimerModal}>
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
                onClick={() => handleSleepTimer(option.value)}
              >
                {option.label}
              </Button>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Keyboard Shortcuts Modal */}
      <Dialog
        open={showKeyboardShortcuts}
        onOpenChange={setShowKeyboardShortcuts}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Keyboard className="w-5 h-5" />
              Keyboard Shortcuts
            </DialogTitle>
          </DialogHeader>
          <div className="grid gap-2">
            {KEYBOARD_SHORTCUTS.map((shortcut) => (
              <div
                key={shortcut.key}
                className="flex items-center justify-between py-2 border-b border-border last:border-0"
              >
                <span className="text-sm text-muted-foreground">
                  {shortcut.action}
                </span>
                <kbd className="px-2 py-1 text-xs font-mono bg-muted rounded">
                  {shortcut.key}
                </kbd>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Series Transition Modal */}
      <Dialog open={showSeriesModal} onOpenChange={setShowSeriesModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FastForward className="w-5 h-5 text-primary" />
              Next in Series
            </DialogTitle>
            <DialogDescription>
              You&apos;ve finished this book! Ready for the next one?
            </DialogDescription>
          </DialogHeader>

          {nextInSeries && (
            <div className="flex gap-4 items-start py-4">
              {/* Next book cover */}
              <div className="w-20 h-20 shrink-0 rounded-lg overflow-hidden bg-muted">
                {getCoverUrl(nextInSeries, "500") ? (
                  <Image
                    src={getCoverUrl(nextInSeries, "500")!}
                    alt={nextInSeries.title}
                    width={80}
                    height={80}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <Headphones className="w-8 h-8 text-muted-foreground/50" />
                  </div>
                )}
              </div>

              {/* Next book info */}
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-base line-clamp-2">
                  {nextInSeries.title}
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {getPrimaryAuthor(nextInSeries)}
                </p>
                {nextInSeries.series?.[0] && (
                  <p className="text-xs text-primary mt-1">
                    {getSeriesInfo(nextInSeries)}
                  </p>
                )}
                <p className="text-xs text-muted-foreground mt-1">
                  {formatRuntime(nextInSeries.runtime_length_min)}
                </p>
              </div>
            </div>
          )}

          <div className="flex gap-3 justify-end">
            <Button
              variant="outline"
              onClick={() => setShowSeriesModal(false)}
            >
              Not Now
            </Button>
            <Button onClick={handlePlayNextInSeries}>
              <Play className="w-4 h-4 mr-2" />
              Play Now
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Position Conflict Modal */}
      <Dialog
        open={showPositionConflictModal}
        onOpenChange={setShowPositionConflictModal}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-yellow-500" />
              Position Conflict Detected
            </DialogTitle>
            <DialogDescription>
              Your local and server positions are different. Which would you
              like to use?
            </DialogDescription>
          </DialogHeader>

          {positionConflict && (
            <div className="space-y-4 py-4">
              {/* Server Position Option */}
              <button
                onClick={handleUseServerPosition}
                className="w-full p-4 border border-border rounded-lg hover:border-primary hover:bg-primary/5 transition-colors text-left group"
              >
                <div className="flex items-start gap-3">
                  <Cloud className="w-5 h-5 text-blue-500 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-medium group-hover:text-primary transition-colors">
                      Server Position
                    </p>
                    <p className="text-2xl font-mono font-bold text-foreground mt-1">
                      {formatTime(positionConflict.serverTime)}
                    </p>
                    {positionConflict.serverLastPlayed && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Last played:{" "}
                        {new Date(
                          positionConflict.serverLastPlayed
                        ).toLocaleString()}
                      </p>
                    )}
                  </div>
                </div>
              </button>

              {/* Local Position Option */}
              <button
                onClick={handleUseLocalPosition}
                className="w-full p-4 border border-border rounded-lg hover:border-primary hover:bg-primary/5 transition-colors text-left group"
              >
                <div className="flex items-start gap-3">
                  <HardDrive className="w-5 h-5 text-green-500 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-medium group-hover:text-primary transition-colors">
                      Local Position
                    </p>
                    <p className="text-2xl font-mono font-bold text-foreground mt-1">
                      {formatTime(positionConflict.localTime)}
                    </p>
                    {positionConflict.localLastPlayed && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Last played:{" "}
                        {new Date(
                          positionConflict.localLastPlayed
                        ).toLocaleString()}
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
    </AppShell>
  );
}

export default function PlayerPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-screen">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      }
    >
      <PlayerContent />
    </Suspense>
  );
}
