# Deploy runbook — datavisual.studio v1.0.0-launch

Copy-pasteable steps to take `v1.0.0-launch` live. Two supported topologies:

- **A) Split (recommended):** Vercel frontend + AWS backend. Polling pipeline + direct upload make
  this work within serverless limits.
- **B) Single box (fallback, already tested):** `docker compose up` on the AWS box serves both halves.
  If anything about the split misbehaves, use this — it needs none of the split-specific config.

Tag to deploy: `git checkout v1.0.0-launch`.

---

## 0. Pre-flight

1. **Backend host / RAM.** *Assumption to confirm:* the backend runs on :8001 because :8000 is taken by
   another of Isa's apps on the existing EC2 (`54.153.178.13`, ap-southeast-2). That box already needed
   a swap file; this backend loads **pandas + xgboost + scikit-learn + Chromium**. **Check free RAM
   (`free -m`). If it's a t3.micro/small, run the backend on a separate instance** — an OOM kill mid-pipeline
   is the most likely failure.
2. Chromium must be present on the backend host (chart PNGs + PDF export): `sudo apt-get install -y chromium-browser`
   (the Docker image already installs it; `BROWSER_PATH` is set to `/usr/bin/chromium` there).

## 1. Secrets (generate once)

```bash
openssl rand -hex 32   # → PROXY_SHARED_SECRET  (identical on BOTH halves)
openssl rand -hex 32   # → SECRET_KEY           (encrypts users' API keys — REQUIRED in prod)
openssl rand -hex 24   # → ADMIN_PASSWORD
```

- `SECRET_KEY` **must be set in prod** or the backend refuses to start. Losing it later means users
  re-enter their API keys (degraded, not catastrophic).
- `PROXY_SHARED_SECRET` must be **byte-identical** on Vercel and AWS.

## 2. Clerk

1. Create a **production** instance at dashboard.clerk.com; add your domain.
2. Copy the prod `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` + `CLERK_SECRET_KEY`.
3. The app locks itself (per-user scoping + route protection) the moment these are set.

---

## 3A. Backend on AWS (split)

```bash
git clone <repo> && cd datavisual.studio && git checkout v1.0.0-launch
cp .env.example .env
# set in .env: PROXY_SHARED_SECRET, SECRET_KEY, ADMIN_PASSWORD, FRONTEND_ORIGIN=https://<your-vercel-domain>
uv sync
sudo apt-get install -y chromium-browser
# systemd unit recommended (see below); quick start:
nohup uv run python -m backend.main > backend.log 2>&1 &   # ALWAYS from the project root
curl -s localhost:8001/health   # {"status":"ok",...}
```

`/etc/systemd/system/datavisual.service`:
```ini
[Unit]
Description=datavisual.studio backend
After=network.target
[Service]
WorkingDirectory=/home/ubuntu/datavisual.studio
Environment=PROXY_SHARED_SECRET=... SECRET_KEY=... ADMIN_PASSWORD=... FRONTEND_ORIGIN=https://app.example.com
ExecStart=/home/ubuntu/.local/bin/uv run python -m backend.main
Restart=always
[Install]
WantedBy=multi-user.target
```

- Put a TLS reverse proxy (Caddy/nginx) in front so the browser can reach the backend origin for
  **direct upload** (needed for >4.5 MB files on Vercel). Expose only the paths the browser needs;
  everything else is already gated by `PROXY_SHARED_SECRET`.
- The backend origin the browser hits becomes `NEXT_PUBLIC_BACKEND_ORIGIN` on Vercel (step 4A).

## 4A. Frontend on Vercel (split)

1. Import the repo. **Root Directory = `frontend`.** (vercel.json pins the Next framework.)
2. Env vars:
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`
   - `BACKEND_URL` = internal/proxy URL of the backend (server-to-server; e.g. `https://api.example.com`)
   - `NEXT_PUBLIC_BACKEND_ORIGIN` = browser-reachable backend origin (enables direct upload; usually same host)
   - `PROXY_SHARED_SECRET` (identical to AWS)
   - `NEXT_PUBLIC_SITE_URL` = `https://app.example.com` (SEO canonical/sitemap)
3. Deploy. Add the custom domain + TLS.
4. Do NOT set `DOCKER_BUILD` — Vercel uses its native build (standalone is Docker-only).

---

## 3B/4B. Single box (fallback)

```bash
git checkout v1.0.0-launch
cp .env.example .env   # set PROXY_SHARED_SECRET, SECRET_KEY, ADMIN_PASSWORD, and the Clerk keys
docker compose up -d --build
```
`docker-compose.yml` runs backend (with Chromium) + frontend. `data/` is a **host bind mount** — it
survives `docker compose down -v` (unlike a named volume). SSE streaming works here (no serverless
timeout), but polling is still the default and is fine.

---

## 5. First-boot checks (do ALL of these before announcing)

```bash
# health
curl -s https://api.example.com/health

# full smoke against the live host
BASE=https://app.example.com SPLIT=1 node scripts/smoke.mjs

# the 3 %2f traversal regressions must all be safe
curl -s -o /dev/null -w "%{http_code}\n" 'https://app.example.com/api/backend/api/public/..%2f..%2fapi%2fconversations'  # 400
```

- [ ] `/health` returns ok
- [ ] `make smoke` (SPLIT=1) green against the live host, including the **>5 MB upload**
- [ ] The 3 `%2f` regression checks are safe (400 / "unavailable" / legit share renders)
- [ ] Upload a real >5 MB file through the UI (exercises the direct-upload ticket)
- [ ] Run one full research pipeline with a real key (polling completes, dashboard appears)
- [ ] Mint and revoke a share link; the revoked link 404s
- [ ] `/admin` rejects a wrong password, accepts `ADMIN_PASSWORD`
- [ ] "Try it with sample data" builds a dashboard with **no key**

## 6. Backups + retention (set up BEFORE announcing)

`data/` is the entire database — there is no other copy.

```cron
# nightly 03:15 — back up data/ (keep 14, offsite to S3)
15 3 * * * cd /home/ubuntu/datavisual.studio && BACKUP_KEEP=14 BACKUP_S3_URI=s3://bucket/dvs ./scripts/backup.sh >> /var/log/dvs-backup.log 2>&1
# nightly 04:00 — GC orphaned uploads/exports (never touches conversations)
0 4 * * * cd /home/ubuntu/datavisual.studio && uv run python -m backend.gc >> /var/log/dvs-gc.log 2>&1
```

## 7. Operational notes

- **Single replica** is assumed: rate-limit buckets, the per-conversation lock, and (post-launch) the
  scheduler are all in-process. Do not run >1 backend replica without addressing these.
- Env knobs: `RATE_LIMIT_PER_MIN` / `RATE_LIMIT_BURST` (default 20), `GC_MAX_AGE_DAYS` (30).
- Users bring their own AI keys (the sidebar "AI keys" panel). Your server-side `OPENROUTER_API_KEY` is
  only used in open dev mode and is never spent on a signed-in user's request.
- Rollback: redeploy the previous tag (frontend on Vercel; `git checkout <tag> && docker compose up -d --build`
  or restart the systemd unit on AWS). `data/` is untouched by a rollback.
