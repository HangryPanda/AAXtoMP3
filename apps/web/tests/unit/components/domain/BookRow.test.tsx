/**
 * Tests for BookRow component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BookRow } from "@/components/domain/BookRow";
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

describe("BookRow", () => {
  it("should render book title", () => {
    render(<BookRow book={mockBook} />);
    expect(screen.getByText("The Great Adventure")).toBeInTheDocument();
  });

  it("should render author name", () => {
    render(<BookRow book={mockBook} />);
    expect(screen.getByText("John Smith")).toBeInTheDocument();
  });

  it("should render narrator name", () => {
    render(<BookRow book={mockBook} />);
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
  });

  it("should render formatted duration", () => {
    render(<BookRow book={mockBook} />);
    expect(screen.getByText("8h")).toBeInTheDocument();
  });

  it("should render status badge", () => {
    render(<BookRow book={mockBook} />);
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("should render small cover thumbnail", () => {
    render(<BookRow book={mockBook} />);
    const img = screen.getByRole("img");
    expect(img).toHaveClass("h-12");
    expect(img).toHaveClass("w-12");
  });

  it("should call onPlay when play button is clicked", async () => {
    const user = userEvent.setup();
    const handlePlay = vi.fn();
    render(<BookRow book={mockBook} onPlay={handlePlay} />);

    const playButton = screen.getByRole("button", { name: /play/i });
    await user.click(playButton);

    expect(handlePlay).toHaveBeenCalledWith(mockBook);
  });

  it("should call onRowClick when row is clicked", async () => {
    const user = userEvent.setup();
    const handleRowClick = vi.fn();
    render(<BookRow book={mockBook} onRowClick={handleRowClick} />);

    const row = screen.getByTestId("book-row");
    await user.click(row);

    expect(handleRowClick).toHaveBeenCalledWith(mockBook);
  });

  it("should highlight row on hover", () => {
    render(<BookRow book={mockBook} />);
    const row = screen.getByTestId("book-row");
    expect(row).toHaveClass("hover:bg-accent");
  });

  it("should show purchase date", () => {
    render(<BookRow book={mockBook} />);
    expect(screen.getByText(/Feb 1, 2023/i)).toBeInTheDocument();
  });

  it("should be selectable", async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();
    render(<BookRow book={mockBook} onSelect={handleSelect} selectable />);

    const checkbox = screen.getByRole("checkbox");
    await user.click(checkbox);

    expect(handleSelect).toHaveBeenCalledWith(mockBook, true);
  });

  it("should apply selected styles when selected", () => {
    render(<BookRow book={mockBook} selected selectable />);
    const row = screen.getByTestId("book-row");
    expect(row).toHaveClass("bg-primary/5");
  });
});
