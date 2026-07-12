import { test, expect } from '@playwright/test';

const CSV = 'region,month,revenue,units\nNorth,2026-01,120,10\nSouth,2026-01,90,8\nWest,2026-02,200,15\n';

// The core deterministic user journey (no AI pipeline): upload a dataset, build
// a dashboard, share it, and open the read-only public view.
test('upload → dashboard → share → public read-only view', async ({ page }) => {
  await page.goto('/studio');

  // Attach the dataset to the hidden file input (Home auto-uploads on change).
  await page.setInputFiles('input[type=file]', {
    name: 'sales.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(CSV),
  });

  // Create the dashboard.
  await page.getByRole('button', { name: /Create dashboard/i }).click();
  await page.waitForURL(/\/dashboard\/[0-9a-f-]+/, { timeout: 30_000 });

  // Widgets rendered.
  await expect(page.locator('.tabular-nums').first()).toBeVisible();

  // Share → modal → grab link.
  await page.getByRole('button', { name: /^Share|Shared$/ }).click();
  await expect(page.getByText('Share this view')).toBeVisible();
  const link = await page.locator('input[readonly]').inputValue();
  expect(link).toMatch(/\/share\/[\w-]+$/);

  // Open the public view — read-only, no editor chrome.
  await page.goto(link);
  await expect(page.getByText('Read-only shared view')).toBeVisible();
  await expect(page.getByRole('button', { name: /Update|Edit with AI/ })).toHaveCount(0);
});

test('unknown share token shows an unavailable state', async ({ page }) => {
  await page.goto('/share/definitelynotarealtoken');
  await expect(page.getByText(/shared link is unavailable/i)).toBeVisible();
});
