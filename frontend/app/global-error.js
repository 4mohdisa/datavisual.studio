'use client';

// Catches errors in the root layout itself. It REPLACES the layout, so it must
// render its own <html>/<body> and can't rely on globals.css classes — inline
// styles only, tuned to the dark theme.
export default function GlobalError({ error, reset }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, background: '#0f0f0f', color: '#eaeaea', fontFamily: 'system-ui, sans-serif' }}>
        <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, textAlign: 'center', padding: 24 }}>
          <div style={{ fontSize: 15, fontWeight: 600 }}>The app hit a fatal error</div>
          <p style={{ fontSize: 13, color: '#a3a3a3', maxWidth: 380, margin: 0 }}>
            Please reload. If it keeps happening, come back in a few minutes.
          </p>
          <button
            onClick={() => reset()}
            style={{ padding: '8px 16px', borderRadius: 6, border: 'none', background: '#fafafa', color: '#0f0f0f', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
