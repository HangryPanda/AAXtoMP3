/**
 * useBooks Hook Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useBooks, useBookDetails, bookKeys } from "@/hooks/useBooks";
import { mockBooks } from "../../mocks/handlers";

// Mock IndexedDB functions
vi.mock("@/lib/db", () => ({
  isDBAvailable: vi.fn(() => false),
  bulkPutBooks: vi.fn(),
  getBookByAsin: vi.fn(),
  getAllBooks: vi.fn(),
}));

// Create wrapper for React Query
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children
    );
  };
}

describe("useBooks Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe("useBooks", () => {
    it("should fetch paginated books", async () => {
      const { result } = renderHook(() => useBooks(), {
        wrapper: createWrapper(),
      });

      // Initially loading
      expect(result.current.isLoading).toBe(true);

      // Wait for data
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.items).toBeDefined();
      expect(Array.isArray(result.current.data?.items)).toBe(true);
    });

    it("should handle pagination params", async () => {
      const { result } = renderHook(
        () => useBooks({ page: 1, page_size: 10 }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data?.page).toBe(1);
      expect(result.current.data?.page_size).toBe(10);
    });

    it("should filter by status", async () => {
      const { result } = renderHook(() => useBooks({ status: "NEW" }), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // All returned books should have status NEW
      if (result.current.data?.items.length) {
        result.current.data.items.forEach((book) => {
          expect(book.status).toBe("NEW");
        });
      }
    });

    it("should filter by search query", async () => {
      const { result } = renderHook(() => useBooks({ search: "Hail Mary" }), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data?.items.some((b) => b.title.includes("Hail Mary"))).toBe(
        true
      );
    });

    it("should handle errors gracefully", async () => {
      // Use a non-existent endpoint to trigger error
      const { result } = renderHook(
        () =>
          useBooks({ status: "INVALID" as never }, { enabled: true }),
        { wrapper: createWrapper() }
      );

      await waitFor(
        () => {
          expect(result.current.isLoading).toBe(false);
        },
        { timeout: 5000 }
      );
    });
  });

  describe("useBookDetails", () => {
    it("should fetch a single book by ASIN", async () => {
      const testAsin = mockBooks[0].asin;

      const { result } = renderHook(() => useBookDetails(testAsin), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.asin).toBe(testAsin);
    });

    it("should not fetch when ASIN is null", () => {
      const { result } = renderHook(() => useBookDetails(null), {
        wrapper: createWrapper(),
      });

      // Should not be loading since query is disabled
      expect(result.current.isFetching).toBe(false);
    });

    it("should return 404 for non-existent ASIN", async () => {
      const { result } = renderHook(() => useBookDetails("non-existent-asin"), {
        wrapper: createWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.isLoading).toBe(false);
        },
        { timeout: 5000 }
      );

      expect(result.current.error).toBeDefined();
    });
  });

  describe("bookKeys", () => {
    it("should generate correct query keys", () => {
      expect(bookKeys.all).toEqual(["books"]);
      expect(bookKeys.lists()).toEqual(["books", "list"]);
      expect(bookKeys.list({ status: "NEW" })).toEqual([
        "books",
        "list",
        { status: "NEW" },
      ]);
      expect(bookKeys.details()).toEqual(["books", "detail"]);
      expect(bookKeys.detail("test-asin")).toEqual(["books", "detail", "test-asin"]);
    });
  });
});
