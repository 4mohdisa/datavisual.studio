'use client';
// First-party product analytics (Overnight Plan 2, 1c). The anon_id cookie is
// set on first visit and survives signup, so a landing visit can be stitched to
// the account it became (the `identify` event). No third-party trackers; events
// post to our own /api/events route. Props are metadata only — never data.

const ANON_KEY = 'dv_anon_id';
const SESSION_KEY = 'dv_session_id';
const FIRST_TOUCH_KEY = 'dv_first_touch';
const COOKIE_DAYS = 365;

function uid(prefix) {
  const rand =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID().replace(/-/g, '')
      : Math.random().toString(16).slice(2) + Date.now().toString(16);
  return prefix + rand.slice(0, 20);
}

function getCookie(name) {
  if (typeof document === 'undefined') return null;
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : null;
}

function setCookie(name, value, days) {
  if (typeof document === 'undefined') return;
  const exp = new Date(Date.now() + days * 864e5).toUTCString();
  // First-party, JS-readable (we need it client-side), lax so it survives the
  // signup redirect. Not a security token — just a stable visitor id.
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${exp}; path=/; SameSite=Lax`;
}

// The anon id: cookie first (survives across tabs + the signup redirect), with
// localStorage as a fallback mirror. Created + persisted on first read.
export function anonId() {
  if (typeof window === 'undefined') return null;
  let id = getCookie(ANON_KEY);
  if (!id) {
    try { id = localStorage.getItem(ANON_KEY); } catch { /* ignore */ }
  }
  if (!id) id = uid('a_');
  setCookie(ANON_KEY, id, COOKIE_DAYS); // refresh expiry each load
  try { localStorage.setItem(ANON_KEY, id); } catch { /* ignore */ }
  return id;
}

function sessionId() {
  if (typeof window === 'undefined') return null;
  try {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) { id = uid('s_'); sessionStorage.setItem(SESSION_KEY, id); }
    return id;
  } catch {
    return uid('s_');
  }
}

// First-touch attribution only: capture UTM + referrer on the very first visit
// and never overwrite, so we attribute the signup to the campaign that started it.
function firstTouch() {
  if (typeof window === 'undefined') return {};
  try {
    const saved = localStorage.getItem(FIRST_TOUCH_KEY);
    if (saved) return JSON.parse(saved);
    const q = new URLSearchParams(window.location.search);
    const utm = {};
    for (const k of ['source', 'medium', 'campaign']) {
      const v = q.get('utm_' + k);
      if (v) utm[k] = v;
    }
    const ft = { utm, referrer: document.referrer || null };
    localStorage.setItem(FIRST_TOUCH_KEY, JSON.stringify(ft));
    return ft;
  } catch {
    return {};
  }
}

export function track(event, props) {
  if (typeof window === 'undefined') return;
  try {
    const ft = firstTouch();
    const body = JSON.stringify({
      event,
      anon_id: anonId(),
      session_id: sessionId(),
      path: window.location.pathname,
      referrer: ft.referrer || null,
      utm: ft.utm && Object.keys(ft.utm).length ? ft.utm : null,
      props: props || null,
    });
    // keepalive so the beacon survives a CTA navigation.
    fetch('/api/events', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => {});
  } catch { /* analytics must never break the app */ }
}

// The anon → user stitch. Called once per user after sign-in.
export function identify(userId) {
  if (userId) track('identify', { user_id: userId });
}
