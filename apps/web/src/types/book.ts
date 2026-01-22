/**
 * Book-related type definitions
 */

export type BookStatus =
  | "NEW"
  | "DOWNLOADING"
  | "DOWNLOADED"
  | "VALIDATING"
  | "VALIDATED"
  | "CONVERTING"
  | "COMPLETED"
  | "FAILED";

export interface Author {
  asin?: string;
  name: string;
}

export interface Narrator {
  name: string;
}

export interface Series {
  asin?: string;
  title: string;
  sequence?: string;
}

export interface Chapter {
  title: string;
  length_ms: number;
  start_offset_ms: number;
}

export interface ProductImages {
  [key: string]: string;
}

export interface Book {
  asin: string;
  title: string;
  subtitle?: string | null;
  authors: Author[];
  narrators: Narrator[];
  series: Series[] | null;
  chapters?: Chapter[];
  runtime_length_min: number;
  release_date: string | null;
  purchase_date: string | null;
  product_images: ProductImages | null;
  publisher?: string | null;
  language?: string | null;
  format_type?: string | null;
  aax_available: boolean;
  aaxc_available: boolean;
  status: BookStatus;
  local_path_aax?: string | null;
  local_path_voucher?: string | null;
  local_path_cover?: string | null;
  local_path_converted?: string | null;
  conversion_format?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BookListParams {
  page?: number;
  page_size?: number;
  status?: BookStatus;
  search?: string;
  series_title?: string;
  has_local?: boolean;
  sort_by?: "title" | "purchase_date" | "runtime_length_min" | "created_at";
  sort_order?: "asc" | "desc";
  since?: string;
}

export interface PaginatedBooks {
  items: Book[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SeriesOption {
  title: string;
  asin?: string | null;
  count: number;
}

export interface SeriesOptionsResponse {
  items: SeriesOption[];
  no_series_count: number;
}

export interface LibrarySyncStatus {
  last_sync_completed_at: string | null;
  last_sync_job_id: string | null;
  total_books: number;
}

export interface LocalItem {
  id: string;
  asin: string | null;
  title: string;
  authors: string | null;
  output_path: string;
  cover_path: string | null;
  format: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedLocalItems {
  items: LocalItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface RepairPreview {
  remote_total: number;
  downloaded_total: number;
  converted_total: number;
  converted_of_downloaded: number;
  orphan_downloads: number;
  orphan_conversions: number;
  missing_files: number;
  duplicate_conversions: number;
  generated_at: string;
}

// Status color mapping for UI
export const STATUS_COLORS: Record<BookStatus, string> = {
  NEW: "gray",
  DOWNLOADING: "blue",
  DOWNLOADED: "cyan",
  VALIDATING: "purple",
  VALIDATED: "indigo",
  CONVERTING: "yellow",
  COMPLETED: "green",
  FAILED: "red",
};

// Status display labels
export const STATUS_LABELS: Record<BookStatus, string> = {
  NEW: "Cloud",
  DOWNLOADING: "Downloading",
  DOWNLOADED: "Downloaded",
  VALIDATING: "Validating",
  VALIDATED: "Validated",
  CONVERTING: "Converting",
  COMPLETED: "Ready",
  FAILED: "Failed",
};

// Helper to check if a book can be downloaded
export function canDownload(book: Book): boolean {
  return (
    book.status === "NEW" ||
    book.status === "FAILED"
  );
}

// Helper to check if a book can be converted
export function canConvert(book: Book): boolean {
  return (
    book.status === "DOWNLOADED" ||
    book.status === "VALIDATED" ||
    book.status === "FAILED"
  );
}

// Helper to check if a book can be played
export function canPlay(book: Book): boolean {
  return book.status === "COMPLETED" && !!book.local_path_converted;
}

// Helper to format runtime
export function formatRuntime(minutes: number): string {
  if (minutes < 60) {
    return `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

// Helper to get cover image URL
export function getCoverUrl(book: Book, size: string = "500"): string | null {
  if (!book.product_images) return null;
  return book.product_images[size] || Object.values(book.product_images)[0] || null;
}

// Helper to get primary author name
export function getPrimaryAuthor(book: Book): string {
  if (!book.authors || book.authors.length === 0) return "Unknown Author";
  return book.authors[0]?.name || "Unknown Author";
}

// Helper to get primary narrator name
export function getPrimaryNarrator(book: Book): string {
  if (!book.narrators || book.narrators.length === 0) return "Unknown Narrator";
  return book.narrators[0]?.name || "Unknown Narrator";
}

// Helper to get series info string
export function getSeriesInfo(book: Book): string | null {
  if (!book.series || book.series.length === 0) return null;
  const primary = book.series[0];
  return primary.sequence
    ? `${primary.title}, Book ${primary.sequence}`
    : primary.title;
}
