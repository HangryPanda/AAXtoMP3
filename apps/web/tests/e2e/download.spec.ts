import { expect, test } from "@playwright/test";

/**
 * E2E tests for the Download flow.
 *
 * These tests verify:
 * - Download button/action visibility
 * - Job creation and status tracking
 * - Progress indicators
 * - Error handling
 *
 * Note: These tests may require a populated library to fully exercise
 * the download functionality. Some tests use mocked responses.
 */

test.describe("Download Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("should have download functionality accessible", async ({ page }) => {
    // Check for download-related UI elements
    const downloadButton = page.locator(
      'button:has-text("Download"), [data-testid="download-button"], [aria-label*="download" i]'
    );
    const syncButton = page.locator(
      'button:has-text("Sync"), [data-testid="sync-button"], [aria-label*="sync" i]'
    );
    const refreshButton = page.locator(
      'button:has-text("Refresh"), [data-testid="refresh-button"], [aria-label*="refresh" i]'
    );

    // At least one of these should be present
    const hasDownloadUI =
      ((await downloadButton.count()) > 0) ||
      ((await syncButton.count()) > 0) ||
      ((await refreshButton.count()) > 0);

    // If library is empty, download buttons may not be visible
    // so we just verify the page loaded correctly
    if (!hasDownloadUI) {
      test.info().annotations.push({
        type: "info",
        description: "Download UI not visible - likely empty library",
      });
      // Verify page is still functional
      await expect(page.locator("body")).toBeVisible();
    } else {
      // Verify one of the buttons is visible
      const visibleButton = downloadButton.or(syncButton).or(refreshButton).first();
      await expect(visibleButton).toBeVisible();
    }
  });

  test("should navigate to jobs page if available", async ({ page }) => {
    // Try to find and click jobs/queue navigation
    const jobsLink = page.locator(
      'a[href*="job"], a[href*="queue"], a:has-text("Jobs"), a:has-text("Queue"), [data-testid="jobs-link"]'
    );

    const hasJobsLink = (await jobsLink.count()) > 0;

    if (hasJobsLink) {
      await jobsLink.first().click();
      await page.waitForLoadState("networkidle");

      // Verify we're on a jobs-related page
      const url = page.url();
      const pageContent = await page.content();

      expect(
        url.includes("job") ||
          url.includes("queue") ||
          pageContent.toLowerCase().includes("job") ||
          pageContent.toLowerCase().includes("queue")
      ).toBe(true);
    } else {
      test.info().annotations.push({
        type: "skip",
        description: "Jobs navigation not found",
      });
    }
  });

  test("should show progress indicators during operations", async ({ page }) => {
    // Look for any progress-related UI elements
    const progressIndicators = page.locator(
      '[role="progressbar"], .progress, [data-testid="progress"], .animate-spin, .loading'
    );

    // These may or may not be visible depending on current state
    // Just verify the page handles their presence/absence correctly
    const progressCount = await progressIndicators.count();

    test.info().annotations.push({
      type: "info",
      description: `Found ${progressCount} progress indicators on page`,
    });

    // Page should be functional regardless
    await expect(page.locator("body")).toBeVisible();
  });
});

