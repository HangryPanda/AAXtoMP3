/**
 * Books Service
 * API functions for managing books
 */

import { apiRequest } from "./api";
import type {
  Book,
  BookListParams,
  PaginatedBooks,
  JobCreateResponse,
  QueuedJobResponse,
  SeriesOptionsResponse,
  LibrarySyncStatus,
  PaginatedLocalItems,
  LocalItem,
  RepairPreview,
  PlaybackProgressResponse,
  BookDetailsResponse,
  PartialDownloadsResponse,
} from "@/types";

/**
 * Get paginated list of books with optional filtering
 */
export async function getBooks(params?: BookListParams): Promise<PaginatedBooks> {
  // Map frontend parameter names to backend API parameter names
  const apiParams: Record<string, string | number | boolean | undefined> = {};

  if (params) {
    // Pagination: convert page/page_size to skip/limit
    const page = params.page ?? 1;
    const pageSize = params.page_size ?? 100;
    apiParams.skip = (page - 1) * pageSize;
    apiParams.limit = pageSize;

    // Search: frontend uses 'search', backend expects 'q'
    if (params.search) {
      apiParams.q = params.search;
    }

    // Status filter
    if (params.status) {
      apiParams.status = params.status;
    }

    // Series filter: frontend uses 'series_title', backend expects 'series'
    if (params.series_title) {
      apiParams.series = params.series_title;
    }

    // Sorting: frontend uses 'sort_order', backend expects 'sort_dir'
    if (params.sort_by) {
      apiParams.sort_by = params.sort_by;
    }
    if (params.sort_order) {
      apiParams.sort_dir = params.sort_order;
    }

    // Has local filter
    if (params.has_local !== undefined) {
      apiParams.has_local = params.has_local;
    }

    // Content type filter
    if (params.content_type) {
      apiParams.content_type = params.content_type;
    }

    // Since filter (for incremental sync)
    if (params.since) {
      apiParams.since = params.since;
    }
  }

  const response = await apiRequest<{
    items: Book[];
    total: number;
    skip: number;
    limit: number;
  }>({
    method: "GET",
    url: "/library",
    params: apiParams,
  });

  // Transform backend response to frontend format
  const page = params?.page ?? 1;
  const pageSize = params?.page_size ?? 100;

  return {
    items: response.items,
    total: response.total,
    page: page,
    page_size: pageSize,
    total_pages: Math.ceil(response.total / pageSize),
  };
}

/**
 * Get a single book by ASIN
 */
export async function getBookDetails(asin: string): Promise<Book> {
  return apiRequest<Book>({
    method: "GET",
    url: `/library/${asin}`,
  });
}

/**
 * Get enriched book details (normalized metadata, chapters, technical info).
 */
export async function getBookDetailsEnriched(asin: string): Promise<BookDetailsResponse> {
  return apiRequest<BookDetailsResponse>({
    method: "GET",
    url: `/library/${asin}/details`,
  });
}

/**
 * Sync library from Audible
 * Triggers a background job to refresh the library
 */
export async function syncLibrary(): Promise<JobCreateResponse> {
  return apiRequest<JobCreateResponse>({
    method: "POST",
    url: "/library/sync",
  });
}

/**
 * Get books updated since a specific timestamp
 * Useful for syncing with local storage
 */
export async function getBooksSince(since: string): Promise<PaginatedBooks> {
  return getBooks({ since, page_size: 1000 });
}

/**
 * Search books by title, author, or narrator
 */
export async function searchBooks(
  query: string,
  params?: Omit<BookListParams, "search">
): Promise<PaginatedBooks> {
  return getBooks({ ...params, search: query });
}

/**
 * Get books by status
 */
export async function getBooksByStatus(
  status: Book["status"],
  params?: Omit<BookListParams, "status">
): Promise<PaginatedBooks> {
  return getBooks({ ...params, status });
}

/**
 * Get all completed books (ready to play)
 */
export async function getCompletedBooks(
  params?: Omit<BookListParams, "status">
): Promise<PaginatedBooks> {
  return getBooksByStatus("COMPLETED", params);
}

/**
 * Get all new books (not downloaded)
 */
export async function getNewBooks(
  params?: Omit<BookListParams, "status">
): Promise<PaginatedBooks> {
  return getBooksByStatus("NEW", params);
}

/**
 * Delete a book by ASIN
 */
export async function deleteBook(asin: string, deleteFiles: boolean = false): Promise<void> {
  return apiRequest<void>({
    method: "DELETE",
    url: `/library/${asin}`,
    params: { delete_files: deleteFiles },
  });
}

/**
 * Batch delete books
 */
export async function deleteBooks(asins: string[], deleteFiles: boolean = false): Promise<{ deleted: number }> {
  return apiRequest<{ deleted: number }>({
    method: "POST",
    url: "/library/delete",
    params: { delete_files: deleteFiles },
    data: { asins },
  });
}

/**
 * Get distinct series options for filtering.
 */
export async function getSeriesOptions(): Promise<SeriesOptionsResponse> {
  return apiRequest<SeriesOptionsResponse>({
    method: "GET",
    url: "/library/series",
  });
}

/**
 * Get last successful sync time and total library size.
 */
export async function getLibrarySyncStatus(): Promise<LibrarySyncStatus> {
  return apiRequest<LibrarySyncStatus>({
    method: "GET",
    url: "/library/sync/status",
  });
}

export async function getLocalItems(params?: {
  page?: number;
  page_size?: number;
  search?: string;
}): Promise<PaginatedLocalItems> {
  return apiRequest<PaginatedLocalItems>({
    method: "GET",
    url: "/library/local",
    params: params as Record<string, string | number | boolean | undefined>,
  });
}

export async function getLocalItemDetails(localId: string): Promise<LocalItem> {
  return apiRequest<LocalItem>({
    method: "GET",
    url: `/library/local/${localId}`,
  });
}

export async function getRepairPreview(): Promise<RepairPreview> {
  return apiRequest<RepairPreview>({
    method: "GET",
    url: "/library/repair/preview",
  });
}

export async function applyRepair(): Promise<QueuedJobResponse> {
  return apiRequest<QueuedJobResponse>({
    method: "POST",
    url: "/library/repair/apply",
  });
}

/**
 * Get playback progress for a book from the server
 */
export async function getPlaybackProgress(
  asin: string
): Promise<PlaybackProgressResponse | null> {
  return apiRequest<PlaybackProgressResponse | null>({
    method: "GET",
    url: `/library/${asin}/progress`,
  });
}

/**
 * Update playback progress for a book
 */
export async function updatePlaybackProgress(
  asin: string,
  data: {
    position_ms: number;
    playback_speed?: number;
    is_finished?: boolean;
    chapter_id?: string;
  }
): Promise<PlaybackProgressResponse> {
  return apiRequest<PlaybackProgressResponse>({
    method: "PATCH",
    url: `/library/${asin}/progress`,
    data,
  });
}

/**
 * Get books in progress (Continue Listening)
 */
export async function getContinueListening(limit = 5): Promise<PlaybackProgressResponse[]> {
  return apiRequest<PlaybackProgressResponse[]>({
    method: "GET",
    url: "/library/continue-listening",
    params: { limit },
  });
}

/**
 * Get partial downloads (cover downloaded but no aaxc file).
 * These need to be re-downloaded before conversion is possible.
 */
export async function getIncompleteDownloads(): Promise<PartialDownloadsResponse> {
  return apiRequest<PartialDownloadsResponse>({
    method: "GET",
    url: "/library/downloads/incomplete",
  });
}
