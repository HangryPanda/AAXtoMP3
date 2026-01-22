/**
 * Tests for Input component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Input } from "@/components/ui/Input";

describe("Input", () => {
  it("should render input", () => {
    render(<Input placeholder="Enter text" />);
    const input = screen.getByPlaceholderText("Enter text");
    expect(input).toBeInTheDocument();
  });

  it("should render with default styles", () => {
    render(<Input data-testid="input" />);
    const input = screen.getByTestId("input");
    expect(input).toHaveClass("flex");
    expect(input).toHaveClass("h-9");
    expect(input).toHaveClass("w-full");
    expect(input).toHaveClass("rounded-md");
    expect(input).toHaveClass("border");
  });

  it("should handle text input", async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();

    render(<Input onChange={handleChange} data-testid="input" />);
    const input = screen.getByTestId("input");

    await user.type(input, "Hello");
    expect(handleChange).toHaveBeenCalled();
    expect(input).toHaveValue("Hello");
  });

  it("should be disabled when disabled prop is true", () => {
    render(<Input disabled data-testid="input" />);
    const input = screen.getByTestId("input");
    expect(input).toBeDisabled();
  });

  it("should support different types", () => {
    const { rerender } = render(<Input type="text" data-testid="input" />);
    expect(screen.getByTestId("input")).toHaveAttribute("type", "text");

    rerender(<Input type="email" data-testid="input" />);
    expect(screen.getByTestId("input")).toHaveAttribute("type", "email");

    rerender(<Input type="password" data-testid="input" />);
    expect(screen.getByTestId("input")).toHaveAttribute("type", "password");

    rerender(<Input type="number" data-testid="input" />);
    expect(screen.getByTestId("input")).toHaveAttribute("type", "number");
  });

  it("should apply custom className", () => {
    render(<Input className="custom-input" data-testid="input" />);
    const input = screen.getByTestId("input");
    expect(input).toHaveClass("custom-input");
  });

  it("should support controlled value", () => {
    render(<Input value="controlled" onChange={() => {}} data-testid="input" />);
    const input = screen.getByTestId("input");
    expect(input).toHaveValue("controlled");
  });

  it("should support ref forwarding", () => {
    const ref = { current: null };
    render(<Input ref={ref} data-testid="input" />);
    expect(ref.current).toBeInstanceOf(HTMLInputElement);
  });

  it("should have focus styles", () => {
    render(<Input data-testid="input" />);
    const input = screen.getByTestId("input");
    expect(input).toHaveClass("focus-visible:outline-none");
    expect(input).toHaveClass("focus-visible:ring-1");
  });

  it("should pass through additional props", () => {
    render(
      <Input
        data-testid="input"
        aria-label="Test input"
        required
        maxLength={50}
      />
    );
    const input = screen.getByTestId("input");
    expect(input).toHaveAttribute("aria-label", "Test input");
    expect(input).toBeRequired();
    expect(input).toHaveAttribute("maxLength", "50");
  });
});