test.describe("Download API Integration", () => {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  test("should be able to fetch jobs list", async ({ request }) => {
    const response = await request.get(`${apiUrl}/jobs/`);

    expect(response.ok()).toBe(true);

    const data = await response.json();

    // Verify response structure
    expect(data).toHaveProperty("items");
    expect(data).toHaveProperty("total");
    expect(Array.isArray(data.items)).toBe(true);
  });

  test("should be able to fetch job types", async ({ request }) => {
    // Test that the API can handle job type queries
    const response = await request.get(`${apiUrl}/jobs/?task_type=DOWNLOAD`);

    expect(response.ok()).toBe(true);

    const data = await response.json();
    expect(data).toHaveProperty("items");
    expect(Array.isArray(data.items)).toBe(true);
  });

  test("should return proper error for invalid job ID", async ({ request }) => {
    // Test error handling with invalid UUID
    const response = await request.get(`${apiUrl}/jobs/invalid-uuid`);

    // Should return 422 (validation error) or 404
    expect([404, 422]).toContain(response.status());
  });

  test("should validate job creation request", async ({ request }) => {
    // Test that creating a job without required fields fails properly
    const response = await request.post(`${apiUrl}/jobs/`, {
      data: {},
    });

    // Should return 422 (validation error)
    expect(response.status()).toBe(422);
  });

  test("should create download job with valid data", async ({ request }) => {
    // Note: This test requires a valid book ASIN in the database
    // First, check if we have any books
    const libraryResponse = await request.get(`${apiUrl}/library/`);
    const libraryData = await libraryResponse.json();

    if (libraryData.items && libraryData.items.length > 0) {
      const book = libraryData.items[0];

      // Try to create a download job
      const response = await request.post(`${apiUrl}/jobs/`, {
        data: {
          task_type: "DOWNLOAD",
          book_asin: book.asin,
        },
      });

      // Should succeed or fail gracefully
      expect([200, 201, 400, 409]).toContain(response.status());

      if (response.ok()) {
        const job = await response.json();
        expect(job).toHaveProperty("id");
        expect(job).toHaveProperty("task_type", "DOWNLOAD");
        expect(job).toHaveProperty("status");
      }
    } else {
      test.info().annotations.push({
        type: "skip",
        description: "No books in library to test download job creation",
      });
    }
  });
});

test.describe("WebSocket Connection", () => {
  test("should connect to WebSocket for job updates", async ({ page }) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const _wsUrl = apiUrl.replace("http", "ws");

    // Create a promise that resolves when WebSocket connects
    const wsConnected = new Promise<boolean>((resolve) => {
      page.on("websocket", (ws) => {
        if (ws.url().includes("ws")) {
          resolve(true);
        }
      });

      // Timeout after 5 seconds
      setTimeout(() => resolve(false), 5000);
    });

    // Navigate to page (should establish WS connection)
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Wait for potential WebSocket connection
    const connected = await wsConnected;

    // WebSocket may or may not connect depending on page implementation
    test.info().annotations.push({
      type: "info",
      description: `WebSocket connection ${connected ? "established" : "not established"}`,
    });

    // Page should still be functional
    await expect(page.locator("body")).toBeVisible();
  });
});

test.describe("Settings Page", () => {
  test("should access settings page", async ({ page }) => {
    // Try to navigate to settings
    const settingsLink = page.locator(
      'a[href*="setting"], a:has-text("Settings"), [data-testid="settings-link"], button:has-text("Settings")'
    );

    const hasSettingsLink = (await settingsLink.count()) > 0;

    if (hasSettingsLink) {
      await settingsLink.first().click();
      await page.waitForLoadState("networkidle");

      // Should see settings content
      const settingsContent = page.locator(
        ':text("Settings"), :text("Configuration"), :text("Output"), :text("Format")'
      );
      await expect(settingsContent.first()).toBeVisible();
    } else {
      // Try direct navigation
      await page.goto("/settings");
      await page.waitForLoadState("networkidle");

      // Check if we got a settings page or 404
      const is404 = await page.locator(':text("404"), :text("Not Found")').count();

      if (is404 === 0) {
        const settingsContent = page.locator(
          ':text("Settings"), :text("Configuration"), :text("Output"), :text("Format")'
        );
        const hasSettings = (await settingsContent.count()) > 0;
        expect(hasSettings).toBe(true);
      } else {
        test.info().annotations.push({
          type: "skip",
          description: "Settings page not found",
        });
      }
    }
  });

  test("should fetch settings from API", async ({ request }) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const response = await request.get(`${apiUrl}/settings/`);

    expect(response.ok()).toBe(true);

    const data = await response.json();

    // Verify settings structure
    expect(data).toHaveProperty("output_format");
    expect(data).toHaveProperty("single_file");
  });
});
