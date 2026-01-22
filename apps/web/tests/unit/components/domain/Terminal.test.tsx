/**
 * Tests for Terminal component
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Terminal } from "@/components/domain/Terminal";

// Mock xterm since it requires DOM and canvas
vi.mock("@xterm/xterm", () => ({
  Terminal: vi.fn().mockImplementation(() => ({
    open: vi.fn(),
    write: vi.fn(),
    writeln: vi.fn(),
    clear: vi.fn(),
    dispose: vi.fn(),
    loadAddon: vi.fn(),
    onData: vi.fn(),
    onResize: vi.fn(),
    options: {},
  })),
}));

vi.mock("@xterm/addon-fit", () => ({
  FitAddon: vi.fn().mockImplementation(() => ({
    fit: vi.fn(),
    dispose: vi.fn(),
  })),
}));

vi.mock("@xterm/addon-search", () => ({
  SearchAddon: vi.fn().mockImplementation(() => ({
    findNext: vi.fn(),
    findPrevious: vi.fn(),
    dispose: vi.fn(),
  })),
}));

describe("Terminal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should render terminal container", () => {
    render(<Terminal />);
    expect(screen.getByTestId("terminal-container")).toBeInTheDocument();
  });

  it("should render terminal title when provided", () => {
    render(<Terminal title="Job Logs" />);
    expect(screen.getByText("Job Logs")).toBeInTheDocument();
  });

  it("should render search input", () => {
    render(<Terminal showSearch />);
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("should call onSearch when search input changes", async () => {
    const user = userEvent.setup();
    const handleSearch = vi.fn();

    render(<Terminal showSearch onSearch={handleSearch} />);

    const searchInput = screen.getByPlaceholderText(/search/i);
    await user.type(searchInput, "error");

    expect(handleSearch).toHaveBeenCalledWith("error");
  });

  it("should render clear button", () => {
    render(<Terminal showClearButton />);
    expect(screen.getByRole("button", { name: /clear/i })).toBeInTheDocument();
  });

  it("should call onClear when clear button is clicked", async () => {
    const user = userEvent.setup();
    const handleClear = vi.fn();

    render(<Terminal showClearButton onClear={handleClear} />);

    await user.click(screen.getByRole("button", { name: /clear/i }));

    expect(handleClear).toHaveBeenCalled();
  });

  it("should render with custom height", () => {
    render(<Terminal height={400} />);
    const container = screen.getByTestId("terminal-container");
    expect(container).toHaveStyle({ height: "400px" });
  });

  it("should render with default height when not specified", () => {
    render(<Terminal />);
    const container = screen.getByTestId("terminal-container");
    expect(container).toHaveStyle({ height: "300px" });
  });

  it("should apply custom className", () => {
    render(<Terminal className="custom-terminal" />);
    const container = screen.getByTestId("terminal-container");
    expect(container).toHaveClass("custom-terminal");
  });

  it("should render copy button", () => {
    render(<Terminal showCopyButton />);
    expect(screen.getByRole("button", { name: /copy/i })).toBeInTheDocument();
  });

  it("should call onCopy when copy button is clicked", async () => {
    const user = userEvent.setup();
    const handleCopy = vi.fn();

    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });

    render(<Terminal showCopyButton onCopy={handleCopy} />);

    await user.click(screen.getByRole("button", { name: /copy/i }));

    expect(handleCopy).toHaveBeenCalled();
  });

  it("should display loading state", () => {
    render(<Terminal loading />);
    expect(screen.getByTestId("terminal-loading")).toBeInTheDocument();
  });

  it("should not display loading when not loading", () => {
    render(<Terminal loading={false} />);
    expect(screen.queryByTestId("terminal-loading")).not.toBeInTheDocument();
  });

  it("should render find next/prev buttons when search is visible", () => {
    render(<Terminal showSearch />);
    expect(screen.getByRole("button", { name: /find next/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /find previous/i })).toBeInTheDocument();
  });

  it("should be accessible", () => {
    render(<Terminal title="Logs" />);
    const container = screen.getByTestId("terminal-container");
    expect(container).toHaveAttribute("role", "log");
    expect(container).toHaveAttribute("aria-label", "Logs");
  });
});
