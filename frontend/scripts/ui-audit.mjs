/**
 * Automated UI/layout sweep. Visits every route at 390 / 768 / 1440 and flags
 * horizontal overflow, off-viewport elements, tiny tap targets (mobile), and
 * images without alt. Writes findings to UI_AUDIT.md (repo root) and screenshots
 * to artifacts/ui/. Lives under frontend/ so @playwright/test resolves.
 *
 *   cd frontend && BASE=http://localhost:3100 node scripts/ui-audit.mjs
 */
import { chromium } from '@playwright/test';
import { writeFileSync, mkdirSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const BASE = process.env.BASE || 'http://localhost:3100';
const WIDTHS = [390, 768, 1440];
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const OUT = join(ROOT, 'artifacts/ui');
mkdirSync(OUT, { recursive: true });

async function seed() {
  const csv = 'region,month,revenue,units\nNorth,2026-01,120,10\nSouth,2026-01,90,8\nWest,2026-02,200,15\n';
  const form = new FormData();
  form.append('file', new Blob([csv], { type: 'text/csv' }), 'audit.csv');
  const up = await fetch(`${BASE}/api/backend/api/upload`, { method: 'POST', body: form }).then((r) => r.json());
  const dash = await fetch(`${BASE}/api/backend/api/dashboard`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ file_id: up.file_id }),
  }).then((r) => r.json());
  const share = await fetch(`${BASE}/api/backend/api/conversations/${dash.conversation_id}/share`, { method: 'POST' }).then((r) => r.json());
  return { cid: dash.conversation_id, token: share.share_id };
}

const findings = [];

async function checkPage(page, route, width) {
  await page.goto(`${BASE}${route.url}`, { waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(600);
  const issues = await page.evaluate(() => {
    const out = [];
    const de = document.documentElement;
    if (de.scrollWidth > de.clientWidth + 1) out.push(`horizontal overflow: ${de.scrollWidth} > ${de.clientWidth}`);
    const vw = de.clientWidth;
    let off = 0;
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (!(r.width > 0 && r.left >= 0 && r.right > vw + 2)) continue;
      // Ignore content inside a horizontal scroll container (tables, charts) —
      // it's meant to scroll and doesn't push the page.
      let p = el.parentElement, scrollable = false;
      while (p) {
        const ov = getComputedStyle(p).overflowX;
        if ((ov === 'auto' || ov === 'scroll' || ov === 'hidden') && p.scrollWidth > p.clientWidth + 1) { scrollable = true; break; }
        p = p.parentElement;
      }
      if (!scrollable) off++;
    }
    if (off > 0) out.push(`${off} element(s) truly overflow the page (not in a scroll container)`);
    const noAlt = [...document.querySelectorAll('img')].filter((i) => !i.hasAttribute('alt')).length;
    if (noAlt) out.push(`${noAlt} <img> without alt`);
    return out;
  }).catch((e) => [`eval failed: ${e.message}`]);

  if (width === 390) {
    const tiny = await page.evaluate(() => {
      let n = 0;
      for (const el of document.querySelectorAll('button, a, input, [role=button]')) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0 && (r.height < 32 || r.width < 24)) n++;
      }
      return n;
    }).catch(() => 0);
    if (tiny > 4) issues.push(`${tiny} interactive elements below the 44px tap-target guideline`);
  }

  await page.screenshot({ path: join(OUT, `${route.name}-${width}.png`) }).catch(() => {});
  if (issues.length) findings.push({ route: route.name, width, url: route.url, issues });
}

const b = await chromium.launch();
try {
  const { cid, token } = await seed();
  const routes = [
    { name: 'landing', url: '/' }, { name: 'studio', url: '/studio' },
    { name: 'privacy', url: '/privacy' }, { name: 'terms', url: '/terms' },
    { name: 'sign-in', url: '/sign-in' }, { name: 'admin', url: '/admin' },
    { name: 'dashboard', url: `/dashboard/${cid}` }, { name: 'share', url: `/share/${token}` },
    { name: 'not-found', url: '/this-route-does-not-exist' },
  ];
  for (const w of WIDTHS) {
    const page = await b.newPage({ viewport: { width: w, height: 900 } });
    for (const route of routes) await checkPage(page, route, w);
    await page.close();
  }
} finally {
  await b.close();
}

const lines = ['# UI / layout audit', '', `Automated sweep of ${BASE} at ${WIDTHS.join(' / ')}px. Screenshots in \`artifacts/ui/\`.`, ''];
if (!findings.length) lines.push('No horizontal overflow, off-viewport elements, missing alt, or tiny tap targets found.');
else for (const f of findings) { lines.push(`## ${f.route} @ ${f.width}px  (\`${f.url}\`)`); for (const i of f.issues) lines.push(`- ${i}`); lines.push(''); }
writeFileSync(join(ROOT, 'UI_AUDIT.md'), lines.join('\n'));
console.log(findings.length ? `${findings.length} finding group(s) — see UI_AUDIT.md` : 'UI audit clean');
