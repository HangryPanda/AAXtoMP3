/**
 * IndexedDB Setup with Dexie
 * Client-side caching for books and playback progress
 */

import Dexie, { type EntityTable } from "dexie";
import type { Book, BookStatus } from "@/types";

/**
 * Playback progress record
 */
export interface PlaybackProgress {
  asin: string;
  currentTime: number;
  duration: number;
  lastPlayedAt: string;
  completed: boolean;
}

/**
 * Cached book with sync metadata
 */
export interface CachedBook extends Book {
  syncedAt: string;
}

/**
 * Filter options for querying books
 */
export interface BookFilterOptions {
  status?: BookStatus;
  search?: string;
  authors?: string;
  limit?: number;
  offset?: number;
}

/**
 * Database schema
 */
class AudioLibraryDB extends Dexie {
  books!: EntityTable<CachedBook, "asin">;
  playbackProgress!: EntityTable<PlaybackProgress, "asin">;

  constructor() {
    super("AudioLibraryDB");

    this.version(1).stores({
      // Books table with indexes for common queries
      books: "asin, status, title, *authors, updated_at, syncedAt",
      // Playback progress table
      playbackProgress: "asin, lastPlayedAt",
    });
  }
}

// Create singleton database instance
let dbInstance: AudioLibraryDB | null = null;

/**
 * Get the database instance (singleton)
 */
export function getDB(): AudioLibraryDB {
  if (typeof window === "undefined") {
    throw new Error("IndexedDB is only available in the browser");
  }

  if (!dbInstance) {
    dbInstance = new AudioLibraryDB();
  }

  return dbInstance;
}

/**
 * Check if database is available
 */
export function isDBAvailable(): boolean {
  return typeof window !== "undefined" && "indexedDB" in window;
}

// ============ Book Operations ============

/**
 * Get all books with optional filtering
 */
export async function getAllBooks(options?: BookFilterOptions): Promise<CachedBook[]> {
  const db = getDB();
  let collection = db.books.toCollection();

  // Apply status filter
  if (options?.status) {
    collection = db.books.where("status").equals(options.status);
  }

  let books = await collection.toArray();

  // Apply search filter (client-side)
  if (options?.search) {
    const searchLower = options.search.toLowerCase();
    books = books.filter(
      (book) =>
        book.title.toLowerCase().includes(searchLower) ||
        book.authors.some((a) => a.name.toLowerCase().includes(searchLower))
    );
  }

  // Apply author filter
  if (options?.authors) {
    const authorLower = options.authors.toLowerCase();
    books = books.filter((book) =>
      book.authors.some((a) => a.name.toLowerCase().includes(authorLower))
    );
  }

  // Sort by title by default
  books.sort((a, b) => a.title.localeCompare(b.title));

  // Apply pagination
  if (options?.offset !== undefined) {
    books = books.slice(options.offset);
  }
  if (options?.limit !== undefined) {
    books = books.slice(0, options.limit);
  }

  return books;
}

/**
 * Bulk put books into the database
 */
export async function bulkPutBooks(books: Book[]): Promise<void> {
  const db = getDB();
  const syncedAt = new Date().toISOString();

  const cachedBooks: CachedBook[] = books.map((book) => ({
    ...book,
    syncedAt,
  }));

  await db.books.bulkPut(cachedBooks);
}

/**
 * Get a book by ASIN
 */
export async function getBookByAsin(asin: string): Promise<CachedBook | undefined> {
  const db = getDB();
  return db.books.get(asin);
}

/**
 * Update a book's status
 */
export async function updateBookStatus(
  asin: string,
  status: BookStatus,
  additionalFields?: Partial<CachedBook>
): Promise<void> {
  const db = getDB();
  await db.books.update(asin, {
    status,
    updated_at: new Date().toISOString(),
    ...additionalFields,
  });
}

/**
 * Delete a book from the cache
 */
export async function deleteBook(asin: string): Promise<void> {
  const db = getDB();
  await db.books.delete(asin);
}

/**
 * Clear all books from the cache
 */
export async function clearAllBooks(): Promise<void> {
  const db = getDB();
  await db.books.clear();
}

/**
 * Get books count
 */
export async function getBooksCount(status?: BookStatus): Promise<number> {
  const db = getDB();
  if (status) {
    return db.books.where("status").equals(status).count();
  }
  return db.books.count();
}

/**
 * Get the last sync time
 */
export async function getLastSyncTime(): Promise<Date | null> {
  const db = getDB();
  const book = await db.books.orderBy("syncedAt").last();
  return book ? new Date(book.syncedAt) : null;
}

// ============ Playback Progress Operations ============

/**
 * Save playback progress for a book
 */
export async function saveProgress(
  asin: string,
  currentTime: number,
  duration: number
): Promise<void> {
  const db = getDB();
  await db.playbackProgress.put({
    asin,
    currentTime,
    duration,
    lastPlayedAt: new Date().toISOString(),
    completed: currentTime >= duration * 0.95, // Consider complete at 95%
  });
}

/**
 * Get playback progress for a book
 */
export async function getProgress(asin: string): Promise<PlaybackProgress | undefined> {
  const db = getDB();
  return db.playbackProgress.get(asin);
}

/**
 * Get recently played books (sorted by lastPlayedAt)
 */
export async function getRecentlyPlayed(limit = 10): Promise<PlaybackProgress[]> {
  const db = getDB();
  return db.playbackProgress
    .orderBy("lastPlayedAt")
    .reverse()
    .limit(limit)
    .toArray();
}

/**
 * Delete playback progress for a book
 */
export async function deleteProgress(asin: string): Promise<void> {
  const db = getDB();
  await db.playbackProgress.delete(asin);
}

/**
 * Clear all playback progress
 */
export async function clearAllProgress(): Promise<void> {
  const db = getDB();
  await db.playbackProgress.clear();
}

// ============ Utility Functions ============

/**
 * Export all data (for backup)
 */
export async function exportData(): Promise<{
  books: CachedBook[];
  progress: PlaybackProgress[];
}> {
  const db = getDB();
  const [books, progress] = await Promise.all([
    db.books.toArray(),
    db.playbackProgress.toArray(),
  ]);

  return { books, progress };
}

/**
 * Import data (for restore)
 */
export async function importData(data: {
  books?: CachedBook[];
  progress?: PlaybackProgress[];
}): Promise<void> {
  const db = getDB();

  await db.transaction("rw", [db.books, db.playbackProgress], async () => {
    if (data.books?.length) {
      await db.books.bulkPut(data.books);
    }
    if (data.progress?.length) {
      await db.playbackProgress.bulkPut(data.progress);
    }
  });
}

/**
 * Close the database connection
 */
export function closeDB(): void {
  if (dbInstance) {
    dbInstance.close();
    dbInstance = null;
  }
}
