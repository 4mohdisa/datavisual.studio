// Web app manifest — installability + theming metadata. The icon reuses the
// generated /icon route so there are no binary asset files to maintain.
export default function manifest() {
  return {
    name: 'datavisual.studio',
    short_name: 'datavisual',
    description: 'Living dashboards and AI-researched reports from your data.',
    start_url: '/studio',
    display: 'standalone',
    background_color: '#0f0f0f',
    theme_color: '#0f0f0f',
    icons: [{ src: '/icon', sizes: '48x48', type: 'image/png' }],
  };
}
