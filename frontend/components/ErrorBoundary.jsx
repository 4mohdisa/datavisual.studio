'use client';

import { Component } from 'react';
import { api } from '../lib/api';

// 7.2 — top-level error boundary. On any unhandled render error, shows a clean
// recovery screen and logs the error to the backend (best-effort).
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    try {
      api.logError({
        message: String(error?.message || error),
        stack: String(error?.stack || ''),
        component_stack: String(info?.componentStack || ''),
      });
    } catch {
      /* logging is best-effort */
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen w-screen flex flex-col items-center justify-center gap-4 bg-[var(--background)] text-[var(--text)] text-center px-6">
          <h1 className="text-xl font-semibold">Something went wrong.</h1>
          <p className="text-[var(--muted)] text-sm">The error has been logged.</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-md bg-white text-black text-sm font-medium hover:bg-[oklch(0.88_0_0)] transition"
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
