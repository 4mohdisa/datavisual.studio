/** @type {import('next').NextConfig} */
// `standalone` output is for the Docker image only (node server.js). On Vercel
// it must stay OFF so Vercel uses its native build — the Dockerfile sets
// DOCKER_BUILD=1 before `next build`.
const nextConfig = {
  output: process.env.DOCKER_BUILD === '1' ? 'standalone' : undefined,
  // Security headers on every response (defence in depth; the proxy is the
  // real gate). CSP intentionally allows Clerk + inline styles Next emits.
  async headers() {
    // Permissive where the app genuinely needs it (Next inlines scripts/styles;
    // Plotly evals; Clerk loads over https), strict where it's free: object-src
    // none, base-uri self, frame-ancestors self (clickjacking). Tighten script-src
    // to nonces post-launch once verified against the live Clerk domain.
    const csp = [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'self'",
      "img-src 'self' data: blob: https:",
      "font-src 'self' data:",
      "style-src 'self' 'unsafe-inline'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:",
      "connect-src 'self' https: wss:",
      "frame-src 'self' https:",
    ].join('; ');
    return [{
      source: '/:path*',
      headers: [
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
        { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
        { key: 'Content-Security-Policy', value: csp },
      ],
    }];
  },
};

export default nextConfig;
