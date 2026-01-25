/**
 * Player Store
 * Zustand store for audio playback state with Howler.js integration
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { useShallow } from "zustand/react/shallow";
import { Howl } from "howler";
import { safeLocalStorage } from "@/lib/utils";
import { saveProgress, getProgress } from "@/lib/db";
import { updatePlaybackProgress, getBookDetailsEnriched } from "@/services/books";
import { Chapter } from "@/types";

// Smart resume threshold in hours - if user hasn't listened for this long, rewind for context
const SMART_RESUME_THRESHOLD_HOURS = 24;
// How many seconds to rewind when smart resume triggers
const SMART_RESUME_REWIND_SECONDS = 20;

/**
 * Player state interface
 */
export interface PlayerState {
  isPlaying: boolean;
  isLoading: boolean;
  currentTime: number;
  duration: number;
  bufferedTime: number;

  currentBookId: string | null;
  currentBookTitle: string | null;
  currentAudioUrl: string | null;

  chapters: Chapter[];
  currentChapterIndex: number | null;

  volume: number;
  playbackRate: number;
  isMuted: boolean;

  sleepTimer: {
    endTime: number | null;
    timeLeft: number | null;
    totalDuration: number | null;
  };

  lastPlayedAt: string | null;
  smartResumeMessage: string | null;
  error: string | null;
}

/**
 * Player actions interface
 */
export interface PlayerActions {
  // Playback controls
  play: () => void;
  pause: () => void;
  toggle: () => void;
  stop: () => void;

  seek: (time: number) => void;
  seekRelative: (delta: number) => void;

  // Chapter navigation
  nextChapter: () => void;
  prevChapter: () => void;
  seekToChapter: (index: number) => void;

  // Book loading
  loadBook: (bookId: string, audioUrl: string, title: string) => Promise<void>;
  unloadBook: () => void;

  // Settings
  setVolume: (volume: number) => void;
  setPlaybackRate: (rate: number) => void;
  toggleMute: () => void;

  // Sleep timer
  setSleepTimer: (minutes: number | null) => void;

  // Internal state updates (used by some UI/tests)
  _setCurrentTime: (currentTime: number) => void;
  _setDuration: (duration: number) => void;
  _setIsLoading: (isLoading: boolean) => void;
  _setError: (error: string | null) => void;

  // Smart resume
  clearSmartResumeMessage: () => void;
}

export type PlayerStore = PlayerState & PlayerActions;

// Howl instance (not stored in state to avoid serialization issues)
let howlInstance: Howl | null = null;

// Position save interval
let savePositionInterval: ReturnType<typeof setInterval> | null = null;
const SAVE_POSITION_INTERVAL = 5000; // Save every 5 seconds

// Sleep timer interval
let sleepTimerInterval: ReturnType<typeof setInterval> | null = null;

/**
 * Start position save interval
 */
function startPositionSaveInterval(
  getState: () => PlayerStore
): void {
// ... existing function ...
}

/**
 * Stop position save interval
 */
function stopPositionSaveInterval(): void {
  if (savePositionInterval) {
    clearInterval(savePositionInterval);
    savePositionInterval = null;
  }
}

/**
 * Update current chapter index based on time
 */
function updateChapterIndex(currentTime: number, chapters: Chapter[]): number | null {
  if (!chapters || chapters.length === 0) return null;
  
  const currentTimeMs = currentTime * 1000;
  for (let i = chapters.length - 1; i >= 0; i--) {
    if (currentTimeMs >= chapters[i].start_offset_ms) {
      return i;
    }
  }
  return 0;
}

/**
 * Player store with persistence
 */
