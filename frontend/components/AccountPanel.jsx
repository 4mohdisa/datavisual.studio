'use client';

import { useEffect, useState } from 'react';
import { KeyRound, LogOut } from 'lucide-react';
import { UserButton, useClerk, useUser } from '@clerk/nextjs';
import ApiKeysModal from './ApiKeysModal';
import { api } from '../lib/api';

// Sidebar footer: who's signed in, with full account management. The avatar
// menu (Clerk UserButton) handles profile/security; the explicit sign-out
// button makes logout one obvious click. Split into an inner component so the
// Clerk hooks are only mounted when a ClerkProvider exists (auth enabled).
//
// The app is BYO-keys: the "AI keys" row opens the per-user key modal, and it
// auto-opens once per session for signed-in users who haven't set a key yet.

function KeysRow({ autoPrompt }) {
  const [open, setOpen] = useState(false);
  const [keySet, setKeySet] = useState(null); // null = unknown

  useEffect(() => {
    let active = true;
    api.getAccountSettings()
      .then((s) => {
        if (!active) return;
        setKeySet(!!s.openrouter_key_set);
        if (autoPrompt && s.scope === 'user' && !s.openrouter_key_set) setOpen(true);
      })
      .catch(() => {});
    return () => { active = false; };
  }, [autoPrompt]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="w-full flex items-center gap-2 px-4 py-2 border-t border-[var(--border)] text-[12px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--active)] transition cursor-pointer"
      >
        <KeyRound size={13} strokeWidth={1.5} />
        <span className="flex-1 text-left">AI keys</span>
        {keySet === false && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--danger)]/15 text-[var(--danger)]">
            required
          </span>
        )}
      </button>
      {open && (
        <ApiKeysModal
          onClose={() => setOpen(false)}
          onSaved={(view) => setKeySet(!!view.openrouter_key_set)}
        />
      )}
    </>
  );
}

function ClerkAccount() {
  const { user, isLoaded } = useUser();
  const { signOut } = useClerk();

  if (!isLoaded) return <div className="h-[56px] border-t border-[var(--border)]" />;
  if (!user) return null; // middleware normally prevents this state

  const name = user.fullName || user.username || 'Account';
  const email = user.primaryEmailAddress?.emailAddress || '';

  return (
    <div>
      <KeysRow autoPrompt />
      <div className="p-3 border-t border-[var(--border)] flex items-center gap-3">
        <UserButton afterSignOutUrl="/" />
        <div className="flex-1 min-w-0">
          <div className="text-[12.5px] font-medium text-[var(--text)] truncate">{name}</div>
          {email && <div className="text-[11px] text-[var(--faint)] truncate">{email}</div>}
        </div>
        <button
          onClick={() => signOut({ redirectUrl: '/' })}
          title="Sign out"
          aria-label="Sign out"
          className="p-1.5 rounded-md text-[var(--muted)] hover:text-[var(--danger)] hover:bg-[var(--active)] transition"
        >
          <LogOut size={15} strokeWidth={1.5} />
        </button>
      </div>
    </div>
  );
}

export default function AccountPanel() {
  if (!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
    return (
      <div>
        <KeysRow autoPrompt={false} />
        <div className="px-4 py-3 border-t border-[var(--border)] text-[11px] text-[var(--faint)]">
          Dev mode — authentication off
        </div>
      </div>
    );
  }
  return <ClerkAccount />;
}
