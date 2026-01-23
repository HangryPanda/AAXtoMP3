/**
 * useProgressStats Hook
 * Reusable hook for calculating speed and ETA for progress-based operations.
 * Extracts logic from ProgressPopover for use in BookProgressOverlay.
 */

import { useState, useEffect, useRef, useMemo } from "react";

interface ProgressStats {
  /** Smoothed speed in percent per second */
  speed: number;
  /** Estimated time remaining in seconds */
  etr: number;
  /** Formatted speed display (e.g. "2.3%/s") */
  speedDisplay: string;
  /** Formatted ETA display (e.g. "3m 45s") */
  etaDisplay: string;
}

interface StatState {
  speed: number;
  etr: number;
  lastProgress: number;
  lastTime: number;
}

/**
 * Format duration in seconds to a human-readable string
 */
function formatDuration(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return "--:--";
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

/**
 * Hook to calculate smoothed speed and ETA for a progress value.
 *
 * @param progress - Current progress percentage (0-100)
 * @param isActive - Whether the operation is actively running (enables calculations)
 * @returns Progress statistics including speed and ETA
 */
const DEFAULT_STATS: ProgressStats = {
  speed: 0,
  etr: 0,
  speedDisplay: "",
  etaDisplay: "--:--",
};

export function useProgressStats(
  progress: number,
  isActive: boolean = true
): ProgressStats {
  const statRef = useRef<StatState | null>(null);
  const [displayStats, setDisplayStats] = useState<ProgressStats>(DEFAULT_STATS);

  // Reset ref when becoming inactive
  useEffect(() => {
    if (!isActive) {
      statRef.current = null;
    }
  }, [isActive]);

  useEffect(() => {
    if (!isActive) {
      return;
    }

    const updateStats = () => {
      const now = Date.now();
      const prev = statRef.current;

      if (!prev) {
        // Initialize state
        statRef.current = {
          speed: 0,
          etr: 0,
          lastProgress: progress,
          lastTime: now,
        };
        return;
      }

      const timeDiff = (now - prev.lastTime) / 1000;

      // Only update if at least 1 second has passed
      if (timeDiff >= 1) {
        const progressDiff = progress - prev.lastProgress;
        const currentSpeed = timeDiff > 0 ? Math.max(0, progressDiff / timeDiff) : 0;
        // Smoothed speed: 30% current, 70% previous
        const smoothedSpeed = currentSpeed * 0.3 + prev.speed * 0.7;
        const remaining = 100 - progress;
        const etr = smoothedSpeed > 0 ? remaining / smoothedSpeed : 0;

        statRef.current = {
          speed: smoothedSpeed,
          etr,
          lastProgress: progress,
          lastTime: now,
        };

        setDisplayStats({
          speed: smoothedSpeed,
          etr,
          speedDisplay: smoothedSpeed > 0 ? `${smoothedSpeed.toFixed(1)}%/s` : "",
          etaDisplay: formatDuration(etr),
        });
      }
    };

    // Initial update
    updateStats();

    // Update every second
    const interval = setInterval(updateStats, 1000);
    return () => clearInterval(interval);
  }, [progress, isActive]);

  // Return default stats when inactive to ensure consistent output
  const result = useMemo(() => {
    return isActive ? displayStats : DEFAULT_STATS;
  }, [isActive, displayStats]);

  return result;
}

export type { ProgressStats };
