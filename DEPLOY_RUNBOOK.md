# Deploy runbook — datavisual.studio

_Target tag: **v1.1.0-golive** (tag only once CI is watched green on GitHub — see HANDOFF.md).
Verify with a single command: `BASE=<url> make verify-deploy`._

Copy-pasteable steps to take `v1.0.2-correctness` live. Two supported topologies:

- **A) Split (recommended):** Vercel frontend + AWS backend. Polling pipeline + direct upload make
  this work within serverless limits.
- **B) Single box (fallback, already tested):** `docker compose up` on the AWS box serves both halves.
  If anything about the split misbehaves, use this — it needs none of the split-specific config.

Tag to deploy: `git checkout v1.0.2-correctness`.

---

## 0. Pre-flight

1. **Backend host / RAM.** *Assumption to confirm:* the backend runs on :8001 because :8000 is taken by
   another of Isa's apps on the existing EC2 (`54.153.178.13`, ap-southeast-2). That box already needed
   a swap file; this backend loads **pandas + xgboost + scikit-learn + Chromium**. **Check free RAM
   (`free -m`). If it's a t3.micro/small, run the backend on a separate instance** — an OOM kill mid-pipeline
   is the most likely failure.
2. Chromium must be present on the backend host (chart PNGs + PDF export): `sudo apt-get install -y chromium-browser`
   (the Docker image already installs it; `BROWSER_PATH` is set to `/usr/bin/chromium` there).
3. **Enforce IMDSv2 on the EC2 instance (do this regardless of the code fix).** The connector SSRF guard
   (`backend/ssrf.py`) blocks `169.254.169.254` in application code, but instance-level IMDSv2 is
   defence-in-depth: it makes the metadata endpoint unreachable without a signed token even if the code
   guard is ever bypassed. The code fix and the instance setting are independent — you want **both**.
   ```bash
   # Require IMDSv2 (token) + drop the hop limit so containers can't reach it:
   aws ec2 modify-instance-metadata-options --instance-id <id> \
     --http-tokens required --http-put-response-hop-limit 1 --http-endpoint enabled
   ```

## 1. Secrets (generate once)

```bash
openssl rand -hex 32   # → PROXY_SHARED_SECRET  (identical on BOTH halves)
openssl rand -hex 32   # → SECRET_KEY           (encrypts users' API keys — REQUIRED in prod)
openssl rand -hex 24   # → ADMIN_PASSWORD
```

- `SECRET_KEY` **must be set in prod** or the backend refuses to start. **`SECRET_KEY` travels WITH
  `data/` — back them up together.** It encrypts users' API keys at rest; a fresh key against a restored
  `data/` can't decrypt them. As of 0e the backend now **refuses to boot** on that mismatch (rather than
  silently showing every user as key-less), naming the fix in the error — restore the original key.
- `PROXY_SHARED_SECRET` must be **byte-identical** on Vercel and AWS.

## 2. Clerk

1. Create a **production** instance at dashboard.clerk.com; add your domain.
2. Copy the prod `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` + `CLERK_SECRET_KEY`.
3. The app locks itself (per-user scoping + route protection) the moment these are set.

---

## 3A. Backend on AWS (split)

```bash
git clone <repo> && cd datavisual.studio && git checkout v1.1.0-golive   # or `main` until it's tagged
cp .env.example .env
# set in .env: PROXY_SHARED_SECRET, SECRET_KEY, ADMIN_PASSWORD, FRONTEND_ORIGIN=https://<your-vercel-domain>
# optional: ALLOWED_ORIGINS=https://app.example.com,https://www.example.com  — CORS allowlist; when set it
#   REPLACES the localhost dev defaults so prod never trusts localhost. NEVER a wildcard. TRUSTED_PROXY_HOPS
#   defaults to 1 (rate limiter reads X-Forwarded-For that many hops in) — raise it if you add proxies.
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
- **Prefer `docker compose` over the bare `uv`+systemd path above** — the backend image installs
  Chromium (the fiddliest dependency) for you. `docker-compose.yml` now requires `SECRET_KEY` and
  wires `ALLOWED_ORIGINS` / `TRUSTED_PROXY_HOPS` / `NEXT_PUBLIC_BACKEND_ORIGIN`. To update: `git pull &&
  docker compose up -d --build`. The `./data` volume survives the rebuild.

## 3A-mem. There is NO database to install

`sqlalchemy`, `psycopg2-binary` and `pymysql` are in the backend dependencies **only for the
user-facing data connectors** — so a *user* can import a table from *their own* Postgres/MySQL/SQLite.
**They are not this application's storage.** All app state is JSON files under `data/`. Do **not**
provision, install, or point the backend at any database server — there is nothing to configure. Back
up `data/` and you have everything. (An app-owned Postgres is a separate, later project; it changes
nothing here.)

## 3A-oom. Memory headroom — measured, because an OOM kill is the likeliest failure

The instance already runs another app and has needed swap; this backend imports pandas/plotly and
spawns Chromium for PDF export. Measured resident memory (portable across hosts — same process, same
footprint):

| State | Resident | Notes |
|---|---|---|
| Backend idle | **~85 MB** | FastAPI; the heavy ML libs are lazy-imported |
| After normal use | ~130 MB | pandas + plotly resident |
| + a prediction run | ~+65 MB | scikit-learn + xgboost load only for ratings data (~200 MB total) |
| **PDF export (peak)** | **~480 MB** | backend ~135 MB **+ headless Chromium ~345 MB**, transient, freed after |

**Verdict:** steady state is small (~130–200 MB). The spike is a **PDF export: plan for ~500 MB of
transient headroom.** With **worker = 1** only one export runs at a time, so the peak doesn't multiply
— but on a box that's already busy, a ~350 MB Chromium burst is exactly what triggers OOM.

- **If free memory (with the other app running) is under ~600 MB, do NOT deploy here** without either a
  **swap file sized ≥1 GB** to absorb the transient Chromium spike, or a **larger / separate instance.**
  A deploy that works until someone exports a PDF is not a deploy.
- Confirm on the real box before inviting anyone: `free -m` with the other app running, then export a
  PDF while watching `while sleep 1; do free -m | awk 'NR==2{print $4" MB free"}'; done`.

## 3A-net. Reachability, TLS, the proxy chain, IMDSv2

- **Do not expose port 8001 to the internet** in the security group — let the TLS reverse proxy front
  it. The backend already 403s any request without `PROXY_SHARED_SECRET`, but the SG is the first wall.
- **`ALLOWED_ORIGINS` = your exact Vercel app origin(s), no wildcard.** When set it replaces the
  localhost defaults, so prod never trusts localhost.
- **`PROXY_SHARED_SECRET` identical on both halves** (backend `.env` and Vercel). Without it a
  publicly-reachable backend could be called directly with a forged identity header.
- **`TRUSTED_PROXY_HOPS` must equal the real chain** (reverse proxy = 1; + Cloudflare = 2). The rate
  limiter reads the client IP that many hops into `X-Forwarded-For`. Too low → a spoofed header bypasses
  the limiter; too high → everyone is throttled as one client. Verify against the actual chain.
- **Enforce IMDSv2** on the instance (`aws ec2 modify-instance-metadata-options --http-tokens required
  --http-endpoint enabled`) — defence in depth alongside the SSRF egress guard; the two are independent.

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
git checkout v1.0.2-correctness
cp .env.example .env   # set PROXY_SHARED_SECRET, SECRET_KEY, ADMIN_PASSWORD, and the Clerk keys
docker compose up -d --build
```
`docker-compose.yml` runs backend (with Chromium) + frontend. `data/` is a **host bind mount** — it
survives `docker compose down -v` (unlike a named volume). SSE streaming works here (no serverless
timeout), but polling is still the default and is fine.

