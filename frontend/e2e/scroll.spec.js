const { test, expect } = require('@playwright/test');

// Night 3, BUG 5 (unscrollable share view): SharedView's root is `min-h-screen`
// under `body{overflow:hidden}`, so its scrollHeight equals its clientHeight —
// nothing scrolls and content below the fold is unreachable. This fails today
// and passes once the root becomes `h-screen` (a real scroll container).
//
// It also seeds the Phase 2b class-killer: the intended scroll container of a
// route must actually reach its own bottom.

async function scrollContainerReachesBottom(page) {
  return page.evaluate(async () => {
    // The page content sits under app/template.js's .page-transition wrapper.
    const root = document.querySelector('.page-transition')?.firstElementChild
      || document.scrollingElement;
    if (!root) return { ok: false, why: 'no root' };
    const scrollable = root.scrollHeight - root.clientHeight;
    root.scrollTop = root.scrollHeight;
    await new Promise((r) => setTimeout(r, 120));
    return {
      ok: scrollable > 40 && root.scrollTop > 40,
      scrollable,
      scrollTop: root.scrollTop,
      cls: (root.className || '').slice(0, 60),
    };
  });
}

test('demo view scrolls to its bottom (BUG 5)', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/demo');
  await page.getByRole('heading', { name: /SaaS revenue/i }).waitFor({ timeout: 20_000 });
  const res = await scrollContainerReachesBottom(page);
  expect(res.ok, `share/demo content is unreachable: ${JSON.stringify(res)}`).toBe(true);
});

// Phase 2b — kill the whole class: on every route, at every breakpoint and a
// SHORT height that forces overflow, the main scroll container must reach its
// own bottom. A page you can't reach the bottom of is broken; find out here.
async function mainScrollerReachesBottom(page) {
  return page.evaluate(async () => {
    const scrollers = [document.scrollingElement, ...document.querySelectorAll('*')].filter((el) => {
      if (!el) return false;
      const oy = getComputedStyle(el).overflowY;
      const canScroll = oy === 'auto' || oy === 'scroll' || el === document.scrollingElement;
      return canScroll && el.scrollHeight - el.clientHeight > 24;
    });
    if (scrollers.length === 0) return { ok: true, why: 'content fits, nothing to scroll' };
    const main = scrollers.sort((a, b) =>
      (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight))[0];
    main.scrollTop = main.scrollHeight;
    await new Promise((r) => setTimeout(r, 120));
    const max = main.scrollHeight - main.clientHeight;
    return { ok: main.scrollTop >= max - 6, scrollTop: Math.round(main.scrollTop), max: Math.round(max),
             cls: (main.className || '').toString().slice(0, 50) };
  });
}

const ROUTES = ['/', '/demo', '/privacy', '/terms', '/studio'];
const SIZES = [{ w: 390, h: 640 }, { w: 768, h: 700 }, { w: 1440, h: 700 }];

for (const route of ROUTES) {
  for (const { w, h } of SIZES) {
    test(`${route} reaches its bottom @ ${w}×${h}`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: h });
      await page.goto(route);
      await page.waitForLoadState('networkidle').catch(() => {});
      await page.waitForTimeout(400);
      const res = await mainScrollerReachesBottom(page);
      expect(res.ok, `${route} @ ${w}×${h} unreachable bottom: ${JSON.stringify(res)}`).toBe(true);
    });
  }
}
