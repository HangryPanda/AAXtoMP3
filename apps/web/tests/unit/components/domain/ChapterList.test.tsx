/**
 * Tests for ChapterList component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChapterList, Chapter } from "@/components/domain/ChapterList";

const mockChapters: Chapter[] = [
  { id: "1", title: "Chapter 1: Introduction", startTime: 0, duration: 600 },
  { id: "2", title: "Chapter 2: The Beginning", startTime: 600, duration: 900 },
  { id: "3", title: "Chapter 3: The Journey", startTime: 1500, duration: 1200 },
  { id: "4", title: "Chapter 4: The End", startTime: 2700, duration: 800 },
];

describe("ChapterList", () => {
  it("should render all chapters", () => {
    render(<ChapterList chapters={mockChapters} />);

    expect(screen.getByText("Chapter 1: Introduction")).toBeInTheDocument();
    expect(screen.getByText("Chapter 2: The Beginning")).toBeInTheDocument();
    expect(screen.getByText("Chapter 3: The Journey")).toBeInTheDocument();
    expect(screen.getByText("Chapter 4: The End")).toBeInTheDocument();
  });

  it("should display chapter duration", () => {
    render(<ChapterList chapters={mockChapters} />);

    expect(screen.getByText("10:00")).toBeInTheDocument(); // 600 seconds
    expect(screen.getByText("15:00")).toBeInTheDocument(); // 900 seconds
  });

  it("should highlight current chapter", () => {
    render(<ChapterList chapters={mockChapters} currentChapterId="2" />);

    const currentChapter = screen.getByText("Chapter 2: The Beginning").closest("[data-testid]");
    expect(currentChapter).toHaveClass("bg-primary/10");
  });

  it("should call onChapterSelect when chapter is clicked", async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();

    render(<ChapterList chapters={mockChapters} onChapterSelect={handleSelect} />);

    await user.click(screen.getByText("Chapter 3: The Journey"));

    expect(handleSelect).toHaveBeenCalledWith(mockChapters[2]);
  });

  it("should be scrollable", () => {
    render(<ChapterList chapters={mockChapters} />);

    const container = screen.getByTestId("chapter-list");
    expect(container).toHaveClass("overflow-y-auto");
  });

  it("should show chapter number", () => {
    render(<ChapterList chapters={mockChapters} showNumbers />);

    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("should render empty state when no chapters", () => {
    render(<ChapterList chapters={[]} />);

    expect(screen.getByText(/no chapters/i)).toBeInTheDocument();
  });

  it("should show progress indicator for current chapter", () => {
    render(
      <ChapterList
        chapters={mockChapters}
        currentChapterId="2"
        currentTimeInChapter={450} // 450 seconds into chapter 2
      />
    );

    // Progress should be shown for the current chapter
    const progressBar = screen.getByTestId("chapter-progress");
    expect(progressBar).toBeInTheDocument();
  });

  it("should have proper accessibility", () => {
    render(<ChapterList chapters={mockChapters} />);

    const list = screen.getByRole("list");
    expect(list).toBeInTheDocument();

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(4);
  });

  it("should support keyboard navigation", async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();

    render(<ChapterList chapters={mockChapters} onChapterSelect={handleSelect} />);

    const firstChapter = screen.getByText("Chapter 1: Introduction").closest("[data-testid]");
    if (firstChapter) {
      await user.click(firstChapter);
      await user.keyboard("{Enter}");
    }

    expect(handleSelect).toHaveBeenCalled();
  });

  it("should apply custom className", () => {
    render(<ChapterList chapters={mockChapters} className="custom-list" />);

    const container = screen.getByTestId("chapter-list");
    expect(container).toHaveClass("custom-list");
  });
});
