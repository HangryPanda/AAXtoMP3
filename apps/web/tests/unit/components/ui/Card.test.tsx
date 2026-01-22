/**
 * Tests for Card components
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/Card";

describe("Card", () => {
  it("should render card", () => {
    render(<Card data-testid="card">Content</Card>);
    const card = screen.getByTestId("card");
    expect(card).toBeInTheDocument();
    expect(card).toHaveClass("rounded-xl");
    expect(card).toHaveClass("border");
  });

  it("should apply custom className", () => {
    render(<Card className="custom-card" data-testid="card">Content</Card>);
    const card = screen.getByTestId("card");
    expect(card).toHaveClass("custom-card");
  });
});

describe("CardHeader", () => {
  it("should render header with flex layout", () => {
    render(<CardHeader data-testid="header">Header</CardHeader>);
    const header = screen.getByTestId("header");
    expect(header).toBeInTheDocument();
    expect(header).toHaveClass("flex");
    expect(header).toHaveClass("flex-col");
  });

  it("should apply custom className", () => {
    render(<CardHeader className="custom-header" data-testid="header">Header</CardHeader>);
    const header = screen.getByTestId("header");
    expect(header).toHaveClass("custom-header");
  });
});

describe("CardTitle", () => {
  it("should render title with heading styles", () => {
    render(<CardTitle>Title</CardTitle>);
    const title = screen.getByText("Title");
    expect(title).toBeInTheDocument();
    expect(title).toHaveClass("font-semibold");
  });

  it("should apply custom className", () => {
    render(<CardTitle className="custom-title">Title</CardTitle>);
    const title = screen.getByText("Title");
    expect(title).toHaveClass("custom-title");
  });
});

describe("CardDescription", () => {
  it("should render description with muted styles", () => {
    render(<CardDescription>Description</CardDescription>);
    const desc = screen.getByText("Description");
    expect(desc).toBeInTheDocument();
    expect(desc).toHaveClass("text-muted-foreground");
  });

  it("should apply custom className", () => {
    render(<CardDescription className="custom-desc">Description</CardDescription>);
    const desc = screen.getByText("Description");
    expect(desc).toHaveClass("custom-desc");
  });
});

describe("CardContent", () => {
  it("should render content with padding", () => {
    render(<CardContent data-testid="content">Content</CardContent>);
    const content = screen.getByTestId("content");
    expect(content).toBeInTheDocument();
    expect(content).toHaveClass("p-6");
  });

  it("should apply custom className", () => {
    render(<CardContent className="custom-content" data-testid="content">Content</CardContent>);
    const content = screen.getByTestId("content");
    expect(content).toHaveClass("custom-content");
  });
});

describe("CardFooter", () => {
  it("should render footer with flex layout", () => {
    render(<CardFooter data-testid="footer">Footer</CardFooter>);
    const footer = screen.getByTestId("footer");
    expect(footer).toBeInTheDocument();
    expect(footer).toHaveClass("flex");
    expect(footer).toHaveClass("items-center");
  });

  it("should apply custom className", () => {
    render(<CardFooter className="custom-footer" data-testid="footer">Footer</CardFooter>);
    const footer = screen.getByTestId("footer");
    expect(footer).toHaveClass("custom-footer");
  });
});

describe("Card composition", () => {
  it("should compose all card parts correctly", () => {
    render(
      <Card data-testid="card">
        <CardHeader>
          <CardTitle>Test Card</CardTitle>
          <CardDescription>This is a test card</CardDescription>
        </CardHeader>
        <CardContent>
          <p>Card body content</p>
        </CardContent>
        <CardFooter>
          <button>Action</button>
        </CardFooter>
      </Card>
    );

    expect(screen.getByTestId("card")).toBeInTheDocument();
    expect(screen.getByText("Test Card")).toBeInTheDocument();
    expect(screen.getByText("This is a test card")).toBeInTheDocument();
    expect(screen.getByText("Card body content")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Action" })).toBeInTheDocument();
  });
});
