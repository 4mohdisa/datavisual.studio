'use client';

import { useState } from 'react';
import { Download, Loader2, AlertCircle } from 'lucide-react';
import { api } from '../lib/api';

// Dashboard export with a real state machine (Night 3, Phase 1e):
// idle → generating → (download | error). Export spawns Chrome and renders
// images — it takes seconds. Silence, or a swallowed error, is a bug.
export default function ExportDashboardButton({ conversationId, className = '' }) {
  const [state, setState] = useState('idle'); // 'idle' | 'generating' | 'error'

  const run = async () => {
    if (state === 'generating') return;
    setState('generating');
    try {
      await api.exportReport(conversationId, null, 'dashboard');
      setState('idle');
    } catch {
      setState('error');
      setTimeout(() => setState('idle'), 5000);
    }
  };

  const label = state === 'generating' ? 'Generating…'
    : state === 'error' ? 'Export failed — retry'
    : 'Export';
  const Icon = state === 'generating' ? Loader2 : state === 'error' ? AlertCircle : Download;

  return (
    <button
      onClick={run}
      disabled={state === 'generating'}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-[var(--border-2)] text-[13px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--active)] transition disabled:opacity-60 ${state === 'error' ? 'text-[var(--danger)] border-[var(--danger)]' : ''} ${className}`}
    >
      <Icon size={14} strokeWidth={1.5} className={state === 'generating' ? 'animate-spin' : ''} /> {label}
    </button>
  );
}
