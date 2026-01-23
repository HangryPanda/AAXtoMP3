/**
 * MSW request handlers for API mocking in tests
 */

import { http, HttpResponse, delay } from "msw";
import type {
  Book,
  PaginatedBooks,
  Job,
  JobCreateResponse,
  JobListResponse,
  Settings,
} from "@/types";

// Base URL for API requests
const API_BASE = "http://localhost:8000";

// Mock data
export const mockBooks: Book[] = [
  {
    asin: "B08C6YJ1LS",
    title: "Project Hail Mary",
    subtitle: "A Novel",
    authors: [{ asin: "B001JP2RJA", name: "Andy Weir" }],
    narrators: [{ name: "Ray Porter" }],
    series: null,
    runtime_length_min: 985,
    release_date: "2021-05-04",
    purchase_date: "2021-05-10",
    product_images: { "500": "https://example.com/cover.jpg" },
    publisher: "Audible Studios",
    language: "English",
    format_type: "aaxc",
    aax_available: false,
    aaxc_available: true,
    status: "NEW",
    local_path_aax: null,
    local_path_voucher: null,
    local_path_cover: null,
    local_path_converted: null,
    conversion_format: null,
    error_message: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    asin: "B07B4FZRNZ",
    title: "Ready Player Two",
    subtitle: null,
    authors: [{ asin: "B002BYL7FU", name: "Ernest Cline" }],
    narrators: [{ name: "Wil Wheaton" }],
    series: [{ asin: "B00L5URNWQ", title: "Ready Player One", sequence: "2" }],
    runtime_length_min: 730,
    release_date: "2020-11-24",
    purchase_date: "2020-12-01",
    product_images: { "500": "https://example.com/cover2.jpg" },
    publisher: "Random House Audio",
    language: "English",
    format_type: "aaxc",
    aax_available: false,
    aaxc_available: true,
    status: "COMPLETED",
    local_path_aax: null,
    local_path_voucher: null,
    local_path_cover: "/covers/ready-player-two.jpg",
    local_path_converted: "/audiobooks/ready-player-two.m4b",
    conversion_format: "m4b",
    error_message: null,
    created_at: "2024-01-02T00:00:00Z",
    updated_at: "2024-01-15T00:00:00Z",
  },
];

export const mockJobs: Job[] = [
  {
    id: "job-001",
    task_type: "DOWNLOAD",
    book_asin: "B08C6YJ1LS",
    status: "RUNNING",
    progress_percent: 45,
    status_message: "Downloading...",
    log_file_path: "/logs/job-001.log",
    error_message: null,
    started_at: "2024-01-15T10:00:00Z",
    completed_at: null,
    created_at: "2024-01-15T09:55:00Z",
  },
  {
    id: "job-002",
    task_type: "CONVERT",
    book_asin: "B07B4FZRNZ",
    status: "COMPLETED",
    progress_percent: 100,
    status_message: null,
    log_file_path: "/logs/job-002.log",
    error_message: null,
    started_at: "2024-01-14T08:00:00Z",
    completed_at: "2024-01-14T09:30:00Z",
    created_at: "2024-01-14T07:55:00Z",
  },
];

export const mockSettings: Settings = {
  output_format: "m4b",
  single_file: true,
  compression_mp3: 4,
  compression_flac: 5,
  compression_opus: 5,
  cover_size: "1215",
  dir_naming_scheme: "$genre/$artist/$title",
  file_naming_scheme: "$title",
  chapter_naming_scheme: "",
  no_clobber: false,
  move_after_complete: false,
  auto_retry: true,
  max_retries: 3,
  author_override: "",
  keep_author_index: 0,
};

// Handler state for testing
let jobIdCounter = 100;

