'use client';

import { useEffect, useState } from 'react';
import { ArrowLeft, Activity, KeyRound, LayoutDashboard, Lock, Search, Users } from 'lucide-react';
import Link from 'next/link';
import Input from './ui/Input';
import Button from './ui/Button';
import { api } from '../lib/api';

// Super-admin view over the local data directory: user registry, per-user
// activity and the analytics event log. Gated by a single password
// (ADMIN_PASSWORD in the backend .env) — no account needed. The password is
// kept in sessionStorage so a refresh doesn't re-prompt.

const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString() : '—');

function StatCard({ icon: Icon, label, value }) {
  return (
    <div className="rounded-xl border border-[var(--border-2)] bg-[var(--raised)] p-5 flex items-center gap-4">
      <div className="w-10 h-10 rounded-lg bg-[oklch(0.2_0.05_250)] flex items-center justify-center shrink-0">
        <Icon size={18} strokeWidth={1.5} className="text-[var(--accent)]" />
      </div>
      <div>
        <div className="text-[22px] font-semibold text-[var(--text)] leading-tight">{value}</div>
        <div className="text-[12px] text-[var(--muted)]">{label}</div>
      </div>
    </div>
  );
}

export default function AdminPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [locked, setLocked] = useState(false);
  const [password, setPassword] = useState('');
  const [wrong, setWrong] = useState(false);

  const load = (pw) => {
    api.adminOverview(pw)
      .then((d) => {
        setData(d);
        setLocked(false);
        setWrong(false);
        if (pw) sessionStorage.setItem('admin_password', pw);
      })
      .catch((e) => {
        if (e.message === 'forbidden') {
          setLocked(true);
          setWrong(!!pw); // a rejected attempt, not the first prompt
          sessionStorage.removeItem('admin_password');
        } else {
          setError('Could not load analytics.');
        }
      });
  };

  useEffect(() => {
    load(sessionStorage.getItem('admin_password') || '');
  }, []);

  if (locked && !data) {
    return (
      <div className="h-screen flex flex-col items-center justify-center gap-4 bg-[var(--background)] px-6">
        <div className="w-11 h-11 rounded-xl bg-[oklch(0.2_0.05_250)] flex items-center justify-center">
          <Lock size={19} strokeWidth={1.5} className="text-[var(--accent)]" />
        </div>
        <div className="text-[15px] font-medium text-[var(--text)]">Admin access</div>
        <form
          className="flex gap-2 w-full max-w-[340px]"
          onSubmit={(e) => { e.preventDefault(); if (password.trim()) load(password.trim()); }}
        >
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Admin password"
            autoFocus
          />
          <Button type="submit" variant="primary" className="shrink-0">Enter</Button>
        </form>
        {wrong && <div className="text-[12.5px] text-[var(--danger)]">Wrong password.</div>}
        <Link href="/studio" className="text-[13px] text-[var(--muted)] hover:text-[var(--text)]">← Back to the studio</Link>
      </div>
    );
  }

  const totals = data?.totals || {};
  const activity = data?.activity || [];
  const maxDay = Math.max(1, ...activity.map((d) => d.events));
  const events = Object.entries(data?.events_by_kind || {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="h-screen overflow-y-auto bg-[var(--background)]">
      <div className="max-w-[1060px] mx-auto px-8 py-10 flex flex-col gap-8">
        <div className="flex items-center gap-3">
          <Link href="/studio" title="Back to studio" className="p-1.5 rounded-md text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--active)] transition">
            <ArrowLeft size={17} strokeWidth={1.5} />
          </Link>
          <div>
            <h1 className="text-[22px] font-semibold text-[var(--text)] m-0">Admin</h1>
            <p className="text-[12.5px] text-[var(--muted)] m-0">Users and project analytics, straight from the data directory.</p>
          </div>
        </div>

        {error && error !== 'forbidden' && <div className="text-[13px] text-[var(--danger)]">{error}</div>}
        {!data && !error && <div className="text-[13px] text-[var(--muted)]">Loading…</div>}

        {data && (
          <>
            {/* Totals */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <StatCard icon={Users} label="Users" value={totals.users ?? 0} />
              <StatCard icon={Search} label="Research runs" value={totals.research ?? 0} />
              <StatCard icon={LayoutDashboard} label="Dashboards" value={totals.dashboards ?? 0} />
              <StatCard icon={Activity} label="Events tracked" value={totals.events ?? 0} />
            </div>

            {/* 14-day activity */}
            <div className="rounded-xl border border-[var(--border-2)] bg-[var(--raised)] p-5">
              <div className="text-[13px] font-medium text-[var(--text)] mb-4">Activity — last 14 days</div>
              <div className="flex items-end gap-1.5 h-[90px]">
                {activity.map((d) => (
                  <div key={d.day} className="flex-1 flex flex-col items-center gap-1" title={`${d.day}: ${d.events} events`}>
                    <div
                      className="w-full rounded-t bg-[var(--accent)]/70 min-h-[2px]"
                      style={{ height: `${(d.events / maxDay) * 80}px` }}
                    />
                    <div className="text-[9px] text-[var(--faint)]">{d.day.slice(8)}</div>
                  </div>
                ))}
              </div>
              {events.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-4">
                  {events.map(([kind, count]) => (
                    <span key={kind} className="text-[11px] px-2 py-1 rounded-full bg-[var(--surface-input)] border border-[var(--border-2)] text-[var(--muted)]">
                      {kind}: <span className="text-[var(--text)] font-medium">{count}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Users table */}
            <div className="rounded-xl border border-[var(--border-2)] bg-[var(--raised)] overflow-hidden">
              <div className="text-[13px] font-medium text-[var(--text)] px-5 pt-4 pb-3">Users</div>
              <div className="overflow-x-auto">
                <table className="w-full text-[12.5px] border-collapse">
                  <thead>
                    <tr className="text-left text-[var(--faint)] border-t border-[var(--border)]">
                      {['Name', 'Email', 'Joined', 'Keys', 'Research', 'Dashboards', 'Events', 'Last active'].map((h) => (
                        <th key={h} className="px-5 py-2 font-medium whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(data.users || []).map((u) => (
                      <tr key={u.id} className="border-t border-[var(--border)] text-[var(--text)]">
                        <td className="px-5 py-2.5 whitespace-nowrap">{u.name || '—'}</td>
                        <td className="px-5 py-2.5 text-[var(--muted)] whitespace-nowrap">{u.email || '—'}</td>
                        <td className="px-5 py-2.5 text-[var(--muted)] whitespace-nowrap">{fmtDate(u.created_at)}</td>
                        <td className="px-5 py-2.5">
                          {u.has_keys
                            ? <span className="inline-flex items-center gap-1 text-[oklch(0.75_0.15_150)]"><KeyRound size={12} strokeWidth={1.5} /> set</span>
                            : <span className="text-[var(--faint)]">none</span>}
                        </td>
                        <td className="px-5 py-2.5">{u.research}</td>
                        <td className="px-5 py-2.5">{u.dashboards}</td>
                        <td className="px-5 py-2.5">{u.events}</td>
                        <td className="px-5 py-2.5 text-[var(--muted)] whitespace-nowrap">{fmtDate(u.last_active)}</td>
                      </tr>
                    ))}
                    {(data.users || []).length === 0 && (
                      <tr className="border-t border-[var(--border)]">
                        <td colSpan={8} className="px-5 py-6 text-center text-[var(--faint)]">
                          No users yet — accounts appear here after their first sign-in.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
