/** @type {import('next').NextConfig} */
// `standalone` output is for the Docker image only (node server.js). On Vercel
// it must stay OFF so Vercel uses its native build — the Dockerfile sets
// DOCKER_BUILD=1 before `next build`.
const nextConfig = {
  output: process.env.DOCKER_BUILD === '1' ? 'standalone' : undefined,
  // Security headers on every response (defence in depth; the proxy is the
  // real gate). CSP intentionally allows Clerk + inline styles Next emits.
  async headers() {
    return [{
      source: '/:path*',
      headers: [
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
        { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
      ],
    }];
  },
};

export default nextConfig;
