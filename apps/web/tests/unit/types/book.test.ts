import { describe, it, expect } from "vitest";
import { canPlay, Book, BookStatus } from "@/types/book";

describe("canPlay", () => {
  const baseBook: Book = {
    asin: "TEST001",
    title: "Test Book",
    authors: [],
    narrators: [],
    series: null,
    runtime_length_min: 100,
    release_date: null,
    purchase_date: null,
    product_images: null,
    aax_available: true,
    aaxc_available: false,
    status: "NEW",
    created_at: "2024-01-01",
    updated_at: "2024-01-01",
  };

  it("should return true for COMPLETED book with converted path", () => {
    const book: Book = {
      ...baseBook,
      status: "COMPLETED",
      local_path_converted: "/path/to/book.m4b",
    };
    expect(canPlay(book)).toBe(true);
  });

  it("should return false for COMPLETED book missing converted path", () => {
    const book: Book = {
      ...baseBook,
      status: "COMPLETED",
      local_path_converted: null,
    };
    expect(canPlay(book)).toBe(false);
  });

  it("should return true for DOWNLOADED book with AAX path (JIT)", () => {
    const book: Book = {
      ...baseBook,
      status: "DOWNLOADED",
      local_path_aax: "/path/to/book.aax",
    };
    expect(canPlay(book)).toBe(true);
  });

  it("should return true for VALIDATED book with AAX path (JIT)", () => {
    const book: Book = {
      ...baseBook,
      status: "VALIDATED",
      local_path_aax: "/path/to/book.aax",
    };
    expect(canPlay(book)).toBe(true);
  });

  it("should return true for CONVERTING book with AAX path (JIT)", () => {
    const book: Book = {
      ...baseBook,
      status: "CONVERTING",
      local_path_aax: "/path/to/book.aax",
    };
    expect(canPlay(book)).toBe(true);
  });

  it("should return false for DOWNLOADED book missing AAX path", () => {
    const book: Book = {
      ...baseBook,
      status: "DOWNLOADED",
      local_path_aax: null,
    };
    expect(canPlay(book)).toBe(false);
  });

  it("should return false for NEW book", () => {
    const book: Book = {
      ...baseBook,
      status: "NEW",
    };
    expect(canPlay(book)).toBe(false);
  });

  it("should return false for DOWNLOADING book", () => {
    const book: Book = {
      ...baseBook,
      status: "DOWNLOADING",
    };
    expect(canPlay(book)).toBe(false);
  });

  it("should return false for FAILED book if no files exist", () => {
    const book: Book = {
      ...baseBook,
      status: "FAILED",
      local_path_aax: null,
      local_path_converted: null,
    };
    expect(canPlay(book)).toBe(false);
  });

  it("should return true for FAILED book if AAX file exists (JIT recovery)", () => {
    const book: Book = {
      ...baseBook,
      status: "FAILED",
      local_path_aax: "/path/to/book.aax",
    };
    expect(canPlay(book)).toBe(true);
  });
});
