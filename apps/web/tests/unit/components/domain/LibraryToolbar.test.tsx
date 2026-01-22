/**
 * Tests for LibraryToolbar component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LibraryToolbar } from "@/components/domain/LibraryToolbar";
import type { BookStatus } from "@/types";

describe("LibraryToolbar", () => {
  it("should render search input", () => {
    render(<LibraryToolbar />);
    expect(screen.getByRole("searchbox")).toBeInTheDocument();
  });

  it("should render filter dropdown", () => {
    render(<LibraryToolbar />);
    expect(screen.getByRole("combobox", { name: /filter/i })).toBeInTheDocument();
  });

  it("should render sort dropdown", () => {
    render(<LibraryToolbar />);
    expect(screen.getByRole("combobox", { name: /sort/i })).toBeInTheDocument();
  });

  it("should render view toggle buttons", () => {
    render(<LibraryToolbar />);
    expect(screen.getByRole("button", { name: /grid view/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /list view/i })).toBeInTheDocument();
  });

  it("should call onSearchChange with debounced value", async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const handleSearch = vi.fn();

    render(<LibraryToolbar onSearchChange={handleSearch} />);

    const searchInput = screen.getByRole("searchbox");
    await user.type(searchInput, "test");

    // Should not be called immediately (debounced)
    expect(handleSearch).not.toHaveBeenCalled();

    // Fast forward past debounce delay
    vi.advanceTimersByTime(300);

    expect(handleSearch).toHaveBeenCalledWith("test");
    vi.useRealTimers();
  });

  it("should call onFilterChange when filter is selected", async () => {
    const user = userEvent.setup();
    const handleFilter = vi.fn();

    render(<LibraryToolbar onFilterChange={handleFilter} />);

    const filterButton = screen.getByRole("combobox", { name: /filter/i });
    await user.click(filterButton);

    await waitFor(() => {
      expect(screen.getByRole("option", { name: /completed/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("option", { name: /completed/i }));

    expect(handleFilter).toHaveBeenCalledWith("COMPLETED" as BookStatus);
  });

  it("should call onSortChange when sort is selected", async () => {
    const user = userEvent.setup();
    const handleSort = vi.fn();

    render(<LibraryToolbar onSortChange={handleSort} />);

    const sortButton = screen.getByRole("combobox", { name: /sort/i });
    await user.click(sortButton);

    await waitFor(() => {
      expect(screen.getByRole("option", { name: /title/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("option", { name: /title/i }));

    expect(handleSort).toHaveBeenCalledWith("title", expect.any(String));
  });

  it("should call onViewChange when view is toggled", async () => {
    const user = userEvent.setup();
    const handleView = vi.fn();

    render(<LibraryToolbar viewMode="grid" onViewChange={handleView} />);

    const listButton = screen.getByRole("button", { name: /list view/i });
    await user.click(listButton);

    expect(handleView).toHaveBeenCalledWith("list");
  });

  it("should highlight current view mode", () => {
    render(<LibraryToolbar viewMode="grid" />);
    const gridButton = screen.getByRole("button", { name: /grid view/i });
    expect(gridButton).toHaveAttribute("aria-pressed", "true");
  });

  it("should show search value when controlled", () => {
    render(<LibraryToolbar searchValue="harry potter" />);
    const searchInput = screen.getByRole("searchbox");
    expect(searchInput).toHaveValue("harry potter");
  });

  it("should show selected filter value", () => {
    render(<LibraryToolbar filterValue="COMPLETED" />);
    const filterButton = screen.getByRole("combobox", { name: /filter/i });
    expect(filterButton).toHaveTextContent(/completed/i);
  });
});
