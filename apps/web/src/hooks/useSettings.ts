/**
 * useSettings Hook
 * React Query hook for loading and saving settings
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { apiRequest } from "@/services/api";
import type { Settings, SettingsUpdate } from "@/types";
import { DEFAULT_SETTINGS } from "@/types";

/**
 * Query keys for settings
 */
export const settingsKeys = {
  all: ["settings"] as const,
  current: () => [...settingsKeys.all, "current"] as const,
};

/**
 * Hook for fetching current settings
 */
export function useSettings(
  options?: Omit<UseQueryOptions<Settings>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: settingsKeys.current(),
    queryFn: async () => {
      try {
        return await apiRequest<Settings>({
          method: "GET",
          url: "/settings",
        });
      } catch {
        // Return defaults if API fails
        return DEFAULT_SETTINGS;
      }
    },
    // Settings don't change often
    staleTime: 10 * 60 * 1000, // 10 minutes
    // Use default settings as placeholder
    placeholderData: DEFAULT_SETTINGS,
    ...options,
  });
}

/**
 * Hook for updating settings
 */
export function useUpdateSettings() {
  const queryClient = useQueryClient();

  return useMutation<Settings, Error, SettingsUpdate, { previousSettings: Settings | undefined }>({
    mutationFn: async (updates) => {
      return apiRequest<Settings>({
        method: "PATCH",
        url: "/settings",
        data: updates,
      });
    },
    onMutate: async (updates) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: settingsKeys.current() });

      // Snapshot previous value
      const previousSettings = queryClient.getQueryData<Settings>(
        settingsKeys.current()
      );

      // Optimistically update
      queryClient.setQueryData<Settings>(settingsKeys.current(), (old) => ({
        ...(old ?? DEFAULT_SETTINGS),
        ...updates,
      }));

      return { previousSettings };
    },
    onError: (_err, _vars, context) => {
      // Rollback on error
      if (context?.previousSettings) {
        queryClient.setQueryData(settingsKeys.current(), context.previousSettings);
      }
    },
    onSettled: () => {
      // Refetch to ensure sync
      queryClient.invalidateQueries({ queryKey: settingsKeys.current() });
    },
  });
}

/**
 * Hook for resetting settings to defaults
 */
export function useResetSettings() {
  const queryClient = useQueryClient();

  return useMutation<Settings, Error>({
    mutationFn: async () => {
      return apiRequest<Settings>({
        method: "PATCH",
        url: "/settings",
        data: DEFAULT_SETTINGS,
      });
    },
    onSuccess: (data) => {
      queryClient.setQueryData(settingsKeys.current(), data);
    },
  });
}

/**
 * Combined hook for settings with update function
 */
export function useSettingsWithUpdate() {
  const { data: settings, isLoading, error } = useSettings();
  const updateMutation = useUpdateSettings();

  return {
    settings: settings ?? DEFAULT_SETTINGS,
    isLoading,
    error,
    updateSettings: updateMutation.mutate,
    updateSettingsAsync: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,
    updateError: updateMutation.error,
  };
}

/**
 * Hook for specific setting value with setter
 */
export function useSettingValue<K extends keyof Settings>(key: K) {
  const { data: settings } = useSettings();
  const updateMutation = useUpdateSettings();

  const value = settings?.[key] ?? DEFAULT_SETTINGS[key];

  const setValue = (newValue: Settings[K]) => {
    updateMutation.mutate({ [key]: newValue } as SettingsUpdate);
  };

  return [value, setValue] as const;
}
