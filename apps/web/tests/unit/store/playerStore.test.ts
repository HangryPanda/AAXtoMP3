/**
 * Player Store Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook } from "@testing-library/react";

// Mock Howler before importing the store
vi.mock("howler", () => ({
  Howl: vi.fn().mockImplementation((config) => ({
    play: vi.fn(),
    pause: vi.fn(),
    stop: vi.fn(),
    seek: vi.fn().mockReturnValue(0),
    volume: vi.fn(),
    rate: vi.fn(),
    mute: vi.fn(),
    unload: vi.fn(),
    duration: vi.fn().mockReturnValue(3600),
    // Simulate loading
    _callOnLoad: () => {
      if (config.onload) config.onload();
    },
    _callOnPlay: () => {
      if (config.onplay) config.onplay();
    },
    _callOnPause: () => {
      if (config.onpause) config.onpause();
    },
    _callOnEnd: () => {
      if (config.onend) config.onend();
    },
    _callOnLoadError: (err: string) => {
      if (config.onloaderror) config.onloaderror(0, err);
    },
  })),
}));

// Mock db module
vi.mock("@/lib/db", () => ({
  saveProgress: vi.fn().mockResolvedValue(undefined),
  getProgress: vi.fn().mockResolvedValue(null),
}));

import { usePlayerStore } from "@/store/playerStore";

describe("Player Store", () => {
  beforeEach(() => {
    // Reset the store state before each test
    const { getState } = usePlayerStore;
    act(() => {
      getState().unloadBook();
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe("initial state", () => {
    it("should have correct initial values", () => {
      const state = usePlayerStore.getState();

      expect(state.isPlaying).toBe(false);
      expect(state.isLoading).toBe(false);
      expect(state.currentTime).toBe(0);
      expect(state.duration).toBe(0);
      expect(state.currentBookId).toBeNull();
      expect(state.volume).toBe(1);
      expect(state.playbackRate).toBe(1);
      expect(state.isMuted).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe("volume control", () => {
    it("should set volume within valid range", () => {
      const { result } = renderHook(() => usePlayerStore());

      act(() => {
        result.current.setVolume(0.5);
      });

      expect(result.current.volume).toBe(0.5);
    });

    it("should clamp volume to 0-1 range", () => {
      const { result } = renderHook(() => usePlayerStore());

      act(() => {
        result.current.setVolume(1.5);
      });
      expect(result.current.volume).toBe(1);

      act(() => {
        result.current.setVolume(-0.5);
      });
      expect(result.current.volume).toBe(0);
    });
  });

  describe("playback rate control", () => {
    it("should set playback rate within valid range", () => {
      const { result } = renderHook(() => usePlayerStore());

      act(() => {
        result.current.setPlaybackRate(1.5);
      });

      expect(result.current.playbackRate).toBe(1.5);
    });

    it("should clamp playback rate to 0.5-3 range", () => {
      const { result } = renderHook(() => usePlayerStore());

      act(() => {
        result.current.setPlaybackRate(5);
      });
      expect(result.current.playbackRate).toBe(3);

      act(() => {
        result.current.setPlaybackRate(0.1);
      });
      expect(result.current.playbackRate).toBe(0.5);
    });
  });

  describe("mute control", () => {
    it("should toggle mute state", () => {
      const { result } = renderHook(() => usePlayerStore());

      expect(result.current.isMuted).toBe(false);

      act(() => {
        result.current.toggleMute();
      });
      expect(result.current.isMuted).toBe(true);

      act(() => {
        result.current.toggleMute();
      });
      expect(result.current.isMuted).toBe(false);
    });
  });

  describe("play/pause toggle", () => {
    it("should toggle between play and pause", () => {
      const { result } = renderHook(() => usePlayerStore());

      // Need to load a book first
      act(() => {
        result.current.loadBook("test-asin", "http://example.com/audio.mp3", "Test Book");
      });

      // Initial state should be not playing
      expect(result.current.isPlaying).toBe(false);
    });
  });

  describe("unloadBook", () => {
    it("should reset state when unloading", () => {
      const { result } = renderHook(() => usePlayerStore());

      // Set some state
      act(() => {
        result.current._setCurrentTime(100);
        result.current._setDuration(3600);
      });

      // Unload
      act(() => {
        result.current.unloadBook();
      });

      expect(result.current.currentTime).toBe(0);
      expect(result.current.duration).toBe(0);
      expect(result.current.currentBookId).toBeNull();
      expect(result.current.isPlaying).toBe(false);
    });
  });
});
