/**
 * Tests for Dialog component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/Dialog";

describe("Dialog", () => {
  const renderDialog = (props: { open?: boolean; onOpenChange?: (open: boolean) => void } = {}) => {
    return render(
      <Dialog open={props.open} onOpenChange={props.onOpenChange}>
        <DialogTrigger asChild>
          <button>Open Dialog</button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Dialog Title</DialogTitle>
            <DialogDescription>Dialog description text</DialogDescription>
          </DialogHeader>
          <div>Dialog content</div>
          <DialogFooter>
            <DialogClose asChild>
              <button>Close</button>
            </DialogClose>
            <button>Confirm</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  };

  it("should render trigger button", () => {
    renderDialog();
    const trigger = screen.getByRole("button", { name: "Open Dialog" });
    expect(trigger).toBeInTheDocument();
  });

  it("should not show dialog content when closed", () => {
    renderDialog();
    expect(screen.queryByText("Dialog Title")).not.toBeInTheDocument();
  });

  it("should open dialog when trigger is clicked", async () => {
    const user = userEvent.setup();
    renderDialog();

    const trigger = screen.getByRole("button", { name: "Open Dialog" });
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText("Dialog Title")).toBeInTheDocument();
      expect(screen.getByText("Dialog description text")).toBeInTheDocument();
    });
  });

  it("should show dialog content when open prop is true", () => {
    renderDialog({ open: true });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Dialog Title")).toBeInTheDocument();
  });

  it("should call onOpenChange when dialog is closed", async () => {
    const user = userEvent.setup();
    const handleOpenChange = vi.fn();
    renderDialog({ open: true, onOpenChange: handleOpenChange });

    const closeButton = screen.getByRole("button", { name: "Close" });
    await user.click(closeButton);

    expect(handleOpenChange).toHaveBeenCalledWith(false);
  });

  it("should close when escape is pressed", async () => {
    const user = userEvent.setup();
    const handleOpenChange = vi.fn();
    renderDialog({ open: true, onOpenChange: handleOpenChange });

    await user.keyboard("{Escape}");

    expect(handleOpenChange).toHaveBeenCalledWith(false);
  });

  it("should render header, footer and content correctly", async () => {
    const user = userEvent.setup();
    renderDialog();

    const trigger = screen.getByRole("button", { name: "Open Dialog" });
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByText("Dialog Title")).toBeInTheDocument();
      expect(screen.getByText("Dialog description text")).toBeInTheDocument();
      expect(screen.getByText("Dialog content")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
    });
  });

  it("should have proper ARIA attributes", async () => {
    const user = userEvent.setup();
    renderDialog();

    const trigger = screen.getByRole("button", { name: "Open Dialog" });
    await user.click(trigger);

    await waitFor(() => {
      const dialog = screen.getByRole("dialog");
      expect(dialog).toHaveAttribute("aria-describedby");
      expect(dialog).toHaveAttribute("aria-labelledby");
    });
  });
});
