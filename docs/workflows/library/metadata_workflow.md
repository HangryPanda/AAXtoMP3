# Metadata Extraction & Scanning Workflow

This document explains how the system extracts, normalizes, and persists rich metadata from media files (specifically `.m4b`) into the relational database.

## Overview

While the **Library Sync** provides basic metadata from the Audible API, the **Metadata Workflow** extracts technical details (bitrate, duration) and embedded tags (chapters, cover art) directly from the converted files. This ensures the player UI has accurate chapter markers and media info.

## Data Flow

### 1. Trigger
*   **Automatic:** Triggered immediately after a successful conversion.
*   **Manual:** Triggered via the "Scan Library" job or "Scan Book" action.
*   **Repair:** Optionally triggered during the Repair workflow if `repair_extract_metadata` is enabled.

### 2. Fingerprinting (Change Detection)
*   **Efficiency:** Before processing, the system checks the file's **Fingerprint** (size + mtime).
*   **Comparison:** It compares this against the stored `BookScanState`.
*   **Decision:** If the fingerprint matches and chapters exist in the DB, the scan is skipped to save resources.

### 3. Extraction (MetadataExtractor)
*   **Tooling:** Uses `ffprobe` (via `ffmpeg`) to read file headers.
*   **Data Points:**
    *   **Technical:** Format, Bitrate, Sample Rate, Channels, Duration.
    *   **Tags:** Title, Author, Narrator, Series.
    *   **Chapters:** Start/End times, Titles.
    *   **Cover Art:** Extracts the embedded cover image to a cache directory (`/data/covers`).

### 4. Persistence (LibraryManager)
*   **Normalization:**
    *   **Authors/Narrators:** Normalized into the `Person` table (many-to-many relationship).
    *   **Series:** Normalized into the `Series` table.
*   **Chapters:** Overwrites the `Chapter` table for the book with the new list.
*   **Assets:** Updates the `BookAsset` table with the path to the extracted cover.
*   **Technical:** Updates the `BookTechnical` table.

## Key Handling Mechanisms

| Mechanism | Description |
| :--- | :--- |
| **Fingerprinting** | Avoids redundant processing of large media files by checking modification times and size. |
| **Normalization** | converting flat string tags (e.g., "Author A, Author B") into proper relational entities allows for features like "Books by this Author". |
| **Cover Extraction** | Since converted files often have better/custom embedded covers than the API, extracting them ensures the UI displays what the user actually sees in other players. |
| **Fallback** | If extraction fails (e.g., corrupt file), the system logs the error but leaves the API-sourced metadata intact. |
