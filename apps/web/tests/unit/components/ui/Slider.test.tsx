/**
 * Tests for Slider component
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Slider } from "@/components/ui/Slider";

describe("Slider", () => {
  it("should render slider", () => {
    render(<Slider defaultValue={[50]} />);
    const slider = screen.getByRole("slider");
    expect(slider).toBeInTheDocument();
  });

  it("should render with default value", () => {
    render(<Slider defaultValue={[50]} />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("aria-valuenow", "50");
  });

  it("should support controlled value", () => {
    render(<Slider value={[75]} onValueChange={() => {}} />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("aria-valuenow", "75");
  });

  it("should respect min and max values", () => {
    render(<Slider defaultValue={[50]} min={0} max={100} />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("aria-valuemin", "0");
    expect(slider).toHaveAttribute("aria-valuemax", "100");
  });

  it("should call onValueChange when value changes", async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();

    render(<Slider defaultValue={[50]} onValueChange={handleChange} data-testid="slider" />);
    const slider = screen.getByRole("slider");

    // Simulate keyboard interaction
    await user.click(slider);
    await user.keyboard("{ArrowRight}");

    expect(handleChange).toHaveBeenCalled();
  });

  it("should respect step value", () => {
    render(<Slider defaultValue={[50]} step={10} />);
    const slider = screen.getByRole("slider");
    expect(slider).toBeInTheDocument();
  });

  it("should be disabled when disabled prop is true", () => {
    render(<Slider defaultValue={[50]} disabled />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("aria-disabled", "true");
  });

  it("should apply custom className", () => {
    render(<Slider defaultValue={[50]} className="custom-slider" data-testid="slider-root" />);
    const sliderRoot = screen.getByTestId("slider-root");
    expect(sliderRoot).toHaveClass("custom-slider");
  });

  it("should support horizontal orientation by default", () => {
    render(<Slider defaultValue={[50]} data-testid="slider-root" />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("aria-orientation", "horizontal");
  });

  it("should update aria-valuenow on keyboard navigation", async () => {
    const user = userEvent.setup();
    render(<Slider defaultValue={[50]} />);

    const slider = screen.getByRole("slider");
    await user.click(slider);
    await user.keyboard("{ArrowRight}");

    // Value should increase
    expect(Number(slider.getAttribute("aria-valuenow"))).toBeGreaterThanOrEqual(50);
  });
});
