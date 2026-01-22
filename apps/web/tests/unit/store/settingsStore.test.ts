/**
 * Settings Store Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useSettingsStore } from "@/store/settingsStore";
import { DEFAULT_SETTINGS } from "@/types";

// Mock the api module
vi.mock("@/services/api", () => ({
  apiRequest: vi.fn(),
}));

import { apiRequest } from "@/services/api";

const mockApiRequest = vi.mocked(apiRequest);

describe("Settings Store", () => {
  beforeEach(() => {
    // Reset the store state
    const store = useSettingsStore.getState();
    store.resetToDefaults();
    store.clearError();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe("initial state", () => {
    it("should have default settings", () => {
      const state = useSettingsStore.getState();

      expect(state.settings).toEqual(DEFAULT_SETTINGS);
      expect(state.isLoading).toBe(false);
      expect(state.isSaving).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe("updateSettings", () => {
    it("should update settings locally", () => {
      const { result } = renderHook(() => useSettingsStore());

      act(() => {
        result.current.updateSettings({ output_format: "mp3" });
      });

      expect(result.current.settings.output_format).toBe("mp3");
    });

    it("should merge partial updates with existing settings", () => {
      const { result } = renderHook(() => useSettingsStore());

      act(() => {
        result.current.updateSettings({ output_format: "flac" });
      });

      act(() => {
        result.current.updateSettings({ single_file: false });
      });

      expect(result.current.settings.output_format).toBe("flac");
      expect(result.current.settings.single_file).toBe(false);
      // Other settings should remain unchanged
      expect(result.current.settings.compression_mp3).toBe(DEFAULT_SETTINGS.compression_mp3);
    });
  });

  describe("loadSettings", () => {
    it("should load settings from API", async () => {
      const apiSettings = {
        ...DEFAULT_SETTINGS,
        output_format: "opus" as const,
        single_file: false,
      };

      mockApiRequest.mockResolvedValueOnce(apiSettings);

      const { result } = renderHook(() => useSettingsStore());

      await act(async () => {
        await result.current.loadSettings();
      });

      expect(result.current.settings.output_format).toBe("opus");
      expect(result.current.settings.single_file).toBe(false);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.lastSynced).not.toBeNull();
    });

    it("should set error on API failure", async () => {
      mockApiRequest.mockRejectedValueOnce(new Error("Network error"));

      const { result } = renderHook(() => useSettingsStore());

      await act(async () => {
        await result.current.loadSettings();
      });

      expect(result.current.error).toBe("Network error");
      expect(result.current.isLoading).toBe(false);
    });

    it("should set loading state during fetch", async () => {
      mockApiRequest.mockImplementationOnce(
        () => new Promise((resolve) => setTimeout(() => resolve(DEFAULT_SETTINGS), 100))
      );

      const { result } = renderHook(() => useSettingsStore());

      // Start loading
      act(() => {
        result.current.loadSettings();
      });

      expect(result.current.isLoading).toBe(true);

      // Wait for completion
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe("saveSettings", () => {
    it("should save settings to API", async () => {
      const savedSettings = {
        ...DEFAULT_SETTINGS,
        output_format: "m4a" as const,
      };

      mockApiRequest.mockResolvedValueOnce(savedSettings);

      const { result } = renderHook(() => useSettingsStore());

      // Update local settings first
      act(() => {
        result.current.updateSettings({ output_format: "m4a" });
      });

      // Save to API
      await act(async () => {
        await result.current.saveSettings();
      });

      expect(mockApiRequest).toHaveBeenCalledWith({
        method: "PUT",
        url: "/api/settings",
        data: expect.objectContaining({ output_format: "m4a" }),
      });
      expect(result.current.isSaving).toBe(false);
    });

    it("should set error on save failure", async () => {
      mockApiRequest.mockRejectedValueOnce(new Error("Save failed"));

      const { result } = renderHook(() => useSettingsStore());

      await expect(
        act(async () => {
          await result.current.saveSettings();
        })
      ).rejects.toThrow("Save failed");

      expect(result.current.error).toBe("Save failed");
      expect(result.current.isSaving).toBe(false);
    });
  });

  describe("resetToDefaults", () => {
    it("should reset settings to defaults", () => {
      const { result } = renderHook(() => useSettingsStore());

      // Change some settings
      act(() => {
        result.current.updateSettings({
          output_format: "flac",
          single_file: false,
          compression_mp3: 9,
        });
      });

      // Reset
      act(() => {
        result.current.resetToDefaults();
      });

      expect(result.current.settings).toEqual(DEFAULT_SETTINGS);
    });
  });

  describe("clearError", () => {
    it("should clear error state", async () => {
      mockApiRequest.mockRejectedValueOnce(new Error("Test error"));

      const { result } = renderHook(() => useSettingsStore());

      // Trigger an error
      await act(async () => {
        await result.current.loadSettings();
      });

      expect(result.current.error).toBe("Test error");

      // Clear error
      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });
  });
});
