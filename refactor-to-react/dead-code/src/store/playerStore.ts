import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface PlayerState {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  currentBookId: string | null;
  volume: number;
  playbackRate: number;
  
  // Actions
  play: (bookId: string) => void;
  pause: () => void;
  seek: (time: number) => void;
  setRate: (rate: number) => void;
  setVolume: (volume: number) => void;
  setDuration: (duration: number) => void;
  setCurrentTime: (time: number) => void;
}

export const usePlayerStore = create<PlayerState>()(
  persist(
    (set, get) => ({
      isPlaying: false,
      currentTime: 0,
      duration: 0,
      currentBookId: null,
      volume: 1.0,
      playbackRate: 1.0,

      play: (bookId: string) => {
        // TODO: integrate with Howler
        set({ isPlaying: true, currentBookId: bookId });
      },
      pause: () => {
        // TODO: integrate with Howler
        set({ isPlaying: false });
      },
      seek: (time: number) => {
        set({ currentTime: time });
      },
      setRate: (rate: number) => {
        set({ playbackRate: rate });
      },
      setVolume: (volume: number) => {
        set({ volume });
      },
      setDuration: (duration: number) => {
        set({ duration });
      },
      setCurrentTime: (time: number) => {
        set({ currentTime: time });
      },
    }),
    {
      name: 'player-storage', // unique name for localStorage
      partialize: (state) => ({ 
        volume: state.volume, 
        playbackRate: state.playbackRate,
        currentBookId: state.currentBookId,
        currentTime: state.currentTime
      }),
    }
  )
);
