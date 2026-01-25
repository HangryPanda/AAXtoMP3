# Library Sync Workflow

This document describes how the application synchronizes its local database with the user's remote Audible library.

## Data Flow

The synchronization process is a "one-way sync" (Remote -> Local) managed by the `JobManager` and executed by the `AudibleClient`.

### 1. Job Initiation
*   **Trigger:** User clicks "Sync Library" or a scheduled task fires.
*   **Action:** `JobManager.queue_sync(job_id)` is called.

### 2. Fetching Data (AudibleClient)
*   **API Call:** The client calls the Audible API endpoint `1.0/library` via the `audible` python library.
*   **Pagination:**
    *   It first fetches the **newest** items (`sort_by=-PurchaseDate`).
    *   If the library is large (>1000 items), it performs a "pincer movement" strategy: it also fetches the **oldest** items (`sort_by=PurchaseDate`) and merges the lists to handle API limits.
*   **Response Groups:** Requests rich metadata including:
    *   `product_attrs`, `product_desc` (Title, Author, Description)
    *   `media` (Cover images)
    *   `contributors` (Narrators)
    *   `series` (Series name and sequence)

### 3. Database Reconciliation (JobManager)
*   **Iterative Update:** The system iterates through every item returned by the API.
*   **Matching:** Books are matched by **ASIN**.
*   **Logic:**
    *   **New Book:** If the ASIN does not exist in the `Book` table, a new record is created with `status=NEW`.
    *   **Existing Book:** If the ASIN exists, metadata fields (Title, Runtime, Series, etc.) are updated to reflect the latest values from Audible.
    *   **JSON Fields:** Complex structures (Authors, Narrators, Series) are serialized into JSON columns (`authors_json`, `series_json`) for the flat `Book` table (though normalization is handled later by the Metadata workflow).

### 4. Completion
*   **Status:** Job marks as `COMPLETED`.
*   **Result:** Returns the total count of items processed.
*   **UI Update:** The frontend receives the completion event and refreshes the library view.

## Key Handling Mechanisms

| Mechanism | Description |
| :--- | :--- |
| **API Limits** | Uses a "newest + oldest" fetch strategy to maximize coverage within Audible's 1000-item response limit per request type. |
| **Data Normalization** | Handles varying data types from the API (e.g., runtimes as strings or ints) before saving to the DB. |
| **Non-Destructive** | The sync updates metadata but **never** deletes local records. If a book is removed from Audible, it remains in the local DB (preservation philosophy). |
| **Progress Reporting** | Calculates progress based on the number of items processed vs. total items fetched, providing real-time feedback to the UI. |
