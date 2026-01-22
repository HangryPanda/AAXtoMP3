/**
 * Tests for Sidebar component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sidebar } from "@/components/layout/Sidebar";

describe("Sidebar", () => {
  it("should render navigation", () => {
    render(<Sidebar />);
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("should render navigation links", () => {
    render(<Sidebar />);
    expect(screen.getByRole("link", { name: /library/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /settings/i })).toBeInTheDocument();
  });

  it("should have active state for current page", () => {
    render(<Sidebar activePath="/library" />);
    const libraryLink = screen.getByRole("link", { name: /library/i });
    expect(libraryLink).toHaveAttribute("aria-current", "page");
  });

  it("should show job indicator when jobs are active", () => {
    render(<Sidebar activeJobCount={3} />);
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("should not show job indicator when no jobs", () => {
    render(<Sidebar activeJobCount={0} />);
    expect(screen.queryByTestId("job-indicator")).not.toBeInTheDocument();
  });

  it("should call onJobsClick when jobs button is clicked", async () => {
    const user = userEvent.setup();
    const handleJobsClick = vi.fn();
    render(<Sidebar activeJobCount={2} onJobsClick={handleJobsClick} />);

    const jobsButton = screen.getByRole("button", { name: /jobs/i });
    await user.click(jobsButton);

    expect(handleJobsClick).toHaveBeenCalledTimes(1);
  });

  it("should apply custom className", () => {
    render(<Sidebar className="custom-sidebar" />);
    const nav = screen.getByRole("navigation");
    expect(nav).toHaveClass("custom-sidebar");
  });

  it("should have proper semantic structure", () => {
    render(<Sidebar />);
    const nav = screen.getByRole("navigation");
    expect(nav).toHaveAttribute("aria-label");
  });

  it("should render logo or brand", () => {
    render(<Sidebar />);
    expect(screen.getByTestId("sidebar-logo")).toBeInTheDocument();
  });

  it("should collapse when collapsed prop is true", () => {
    render(<Sidebar collapsed />);
    const nav = screen.getByRole("navigation");
    expect(nav).toHaveClass("w-16");
  });

  it("should expand when collapsed prop is false", () => {
    render(<Sidebar collapsed={false} />);
    const nav = screen.getByRole("navigation");
    expect(nav).toHaveClass("w-64");
  });
});
