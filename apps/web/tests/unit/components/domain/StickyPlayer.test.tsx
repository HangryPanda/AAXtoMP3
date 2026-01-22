/**
 * Tests for StickyPlayer component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StickyPlayer } from "@/components/domain/StickyPlayer";
import type { Book } from "@/types";

const mockBook: Book = {
  asin: "B001234567",
  title: "The Great Adventure",
  authors: [{ name: "John Smith" }],
  narrators: [{ name: "Jane Doe" }],
  series: null,
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

describe("StickyPlayer", () => {
  it("should render empty state when no book is playing", () => {
    render(<StickyPlayer />);
    expect(screen.getByText(/no track playing/i)).toBeInTheDocument();
  });

  it("should render book info when playing", () => {
    render(<StickyPlayer currentBook={mockBook} />);
    expect(screen.getByText("The Great Adventure")).toBeInTheDocument();
    expect(screen.getByText("John Smith")).toBeInTheDocument();
  });

  it("should render book cover when available", () => {
    render(<StickyPlayer currentBook={mockBook} />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", expect.stringContaining("cover.jpg"));
  });

  it("should render play button when paused", () => {
    render(<StickyPlayer currentBook={mockBook} isPlaying={false} />);
    expect(screen.getByRole("button", { name: /play/i })).toBeInTheDocument();
  });

  it("should render pause button when playing", () => {
    render(<StickyPlayer currentBook={mockBook} isPlaying={true} />);
    expect(screen.getByRole("button", { name: /pause/i })).toBeInTheDocument();
  });

  it("should call onPlayPause when play/pause is clicked", async () => {
    const user = userEvent.setup();
    const handlePlayPause = vi.fn();

    render(<StickyPlayer currentBook={mockBook} onPlayPause={handlePlayPause} />);

    await user.click(screen.getByRole("button", { name: /play/i }));
    expect(handlePlayPause).toHaveBeenCalled();
  });

  it("should render skip forward button", () => {
    render(<StickyPlayer currentBook={mockBook} />);
    expect(screen.getByRole("button", { name: /skip forward/i })).toBeInTheDocument();
  });

  it("should render skip back button", () => {
    render(<StickyPlayer currentBook={mockBook} />);
    expect(screen.getByRole("button", { name: /skip back/i })).toBeInTheDocument();
  });

  it("should call onSkipForward when skip forward is clicked", async () => {
    const user = userEvent.setup();
    const handleSkipForward = vi.fn();

    render(<StickyPlayer currentBook={mockBook} onSkipForward={handleSkipForward} />);

    await user.click(screen.getByRole("button", { name: /skip forward/i }));
    expect(handleSkipForward).toHaveBeenCalled();
  });

  it("should call onSkipBack when skip back is clicked", async () => {
    const user = userEvent.setup();
    const handleSkipBack = vi.fn();

    render(<StickyPlayer currentBook={mockBook} onSkipBack={handleSkipBack} />);

    await user.click(screen.getByRole("button", { name: /skip back/i }));
    expect(handleSkipBack).toHaveBeenCalled();
  });

  it("should render progress slider", () => {
    render(<StickyPlayer currentBook={mockBook} currentTime={120} duration={480} />);
    expect(screen.getByRole("slider")).toBeInTheDocument();
  });

  it("should display current time and duration", () => {
    render(<StickyPlayer currentBook={mockBook} currentTime={125} duration={480} />);
    expect(screen.getByText("2:05")).toBeInTheDocument();
    expect(screen.getByText("8:00")).toBeInTheDocument();
  });

  it("should call onSeek when slider is changed", async () => {
    const user = userEvent.setup();
    const handleSeek = vi.fn();

    render(<StickyPlayer currentBook={mockBook} currentTime={0} duration={480} onSeek={handleSeek} />);

    const slider = screen.getByRole("slider");
    await user.click(slider);
    await user.keyboard("{ArrowRight}");

    expect(handleSeek).toHaveBeenCalled();
  });

  it("should render volume control", () => {
    render(<StickyPlayer currentBook={mockBook} />);
    expect(screen.getByRole("button", { name: /volume/i })).toBeInTheDocument();
  });

  it("should render chapters button", () => {
    render(<StickyPlayer currentBook={mockBook} />);
    expect(screen.getByRole("button", { name: /chapters/i })).toBeInTheDocument();
  });

  it("should call onChaptersClick when chapters is clicked", async () => {
    const user = userEvent.setup();
    const handleChapters = vi.fn();

    render(<StickyPlayer currentBook={mockBook} onChaptersClick={handleChapters} />);

    await user.click(screen.getByRole("button", { name: /chapters/i }));
    expect(handleChapters).toHaveBeenCalled();
  });
});
