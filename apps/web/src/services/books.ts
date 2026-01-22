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
} from "@/types";

/**
 * Get paginated list of books with optional filtering
 */
export async function getBooks(params?: BookListParams): Promise<PaginatedBooks> {
  return apiRequest<PaginatedBooks>({
    method: "GET",
    url: "/library",
    params: params as Record<string, string | number | boolean | undefined>,
  });
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
export async function deleteBook(asin: string): Promise<void> {
  return apiRequest<void>({
    method: "DELETE",
    url: `/library/${asin}`,
  });
}

/**
 * Batch delete books
 */
export async function deleteBooks(asins: string[]): Promise<{ deleted: number }> {
  return apiRequest<{ deleted: number }>({
    method: "POST",
    url: "/library/delete",
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
