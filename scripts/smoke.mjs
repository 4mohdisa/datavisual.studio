#!/usr/bin/env node
/**
 * Functional smoke test — exercises the whole stack (Next frontend + proxy +
 * FastAPI backend) over HTTP, no browser required. Run against a running stack:
 *
 *   node scripts/smoke.mjs                 # defaults to http://localhost:3000
 *   BASE=https://app.example.com node scripts/smoke.mjs
 *
 * Assumes OPEN dev mode (no Clerk) so the app routes are reachable without a
 * session. Exits non-zero on the first failure.
 */

const BASE = process.env.BASE || 'http://localhost:3000';
let passed = 0;
const failures = [];

async function check(name, fn) {
  try {
    await fn();
    passed++;
    console.log(`  \x1b[32m✓\x1b[0m ${name}`);
  } catch (e) {
    failures.push({ name, error: e.message });
    console.log(`  \x1b[31m✗\x1b[0m ${name}\n      ${e.message}`);
  }
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

async function get(path, opts) {
  const r = await fetch(`${BASE}${path}`, opts);
  return r;
}

async function main() {
  console.log(`\nSmoke testing ${BASE}\n`);

  // --- Marketing + SEO surfaces ---------------------------------------------
  await check('GET / (landing) 200 + brand + OG image meta', async () => {
    const r = await get('/');
    assert(r.status === 200, `status ${r.status}`);
    const html = await r.text();
    assert(html.includes('datavisual.studio'), 'brand missing');
    assert(/og:image/.test(html), 'og:image meta missing');
    assert(/application\/ld\+json/.test(html), 'JSON-LD missing');
  });
  await check('GET /privacy 200', async () => assert((await get('/privacy')).status === 200, 'not 200'));
  await check('GET /terms 200', async () => assert((await get('/terms')).status === 200, 'not 200'));
  await check('GET /robots.txt has Sitemap + disallows /share', async () => {
    const t = await (await get('/robots.txt')).text();
    assert(/Sitemap:/i.test(t), 'no sitemap');
    assert(t.includes('/share'), 'share not disallowed');
  });
  await check('GET /sitemap.xml 200 + urls', async () => {
    const r = await get('/sitemap.xml');
    assert(r.status === 200, `status ${r.status}`);
    assert((await r.text()).includes('<loc>'), 'no urls');
  });
  await check('GET /opengraph-image 200 image/png', async () => {
    const r = await get('/opengraph-image');
    assert(r.status === 200, `status ${r.status}`);
    assert((r.headers.get('content-type') || '').includes('image/png'), 'not png');
  });
  await check('GET /studio 200 (open mode)', async () => {
    assert((await get('/studio')).status === 200, 'not 200');
  });
  await check('Backend /health reachable through proxy', async () => {
    const r = await get('/api/backend/health');
    assert(r.status === 200, `status ${r.status}`);
    assert((await r.json()).status === 'ok', 'not ok');
  });

  // --- Security: path-traversal guards must NOT leak -------------------------
  await check('Proxy rejects %2f traversal (api/public/..) → 400, no leak', async () => {
    const r = await get('/api/backend/api/public/..%2f..%2fapi%2fconversations');
    const body = await r.text();
    assert(r.status === 400, `expected 400, got ${r.status}`);
    assert(!body.includes('owner_id'), 'LEAK: conversation data returned');
  });
  await check('Share page traversal renders "unavailable" (no leak)', async () => {
    const r = await get('/share/..%2f..%2fapi%2fconversations');
    const html = await r.text();
    assert(!html.includes('owner_id'), 'LEAK: data in share page');
  });

  // --- Golden path via the proxy (deterministic, no AI) ----------------------
  const csv = 'region,month,revenue,units\nNorth,2026-01,120,10\nSouth,2026-01,90,8\nWest,2026-02,200,15\n';
  let cid, token;

  await check('Upload CSV via proxy → file_id', async () => {
    const form = new FormData();
    form.append('file', new Blob([csv], { type: 'text/csv' }), 'smoke.csv');
    const r = await get('/api/backend/api/upload', { method: 'POST', body: form });
    assert(r.status === 200, `status ${r.status}`);
    const j = await r.json();
    assert(j.file_id, 'no file_id');
    globalThis.__fid = j.file_id;
  });

  // The launch blocker was a >4.5 MB file dying on a serverless proxy. Prove a
  // large upload survives the current transport (SPLIT=1 to gate it in CI).
  if (process.env.SPLIT === '1' || process.env.LARGE_UPLOAD === '1') {
    await check('Upload >5 MB CSV survives the transport', async () => {
      const header = 'id,value\n';
      const row = '1,1234567\n';
      const body = header + row.repeat(Math.ceil((5.5 * 1024 * 1024) / row.length));
      assert(body.length > 5 * 1024 * 1024, 'test body not >5MB');
      const form = new FormData();
      form.append('file', new Blob([body], { type: 'text/csv' }), 'big.csv');
      const r = await get('/api/backend/api/upload', { method: 'POST', body: form });
      assert(r.status === 200, `status ${r.status} (a >5MB upload was rejected)`);
      assert((await r.json()).file_id, 'no file_id for large upload');
    });
  }

  await check('Create dashboard from upload → widgets', async () => {
    const r = await get('/api/backend/api/dashboard', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ file_id: globalThis.__fid }),
    });
    assert(r.status === 200, `status ${r.status}`);
    cid = (await r.json()).conversation_id;
    const conv = await (await get(`/api/backend/api/conversations/${cid}`)).json();
    const kinds = new Set(conv.dashboard.widgets.map((w) => w.kind));
    assert(kinds.has('metric') && kinds.has('chart'), 'missing widget kinds');
  });

  await check('Edit dashboard by ops (add_metric)', async () => {
    const r = await get(`/api/backend/api/dashboard/${cid}/chat`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ops: [{ op: 'add_metric', column: 'revenue', agg: 'sum', label: 'Total' }] }),
    });
    assert(r.status === 200, `status ${r.status}`);
    assert((await r.json()).dashboard.widgets.some((w) => w.label === 'Total'), 'metric not added');
  });

  await check('Share → public read-only allowlist (no leaks)', async () => {
    token = (await (await get(`/api/backend/api/conversations/${cid}/share`, { method: 'POST' })).json()).share_id;
    assert(token, 'no token');
    const pub = await (await get(`/api/backend/api/public/${token}`)).json();
    assert(pub.dashboard.widgets.length > 0, 'no widgets in public view');
    assert(!('owner_id' in pub) && !('file' in pub), 'LEAK: sensitive fields present');
  });

  await check('Public /share/[token] page renders read-only', async () => {
    const html = await (await get(`/share/${token}`)).text();
    assert(html.includes('Read-only shared view') || html.includes('Build your own'), 'share page not rendered');
  });

  await check('Revoke → public 404', async () => {
    await get(`/api/backend/api/conversations/${cid}/share`, { method: 'DELETE' });
    assert((await get(`/api/backend/api/public/${token}`)).status === 404, 'still reachable after revoke');
  });

  // --- More security surfaces (verify-deploy) --------------------------------
  await check('Third %2f vector (api/export/..) → not a data leak', async () => {
    const r = await get('/api/backend/api/export/..%2f..%2fapi%2fconversations');
    const body = await r.text();
    assert(r.status !== 200 || !body.includes('owner_id'), `LEAK via export traversal (status ${r.status})`);
  });

  await check('Admin overview: bad password rejected when gated (403), open in dev', async () => {
    const r = await get('/api/backend/api/admin/overview', { headers: { 'x-admin-password': 'definitely-wrong' } });
    // Prod (ADMIN_PASSWORD set) → 403. Open dev (unset) → 200. Never 200-with-a-bad-password in prod.
    assert(r.status === 403 || r.status === 200, `unexpected ${r.status}`);
    if (r.status === 200) console.log('      \x1b[33m(open mode — set ADMIN_PASSWORD before prod)\x1b[0m');
  });

  // --- Summary --------------------------------------------------------------
  console.log(`\n${passed} passed, ${failures.length} failed\n`);
  if (failures.length) process.exit(1);
}

main().catch((e) => { console.error('Smoke run crashed:', e); process.exit(1); });
