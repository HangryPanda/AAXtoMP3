/**
 * Tests for BookCard component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BookCard } from "@/components/domain/BookCard";
import type { Book } from "@/types";

const mockBook: Book = {
  asin: "B001234567",
  title: "The Great Adventure",
  subtitle: "A Journey Through Time",
  authors: [{ name: "John Smith" }],
  narrators: [{ name: "Jane Doe" }],
  series: [{ title: "Adventure Series", sequence: "1" }],
  runtime_length_min: 480,
  release_date: "2023-01-15",
  purchase_date: "2023-02-01",
  product_images: { "500": "https://example.com/cover.jpg" },
  aax_available: true,
  aaxc_available: false,
  status: "COMPLETED",
  local_path_converted: "/path/to/book.m4b",
  created_at: "2023-02-01T00:00:00Z",
  updated_at: "2023-02-15T00:00:00Z",
};

describe("BookCard", () => {
  it("should render book title", () => {
    render(<BookCard book={mockBook} />);
    expect(screen.getByText("The Great Adventure")).toBeInTheDocument();
  });

  it("should render author name", () => {
    render(<BookCard book={mockBook} />);
    expect(screen.getByText("John Smith")).toBeInTheDocument();
  });

  it("should render book cover", () => {
    render(<BookCard book={mockBook} />);
    const img = screen.getByRole("img", { name: /the great adventure/i });
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", expect.stringContaining("cover.jpg"));
  });

  it("should render formatted duration", () => {
    render(<BookCard book={mockBook} />);
    expect(screen.getByText("8h")).toBeInTheDocument();
  });

  it("should render status badge", () => {
    render(<BookCard book={mockBook} />);
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("should call onPlay when play button is clicked", async () => {
    const user = userEvent.setup();
    const handlePlay = vi.fn();
    render(<BookCard book={mockBook} onPlay={handlePlay} />);

    const playButton = screen.getByRole("button", { name: /play/i });
    await user.click(playButton);

    expect(handlePlay).toHaveBeenCalledWith(mockBook);
  });

  it("should call onAction when action menu is clicked", async () => {
    const user = userEvent.setup();
    const handleAction = vi.fn();
    render(<BookCard book={mockBook} onAction={handleAction} />);

    const menuButton = screen.getByRole("button", { name: /more actions/i });
    await user.click(menuButton);

    expect(screen.getByText("Download")).toBeInTheDocument();
    expect(screen.getByText("Convert")).toBeInTheDocument();
  });

  it("should disable play button when book cannot be played", () => {
    const newBook: Book = { ...mockBook, status: "NEW", local_path_converted: null };
    render(<BookCard book={newBook} />);

    const playButton = screen.getByRole("button", { name: /play/i });
    expect(playButton).toBeDisabled();
  });

  it("should display series info when available", () => {
    render(<BookCard book={mockBook} />);
    expect(screen.getByText(/adventure series/i)).toBeInTheDocument();
  });

  it("should handle missing cover image gracefully", () => {
    const bookWithoutCover: Book = { ...mockBook, product_images: null };
    render(<BookCard book={bookWithoutCover} />);
    expect(screen.getByTestId("book-cover-placeholder")).toBeInTheDocument();
  });

  it("should apply custom className", () => {
    render(<BookCard book={mockBook} className="custom-card" />);
    const card = screen.getByTestId("book-card");
    expect(card).toHaveClass("custom-card");
  });

  it("should be focusable for keyboard navigation", () => {
    render(<BookCard book={mockBook} />);
    const card = screen.getByTestId("book-card");
    expect(card).toHaveAttribute("tabIndex", "0");
  });
});
