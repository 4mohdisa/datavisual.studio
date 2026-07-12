# Decisions log

Every non-obvious call made during the overnight run, one line of rationale each.
Newest phase last.

## Phase 0 — commit the working tree
- Committed in 7 logical groups, **security fix first** (`fix(security)` → share → seo →
  auth → build → test → docs). Files interleave concerns, so groups are dependency-ordered
  whole files rather than per-hunk splits — HEAD is the full green tree either way.
- No `Co-Authored-By: Claude` trailer — Isa earlier had me strip Claude from the
  contributor history, so commits are authored solely by his git identity.

## Phase 1 — data safety
- **Atomic writes** (`backend/atomic.py`) for every persistent JSON state file (conversations,
  users, shares, sources, settings) via temp-file + fsync + `os.replace`. `analytics.jsonl`
  stays append-only (a single append can't tear the file meaningfully).
- **Per-conversation `threading.RLock`** (`storage.conversation_lock`) + `update_conversation`
  helper that re-reads under the lock. The async editor endpoints do their LLM work OUTSIDE
  the lock, then persist via a short synchronous re-read-and-merge — holding a threading lock
  across an `await` would stall the event loop, so that was deliberately avoided.
- `create_share` / `delete_share` now take the per-conversation lock (plus the shares-index
  lock) so a mint can't be clobbered by a concurrent dashboard save.
- **Key encryption at rest** (`backend/crypto.py`, Fernet). Stored form `enc:v1:<token>`;
  plaintext passes through `decrypt` so the boot migration is safe and idempotent. Keys are
  derived from `SECRET_KEY` via SHA-256 so any-length secret works.
- **`SECRET_KEY` policy:** present → use it; missing + `PROXY_SHARED_SECRET` set (prod signal)
  → refuse to start; missing in dev → generate one, append to `.env`, warn loudly.
- **Migration** runs in the FastAPI **lifespan** (not deprecated `on_event`), best-effort so a
  failure never blocks startup.
- Backup is a shell script + cron line (Hard Rule 2: no DB/queue). `data/` is the only copy.

### Assumptions to confirm with Isa
- Losing `SECRET_KEY` means users must re-enter their API keys (ciphertext becomes
  unreadable → treated as "no key"). This is degraded, not catastrophic — acceptable?
- The per-conversation lock is **in-process** and assumes a **single backend replica**. Scaling
  the backend horizontally would reintroduce lost-update races (and, later, double-fired
  scheduler jobs). Single replica is assumed throughout.
- Dashboard-chat now persists via re-read-and-merge of only `dashboard` + `title`. If a future
  field must survive a concurrent edit the same way, add it to that merge.
