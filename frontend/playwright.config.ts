import { defineConfig, devices } from "@playwright/test";

const PORT = 8799;

export default defineConfig({
  testDir: "./test/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}/latest/`,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    // Build the demo (jaffle_shop fixtures) into docs/demo/, then serve it. The
    // SPA lands at /latest/ (the deploy alias) — baseURL above points there.
    command:
      "cd .. && uv run dbdocs -c docs/dbdocs-demo.yml deploy --version e2e --alias latest" +
      ` && uv run dbdocs -c docs/dbdocs-demo.yml serve -p ${PORT}`,
    url: `http://127.0.0.1:${PORT}/latest/index.html`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
