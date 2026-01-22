/**
 * Formatting utility functions for dates, durations, and other values
 */
import { format, isValid, parseISO, differenceInMinutes, differenceInHours, differenceInDays } from "date-fns";

/**
 * Formats an ISO date string to a readable format
 *
 * @param dateString - ISO date string or null/undefined
 * @param formatStr - date-fns format string (default: "MMM d, yyyy")
 * @returns Formatted date string or "-" if invalid
 */
export function formatDate(
  dateString: string | null | undefined,
  formatStr: string = "MMM d, yyyy"
): string {
  if (!dateString) return "-";

  try {
    const date = parseISO(dateString);
    if (!isValid(date)) return "-";
    return format(date, formatStr);
  } catch {
    return "-";
  }
}

/**
 * Formats an ISO date string to a relative time string (e.g., "5 minutes ago")
 *
 * @param dateString - ISO date string or null/undefined
 * @returns Relative time string or "-" if invalid
 */
export function formatRelativeDate(dateString: string | null | undefined): string {
  if (!dateString) return "-";

  try {
    const date = parseISO(dateString);
    if (!isValid(date)) return "-";

    const now = new Date();
    const minutesAgo = differenceInMinutes(now, date);
    const hoursAgo = differenceInHours(now, date);
    const daysAgo = differenceInDays(now, date);

    if (minutesAgo < 1) {
      return "just now";
    }

    if (minutesAgo < 60) {
      return minutesAgo === 1 ? "1 minute ago" : `${minutesAgo} minutes ago`;
    }

    if (hoursAgo < 24) {
      return hoursAgo === 1 ? "1 hour ago" : `${hoursAgo} hours ago`;
    }

    if (daysAgo === 1) {
      return "yesterday";
    }

    if (daysAgo < 7) {
      return `${daysAgo} days ago`;
    }

    return format(date, "MMM d, yyyy");
  } catch {
    return "-";
  }
}

/**
 * Formats a duration in minutes to a compact string (e.g., "2h 30m")
 *
 * @param minutes - Duration in minutes
 * @returns Compact duration string
 */
export function formatDuration(minutes: number): string {
  if (minutes < 60) {
    return `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;

  if (mins === 0) {
    return `${hours}h`;
  }

  return `${hours}h ${mins}m`;
}

/**
 * Formats a duration in minutes to a verbose string (e.g., "2 hours 30 minutes")
 *
 * @param minutes - Duration in minutes
 * @returns Verbose duration string
 */
export function formatDurationVerbose(minutes: number): string {
  if (minutes < 60) {
    return minutes === 1 ? "1 minute" : `${minutes} minutes`;
  }

  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;

  const hourStr = hours === 1 ? "1 hour" : `${hours} hours`;

  if (mins === 0) {
    return hourStr;
  }

  const minStr = mins === 1 ? "1 minute" : `${mins} minutes`;
  return `${hourStr} ${minStr}`;
}

/**
 * Formats bytes to a human-readable string (e.g., "1.5 MB")
 *
 * @param bytes - Number of bytes
 * @param decimals - Number of decimal places (default: 1)
 * @returns Human-readable size string
 */
export function formatBytes(bytes: number, decimals: number = 1): string {
  if (bytes === 0) return "0 B";

  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  if (i === 0) {
    return `${bytes} B`;
  }

  const value = bytes / Math.pow(k, i);
  const formatted = decimals === 0
    ? Math.round(value).toString()
    : value.toFixed(decimals).replace(/\.?0+$/, "");

  // Handle edge case where toFixed creates trailing zeros that we want to keep
  if (decimals > 0 && !formatted.includes(".")) {
    const roundedValue = Math.round(value * Math.pow(10, decimals)) / Math.pow(10, decimals);
    return `${roundedValue.toFixed(decimals)} ${sizes[i]}`;
  }

  return `${formatted} ${sizes[i]}`;
}

/**
 * Formats a number as a percentage
 *
 * @param value - Number to format (0-100)
 * @param decimals - Number of decimal places (default: 0)
 * @returns Formatted percentage string
 */
export function formatPercentage(value: number, decimals: number = 0): string {
  const clamped = Math.max(0, Math.min(100, value));

  if (decimals === 0) {
    return `${Math.round(clamped)}%`;
  }

  return `${clamped.toFixed(decimals)}%`;
}
