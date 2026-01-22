/**
 * useSettings Hook Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import {
  useSettings,
  useUpdateSettings,
  useResetSettings,
  useSettingsWithUpdate,
  settingsKeys,
} from "@/hooks/useSettings";
import { DEFAULT_SETTINGS } from "@/types";
import { mockSettings } from "../../mocks/handlers";

// Create wrapper for React Query
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children
    );
  };
}

describe("useSettings Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe("useSettings", () => {
    it("should fetch settings from API", async () => {
      const { result } = renderHook(() => useSettings(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.output_format).toBeDefined();
    });

    it("should have placeholder data while loading", () => {
      const { result } = renderHook(() => useSettings(), {
        wrapper: createWrapper(),
      });

      // Placeholder data should be available immediately
      expect(result.current.data).toEqual(DEFAULT_SETTINGS);
    });
  });

  describe("useUpdateSettings", () => {
    it("should update settings", async () => {
      const { result } = renderHook(() => useUpdateSettings(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.mutateAsync({ output_format: "mp3" });
      });

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.output_format).toBe("mp3");
    });

    it("should handle partial updates", async () => {
      const { result } = renderHook(() => useUpdateSettings(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.mutateAsync({
          single_file: false,
          compression_mp3: 6,
        });
      });

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.single_file).toBe(false);
      expect(result.current.data?.compression_mp3).toBe(6);
    });
  });

  describe("useResetSettings", () => {
    it("should reset settings to defaults", async () => {
      const { result } = renderHook(() => useResetSettings(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.mutateAsync();
      });

      expect(result.current.data).toBeDefined();
      // The API returns the updated settings which should be defaults
      expect(result.current.data).toEqual(DEFAULT_SETTINGS);
    });
  });

  describe("useSettingsWithUpdate", () => {
    it("should provide settings and update function", async () => {
      const { result } = renderHook(() => useSettingsWithUpdate(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.settings).toBeDefined();
      expect(typeof result.current.updateSettings).toBe("function");
      expect(typeof result.current.updateSettingsAsync).toBe("function");
    });

    it("should show loading state correctly", () => {
      const { result } = renderHook(() => useSettingsWithUpdate(), {
        wrapper: createWrapper(),
      });

      // Initially loading
      expect(result.current.isLoading).toBe(true);
    });
  });

  describe("settingsKeys", () => {
    it("should generate correct query keys", () => {
      expect(settingsKeys.all).toEqual(["settings"]);
      expect(settingsKeys.current()).toEqual(["settings", "current"]);
    });
  });
});
