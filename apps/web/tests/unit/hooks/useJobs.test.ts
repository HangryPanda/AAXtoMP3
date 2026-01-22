/**
 * useJobs Hook Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import {
  useJobs,
  useActiveJobs,
  useJob,
  useCreateDownloadJob,
  useCreateConvertJob,
  useCancelJob,
  jobKeys,
} from "@/hooks/useJobs";
import { mockJobs } from "../../mocks/handlers";

// Create wrapper for React Query
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
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

describe("useJobs Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe("useJobs", () => {
    it("should fetch all jobs", async () => {
      const { result } = renderHook(() => useJobs(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.items).toBeDefined();
      expect(Array.isArray(result.current.data?.items)).toBe(true);
    });

    it("should filter jobs by status", async () => {
      const { result } = renderHook(() => useJobs("RUNNING"), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      if (result.current.data?.items.length) {
        result.current.data.items.forEach((job) => {
          expect(job.status).toBe("RUNNING");
        });
      }
    });
  });

  describe("useActiveJobs", () => {
    it("should fetch active jobs", async () => {
      const { result } = renderHook(() => useActiveJobs(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeDefined();
    });
  });

  describe("useJob", () => {
    it("should fetch a single job by ID", async () => {
      const testJobId = mockJobs[0].id;

      const { result } = renderHook(() => useJob(testJobId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.id).toBe(testJobId);
    });

    it("should not fetch when jobId is null", () => {
      const { result } = renderHook(() => useJob(null), {
        wrapper: createWrapper(),
      });

      expect(result.current.isFetching).toBe(false);
    });
  });

  describe("useCreateDownloadJob", () => {
    it("should create a download job for a single ASIN", async () => {
      const { result } = renderHook(() => useCreateDownloadJob(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.mutateAsync("B08C6YJ1LS");
      });

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.job_id).toBeDefined();
      expect(result.current.data?.status).toBe("PENDING");
    });

    it("should create a download job for multiple ASINs", async () => {
      const { result } = renderHook(() => useCreateDownloadJob(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.mutateAsync(["B08C6YJ1LS", "B07B4FZRNZ"]);
      });

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.job_id).toBeDefined();
    });
  });

  describe("useCreateConvertJob", () => {
    it("should create a convert job", async () => {
      const { result } = renderHook(() => useCreateConvertJob(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.mutateAsync({
          asin: "B08C6YJ1LS",
          settings: { output_format: "m4b" },
        });
      });

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.job_id).toBeDefined();
    });
  });

  describe("useCancelJob", () => {
    it("should cancel an active job", async () => {
      const { result } = renderHook(() => useCancelJob(), {
        wrapper: createWrapper(),
      });

      // Use the running job from mock data
      const runningJob = mockJobs.find((j) => j.status === "RUNNING");
      if (!runningJob) {
        throw new Error("No running job in mock data");
      }

      await act(async () => {
        await result.current.mutateAsync(runningJob.id);
      });

      expect(result.current.data).toBeDefined();
      expect(result.current.data?.message).toBeDefined();
    });
  });

  describe("jobKeys", () => {
    it("should generate correct query keys", () => {
      expect(jobKeys.all).toEqual(["jobs"]);
      expect(jobKeys.lists()).toEqual(["jobs", "list"]);
      expect(jobKeys.list("RUNNING")).toEqual(["jobs", "list", { status: "RUNNING" }]);
      expect(jobKeys.active()).toEqual(["jobs", "list", "active"]);
      expect(jobKeys.details()).toEqual(["jobs", "detail"]);
      expect(jobKeys.detail("job-001")).toEqual(["jobs", "detail", "job-001"]);
    });
  });
});
