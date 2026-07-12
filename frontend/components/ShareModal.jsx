'use client';

import { useEffect, useState } from 'react';
import { Check, Copy, Globe, Loader2, Link2Off } from 'lucide-react';
import Modal from './ui/Modal';
import Button from './ui/Button';
import { api } from '../lib/api';

// Toggle a public read-only link for a dashboard or research report. Opening
// the modal creates the link immediately (idempotent) so it's ready to copy;
// "Stop sharing" revokes it. The parent is told the current share_id so it can
// reflect the shared/not-shared state in its header.
export default function ShareModal({ conversationId, shareId: initialShareId, onClose, onChange }) {
  const [shareId, setShareId] = useState(initialShareId || null);
  const [busy, setBusy] = useState(!initialShareId);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  const url = shareId && typeof window !== 'undefined' ? `${window.location.origin}/share/${shareId}` : '';

  useEffect(() => {
    if (initialShareId) return; // already shared — nothing to create
    let active = true;
    api.shareConversation(conversationId)
      .then((r) => { if (active) { setShareId(r.share_id); onChange?.(r.share_id); } })
      .catch((e) => { if (active) setError(e.message || 'Could not create a share link'); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch { /* clipboard blocked — user can select the field */ }
  };

  const stopSharing = async () => {
    setBusy(true);
    try {
      await api.unshareConversation(conversationId);
      setShareId(null);
      onChange?.(null);
      onClose();
    } catch (e) {
      setError(e.message || 'Could not revoke the link');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Share this view" onClose={onClose} width="w-[480px]">
      <p className="text-[12.5px] text-[var(--muted)] -mt-2 mb-4 leading-relaxed">
        Anyone with the link can view this as a live, read-only dashboard — no sign-in.
        They can&apos;t edit it, and your data source and AI keys are never exposed.
      </p>

      {error && <div className="mb-3 text-[13px] text-[var(--danger)]">{error}</div>}

      {busy && !shareId ? (
        <div className="flex items-center gap-2 text-[13px] text-[var(--muted)] py-3">
          <Loader2 size={15} className="animate-spin" /> Creating your link…
        </div>
      ) : shareId ? (
        <>
          <div className="flex gap-2">
            <div className="flex-1 flex items-center gap-2 min-w-0 bg-[var(--surface-input)] border border-[var(--border-2)] rounded-md px-3 py-2">
              <Globe size={14} strokeWidth={1.5} className="shrink-0 text-[var(--accent)]" />
              <input
                readOnly
                value={url}
                onFocus={(e) => e.target.select()}
                className="flex-1 min-w-0 bg-transparent text-[13px] text-[var(--text)] outline-none"
              />
            </div>
            <Button variant="primary" onClick={copy} className="shrink-0">
              {copied ? <Check size={15} strokeWidth={1.5} /> : <Copy size={15} strokeWidth={1.5} />}
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>

          <div className="flex items-center justify-between mt-5">
            <a href={url} target="_blank" rel="noreferrer" className="text-[12.5px] text-[var(--accent)] hover:underline">
              Open the shared view ↗
            </a>
            <button
              onClick={stopSharing}
              disabled={busy}
              className="inline-flex items-center gap-1.5 text-[12.5px] text-[var(--muted)] hover:text-[var(--danger)] transition disabled:opacity-50"
            >
              <Link2Off size={14} strokeWidth={1.5} /> Stop sharing
            </button>
          </div>
        </>
      ) : null}
    </Modal>
  );
}
