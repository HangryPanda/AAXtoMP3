/**
 * Settings Store
 * Zustand store for application settings with API sync
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { safeLocalStorage } from "@/lib/utils";
import type { Settings, SettingsUpdate } from "@/types";
import { DEFAULT_SETTINGS } from "@/types";
import { apiRequest } from "@/services/api";

/**
 * Settings state interface
 */
export interface SettingsState {
  // Settings data
  settings: Settings;

  // Sync state
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  lastSynced: string | null;
}

/**
 * Settings actions interface
 */
export interface SettingsActions {
  // Load settings from API
  loadSettings: () => Promise<void>;

  // Update settings locally
  updateSettings: (updates: SettingsUpdate) => void;

  // Save settings to API
  saveSettings: () => Promise<void>;

  // Reset to defaults
  resetToDefaults: () => void;

  // Clear error
  clearError: () => void;
}

export type SettingsStore = SettingsState & SettingsActions;

/**
 * Settings store with persistence
 */
export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set, get) => ({
      // Initial state
      settings: DEFAULT_SETTINGS,
      isLoading: false,
      isSaving: false,
      error: null,
      lastSynced: null,

      // Load settings from API
      loadSettings: async () => {
        set({ isLoading: true, error: null });

        try {
          const settings = await apiRequest<Settings>({
            method: "GET",
            url: "/settings",
          });

          set({
            settings,
            isLoading: false,
            lastSynced: new Date().toISOString(),
          });
        } catch (error) {
          const message =
            error instanceof Error ? error.message : "Failed to load settings";
          set({
            isLoading: false,
            error: message,
          });
        }
      },

      // Update settings locally
      updateSettings: (updates: SettingsUpdate) => {
        set((state) => ({
          settings: { ...state.settings, ...updates },
        }));
      },

      // Save settings to API
      saveSettings: async () => {
        const { settings } = get();
        set({ isSaving: true, error: null });

        try {
          const savedSettings = await apiRequest<Settings>({
            method: "PATCH",
            url: "/settings",
            data: settings,
          });

          set({
            settings: savedSettings,
            isSaving: false,
            lastSynced: new Date().toISOString(),
          });
        } catch (error) {
          const message =
            error instanceof Error ? error.message : "Failed to save settings";
          set({
            isSaving: false,
            error: message,
          });
          throw error;
        }
      },

      // Reset to defaults
      resetToDefaults: () => {
        set({ settings: DEFAULT_SETTINGS });
      },

      // Clear error
      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: "settings-storage",
      storage: createJSONStorage(() => safeLocalStorage),
      // Persist settings and last synced time
      partialize: (state) => ({
        settings: state.settings,
        lastSynced: state.lastSynced,
      }),
    }
  )
);

/**
 * Selector hooks for specific settings
 */
export const useOutputFormat = () =>
  useSettingsStore((state) => state.settings.output_format);

export const useSingleFile = () =>
  useSettingsStore((state) => state.settings.single_file);

export const useNamingSchemes = () =>
  useSettingsStore((state) => ({
    dir: state.settings.dir_naming_scheme,
    file: state.settings.file_naming_scheme,
    chapter: state.settings.chapter_naming_scheme,
  }));

export const useCompressionSettings = () =>
  useSettingsStore((state) => ({
    mp3: state.settings.compression_mp3,
    flac: state.settings.compression_flac,
    opus: state.settings.compression_opus,
  }));

export const useAutoRetrySettings = () =>
  useSettingsStore((state) => ({
    enabled: state.settings.auto_retry,
    maxRetries: state.settings.max_retries,
  }));
