# Specification: Manager View (Library Dashboard)

## Overview
The "Manager" is the primary landing page and control center. It allows users to view their Audible library, filter/search books, manage downloads, and trigger conversions. It effectively replaces the "Library" and "Download/Convert" tabs of the legacy Streamlit app.

## User Experience (UX) Goals
*   **Density:** Desktop users should see a "Data Grid" or "Compact Card" view. Maximize information per pixel.
*   **Responsiveness:** Collapse to a vertical list/card view on mobile.
*   **State Awareness:** Instantly see if a book is `Online Only`, `Downloaded (AAX)`, `Converting`, or `Completed (MP3/M4B)`.

## Core Features

### 1. Library Grid / List
*   **Display Modes:** Toggle between Grid (Album Art focus) and Table (Metadata focus).
*   **Data Points:** Cover Art, Title, Author, Narrator, Series (w/ Sequence #), Duration, Release Date, Current Status.
*   **Status Indicators:** Color-coded badges (e.g., Gray: Cloud, Blue: Downloaded, Yellow: Processing, Green: Ready).

### 2. Advanced Filtering & Search
*   **Search:** Fuzzy text search across Title, Author, Narrator, Series.
*   **Smart Filters:**
    *   *Status:* "Missing Locally", "Ready to Convert", "Completed", "Failed".
    *   *Duration:* Short (< 3h), Medium, Long (> 20h).
    *   *Genre/Category:* Extracted from metadata.
*   **Sorting:** By Purchase Date (Default), Title, Author, Duration.

### 3. Actions (Bulk & Single)
*   **Download:** Fetch `.aax` or `.aaxc` from Audible (requires `audible-cli` integration).
    *   *Option:* "Download & Convert" (One-click workflow).
*   **Convert:** Trigger conversion for downloaded items.
    *   *Modal:* Open "Conversion Settings" modal (Format, Bitrate, Split/Single) before confirming.
*   **Metadata Edit:** (New Feature) Allow correcting Author/Title before conversion (passes to `AAXtoMP3` flags).
*   **Open Folder:** Open the system file explorer to the book's location (Desktop only, via API).

### 4. Job Monitor (The "Sidebar" or "Drawer")
*   **Global Activity:** A persistent indicator of active background jobs (e.g., "3 Jobs Running").
*   **Job Drawer:** Slide-out panel showing detailed progress:
    *   *Progress Bar:* Overall percent complete.
    *   *Console Output:* A high-performance "Terminal" component to display real-time streaming logs (FFmpeg output).
        *   **Virtualization:** Only render the visible portion of the logs to handle thousands of lines without lag.
        *   **Auto-Scroll:** Default to "Follow" mode (auto-scroll to bottom), but allow the user to scroll up to pause following.
        *   **Features:** ANSI color support, search/filter within logs, and a "Copy to Clipboard" button.
        *   **Persistence:** Ability to load historical logs for completed/failed jobs from the backend.
    *   *Cancel:* Ability to kill a specific job.

## Technical Requirements
*   **Virtualization:** The library may contain 1000+ books. Use virtual scrolling (e.g., `@tanstack/react-virtual`) for performance.
*   **Optimistic UI:** When a user clicks "Download", instantly update UI state to "Queued" before the API confirms.
*   **Polling/Sockets:** Use WebSockets or aggressive polling (SWR) to update file statuses without manual refresh.

## Component Breakdown (Suggestions)
*   `LibraryToolbar`: Search input, Filter dropdowns, View toggle.
*   `BookCard`: Individual item component (Grid mode).
*   `BookRow`: Individual item component (Table mode).
*   `ActionMenu`: Context menu for individual book actions (Download, Convert, etc.).
*   `StatusBadge`: Reusable status indicator.
