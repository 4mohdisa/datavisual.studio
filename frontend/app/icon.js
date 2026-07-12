import { ImageResponse } from 'next/og';

// Generated favicon — a small bar-chart glyph in the brand accent. Next wires
// this in as the tab icon automatically, so no .ico asset is needed.
export const runtime = 'nodejs';
export const size = { width: 48, height: 48 };
export const contentType = 'image/png';

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'center',
          gap: 4,
          background: '#0f0f0f',
          borderRadius: 10,
          padding: 11,
        }}
      >
        <div style={{ width: 7, height: 14, borderRadius: 2, background: '#4a90e2', display: 'flex' }} />
        <div style={{ width: 7, height: 24, borderRadius: 2, background: '#9b59e0', display: 'flex' }} />
        <div style={{ width: 7, height: 19, borderRadius: 2, background: '#5cb85c', display: 'flex' }} />
      </div>
    ),
    { ...size },
  );
}
