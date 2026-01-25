/**
 * Tests for formatting functions
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  formatDate,
  formatRelativeDate,
  formatDuration,
  formatDurationVerbose,
  formatBytes,
  formatPercentage,
  formatTime,
} from "@/lib/format";

describe("formatDate", () => {
  it("should format ISO date string to readable date", () => {
    expect(formatDate("2024-01-15T10:30:00Z")).toBe("Jan 15, 2024");
  });

  it("should handle null/undefined", () => {
    expect(formatDate(null)).toBe("-");
    expect(formatDate(undefined)).toBe("-");
  });

  it("should handle invalid dates", () => {
    expect(formatDate("invalid")).toBe("-");
  });

  it("should support custom format", () => {
    expect(formatDate("2024-01-15T10:30:00Z", "yyyy-MM-dd")).toBe("2024-01-15");
  });
});

describe("formatRelativeDate", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-01-15T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should return 'just now' for very recent dates", () => {
    expect(formatRelativeDate("2024-01-15T11:59:30Z")).toBe("just now");
  });

  it("should return minutes ago for recent dates", () => {
    expect(formatRelativeDate("2024-01-15T11:55:00Z")).toBe("5 minutes ago");
    expect(formatRelativeDate("2024-01-15T11:59:00Z")).toBe("1 minute ago");
  });

  it("should return hours ago for same day", () => {
    expect(formatRelativeDate("2024-01-15T09:00:00Z")).toBe("3 hours ago");
    expect(formatRelativeDate("2024-01-15T11:00:00Z")).toBe("1 hour ago");
  });

  it("should return days ago for recent past", () => {
    expect(formatRelativeDate("2024-01-14T12:00:00Z")).toBe("yesterday");
    expect(formatRelativeDate("2024-01-12T12:00:00Z")).toBe("3 days ago");
  });

  it("should return formatted date for older dates", () => {
    expect(formatRelativeDate("2023-12-01T12:00:00Z")).toBe("Dec 1, 2023");
  });

  it("should handle null/undefined", () => {
    expect(formatRelativeDate(null)).toBe("-");
    expect(formatRelativeDate(undefined)).toBe("-");
  });
});

describe("formatDuration", () => {
  it("should format minutes to compact format", () => {
    expect(formatDuration(30)).toBe("30m");
    expect(formatDuration(60)).toBe("1h");
    expect(formatDuration(90)).toBe("1h 30m");
    expect(formatDuration(150)).toBe("2h 30m");
  });

  it("should handle zero and small values", () => {
    expect(formatDuration(0)).toBe("0m");
    expect(formatDuration(1)).toBe("1m");
  });

  it("should handle large values", () => {
    expect(formatDuration(1440)).toBe("24h");
    expect(formatDuration(1500)).toBe("25h");
  });
});

describe("formatDurationVerbose", () => {
  it("should format minutes to verbose format", () => {
    expect(formatDurationVerbose(30)).toBe("30 minutes");
    expect(formatDurationVerbose(60)).toBe("1 hour");
    expect(formatDurationVerbose(90)).toBe("1 hour 30 minutes");
    expect(formatDurationVerbose(150)).toBe("2 hours 30 minutes");
  });

  it("should handle singular/plural correctly", () => {
    expect(formatDurationVerbose(1)).toBe("1 minute");
    expect(formatDurationVerbose(61)).toBe("1 hour 1 minute");
    expect(formatDurationVerbose(121)).toBe("2 hours 1 minute");
  });
});

describe("formatBytes", () => {
  it("should format bytes to human readable format", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1023)).toBe("1023 B");
    expect(formatBytes(1024)).toBe("1 KB");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(1048576)).toBe("1 MB");
    expect(formatBytes(1073741824)).toBe("1 GB");
  });

  it("should respect decimal places", () => {
    expect(formatBytes(1536, 0)).toBe("2 KB");
    expect(formatBytes(1536, 2)).toBe("1.50 KB");
  });
});

describe("formatPercentage", () => {
  it("should format numbers as percentages", () => {
    expect(formatPercentage(0)).toBe("0%");
    expect(formatPercentage(50)).toBe("50%");
    expect(formatPercentage(100)).toBe("100%");
    expect(formatPercentage(33.333)).toBe("33%");
  });

  it("should respect decimal places", () => {
    expect(formatPercentage(33.333, 1)).toBe("33.3%");
    expect(formatPercentage(33.333, 2)).toBe("33.33%");
  });

  it("should clamp values to valid range", () => {
    expect(formatPercentage(-10)).toBe("0%");
    expect(formatPercentage(150)).toBe("100%");
  });
});

describe("formatTime", () => {
  it("should format seconds to MM:SS", () => {
    expect(formatTime(0)).toBe("00:00");
    expect(formatTime(59)).toBe("00:59");
    expect(formatTime(60)).toBe("01:00");
    expect(formatTime(90)).toBe("01:30");
  });

  it("should format seconds to HH:MM:SS when hours exist", () => {
    expect(formatTime(3600)).toBe("1:00:00");
    expect(formatTime(3661)).toBe("1:01:01");
    expect(formatTime(7322)).toBe("2:02:02");
  });

  it("should handle invalid values gracefully", () => {
    expect(formatTime(-1)).toBe("00:00");
    // @ts-expect-error Testing invalid input
    expect(formatTime(null)).toBe("00:00");
    // @ts-expect-error Testing invalid input
    expect(formatTime(undefined)).toBe("00:00");
    expect(formatTime(NaN)).toBe("00:00");
  });
});

