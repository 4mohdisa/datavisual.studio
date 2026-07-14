const { defineConfig, devices } = require('@playwright/test');

// Browser-level e2e. Auto-starts the frontend AND the backend (reusing them if
// already running). Assumes OPEN dev mode (no Clerk keys) so app routes are
// reachable without a session.
//
// PORT BINDING (Night 3, Phase 4a): the port is configurable via E2E_PORT and
// defaults to 3100 — NEVER 3000. Night 2 skipped e2e because another app held
// 3000; "a test suite that can't run because an unrelated program is using a
// port is not a test suite." Override with E2E_PORT=<n> if 3100 is taken too.
const PORT = process.env.E2E_PORT || '3100';
const BASE_URL = process.env.BASE_URL || `http://localhost:${PORT}`;

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `npm run dev -- --port ${PORT}`,
      url: BASE_URL,
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