export const usePlayerStore = create<PlayerStore>()(
  persist(
    (set, get) => ({
      // Initial state
      isPlaying: false,
      isLoading: false,
      currentTime: 0,
      duration: 0,
      bufferedTime: 0,
      currentBookId: null,
      currentBookTitle: null,
      currentAudioUrl: null,
      chapters: [],
      currentChapterIndex: null,
      volume: 1,
      playbackRate: 1,
      isMuted: false,
      sleepTimer: {
        endTime: null,
        timeLeft: null,
        totalDuration: null,
      },
      lastPlayedAt: null,
      smartResumeMessage: null,
      error: null,

      // Playback controls
      play: () => {
        if (howlInstance && !get().isPlaying) {
          howlInstance.play();
          set({ isPlaying: true, error: null, lastPlayedAt: new Date().toISOString() });
          startPositionSaveInterval(get);
        }
      },

      pause: () => {
        if (howlInstance && get().isPlaying) {
          howlInstance.pause();
          set({ isPlaying: false });
          stopPositionSaveInterval();

          // Save position immediately on pause
          const state = get();
          if (state.currentBookId && state.duration > 0) {
            const positionMs = Math.floor(state.currentTime * 1000);
            
            saveProgress(state.currentBookId, state.currentTime, state.duration).catch(
              console.error
            );

            updatePlaybackProgress(state.currentBookId, {
              position_ms: positionMs,
              playback_speed: state.playbackRate,
              is_finished: state.currentTime >= state.duration * 0.95,
            }).catch(console.error);
          }
        }
      },

      toggle: () => {
        const { isPlaying, play, pause } = get();
        if (isPlaying) {
          pause();
        } else {
          play();
        }
      },

      stop: () => {
        if (howlInstance) {
          howlInstance.stop();
          set({ isPlaying: false, currentTime: 0, currentChapterIndex: 0 });
          stopPositionSaveInterval();
        }
      },

      seek: (time: number) => {
        if (howlInstance) {
          const clampedTime = Math.max(0, Math.min(time, get().duration));
          howlInstance.seek(clampedTime);
          const currentChapterIndex = updateChapterIndex(clampedTime, get().chapters);
          set({ currentTime: clampedTime, currentChapterIndex });
        }
      },

      seekRelative: (delta: number) => {
        const { currentTime, seek } = get();
        seek(currentTime + delta);
      },

      // Chapter navigation
      nextChapter: () => {
        const { chapters, currentChapterIndex, seek } = get();
        if (currentChapterIndex !== null && currentChapterIndex < chapters.length - 1) {
          const nextChapter = chapters[currentChapterIndex + 1];
          seek(nextChapter.start_offset_ms / 1000);
        }
      },

      prevChapter: () => {
        const { chapters, currentChapterIndex, currentTime, seek } = get();
        if (currentChapterIndex !== null) {
          const currentChapter = chapters[currentChapterIndex];
          const chapterStartTime = currentChapter.start_offset_ms / 1000;
          
          // If we're more than 3 seconds into the chapter, go to start of current chapter
          if (currentTime - chapterStartTime > 3) {
            seek(chapterStartTime);
          } else if (currentChapterIndex > 0) {
            // Otherwise go to previous chapter
            const prevChapter = chapters[currentChapterIndex - 1];
            seek(prevChapter.start_offset_ms / 1000);
          } else {
            // Beginning of book
            seek(0);
          }
        }
      },

      seekToChapter: (index: number) => {
        const { chapters, seek } = get();
        if (index >= 0 && index < chapters.length) {
          seek(chapters[index].start_offset_ms / 1000);
        }
      },

      // Book loading
      loadBook: async (bookId: string, audioUrl: string, title: string) => {
        const currentState = get();

        // Don't reload if same book
        if (currentState.currentBookId === bookId && howlInstance) {
          return;
        }

        // Unload previous book
        if (howlInstance) {
          get().unloadBook();
        }

        set({
          isLoading: true,
          error: null,
          currentBookId: bookId,
          currentBookTitle: title,
          currentAudioUrl: audioUrl,
          chapters: [],
          currentChapterIndex: null,
        });

        // Fetch chapters and details
        try {
          const details = await getBookDetailsEnriched(bookId);
          if (details.chapters) {
            set({ chapters: details.chapters });
          }
        } catch (err) {
          console.warn("Failed to fetch chapters:", err);
        }

        // Try to restore saved position with smart resume
        let startPosition = 0;
        let smartResumeMessage: string | null = null;
        try {
          const progress = await getProgress(bookId);
          if (progress && !progress.completed) {
            startPosition = progress.currentTime;

            // Check if we should apply smart resume (rewind for context)
            if (progress.lastPlayedAt) {
              const lastPlayed = new Date(progress.lastPlayedAt);
              const now = new Date();
              const hoursSinceLastPlayed =
                (now.getTime() - lastPlayed.getTime()) / (1000 * 60 * 60);

              if (hoursSinceLastPlayed >= SMART_RESUME_THRESHOLD_HOURS && startPosition > SMART_RESUME_REWIND_SECONDS) {
                startPosition = Math.max(0, startPosition - SMART_RESUME_REWIND_SECONDS);
                smartResumeMessage = `Rewound ${SMART_RESUME_REWIND_SECONDS}s for context`;
              }
            }
          }
        } catch {
          // Ignore - start from beginning
        }

        // Create new Howl instance
        howlInstance = new Howl({
          src: [audioUrl],
          html5: true, // Use HTML5 Audio for large files
          format: ["m4b", "m4a", "mp4", "mp3", "flac", "ogg", "opus"],
          volume: currentState.volume,
          rate: currentState.playbackRate,
          mute: currentState.isMuted,
          onload: () => {
            const duration = howlInstance?.duration() ?? 0;
            const currentChapterIndex = updateChapterIndex(startPosition, get().chapters);
            set({
              isLoading: false,
              duration,
              currentTime: startPosition,
              currentChapterIndex,
              smartResumeMessage,
            });

            // Seek to saved position
            if (startPosition > 0 && howlInstance) {
              howlInstance.seek(startPosition);
            }
          },
          onplay: () => {
            set({ isPlaying: true });
            startPositionSaveInterval(get);

            // Update time during playback
            const updateTime = () => {
              if (howlInstance && get().isPlaying) {
                const currentTime = howlInstance.seek() as number;
                const currentChapterIndex = updateChapterIndex(currentTime, get().chapters);
                set({ currentTime, currentChapterIndex });
                requestAnimationFrame(updateTime);
              }
            };
            requestAnimationFrame(updateTime);
          },
          onpause: () => {
            set({ isPlaying: false });
            stopPositionSaveInterval();
          },
          onstop: () => {
            set({ isPlaying: false, currentTime: 0, currentChapterIndex: 0 });
            stopPositionSaveInterval();
          },
          onend: () => {
            set({ isPlaying: false });
            stopPositionSaveInterval();

            // Mark as completed
            const state = get();
            if (state.currentBookId) {
              const positionMs = Math.floor(state.duration * 1000);
              
              saveProgress(state.currentBookId, state.duration, state.duration).catch(
                console.error
              );

              updatePlaybackProgress(state.currentBookId, {
                position_ms: positionMs,
                playback_speed: state.playbackRate,
                is_finished: true,
              }).catch(console.error);
            }
          },
          onloaderror: (_id, error) => {
            set({
              isLoading: false,
              error: `Failed to load audio: ${error}`,
            });
          },
          onplayerror: (_id, error) => {
            set({
              isPlaying: false,
              error: `Playback error: ${error}`,
            });
          },
        });
      },

      unloadBook: () => {
        // Save final position
        const state = get();
        if (state.currentBookId && state.duration > 0) {
          const positionMs = Math.floor(state.currentTime * 1000);
          
          saveProgress(state.currentBookId, state.currentTime, state.duration).catch(
            console.error
          );

          updatePlaybackProgress(state.currentBookId, {
            position_ms: positionMs,
            playback_speed: state.playbackRate,
            is_finished: state.currentTime >= state.duration * 0.95,
          }).catch(console.error);
        }

        // Cleanup
        stopPositionSaveInterval();
        if (howlInstance) {
          howlInstance.unload();
          howlInstance = null;
        }

        set({
          isPlaying: false,
          isLoading: false,
          currentTime: 0,
          duration: 0,
          bufferedTime: 0,
          currentBookId: null,
          currentBookTitle: null,
          currentAudioUrl: null,
          chapters: [],
          currentChapterIndex: null,
          error: null,
        });
      },

      // Settings
      setVolume: (volume: number) => {
        const clampedVolume = Math.max(0, Math.min(1, volume));
        if (howlInstance) {
          howlInstance.volume(clampedVolume);
        }
        set({ volume: clampedVolume });
      },

      setPlaybackRate: (rate: number) => {
        const clampedRate = Math.max(0.5, Math.min(3, rate));
        if (howlInstance) {
          howlInstance.rate(clampedRate);
        }
        set({ playbackRate: clampedRate });
      },

      toggleMute: () => {
        const isMuted = !get().isMuted;
        if (howlInstance) {
          howlInstance.mute(isMuted);
        }
        set({ isMuted });
      },

      // Sleep timer
      setSleepTimer: (minutes: number | null) => {
        if (sleepTimerInterval) {
          clearInterval(sleepTimerInterval);
          sleepTimerInterval = null;
        }

        if (minutes === null) {
          set({
            sleepTimer: { endTime: null, timeLeft: null, totalDuration: null },
          });
          return;
        }

        const durationMs = minutes * 60 * 1000;
        const endTime = Date.now() + durationMs;

        set({
          sleepTimer: {
            endTime,
            timeLeft: durationMs,
            totalDuration: durationMs,
          },
        });

        sleepTimerInterval = setInterval(() => {
          const now = Date.now();
          const timeLeft = Math.max(0, endTime - now);

          set({
            sleepTimer: { ...get().sleepTimer, timeLeft },
          });

          if (timeLeft <= 0) {
            clearInterval(sleepTimerInterval!);
            sleepTimerInterval = null;
            get().pause();
            set({
              sleepTimer: { endTime: null, timeLeft: null, totalDuration: null },
            });
          }
        }, 1000);
      },

      // Internal state updates
      _setCurrentTime: (currentTime: number) => set({ currentTime }),
      _setDuration: (duration: number) => set({ duration }),
      _setIsLoading: (isLoading: boolean) => set({ isLoading }),
      _setError: (error: string | null) => set({ error }),

      // Smart resume
      clearSmartResumeMessage: () => set({ smartResumeMessage: null }),
    }),
    {
      name: "player-storage",
      storage: createJSONStorage(() => safeLocalStorage),
      // Only persist these fields
      partialize: (state) => ({
        volume: state.volume,
        playbackRate: state.playbackRate,
        isMuted: state.isMuted,
        lastPlayedAt: state.lastPlayedAt,
        smartResumeMessage: state.smartResumeMessage,
        // Optionally persist current book for resume
        currentBookId: state.currentBookId,
        currentBookTitle: state.currentBookTitle,
        currentAudioUrl: state.currentAudioUrl,
      }),
    }
  )
);

/**
 * Utility hook for common player selectors
 */
export const usePlayerIsPlaying = (): boolean =>
  usePlayerStore((state) => state.isPlaying);

export const usePlayerCurrentBook = (): {
  id: string | null;
  title: string | null;
} =>
  usePlayerStore(
    useShallow((state) => ({
      id: state.currentBookId,
      title: state.currentBookTitle,
    }))
  );

export const usePlayerProgress = (): {
  currentTime: number;
  duration: number;
  percent: number;
} =>
  usePlayerStore(
    useShallow((state) => ({
      currentTime: state.currentTime,
      duration: state.duration,
      percent: state.duration > 0 ? (state.currentTime / state.duration) * 100 : 0,
    }))
  );
