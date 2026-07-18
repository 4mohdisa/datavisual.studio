import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Emulate reduced motion so the page-transition fade-in (opacity 0→1) is
// instant — otherwise axe can scan mid-animation and read every colour at
// partial opacity over black, a transient false positive. It's also the more
// representative scan: a reduced-motion user sees the settled page.
test.use({ reducedMotion: 'reduce' });

// Phase 4e — automated accessibility scan. Zero critical/serious violations on
// every route we can reach without a live Clerk session (open dev mode). axe
// can't judge keyboard flow or screen-reader sense — that's the manual pass in
// A11Y_AUDIT.md — but it catches contrast, names, roles, and landmark misuse.

const CSV = 'month,plan,customers\n2026-05,Starter,470\n2026-06,Starter,483\n2026-06,Pro,207\n2026-06,Enterprise,41\n';

async function scan(page) {
  // Wait for the page-transition fade (opacity 0→1) to finish — scanning
  // mid-fade reads every colour at partial opacity over black (false positives).
  await page.waitForFunction(() => {
    const el = document.querySelector('.page-transition');
    return !el || getComputedStyle(el).opacity === '1';
  }, { timeout: 5000 }).catch(() => {});
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  const serious = results.violations.filter((v) => ['critical', 'serious'].includes(v.impact));
  // Surface a readable summary when it fails.
  if (serious.length) {
    console.log(JSON.stringify(serious.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help })), null, 2));
  }
  return serious;
}

for (const path of ['/', '/about', '/demo', '/studio']) {
  test(`no serious axe violations: ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    expect(await scan(page)).toEqual([]);
  });
}

test('no serious axe violations: a built dashboard', async ({ page }) => {
  await page.goto('/studio');
  await page.setInputFiles('input[type=file]', { name: 'saas.csv', mimeType: 'text/csv', buffer: Buffer.from(CSV) });
  await page.getByRole('button', { name: /Create dashboard/i }).click();
  await page.waitForURL(/\/dashboard\/[0-9a-f-]+/, { timeout: 30_000 });
  await expect(page.locator('.tabular-nums').first()).toBeVisible();
  expect(await scan(page)).toEqual([]);
});
