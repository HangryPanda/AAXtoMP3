/**
 * Tests for Progress component
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Progress } from "@/components/ui/Progress";

describe("Progress", () => {
  it("should render progress bar", () => {
    render(<Progress value={50} />);
    const progress = screen.getByRole("progressbar");
    expect(progress).toBeInTheDocument();
  });

  it("should set aria-valuenow correctly", () => {
    render(<Progress value={75} />);
    const progress = screen.getByRole("progressbar");
    expect(progress).toHaveAttribute("aria-valuenow", "75");
  });

  it("should handle 0% value", () => {
    render(<Progress value={0} />);
    const progress = screen.getByRole("progressbar");
    expect(progress).toHaveAttribute("aria-valuenow", "0");
  });

  it("should handle 100% value", () => {
    render(<Progress value={100} />);
    const progress = screen.getByRole("progressbar");
    expect(progress).toHaveAttribute("aria-valuenow", "100");
  });

  it("should handle undefined value (indeterminate)", () => {
    render(<Progress />);
    const progress = screen.getByRole("progressbar");
    expect(progress).toBeInTheDocument();
  });

  it("should apply custom className", () => {
    render(<Progress value={50} className="custom-progress" />);
    const progress = screen.getByRole("progressbar");
    expect(progress).toHaveClass("custom-progress");
  });

  it("should have min and max aria attributes", () => {
    render(<Progress value={50} />);
    const progress = screen.getByRole("progressbar");
    expect(progress).toHaveAttribute("aria-valuemin", "0");
    expect(progress).toHaveAttribute("aria-valuemax", "100");
  });
});
