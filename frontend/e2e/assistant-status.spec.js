import { test, expect } from '@playwright/test';

// Phase 3a — the assistant's busy status must follow intent. The reported bug:
// asking a data question showed "Updating dashboard" while the server was
// actually ANSWERING. We hold the chat request open so the status is visible,
// then assert it names the right action. "biggest month" is the exact class
// the old client heuristic got wrong (no leading question-word, no '?').

const CSV = 'month,plan,customers\n2026-05,Starter,470\n2026-06,Starter,483\n2026-06,Pro,207\n2026-06,Enterprise,41\n';

async function buildDashboard(page) {
  await page.goto('/studio');
  await page.setInputFiles('input[type=file]', {
    name: 'saas.csv', mimeType: 'text/csv', buffer: Buffer.from(CSV),
  });
  await page.getByRole('button', { name: /Create dashboard/i }).click();
  await page.waitForURL(/\/dashboard\/[0-9a-f-]+/, { timeout: 30_000 });
  await expect(page.locator('.tabular-nums').first()).toBeVisible();
}

test('a data question shows "Reading your data…", never "Updating the dashboard…"', async ({ page }) => {
  await buildDashboard(page);

  // Hold the chat POST open, then answer with a canned response — deterministic,
  // no LLM. The status we assert renders during the hold.
  await page.route('**/api/dashboard/*/chat', async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.fulfill({ json: {
      dashboard: { title: 'saas', widgets: [], history: [
        { role: 'user', content: 'biggest month' },
        { role: 'assistant', content: 'June was the biggest month.' },
      ] },
      reply: 'June was the biggest month.',
    } });
  });

  const input = page.getByPlaceholder(/Ask about the data/i);
  await input.fill('biggest month');
  await input.press('Enter');

  // While the request is in flight the status must name the answering action.
  await expect(page.getByText('Reading your data…')).toBeVisible();
  await expect(page.getByText('Updating the dashboard…')).toHaveCount(0);
});

test('an edit shows "Updating the dashboard…"', async ({ page }) => {
  await buildDashboard(page);

  await page.route('**/api/dashboard/*/chat', async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.fulfill({ json: {
      dashboard: { title: 'saas', widgets: [], history: [
        { role: 'user', content: 'add a bar chart of customers' },
        { role: 'assistant', content: 'Added a bar chart.' },
      ] },
    } });
  });

  const input = page.getByPlaceholder(/Ask about the data/i);
  await input.fill('add a bar chart of customers');
  await input.press('Enter');

  await expect(page.getByText('Updating the dashboard…')).toBeVisible();
});
