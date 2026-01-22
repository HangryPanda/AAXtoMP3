/**
 * Tests for Select component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/Select";

describe("Select", () => {
  const renderSelect = (props: { onValueChange?: (value: string) => void; defaultValue?: string } = {}) => {
    return render(
      <Select onValueChange={props.onValueChange} defaultValue={props.defaultValue}>
        <SelectTrigger data-testid="select-trigger">
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="option1">Option 1</SelectItem>
          <SelectItem value="option2">Option 2</SelectItem>
          <SelectItem value="option3">Option 3</SelectItem>
        </SelectContent>
      </Select>
    );
  };

  it("should render select trigger", () => {
    renderSelect();
    const trigger = screen.getByTestId("select-trigger");
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveTextContent("Select an option");
  });

  it("should have proper ARIA role", () => {
    renderSelect();
    const trigger = screen.getByRole("combobox");
    expect(trigger).toBeInTheDocument();
  });

  it("should open dropdown on click", async () => {
    const user = userEvent.setup();
    renderSelect();

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByRole("listbox")).toBeInTheDocument();
    });
  });

  it("should show options when opened", async () => {
    const user = userEvent.setup();
    renderSelect();

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Option 1" })).toBeInTheDocument();
      expect(screen.getByRole("option", { name: "Option 2" })).toBeInTheDocument();
      expect(screen.getByRole("option", { name: "Option 3" })).toBeInTheDocument();
    });
  });

  it("should call onValueChange when option is selected", async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    renderSelect({ onValueChange: handleChange });

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByRole("listbox")).toBeInTheDocument();
    });

    const option = screen.getByRole("option", { name: "Option 2" });
    await user.click(option);

    expect(handleChange).toHaveBeenCalledWith("option2");
  });

  it("should display selected value", async () => {
    const user = userEvent.setup();
    renderSelect();

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByRole("listbox")).toBeInTheDocument();
    });

    const option = screen.getByRole("option", { name: "Option 1" });
    await user.click(option);

    await waitFor(() => {
      expect(trigger).toHaveTextContent("Option 1");
    });
  });

  it("should render with default value", () => {
    renderSelect({ defaultValue: "option2" });
    const trigger = screen.getByRole("combobox");
    expect(trigger).toHaveTextContent("Option 2");
  });

  it("should have proper styling on trigger", () => {
    renderSelect();
    const trigger = screen.getByTestId("select-trigger");
    expect(trigger).toHaveClass("flex");
    expect(trigger).toHaveClass("h-9");
    expect(trigger).toHaveClass("w-full");
    expect(trigger).toHaveClass("rounded-md");
    expect(trigger).toHaveClass("border");
  });
});
