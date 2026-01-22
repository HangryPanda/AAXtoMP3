/**
 * Tests for JobDrawer component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { JobDrawer } from "@/components/domain/JobDrawer";
import type { Job } from "@/types";

const mockJobs: Job[] = [
  {
    id: "job-1",
    task_type: "DOWNLOAD",
    book_asin: "B001",
    status: "RUNNING",
    progress_percent: 45,
    log_file_path: null,
    error_message: null,
    started_at: "2023-01-01T10:00:00Z",
    completed_at: null,
    created_at: "2023-01-01T09:55:00Z",
  },
  {
    id: "job-2",
    task_type: "CONVERT",
    book_asin: "B002",
    status: "QUEUED",
    progress_percent: 0,
    log_file_path: null,
    error_message: null,
    started_at: null,
    completed_at: null,
    created_at: "2023-01-01T10:00:00Z",
  },
  {
    id: "job-3",
    task_type: "DOWNLOAD",
    book_asin: "B003",
    status: "COMPLETED",
    progress_percent: 100,
    log_file_path: "/path/to/log",
    error_message: null,
    started_at: "2023-01-01T09:00:00Z",
    completed_at: "2023-01-01T09:30:00Z",
    created_at: "2023-01-01T08:55:00Z",
  },
];

describe("JobDrawer", () => {
  it("should not render when closed", () => {
    render(<JobDrawer open={false} jobs={mockJobs} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("should render when open", () => {
    render(<JobDrawer open={true} jobs={mockJobs} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("should display drawer title", () => {
    render(<JobDrawer open={true} jobs={mockJobs} />);
    expect(screen.getByText(/jobs/i)).toBeInTheDocument();
  });

  it("should render all jobs", () => {
    render(<JobDrawer open={true} jobs={mockJobs} />);

    expect(screen.getByText(/job-1/i)).toBeInTheDocument();
    expect(screen.getByText(/job-2/i)).toBeInTheDocument();
    expect(screen.getByText(/job-3/i)).toBeInTheDocument();
  });

  it("should show job type", () => {
    render(<JobDrawer open={true} jobs={mockJobs} />);

    const downloadJobs = screen.getAllByText(/download/i);
    expect(downloadJobs.length).toBeGreaterThan(0);

    expect(screen.getByText(/convert/i)).toBeInTheDocument();
  });

  it("should show job status", () => {
    render(<JobDrawer open={true} jobs={mockJobs} />);

    expect(screen.getByText(/running/i)).toBeInTheDocument();
    expect(screen.getByText(/queued/i)).toBeInTheDocument();
    expect(screen.getByText(/completed/i)).toBeInTheDocument();
  });

  it("should show progress for running jobs", () => {
    render(<JobDrawer open={true} jobs={mockJobs} />);

    const progressBar = screen.getByRole("progressbar");
    expect(progressBar).toHaveAttribute("aria-valuenow", "45");
  });

  it("should call onClose when close button is clicked", async () => {
    const user = userEvent.setup();
    const handleClose = vi.fn();

    render(<JobDrawer open={true} jobs={mockJobs} onClose={handleClose} />);

    const closeButton = screen.getByRole("button", { name: /close/i });
    await user.click(closeButton);

    expect(handleClose).toHaveBeenCalled();
  });

  it("should call onCancelJob when cancel button is clicked", async () => {
    const user = userEvent.setup();
    const handleCancel = vi.fn();

    render(<JobDrawer open={true} jobs={mockJobs} onCancelJob={handleCancel} />);

    // Only RUNNING or QUEUED jobs should have cancel button
    const cancelButtons = screen.getAllByRole("button", { name: /cancel/i });
    await user.click(cancelButtons[0]);

    expect(handleCancel).toHaveBeenCalledWith(expect.objectContaining({ id: "job-1" }));
  });

  it("should not show cancel for completed jobs", () => {
    render(
      <JobDrawer
        open={true}
        jobs={[{ ...mockJobs[2], status: "COMPLETED" }]}
      />
    );

    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
  });

  it("should call onViewLogs when view logs is clicked", async () => {
    const user = userEvent.setup();
    const handleViewLogs = vi.fn();

    render(
      <JobDrawer
        open={true}
        jobs={[mockJobs[0]]}
        onViewLogs={handleViewLogs}
      />
    );

    const viewLogsButton = screen.getByRole("button", { name: /logs/i });
    await user.click(viewLogsButton);

    expect(handleViewLogs).toHaveBeenCalledWith(mockJobs[0]);
  });

  it("should show empty state when no jobs", () => {
    render(<JobDrawer open={true} jobs={[]} />);

    expect(screen.getByText(/no jobs/i)).toBeInTheDocument();
  });

  it("should show job duration for completed jobs", () => {
    render(<JobDrawer open={true} jobs={mockJobs} />);

    // Job 3 has started_at and completed_at
    expect(screen.getByText(/30m/i)).toBeInTheDocument();
  });

  it("should close on escape key", async () => {
    const user = userEvent.setup();
    const handleClose = vi.fn();

    render(<JobDrawer open={true} jobs={mockJobs} onClose={handleClose} />);

    await user.keyboard("{Escape}");

    expect(handleClose).toHaveBeenCalled();
  });
});
