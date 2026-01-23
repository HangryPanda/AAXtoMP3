/**
 * Player Store
 * Zustand store for audio playback state with Howler.js integration
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { Howl } from "howler";
import { saveProgress, getProgress } from "@/lib/db";
import { updatePlaybackProgress } from "@/services/books";

/**
 * Player state interface
 */
export interface PlayerState {
  // Playback state
  isPlaying: boolean;
  isLoading: boolean;
  currentTime: number;
  duration: number;
  bufferedTime: number;

  // Current book
  currentBookId: string | null;
  currentBookTitle: string | null;
  currentAudioUrl: string | null;

  // Settings
  volume: number;
  playbackRate: number;
  isMuted: boolean;

  // Error state
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

  // Book loading
  loadBook: (bookId: string, audioUrl: string, title: string) => Promise<void>;
  unloadBook: () => void;

  // Settings
  setVolume: (volume: number) => void;
  setPlaybackRate: (rate: number) => void;
  toggleMute: () => void;

  // State updates (internal)
  _setCurrentTime: (time: number) => void;
  _setDuration: (duration: number) => void;
  _setIsLoading: (loading: boolean) => void;
  _setError: (error: string | null) => void;
}

export type PlayerStore = PlayerState & PlayerActions;

// Howl instance (not stored in state to avoid serialization issues)
let howlInstance: Howl | null = null;

// Position save interval
let savePositionInterval: ReturnType<typeof setInterval> | null = null;
const SAVE_POSITION_INTERVAL = 5000; // Save every 5 seconds

/**
 * Start position save interval
 */
function startPositionSaveInterval(
  getState: () => PlayerState
): void {
  stopPositionSaveInterval();

  savePositionInterval = setInterval(() => {
    const state = getState();
    if (state.currentBookId && state.isPlaying && state.duration > 0) {
      const positionMs = Math.floor(state.currentTime * 1000);
      
      // Save locally first
      saveProgress(state.currentBookId, state.currentTime, state.duration).catch(
        console.error
      );

      // Sync to backend
      updatePlaybackProgress(state.currentBookId, {
        position_ms: positionMs,
        playback_speed: state.playbackRate,
        is_finished: state.currentTime >= state.duration * 0.95,
      }).catch(err => {
        console.warn("Failed to sync progress to backend:", err);
      });
    }
  }, SAVE_POSITION_INTERVAL);
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
      volume: 1,
      playbackRate: 1,
      isMuted: false,
      error: null,

      // Playback controls
      play: () => {
        if (howlInstance && !get().isPlaying) {
          howlInstance.play();
          set({ isPlaying: true, error: null });
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
          set({ isPlaying: false, currentTime: 0 });
          stopPositionSaveInterval();
        }
      },

      seek: (time: number) => {
        if (howlInstance) {
          const clampedTime = Math.max(0, Math.min(time, get().duration));
          howlInstance.seek(clampedTime);
          set({ currentTime: clampedTime });
        }
      },

      seekRelative: (delta: number) => {
        const { currentTime, seek } = get();
        seek(currentTime + delta);
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
        });

        // Try to restore saved position
        let startPosition = 0;
        try {
          const progress = await getProgress(bookId);
          if (progress && !progress.completed) {
            startPosition = progress.currentTime;
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
            set({
              isLoading: false,
              duration,
              currentTime: startPosition,
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
                set({ currentTime });
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
            set({ isPlaying: false, currentTime: 0 });
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

      // Internal state updates
      _setCurrentTime: (currentTime: number) => set({ currentTime }),
      _setDuration: (duration: number) => set({ duration }),
      _setIsLoading: (isLoading: boolean) => set({ isLoading }),
      _setError: (error: string | null) => set({ error }),
    }),
    {
      name: "player-storage",
      storage: createJSONStorage(() => localStorage),
      // Only persist these fields
      partialize: (state) => ({
        volume: state.volume,
        playbackRate: state.playbackRate,
        isMuted: state.isMuted,
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
  usePlayerStore((state) => ({
    id: state.currentBookId,
    title: state.currentBookTitle,
  }));

export const usePlayerProgress = (): {
  currentTime: number;
  duration: number;
  percent: number;
} =>
  usePlayerStore((state) => ({
    currentTime: state.currentTime,
    duration: state.duration,
    percent: state.duration > 0 ? (state.currentTime / state.duration) * 100 : 0,
  }));