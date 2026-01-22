/**
 * Tests for AppShell component
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppShell } from "@/components/layout/AppShell";

describe("AppShell", () => {
  it("should render children content", () => {
    render(
      <AppShell>
        <div data-testid="content">Main Content</div>
      </AppShell>
    );
    expect(screen.getByTestId("content")).toBeInTheDocument();
    expect(screen.getByText("Main Content")).toBeInTheDocument();
  });

  it("should render sidebar", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("should render header", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });

  it("should render player area", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );
    // Player area should have a specific role or test id
    expect(screen.getByTestId("player-area")).toBeInTheDocument();
  });

  it("should have proper layout structure", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );
    const shell = screen.getByTestId("app-shell");
    expect(shell).toHaveClass("flex");
    expect(shell).toHaveClass("h-screen");
  });

  it("should apply custom className", () => {
    render(
      <AppShell className="custom-shell">
        <div>Content</div>
      </AppShell>
    );
    const shell = screen.getByTestId("app-shell");
    expect(shell).toHaveClass("custom-shell");
  });

  it("should have main content area", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );
    expect(screen.getByRole("main")).toBeInTheDocument();
  });
});
