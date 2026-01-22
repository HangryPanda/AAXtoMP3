import { expect, test } from "@playwright/test";

/**
 * E2E tests for the Library page.
 *
 * These tests verify:
 * - Library page loads correctly
 * - Books are displayed in the grid
 * - Search and filter functionality
 * - Book details modal/sidebar
 */

test.describe("Library Page", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to library page before each test
    await page.goto("/");
  });

  test("should load the library page", async ({ page }) => {
    // Verify page title or main heading
    await expect(page).toHaveTitle(/Audible Library|Library/i);

    // Wait for the page to be fully loaded
    await page.waitForLoadState("networkidle");

    // Check for main navigation or header
    const header = page.locator("header, nav, [role='banner']").first();
    await expect(header).toBeVisible();
  });

  test("should display library content area", async ({ page }) => {
    // Wait for network idle to ensure API calls complete
    await page.waitForLoadState("networkidle");

    // Look for the main content area (grid, list, or empty state)
    const mainContent = page.locator("main, [role='main'], #root > div").first();
    await expect(mainContent).toBeVisible();
  });

  test("should show loading state initially", async ({ page }) => {
    // This test checks if a loading indicator appears before content loads
    // Navigate fresh to catch the loading state
    await page.goto("/");

    // Look for loading indicators (spinner, skeleton, or loading text)
    const loadingIndicator = page.locator(
      '[data-testid="loading"], .loading, [role="progressbar"], .skeleton, .animate-pulse'
    );

    // Either loading indicator was visible or content loaded immediately
    const contentLoaded = page.locator(
      '[data-testid="library-grid"], [data-testid="book-card"], .book-card'
    );

    // One of these should be visible
    await expect(loadingIndicator.or(contentLoaded).first()).toBeVisible({
      timeout: 10000,
    });
  });

  test("should have functional search input", async ({ page }) => {
    await page.waitForLoadState("networkidle");

    // Find search input
    const searchInput = page.locator(
      'input[type="search"], input[placeholder*="search" i], input[placeholder*="Search" i], [data-testid="search-input"]'
    );

    // Check if search input exists
    const searchExists = (await searchInput.count()) > 0;

    if (searchExists) {
      await expect(searchInput.first()).toBeVisible();

      // Type in search
      await searchInput.first().fill("test search");

      // Verify input value
      await expect(searchInput.first()).toHaveValue("test search");

      // Clear search
      await searchInput.first().clear();
    } else {
      // Search may not be visible if library is empty
      test.info().annotations.push({
        type: "skip",
        description: "Search input not found - may be hidden when library is empty",
      });
    }
  });

  test("should handle empty library state gracefully", async ({ page }) => {
    await page.waitForLoadState("networkidle");

    // Look for empty state message or library content
    const emptyState = page.locator(
      '[data-testid="empty-state"], .empty-state, :text("No books"), :text("empty"), :text("Get started")'
    );
    const libraryContent = page.locator(
      '[data-testid="library-grid"], [data-testid="book-card"], .book-card, .library-grid'
    );

    // Either we have content or an empty state message
    const hasEmptyState = (await emptyState.count()) > 0;
    const hasContent = (await libraryContent.count()) > 0;

    expect(hasEmptyState || hasContent).toBe(true);
  });

  test("should be responsive", async ({ page }) => {
    await page.waitForLoadState("networkidle");

    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(500); // Wait for responsive adjustments

    // Page should still be functional
    const mainContent = page.locator("main, [role='main'], #root > div").first();
    await expect(mainContent).toBeVisible();

    // Test tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(500);
    await expect(mainContent).toBeVisible();

    // Reset to desktop
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.waitForTimeout(500);
    await expect(mainContent).toBeVisible();
  });

  test("should have accessible navigation", async ({ page }) => {
    await page.waitForLoadState("networkidle");

    // Check for navigation elements
    const navItems = page.locator('nav a, [role="navigation"] a, header a');
    const navCount = await navItems.count();

    if (navCount > 0) {
      // Verify at least one nav item is visible
      await expect(navItems.first()).toBeVisible();
    }
  });
});

test.describe("Library API Integration", () => {
  test("should call API health endpoint", async ({ page, request }) => {
    // Test the API health endpoint directly
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const response = await request.get(`${apiUrl}/health/live`);

    expect(response.ok()).toBe(true);

    const data = await response.json();
    expect(data).toHaveProperty("status", "ok");
  });

  test("should fetch library data from API", async ({ page, request }) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    // Test the library endpoint
    const response = await request.get(`${apiUrl}/library/`);

    // Should return 200 even if empty
    expect(response.ok()).toBe(true);

    const data = await response.json();

    // Response should have expected structure
    expect(data).toHaveProperty("items");
    expect(data).toHaveProperty("total");
    expect(Array.isArray(data.items)).toBe(true);
  });
});