---

## 5. First-boot checks (do ALL of these before announcing)

```bash
# ONE command — the whole pre-deploy checklist, pass/fail per line, against the live host.
# Runs the full smoke (health · the %2f trio · >5 MB upload · pipeline · share mint/revoke ·
# admin gate) + the SECRET_KEY restore drill, then prints the owner-run manual items.
BASE=https://app.example.com make verify-deploy
```

- [ ] `make verify-deploy` green against the live host (health, the `%2f` trio, **>5 MB upload**,
      pipeline, share mint/revoke, admin gate, restore-drill)
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

**A backup you have never restored is a hypothesis.** Prove the round-trip with `make restore-test`
(backs up a synthetic `data/`, restores it, boots the storage+crypto layer, asserts conversations load
**and** encrypted keys still decrypt). Run it after any change to backup/restore or key encryption, and
periodically (a monthly cron is cheap insurance):
```cron
# monthly 05:00 on the 1st — prove the backup format still restores + decrypts
0 5 1 * * cd /home/ubuntu/datavisual.studio && make restore-test >> /var/log/dvs-restore-test.log 2>&1
```

## 7. Operational notes

- **Single replica** is assumed: rate-limit buckets, the per-conversation lock, and (post-launch) the
  scheduler are all in-process. Do not run >1 backend replica without addressing these.
- Env knobs: `RATE_LIMIT_PER_MIN` / `RATE_LIMIT_BURST` (default 20), `GC_MAX_AGE_DAYS` (30).
- Users bring their own AI keys (the sidebar "AI keys" panel). Your server-side `OPENROUTER_API_KEY` is
  only used in open dev mode and is never spent on a signed-in user's request.
- Rollback: redeploy the previous tag (frontend on Vercel; `git checkout <tag> && docker compose up -d --build`
  or restart the systemd unit on AWS). `data/` is untouched by a rollback.

## 8. Environment variables (reference)

| Variable | Where | Required | What |
|---|---|---|---|
| `PROXY_SHARED_SECRET` | both | yes (prod) | Long random (`openssl rand -hex 32`), **byte-identical** on both halves. Backend 403s any `/api` request without it. |
| `SECRET_KEY` | backend | yes (prod) | Fernet key for API keys at rest. **Travels with `data/`** — back them up together; a mismatch refuses boot. |
| `ADMIN_PASSWORD` | backend | recommended | Gate for `/admin` (`X-Admin-Password`). Long + random. |
| `FRONTEND_ORIGIN` | backend | recommended | Public frontend URL; appended to CORS + used as the prod marker. |
| `ALLOWED_ORIGINS` | backend | optional | Comma-sep CORS allowlist; when set it REPLACES the localhost dev defaults. Never a wildcard. |
| `TRUSTED_PROXY_HOPS` | backend | optional | X-Forwarded-For hops the rate limiter trusts (default 1). |
| `BROWSER_PATH` | backend | optional | Chrome/Chromium path for chart PNGs + PDF (Docker sets `/usr/bin/chromium`). |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` / `CLERK_SECRET_KEY` | frontend | yes (auth) | Clerk identity; the app locks to per-user scoping the moment these are set. |
| `BACKEND_URL` | frontend | yes (split) | Server-to-server backend URL the Next proxy calls. |
| `NEXT_PUBLIC_BACKEND_ORIGIN` | frontend | split | Browser-reachable backend origin; enables >4.5 MB direct upload. |
| `NEXT_PUBLIC_SITE_URL` | frontend | recommended | Canonical URL for SEO/sitemap. |
