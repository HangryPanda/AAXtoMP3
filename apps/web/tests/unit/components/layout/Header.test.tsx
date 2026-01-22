/**
 * Tests for Header component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Header } from "@/components/layout/Header";

describe("Header", () => {
  it("should render header with banner role", () => {
    render(<Header title="My Library" />);
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });

  it("should display title", () => {
    render(<Header title="My Library" />);
    expect(screen.getByText("My Library")).toBeInTheDocument();
  });

  it("should render search input", () => {
    render(<Header title="Library" />);
    expect(screen.getByRole("searchbox")).toBeInTheDocument();
  });

  it("should call onSearch when search input changes", async () => {
    const user = userEvent.setup();
    const handleSearch = vi.fn();
    render(<Header title="Library" onSearch={handleSearch} />);

    const searchInput = screen.getByRole("searchbox");
    await user.type(searchInput, "harry potter");

    expect(handleSearch).toHaveBeenCalled();
  });

  it("should render action buttons", () => {
    render(
      <Header
        title="Library"
        actions={
          <>
            <button>Refresh</button>
            <button>Settings</button>
          </>
        }
      />
    );
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Settings" })).toBeInTheDocument();
  });

  it("should apply custom className", () => {
    render(<Header title="Library" className="custom-header" />);
    const header = screen.getByRole("banner");
    expect(header).toHaveClass("custom-header");
  });

  it("should show search value when controlled", () => {
    render(<Header title="Library" searchValue="test" onSearch={() => {}} />);
    const searchInput = screen.getByRole("searchbox");
    expect(searchInput).toHaveValue("test");
  });

  it("should have proper accessibility attributes", () => {
    render(<Header title="Library" />);
    const searchInput = screen.getByRole("searchbox");
    expect(searchInput).toHaveAttribute("aria-label");
  });

  it("should render subtitle when provided", () => {
    render(<Header title="Library" subtitle="1,234 books" />);
    expect(screen.getByText("1,234 books")).toBeInTheDocument();
  });

  it("should not render subtitle when not provided", () => {
    render(<Header title="Library" />);
    expect(screen.queryByTestId("header-subtitle")).not.toBeInTheDocument();
  });
});
