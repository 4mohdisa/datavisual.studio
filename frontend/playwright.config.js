const { defineConfig, devices } = require('@playwright/test');

// Browser-level e2e. Auto-starts the frontend AND the backend (reusing them if
// already running). Assumes OPEN dev mode (no Clerk keys) so app routes are
// reachable without a session — the golden path here is fully deterministic
// (no AI pipeline calls).
module.exports = defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'npm run dev',
      url: 'http://localhost:3000',
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: 'cd .. && uv run python -m backend.main',
      url: 'http://localhost:8001/api/export-format',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
