/**
 * useBooks Hook
 * React Query hook for fetching and managing books with IndexedDB caching
 */

import { useMemo } from "react";
import {
  useQuery,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { getBooks, getBookDetails, getBookDetailsEnriched, syncLibrary, deleteBook, deleteBooks, getSeriesOptions, getLibrarySyncStatus, getLocalItems, getLocalItemDetails, getRepairPreview, applyRepair, getContinueListening } from "@/services/books";
import {
  getAllBooks,
  bulkPutBooks,
  getBookByAsin,
  isDBAvailable,
} from "@/lib/db";
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
  BookDetailsResponse,
} from "@/types";

/**
 * Query keys for books
 */
export const bookKeys = {
  all: ["books"] as const,
  lists: () => [...bookKeys.all, "list"] as const,
  list: (params: BookListParams) => [...bookKeys.lists(), params] as const,
  details: () => [...bookKeys.all, "detail"] as const,
  detail: (asin: string) => [...bookKeys.details(), asin] as const,
  detailsEnriched: () => [...bookKeys.all, "detailEnriched"] as const,
  detailEnriched: (asin: string) => [...bookKeys.detailsEnriched(), asin] as const,
  series: () => [...bookKeys.all, "series"] as const,
  syncStatus: () => [...bookKeys.all, "syncStatus"] as const,
  local: () => [...bookKeys.all, "local"] as const,
  localList: (params: { page?: number; page_size?: number; search?: string }) =>
    [...bookKeys.local(), "list", params] as const,
  localDetail: (id: string) => [...bookKeys.local(), "detail", id] as const,
  repairPreview: () => [...bookKeys.all, "repairPreview"] as const,
};

/**
 * Hook options type
 */
export interface UseBooksOptions {
  /** Initial page size */
  pageSize?: number;
  /** Enable IndexedDB caching */
  enableCache?: boolean;
  /** Stale time in ms */
  staleTime?: number;
}

/**
 * Hook for fetching paginated books
 */
export function useBooks(
  params?: BookListParams,
  options?: UseBooksOptions & Omit<UseQueryOptions<PaginatedBooks>, "queryKey" | "queryFn">
) {
  const { pageSize = 20, enableCache = true, staleTime = 5 * 60 * 1000, ...queryOptions } = options ?? {};

  const mergedParams = useMemo((): BookListParams => ({
    page: 1,
    page_size: pageSize,
    ...params,
  }), [params, pageSize]);

  return useQuery({
    queryKey: bookKeys.list(mergedParams),
    queryFn: async () => {
      const result = await getBooks(mergedParams);

      // Cache to IndexedDB
      if (enableCache && isDBAvailable() && result.items.length > 0) {
        try {
          await bulkPutBooks(result.items);
        } catch (error) {
          console.warn("Failed to cache books:", error);
        }
      }

      return result;
    },
    staleTime,
    ...queryOptions,
  });
}

/**
 * Hook for infinite scrolling books list
 */
export function useInfiniteBooks(
  params?: Omit<BookListParams, "page">,
  options?: UseBooksOptions & {
    enabled?: boolean;
    refetchOnWindowFocus?: boolean;
    refetchOnMount?: boolean;
  }
) {
  const { pageSize = 20, enableCache = true, staleTime = 5 * 60 * 1000, ...queryOptions } = options ?? {};

  const queryKey = useMemo(() => bookKeys.list({ ...params, page_size: pageSize }), [params, pageSize]);

  return useInfiniteQuery({
    queryKey,
    queryFn: async ({ pageParam }) => {
      const result = await getBooks({
        ...params,
        page: pageParam,
        page_size: pageSize,
      });

      // Cache to IndexedDB
      if (enableCache && isDBAvailable() && result.items.length > 0) {
        try {
          await bulkPutBooks(result.items);
        } catch (error) {
          console.warn("Failed to cache books:", error);
        }
      }

      return result;
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      if (lastPage.page < lastPage.total_pages) {
        return lastPage.page + 1;
      }
      return undefined;
    },
    staleTime,
    ...queryOptions,
  });
}

/**
 * Hook for fetching a single book's details
 */
export function useBookDetails(
  asin: string | null | undefined,
  options?: UseBooksOptions & Omit<UseQueryOptions<Book | null>, "queryKey" | "queryFn">
) {
  const { enableCache = true, staleTime = 5 * 60 * 1000, ...queryOptions } = options ?? {};

  return useQuery({
    queryKey: asin ? bookKeys.detail(asin) : ["disabled"],
    queryFn: async () => {
      if (!asin) return null;

      // Try cache first
      if (enableCache && isDBAvailable()) {
        try {
          const cached = await getBookByAsin(asin);
          if (cached) {
            // Fetch fresh in background
            getBookDetails(asin)
              .then((fresh) => bulkPutBooks([fresh]))
              .catch(console.warn);
            return cached;
          }
        } catch {
          // Continue to fetch from API
        }
      }

      const book = await getBookDetails(asin);

      // Cache result
      if (enableCache && isDBAvailable()) {
        try {
          await bulkPutBooks([book]);
        } catch (error) {
          console.warn("Failed to cache book:", error);
        }
      }

      return book;
    },
    enabled: !!asin,
    staleTime,
    ...queryOptions,
  });
}

/**
 * Hook for fetching enriched book details (chapters/technical/etc).
 * When the API returns synthetic chapters, poll briefly for real chapters.
 */
