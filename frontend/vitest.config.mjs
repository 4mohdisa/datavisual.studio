import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Component tests (Vitest + React Testing Library). Dev-only — never bundled
// into the app. jsdom gives components a DOM to render into.
export default defineConfig({
  plugins: [react()],
  // Automatic JSX runtime so components need no `import React` (matches Next).
  esbuild: { jsx: 'automatic' },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.js'],
    include: ['components/**/*.test.{js,jsx}', 'lib/**/*.test.{js,jsx}'],
    exclude: ['e2e/**', 'node_modules/**', '.next/**'],
    css: false,
  },
});
