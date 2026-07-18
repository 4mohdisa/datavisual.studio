# Contributing

Thanks for looking. This is a solo project but issues and PRs are welcome.

## Run it locally

```bash
make install     # backend (uv) + frontend (npm) deps
make dev         # backend :8001 + frontend :3000 together
```

With no Clerk keys the app runs in **open dev mode** (no sign-in). See the
[README](README.md#quick-start) for the full quickstart and [ARCHITECTURE.md](ARCHITECTURE.md) for
how the pieces fit.

## The test bar

Everything must be green before a PR merges — CI runs the lot on every push:

```bash
make test            # backend pytest (hermetic) + frontend production build
make test-backend    # pytest only
make e2e-install     # one-time: Playwright chromium
make e2e             # browser e2e incl. the axe accessibility scan
cd frontend && npx vitest run   # component + lib unit tests
```

New non-trivial logic ships with a test. Bug fixes ship with a test that fails before the fix.

## Invariants a contributor must not break

These are the load-bearing decisions (fuller list in [ARCHITECTURE.md](ARCHITECTURE.md)):

1. **The LLM emits query specs; deterministic Python computes.** The model never does arithmetic.
   Every number in an answer must be defensible from the executed result (`answer_guard.py`).
2. **Strict public allowlist.** The public share/demo payload is an explicit allowlist — every new
   field on a dashboard record is owner-only until a test proves it's safe to expose.
3. **No `%2f` interpolation** of decoded route params into fetch URLs (auth-bypass class).
4. **BYO keys.** The owner's key is never spent on a user's request; keys are encrypted at rest.
5. **Accessibility is a property of the component, not a later audit** — charts keep their text
   alternative, interactive elements stay keyboard-operable, axe stays clean.
6. **Single replica.** In-process locks/limiter/nonces — don't add state that assumes otherwise
   without externalising it.

## PRs

Conventional-commit style messages, one focused change per PR, and describe what you verified.
Deleting code needs a zero-reference check in the PR description.
