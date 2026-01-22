/**
 * Tests for ActionMenu component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ActionMenu } from "@/components/domain/ActionMenu";
import type { Book } from "@/types";

const createMockBook = (overrides: Partial<Book> = {}): Book => ({
  asin: "B001234567",
  title: "Test Book",
  authors: [{ name: "Author" }],
  narrators: [{ name: "Narrator" }],
  series: null,
  runtime_length_min: 300,
  release_date: "2023-01-01",
  purchase_date: "2023-01-01",
  product_images: null,
  aax_available: true,
  aaxc_available: false,
  status: "NEW",
  created_at: "2023-01-01T00:00:00Z",
  updated_at: "2023-01-01T00:00:00Z",
  ...overrides,
});

describe("ActionMenu", () => {
  it("should render menu trigger button", () => {
    render(<ActionMenu book={createMockBook()} />);
    expect(screen.getByRole("button", { name: /actions/i })).toBeInTheDocument();
  });

  it("should open menu on click", async () => {
    const user = userEvent.setup();
    render(<ActionMenu book={createMockBook()} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));

    await waitFor(() => {
      expect(screen.getByRole("menu")).toBeInTheDocument();
    });
  });

  it("should show Download option for NEW books", async () => {
    const user = userEvent.setup();
    render(<ActionMenu book={createMockBook({ status: "NEW" })} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));

    await waitFor(() => {
      expect(screen.getByRole("menuitem", { name: /download/i })).toBeInTheDocument();
    });
  });

  it("should show Convert option for DOWNLOADED books", async () => {
    const user = userEvent.setup();
    render(<ActionMenu book={createMockBook({ status: "DOWNLOADED" })} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));

    await waitFor(() => {
      expect(screen.getByRole("menuitem", { name: /convert/i })).toBeInTheDocument();
    });
  });

  it("should show Play option for COMPLETED books", async () => {
    const user = userEvent.setup();
    render(<ActionMenu book={createMockBook({ status: "COMPLETED", local_path_converted: "/path/to/file.m4b" })} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));

    await waitFor(() => {
      expect(screen.getByRole("menuitem", { name: /play/i })).toBeInTheDocument();
    });
  });

  it("should call onDownload when Download is clicked", async () => {
    const user = userEvent.setup();
    const handleDownload = vi.fn();
    const book = createMockBook({ status: "NEW" });

    render(<ActionMenu book={book} onDownload={handleDownload} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));

    await waitFor(() => {
      expect(screen.getByRole("menuitem", { name: /download/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("menuitem", { name: /download/i }));

    expect(handleDownload).toHaveBeenCalledWith(book);
  });

  it("should call onConvert when Convert is clicked", async () => {
    const user = userEvent.setup();
    const handleConvert = vi.fn();
    const book = createMockBook({ status: "DOWNLOADED" });

    render(<ActionMenu book={book} onConvert={handleConvert} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));

    await waitFor(() => {
      expect(screen.getByRole("menuitem", { name: /convert/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("menuitem", { name: /convert/i }));

    expect(handleConvert).toHaveBeenCalledWith(book);
  });

  it("should call onPlay when Play is clicked", async () => {
    const user = userEvent.setup();
    const handlePlay = vi.fn();
    const book = createMockBook({ status: "COMPLETED", local_path_converted: "/path/to/file.m4b" });

    render(<ActionMenu book={book} onPlay={handlePlay} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));

    await waitFor(() => {
      expect(screen.getByRole("menuitem", { name: /play/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("menuitem", { name: /play/i }));

    expect(handlePlay).toHaveBeenCalledWith(book);
  });

  it("should disable Download for books being downloaded", async () => {
    const user = userEvent.setup();
    render(<ActionMenu book={createMockBook({ status: "DOWNLOADING" })} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));

    await waitFor(() => {
      const downloadItem = screen.queryByRole("menuitem", { name: /download/i });
      // Download should not be available for DOWNLOADING status
      expect(downloadItem).not.toBeInTheDocument();
    });
  });

  it("should show View Details option", async () => {
    const user = userEvent.setup();
    render(<ActionMenu book={createMockBook()} />);

    await user.click(screen.getByRole("button", { name: /actions/i }));

    await waitFor(() => {
      expect(screen.getByRole("menuitem", { name: /view details/i })).toBeInTheDocument();
    });
  });
});
