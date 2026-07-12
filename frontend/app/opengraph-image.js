import { ImageResponse } from 'next/og';

// Default social-share card for every route (shared links, landing, legal).
// Generated at request time from system fonts — no asset files to ship.
export const runtime = 'nodejs';
export const alt = 'datavisual.studio — living dashboards & AI-researched reports';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

const BARS = [
  { h: 150, c: '#4a90e2' },
  { h: 96, c: '#9b59e0' },
  { h: 210, c: '#5cb85c' },
  { h: 130, c: '#e3c34d' },
  { h: 180, c: '#4a90e2' },
];

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          background: 'linear-gradient(135deg, #0d0d0f 0%, #12131a 55%, #0d0d12 100%)',
          padding: '72px 80px',
          fontFamily: 'sans-serif',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ width: 30, height: 30, borderRadius: 8, background: '#4a90e2', display: 'flex' }} />
          <div style={{ fontSize: 30, color: '#e8e8ea', fontWeight: 600 }}>datavisual.studio</div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ fontSize: 62, lineHeight: 1.08, color: '#f4f4f6', fontWeight: 700, maxWidth: 900, display: 'flex' }}>
            Dashboards that track your situation and tell you what changed
          </div>
          <div style={{ fontSize: 27, color: '#9aa0ac', maxWidth: 820, display: 'flex' }}>
            Live data + a council of AI models researching the web — on one screen, always current.
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, height: 210 }}>
            {BARS.map((b, i) => (
              <div key={i} style={{ width: 54, height: b.h, borderRadius: 10, background: b.c, opacity: 0.9, display: 'flex' }} />
            ))}
          </div>
          <div style={{ fontSize: 22, color: '#6b7280', display: 'flex' }}>Free · bring your own AI keys</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
