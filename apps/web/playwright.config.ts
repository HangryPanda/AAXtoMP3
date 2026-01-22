import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for Audible Library Manager E2E tests.
 *
 * @see https://playwright.dev/docs/test-configuration
 */

const CI = !!process.env.CI;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default defineConfig({
  // Test directory
  testDir: "./tests/e2e",

  // Test file pattern
  testMatch: "**/*.spec.ts",

  // Timeout for each test
  timeout: 30000,

  // Timeout for expect() assertions
  expect: {
    timeout: 10000,
  },

  // Run tests in parallel
  fullyParallel: true,

  // Fail the build on CI if test.only is left in source code
  forbidOnly: CI,

  // Retry failed tests
  retries: CI ? 2 : 0,

  // Number of parallel workers
  workers: CI ? 1 : undefined,

  // Reporter configuration
  reporter: CI
    ? [
        ["html", { outputFolder: "playwright-report" }],
        ["github"],
        ["list"],
      ]
    : [["html", { outputFolder: "playwright-report" }], ["list"]],

  // Output directory for test artifacts
  outputDir: "test-results",

  // Shared settings for all projects
  use: {
    // Base URL for navigation
    baseURL: BASE_URL,

    // Collect trace on failure
    trace: CI ? "on-first-retry" : "on",

    // Screenshot on failure
    screenshot: "only-on-failure",

    // Video on failure
    video: CI ? "on-first-retry" : "off",

    // Headless mode
    headless: true,

    // Viewport size
    viewport: { width: 1280, height: 720 },

    // Action timeout
    actionTimeout: 15000,

    // Navigation timeout
    navigationTimeout: 30000,

    // Extra HTTP headers
    extraHTTPHeaders: {
      Accept: "application/json, text/html, */*",
    },
  },

  // Project configuration for different browsers
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },

    // Optionally enable additional browsers
    // {
    //   name: "firefox",
    //   use: { ...devices["Desktop Firefox"] },
    // },

    // {
    //   name: "webkit",
    //   use: { ...devices["Desktop Safari"] },
    // },

    // Mobile viewport testing
    // {
    //   name: "Mobile Chrome",
    //   use: { ...devices["Pixel 5"] },
    // },
  ],

  // Web server configuration for local development
  webServer: CI
    ? undefined
    : [
        {
          // Start the API server
          command: "cd ../api && uvicorn main:app --host 0.0.0.0 --port 8000",
          url: `${API_URL}/health/live`,
          reuseExistingServer: !CI,
          timeout: 60000,
        },
        {
          // Start the Next.js dev server
          command: "npm run dev",
          url: BASE_URL,
          reuseExistingServer: !CI,
          timeout: 60000,
        },
      ],

  // Global setup and teardown
  // globalSetup: require.resolve("./tests/global-setup.ts"),
  // globalTeardown: require.resolve("./tests/global-teardown.ts"),
});
