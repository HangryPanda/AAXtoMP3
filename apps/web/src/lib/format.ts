import { 
  format as formatFn, 
  formatDistanceToNow, 
  isToday, 
  isYesterday, 
  isValid, 
  parseISO,
  differenceInMinutes,
  differenceInHours,
  differenceInDays
} from "date-fns";

/**
 * Formats a date string to a readable format
 */
export function formatDate(
  date: string | Date | null | undefined,
  formatStr: string = "MMM d, yyyy"
): string {
  if (!date) return "-";
  
  const parsedDate = typeof date === "string" ? parseISO(date) : date;
  
  if (!isValid(parsedDate)) return "-";
  
  return formatFn(parsedDate, formatStr);
}

/**
 * Formats a date string to a relative format (e.g., "2 minutes ago", "yesterday")
 */
export function formatRelativeDate(date: string | Date | null | undefined): string {
  if (!date) return "-";
  
  const parsedDate = typeof date === "string" ? parseISO(date) : date;
  if (!isValid(parsedDate)) return "-";
  
  const now = new Date();
  const minutes = differenceInMinutes(now, parsedDate);
  
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} ${minutes === 1 ? "minute" : "minutes"} ago`;
  
  if (isToday(parsedDate)) {
    const hours = differenceInHours(now, parsedDate);
    return `${hours} ${hours === 1 ? "hour" : "hours"} ago`;
  }
  
  if (isYesterday(parsedDate)) return "yesterday";
  
  const days = differenceInDays(now, parsedDate);
  if (days < 7) return `${days} ${days === 1 ? "day" : "days"} ago`;
  
  return formatDate(parsedDate);
}

/**
 * Formats a duration in minutes to a compact string (e.g., "1h 30m")
 */
export function formatDuration(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "-";
  if (minutes === 0) return "0m";
  
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  
  const parts = [];
  if (h > 0) parts.push(`${h}h`);
  if (m > 0 || h === 0) parts.push(`${m}m`);
  
  return parts.join(" ");
}

/**
 * Formats a duration in minutes to a verbose string (e.g., "1 hour 30 minutes")
 */
export function formatDurationVerbose(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "-";
  if (minutes === 0) return "0 minutes";
  
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  
  const parts = [];
  if (h > 0) {
    parts.push(`${h} ${h === 1 ? "hour" : "hours"}`);
  }
  if (m > 0 || h === 0) {
    parts.push(`${m} ${m === 1 ? "minute" : "minutes"}`);
  }
  
  return parts.join(" ");
}

/**
 * Formats bytes to a human readable format
 */
export function formatBytes(bytes: number | null | undefined, decimals: number = 1): string {
  if (bytes === null || bytes === undefined) return "-";
  if (bytes === 0) return "0 B";
  
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"];
  
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const res = bytes / Math.pow(k, i);
  
  return (res % 1 === 0 ? res.toFixed(0) : res.toFixed(dm)) + " " + sizes[i];
}

/**
 * Formats a number as a percentage
 */
export function formatPercentage(
  value: number | null | undefined,
  decimals: number = 0
): string {
  if (value === null || value === undefined) return "-";
  
  const clamped = Math.min(100, Math.max(0, value));
  return `${clamped.toFixed(decimals)}%`;
}

/**
 * Formats MB/s throughput
 */
export function formatMBps(bytesPerSec: number | null | undefined): string | null {
  if (!bytesPerSec || !Number.isFinite(bytesPerSec) || bytesPerSec <= 0) return null;
  const mb = bytesPerSec / (1024 * 1024);
  return `${mb.toFixed(1)} MB/s`;
}

/**
 * Formats seconds into MM:SS or HH:MM:SS
 */
export function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00";
  
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  
  const mStr = m.toString().padStart(2, "0");
  const sStr = s.toString().padStart(2, "0");
  
  if (h > 0) {
    return `${h}:${mStr}:${sStr}`;
  }
  return `${mStr}:${sStr}`;
}