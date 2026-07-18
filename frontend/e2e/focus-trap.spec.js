import { test, expect } from '@playwright/test';

// Phase 1c — the gap axe cannot see. The mobile assistant is a modal drawer; a
// keyboard user must be able to open it, stay inside it while tabbing, close it
// with Escape, and land back on the trigger. This drives exactly that flow in a
// real browser.

const CSV = 'month,plan,customers\n2026-05,Starter,470\n2026-06,Starter,483\n2026-06,Pro,207\n';

test.use({ viewport: { width: 390, height: 820 } });   // mobile → assistant is an overlay

async function buildDashboard(page) {
  await page.goto('/studio');
  await page.setInputFiles('input[type=file]', { name: 'saas.csv', mimeType: 'text/csv', buffer: Buffer.from(CSV) });
  await page.getByRole('button', { name: /Create dashboard/i }).click();
  await page.waitForURL(/\/dashboard\/[0-9a-f-]+/, { timeout: 30_000 });
  await expect(page.locator('.tabular-nums').first()).toBeVisible();
}

test('mobile assistant drawer: focus trapped while open, restored to trigger on Escape', async ({ page }) => {
  await buildDashboard(page);

  // On mobile the drawer starts closed with an "Edit with AI" trigger.
  const trigger = page.getByRole('button', { name: /Edit with AI/i });
  await expect(trigger).toBeVisible();
  await trigger.focus();
  await trigger.press('Enter');

  const dialog = page.getByRole('dialog', { name: /Dashboard assistant/i });
  await expect(dialog).toBeVisible();

  // Focus moved into the dialog on open.
  expect(await dialog.evaluate((el) => el.contains(document.activeElement))).toBe(true);

  // Tab all the way round — focus must never escape the dialog.
  for (let i = 0; i < 10; i++) {
    await page.keyboard.press('Tab');
    expect(await dialog.evaluate((el) => el.contains(document.activeElement))).toBe(true);
  }
  // Shift+Tab too.
  for (let i = 0; i < 4; i++) {
    await page.keyboard.press('Shift+Tab');
    expect(await dialog.evaluate((el) => el.contains(document.activeElement))).toBe(true);
  }

  // Escape closes and focus returns to the trigger.
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
});
