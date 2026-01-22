/**
 * Tests for StatusBadge component
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "@/components/domain/StatusBadge";
import type { BookStatus } from "@/types";

describe("StatusBadge", () => {
  it.each<[BookStatus, string]>([
    ["NEW", "Cloud"],
    ["DOWNLOADING", "Downloading"],
    ["DOWNLOADED", "Downloaded"],
    ["VALIDATING", "Validating"],
    ["VALIDATED", "Validated"],
    ["CONVERTING", "Converting"],
    ["COMPLETED", "Ready"],
    ["FAILED", "Failed"],
  ])("should render correct label for status %s", (status, expectedLabel) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(expectedLabel)).toBeInTheDocument();
  });

  it("should render NEW status with gray color", () => {
    render(<StatusBadge status="NEW" />);
    const badge = screen.getByText("Cloud");
    expect(badge).toHaveClass("bg-gray-500");
  });

  it("should render DOWNLOADING status with blue color", () => {
    render(<StatusBadge status="DOWNLOADING" />);
    const badge = screen.getByText("Downloading");
    expect(badge).toHaveClass("bg-blue-500");
  });

  it("should render COMPLETED status with green color", () => {
    render(<StatusBadge status="COMPLETED" />);
    const badge = screen.getByText("Ready");
    expect(badge).toHaveClass("bg-green-500");
  });

  it("should render FAILED status with red color", () => {
    render(<StatusBadge status="FAILED" />);
    const badge = screen.getByText("Failed");
    expect(badge).toHaveClass("bg-red-500");
  });

  it("should render CONVERTING status with yellow color", () => {
    render(<StatusBadge status="CONVERTING" />);
    const badge = screen.getByText("Converting");
    expect(badge).toHaveClass("bg-yellow-500");
  });

  it("should apply custom className", () => {
    render(<StatusBadge status="NEW" className="custom-class" />);
    const badge = screen.getByText("Cloud");
    expect(badge).toHaveClass("custom-class");
  });

  it("should show icon when showIcon is true", () => {
    render(<StatusBadge status="DOWNLOADING" showIcon />);
    expect(screen.getByTestId("status-icon")).toBeInTheDocument();
  });

  it("should not show icon by default", () => {
    render(<StatusBadge status="DOWNLOADING" />);
    expect(screen.queryByTestId("status-icon")).not.toBeInTheDocument();
  });
});