// Handlers
export const handlers = [
  // Books endpoints
  http.get(`${API_BASE}/api/books`, async ({ request }) => {
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get("page") || "1", 10);
    const pageSize = parseInt(url.searchParams.get("page_size") || "20", 10);
    const status = url.searchParams.get("status");
    const search = url.searchParams.get("search");

    let filteredBooks = [...mockBooks];

    // Filter by status
    if (status) {
      filteredBooks = filteredBooks.filter((book) => book.status === status);
    }

    // Filter by search
    if (search) {
      const searchLower = search.toLowerCase();
      filteredBooks = filteredBooks.filter(
        (book) =>
          book.title.toLowerCase().includes(searchLower) ||
          book.authors.some((a) => a.name.toLowerCase().includes(searchLower))
      );
    }

    // Paginate
    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    const paginatedItems = filteredBooks.slice(start, end);

    const response: PaginatedBooks = {
      items: paginatedItems,
      total: filteredBooks.length,
      page,
      page_size: pageSize,
      total_pages: Math.ceil(filteredBooks.length / pageSize),
    };

    await delay(10);
    return HttpResponse.json(response);
  }),

  http.get(`${API_BASE}/api/books/:asin`, async ({ params }) => {
    const { asin } = params;
    const book = mockBooks.find((b) => b.asin === asin);

    if (!book) {
      return HttpResponse.json(
        { detail: "Book not found" },
        { status: 404 }
      );
    }

    await delay(10);
    return HttpResponse.json(book);
  }),

  http.post(`${API_BASE}/api/sync/library`, async () => {
    await delay(50);
    const response: JobCreateResponse = {
      job_id: `job-sync-${++jobIdCounter}`,
      status: "PENDING",
      message: "Library sync started",
    };
    return HttpResponse.json(response);
  }),

  // Jobs endpoints
  http.get(`${API_BASE}/api/jobs`, async ({ request }) => {
    const url = new URL(request.url);
    const status = url.searchParams.get("status");

    let filteredJobs = [...mockJobs];
    if (status) {
      filteredJobs = filteredJobs.filter((job) => job.status === status);
    }

    const response: JobListResponse = {
      items: filteredJobs,
      total: filteredJobs.length,
    };

    await delay(10);
    return HttpResponse.json(response);
  }),

  http.get(`${API_BASE}/api/jobs/:id`, async ({ params }) => {
    const { id } = params;
    const job = mockJobs.find((j) => j.id === id);

    if (!job) {
      return HttpResponse.json(
        { detail: "Job not found" },
        { status: 404 }
      );
    }

    await delay(10);
    return HttpResponse.json(job);
  }),

  http.post(`${API_BASE}/api/jobs/download`, async ({ request }) => {
    const body = (await request.json()) as { asin?: string; asins?: string[] };
    const asins = body.asins || (body.asin ? [body.asin] : []);

    if (asins.length === 0) {
      return HttpResponse.json(
        { detail: "No ASINs provided" },
        { status: 400 }
      );
    }

    const response: JobCreateResponse = {
      job_id: `job-dl-${++jobIdCounter}`,
      status: "PENDING",
      message: `Download job created for ${asins.length} book(s)`,
    };

    await delay(10);
    return HttpResponse.json(response, { status: 201 });
  }),

  http.post(`${API_BASE}/api/jobs/convert`, async ({ request }) => {
    const body = (await request.json()) as {
      asin: string;
      format?: string;
      naming_scheme?: string;
    };

    if (!body.asin) {
      return HttpResponse.json(
        { detail: "ASIN is required" },
        { status: 400 }
      );
    }

    const response: JobCreateResponse = {
      job_id: `job-conv-${++jobIdCounter}`,
      status: "PENDING",
      message: `Convert job created for book ${body.asin}`,
    };

    await delay(10);
    return HttpResponse.json(response, { status: 201 });
  }),

  http.delete(`${API_BASE}/api/jobs/:id`, async ({ params }) => {
    const { id } = params;
    const job = mockJobs.find((j) => j.id === id);

    if (!job) {
      return HttpResponse.json(
        { detail: "Job not found" },
        { status: 404 }
      );
    }

    if (job.status === "COMPLETED" || job.status === "CANCELLED") {
      return HttpResponse.json(
        { detail: "Job cannot be cancelled" },
        { status: 400 }
      );
    }

    await delay(10);
    return HttpResponse.json({ message: "Job cancelled" });
  }),

  // Settings endpoints
  http.get(`${API_BASE}/api/settings`, async () => {
    await delay(10);
    return HttpResponse.json(mockSettings);
  }),

  http.put(`${API_BASE}/api/settings`, async ({ request }) => {
    const updates = (await request.json()) as Partial<Settings>;
    const updatedSettings = { ...mockSettings, ...updates };

    await delay(10);
    return HttpResponse.json(updatedSettings);
  }),

  // Error simulation handlers (for testing error handling)
  http.get(`${API_BASE}/api/error/500`, () => {
    return HttpResponse.json(
      { detail: "Internal Server Error" },
      { status: 500 }
    );
  }),

  http.get(`${API_BASE}/api/error/401`, () => {
    return HttpResponse.json(
      { detail: "Unauthorized" },
      { status: 401 }
    );
  }),

  http.get(`${API_BASE}/api/error/network`, () => {
    return HttpResponse.error();
  }),
];

// Server setup helper
export function createTestServer() {
  // Dynamic import is required since msw/node is ESM
  return import("msw/node").then(({ setupServer }) => {
    return setupServer(...handlers);
  });
}
