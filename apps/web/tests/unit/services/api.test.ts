/**
 * API Client Tests
 * Tests the core API client functionality including interceptors, error handling, and retry logic
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { http, HttpResponse, delay } from "msw";
import { server } from "../../mocks/server";
import { z } from "zod";

// We'll import these after creating the api module
import {
  apiClient,
  apiRequest,
  setAuthToken,
  clearAuthToken,
  ApiError,
} from "@/services/api";
import type { Book } from "@/types";

const API_BASE = "http://localhost:8000";

describe("API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearAuthToken();
  });

  afterEach(() => {
    server.resetHandlers();
  });

  describe("apiClient axios instance", () => {
    it("should have the correct base URL configured", () => {
      expect(apiClient.defaults.baseURL).toBe(API_BASE);
    });

    it("should have JSON content-type header", () => {
      expect(apiClient.defaults.headers["Content-Type"]).toBe(
        "application/json"
      );
    });
  });

  describe("authentication", () => {
    it("should add auth token to requests when set", async () => {
      let authHeader: string | null = null;

      server.use(
        http.get(`${API_BASE}/api/test-auth`, ({ request }) => {
          authHeader = request.headers.get("Authorization");
          return HttpResponse.json({ success: true });
        })
      );

      setAuthToken("test-token-123");
      await apiClient.get("/api/test-auth");

      expect(authHeader).toBe("Bearer test-token-123");
    });

    it("should not add auth header when token is not set", async () => {
      let authHeader: string | null = null;

      server.use(
        http.get(`${API_BASE}/api/test-no-auth`, ({ request }) => {
          authHeader = request.headers.get("Authorization");
          return HttpResponse.json({ success: true });
        })
      );

      await apiClient.get("/api/test-no-auth");

      expect(authHeader).toBeNull();
    });

    it("should clear auth token properly", async () => {
      let authHeader: string | null = null;

      server.use(
        http.get(`${API_BASE}/api/test-cleared`, ({ request }) => {
          authHeader = request.headers.get("Authorization");
          return HttpResponse.json({ success: true });
        })
      );

      setAuthToken("test-token");
      clearAuthToken();
      await apiClient.get("/api/test-cleared");

      expect(authHeader).toBeNull();
    });
  });

  describe("error handling", () => {
    it("should handle 401 errors and clear auth token", async () => {
      setAuthToken("expired-token");

      await expect(apiClient.get("/api/error/401")).rejects.toThrow();

      // Token should be cleared after 401
      let authHeader: string | null = "initial";
      server.use(
        http.get(`${API_BASE}/api/check-token`, ({ request }) => {
          authHeader = request.headers.get("Authorization");
          return HttpResponse.json({ success: true });
        })
      );

      await apiClient.get("/api/check-token");
      expect(authHeader).toBeNull();
    });

    it("should throw ApiError with proper structure for HTTP errors", async () => {
      try {
        await apiClient.get("/api/error/500");
        expect.fail("Should have thrown");
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        if (error instanceof ApiError) {
          expect(error.status).toBe(500);
          expect(error.message).toBeDefined();
        }
      }
    });

    it("should handle network errors gracefully", async () => {
      try {
        await apiClient.get("/api/error/network");
        expect.fail("Should have thrown");
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        if (error instanceof ApiError) {
          expect(error.isNetworkError).toBe(true);
        }
      }
    });
  });

  describe("retry logic", () => {
    it("should retry on 500 errors up to max retries", async () => {
      let requestCount = 0;

      server.use(
        http.get(`${API_BASE}/api/flaky`, () => {
          requestCount++;
          if (requestCount < 3) {
            return HttpResponse.json(
              { detail: "Server Error" },
              { status: 500 }
            );
          }
          return HttpResponse.json({ success: true });
        })
      );

      const result = await apiRequest<{ success: boolean }>({
        method: "GET",
        url: "/api/flaky",
        retry: { maxRetries: 3, retryDelay: 10 },
      });

      expect(result.success).toBe(true);
      expect(requestCount).toBe(3);
    });

    it("should fail after max retries exceeded", async () => {
      let requestCount = 0;

      server.use(
        http.get(`${API_BASE}/api/always-fails`, () => {
          requestCount++;
          return HttpResponse.json({ detail: "Server Error" }, { status: 500 });
        })
      );

      await expect(
        apiRequest({
          method: "GET",
          url: "/api/always-fails",
          retry: { maxRetries: 2, retryDelay: 10 },
        })
      ).rejects.toThrow();

      expect(requestCount).toBe(3); // Initial + 2 retries
    });

    it("should not retry on 4xx errors (except specific ones)", async () => {
      let requestCount = 0;

      server.use(
        http.get(`${API_BASE}/api/bad-request`, () => {
          requestCount++;
          return HttpResponse.json({ detail: "Bad Request" }, { status: 400 });
        })
      );

      await expect(
        apiRequest({
          method: "GET",
          url: "/api/bad-request",
          retry: { maxRetries: 3, retryDelay: 10 },
        })
      ).rejects.toThrow();

      expect(requestCount).toBe(1); // No retries for 4xx
    });
  });

  describe("apiRequest function", () => {
    it("should make GET requests and return typed data", async () => {
      const books = await apiRequest<{ items: Book[] }>({
        method: "GET",
        url: "/api/books",
      });

      expect(books.items).toBeDefined();
      expect(Array.isArray(books.items)).toBe(true);
    });

    it("should make POST requests with body", async () => {
      const response = await apiRequest<{ job_id: string }>({
        method: "POST",
        url: "/api/jobs/download",
        data: { asins: ["B08C6YJ1LS"] },
      });

      expect(response.job_id).toBeDefined();
      expect(typeof response.job_id).toBe("string");
    });

    it("should validate response with Zod schema when provided", async () => {
      const bookSchema = z.object({
        asin: z.string(),
        title: z.string(),
        status: z.string(),
      });

      const book = await apiRequest({
        method: "GET",
        url: "/api/books/B08C6YJ1LS",
        schema: bookSchema,
      });

      expect(book.asin).toBe("B08C6YJ1LS");
      expect(book.title).toBeDefined();
    });

    it("should throw validation error when schema validation fails", async () => {
      const strictSchema = z.object({
        invalidField: z.string(),
      });

      await expect(
        apiRequest({
          method: "GET",
          url: "/api/books/B08C6YJ1LS",
          schema: strictSchema,
        })
      ).rejects.toThrow();
    });

    it("should support query parameters", async () => {
      const response = await apiRequest<{ items: Book[]; total: number }>({
        method: "GET",
        url: "/api/books",
        params: { status: "NEW", page: 1, page_size: 10 },
      });

      expect(response.items).toBeDefined();
    });
  });

  describe("request timeout", () => {
    it("should timeout after configured duration", async () => {
      server.use(
        http.get(`${API_BASE}/api/slow`, async () => {
          await delay(5000); // 5 second delay
          return HttpResponse.json({ success: true });
        })
      );

      await expect(
        apiRequest({
          method: "GET",
          url: "/api/slow",
          timeout: 100, // 100ms timeout
        })
      ).rejects.toThrow();
    });
  });
});