export function useBookDetailsEnriched(
  asin: string | null | undefined,
  options?: Omit<UseQueryOptions<BookDetailsResponse | null>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: asin ? bookKeys.detailEnriched(asin) : ["disabled"],
    queryFn: async () => {
      if (!asin) return null;
      return getBookDetailsEnriched(asin);
    },
    enabled: !!asin,
    staleTime: 0,
    refetchInterval: (query) => {
      const data = query.state.data as BookDetailsResponse | null | undefined;
      if (!data) return false;
      if (data.chapters_synthetic) return 3000;
      if (Array.isArray(data.chapters) && data.chapters.length === 0) return 3000;
      return false;
    },
    ...options,
  });
}

/**
 * Hook for syncing library from Audible
 */
export function useSyncLibrary() {
  const queryClient = useQueryClient();

  return useMutation<JobCreateResponse, Error>({
    mutationFn: syncLibrary,
    onSuccess: () => {
      // Invalidate books cache after sync completes
      // The actual invalidation should happen when the job completes
      queryClient.invalidateQueries({ queryKey: bookKeys.all });
    },
  });
}

/**
 * Hook for getting cached books from IndexedDB
 * Useful for offline support
 */
export function useCachedBooks(
  params?: {
    status?: Book["status"];
    search?: string;
    limit?: number;
    offset?: number;
  },
  options?: Omit<UseQueryOptions<Book[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: ["cachedBooks", params],
    queryFn: async () => {
      if (!isDBAvailable()) {
        return [];
      }
      return getAllBooks(params);
    },
    ...options,
  });
}

/**
 * Hook for fetching distinct series titles for filtering.
 */
export function useSeriesOptions(
  options?: Omit<UseQueryOptions<SeriesOptionsResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: bookKeys.series(),
    queryFn: getSeriesOptions,
    staleTime: 10 * 60 * 1000,
    ...options,
  });
}

/**
 * Hook for fetching last successful sync time and library size.
 */
export function useLibrarySyncStatus(
  options?: Omit<UseQueryOptions<LibrarySyncStatus>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: bookKeys.syncStatus(),
    queryFn: getLibrarySyncStatus,
    staleTime: 30 * 1000,
    refetchInterval: 30 * 1000,
    ...options,
  });
}

export function useLocalItems(
  params?: { page?: number; page_size?: number; search?: string },
  options?: Omit<UseQueryOptions<PaginatedLocalItems>, "queryKey" | "queryFn">
) {
  const mergedParams = useMemo(
    () => ({
      page: 1,
      page_size: 50,
      ...params,
    }),
    [params]
  );

  return useQuery({
    queryKey: bookKeys.localList(mergedParams),
    queryFn: () => getLocalItems(mergedParams),
    staleTime: 30 * 1000,
    ...options,
  });
}

export function useLocalItemDetails(
  localId: string | null | undefined,
  options?: Omit<UseQueryOptions<LocalItem | null>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: localId ? bookKeys.localDetail(localId) : ["disabled"],
    queryFn: async () => {
      if (!localId) return null;
      return getLocalItemDetails(localId);
    },
    enabled: !!localId,
    staleTime: 30 * 1000,
    ...options,
  });
}

export function useRepairPreview(
  options?: Omit<UseQueryOptions<RepairPreview>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: bookKeys.repairPreview(),
    queryFn: getRepairPreview,
    staleTime: 30 * 1000,
    refetchInterval: 30 * 1000,
    ...options,
  });
}

export function useApplyRepair() {
  const queryClient = useQueryClient();

  return useMutation<QueuedJobResponse, Error>({
    mutationFn: applyRepair,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: bookKeys.repairPreview() });
      queryClient.invalidateQueries({ queryKey: bookKeys.all });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

/**
 * Hook for fetching books in progress (Continue Listening)
 */
export function useContinueListening(
  limit = 5,
  options?: Omit<UseQueryOptions<any>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: [...bookKeys.all, "continue-listening", limit],
    queryFn: () => getContinueListening(limit),
    staleTime: 15 * 1000,
    ...options,
  });
}

/**
 * Hook to prefetch books
 */
export function usePrefetchBooks() {
  const queryClient = useQueryClient();

  return {
    prefetchPage: (params: BookListParams) => {
      return queryClient.prefetchQuery({
        queryKey: bookKeys.list(params),
        queryFn: () => getBooks(params),
        staleTime: 5 * 60 * 1000,
      });
    },
    prefetchBook: (asin: string) => {
      return queryClient.prefetchQuery({
        queryKey: bookKeys.detail(asin),
        queryFn: () => getBookDetails(asin),
        staleTime: 5 * 60 * 1000,
      });
    },
  };
}

/**
 * Hook for book search with debounce
 */
export function useBookSearch(
  query: string,
  params?: Omit<BookListParams, "search">,
  options?: UseBooksOptions
) {
  return useBooks(
    { ...params, search: query || undefined },
    {
      ...options,
      enabled: query.length >= 2,
    }
  );
}

/**
 * Hook for fetching books by status
 */
export function useBooksByStatus(
  status: Book["status"],
  params?: Omit<BookListParams, "status">,
  options?: UseBooksOptions
) {
  return useBooks(
    { ...params, status },
    options
  );
}

/**
 * Hook for deleting a single book
 */
export function useDeleteBook() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: (asin) => deleteBook(asin),
    onSuccess: (_, asin) => {
      queryClient.invalidateQueries({ queryKey: bookKeys.all });
      queryClient.removeQueries({ queryKey: bookKeys.detail(asin) });
    },
  });
}

/**
 * Hook for batch deleting books
 */
export function useDeleteBooks() {
  const queryClient = useQueryClient();

  return useMutation<{ deleted: number }, Error, string[]>({
    mutationFn: (asins) => deleteBooks(asins),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: bookKeys.all });
    },
  });
}
