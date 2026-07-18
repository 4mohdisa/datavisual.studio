import { test, expect } from '@playwright/test';

test.describe('Marketing + legal', () => {
  test('landing renders hero, nav, animated sections, FAQ, footer', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/datavisual\.studio/);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('track your situation');
    await expect(page.getByRole('link', { name: /Open studio/i })).toBeVisible();

    // Feature showcase headings exist
    await expect(page.getByText('One update, and it tells you what changed')).toBeVisible();

    // FAQ accordion expands
    const faq = page.getByText('Is datavisual.studio really free?');
    await faq.click();
    await expect(page.getByText(/bring your own AI provider keys/i)).toBeVisible();

    // Footer legal links + author credit
    await expect(page.getByRole('link', { name: 'Privacy policy' }).first()).toBeVisible();
    // Author byline links the author's site; the star button links the repo.
    await expect(page.getByRole('link', { name: /Mohammed Isa/ })).toHaveAttribute('href', /isaxcode\.com/);
    await expect(page.getByRole('link', { name: /Star on GitHub/i })).toHaveAttribute('href', /github\.com\/4mohdisa\/datavisual\.studio/);
  });

  test('no horizontal overflow on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    );
    expect(overflow).toBe(false);
  });

  test('privacy and terms pages load', async ({ page }) => {
    await page.goto('/privacy');
    await expect(page.getByRole('heading', { name: 'Privacy policy' })).toBeVisible();
    await page.goto('/terms');
    await expect(page.getByRole('heading', { name: 'Terms of use' })).toBeVisible();
  });

  test('SEO endpoints resolve', async ({ request }) => {
    expect((await request.get('/robots.txt')).status()).toBe(200);
    expect((await request.get('/sitemap.xml')).status()).toBe(200);
    const og = await request.get('/opengraph-image');
    expect(og.status()).toBe(200);
    expect(og.headers()['content-type']).toContain('image/png');
  });
});
