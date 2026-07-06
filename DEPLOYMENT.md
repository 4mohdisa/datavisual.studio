# Deploying datavisual.studio

Two pieces:

- **Backend** — FastAPI engine on port **8001**. Owns ALL data (users, uploads,
  dashboards, research, analytics) on its local disk under `data/`. This is the
  part you host on your AWS server.
- **Frontend** — Next.js app on port **3000**. Handles Clerk auth and proxies
  every API call to the backend with trusted identity headers. Host it anywhere
  (same box, Vercel, etc.).

There is no external database. Back up the backend's `data/` directory and you
have backed up everything.

## Option A — Docker Compose (single box, recommended)

```bash
cp .env.example .env            # fill in the values below
docker compose up -d --build
```

Set in `.env` (compose reads it):

| Variable | Required | What |
|---|---|---|
| `PROXY_SHARED_SECRET` | yes | Any long random string (`openssl rand -hex 32`). Same value is injected into both containers; the backend rejects requests without it. |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | yes | From dashboard.clerk.com → API keys. Baked into the frontend build. |
| `CLERK_SECRET_KEY` | yes | Same page. Server-side only. |
| `ADMIN_PASSWORD` | recommended | Password for `/admin` (users + analytics). Anyone with it gets in — make it long. |
| `FRONTEND_ORIGIN` | recommended | Public URL of the frontend, e.g. `https://app.example.com`. |

Data persists in `./data` on the host. Put a reverse proxy (Caddy/nginx) with
TLS in front of port 3000; port 8001 should NOT be exposed publicly — if it
must be, the proxy secret is what keeps strangers out.

## Option B — Backend on AWS, frontend elsewhere

### Backend (AWS box)

```bash
git clone <repo> && cd datavisual.studio
cp .env.example .env    # set PROXY_SHARED_SECRET, ADMIN_PASSWORD, FRONTEND_ORIGIN
uv sync                 # or: pip install -e .
# Chromium/Chrome is needed for chart images + PDF export:
sudo apt-get install -y chromium-browser   # Ubuntu; sets nothing else up
nohup uv run python -m backend.main > backend.log 2>&1 &   # or a systemd unit
```

Always start from the **project root** (module imports require it).

Suggested systemd unit (`/etc/systemd/system/datavisual.service`):

```ini
[Unit]
Description=datavisual.studio backend
After=network.target

[Service]
WorkingDirectory=/home/ubuntu/datavisual.studio
ExecStart=/home/ubuntu/.local/bin/uv run python -m backend.main
Restart=always

[Install]
WantedBy=multi-user.target
```

### Frontend

Set in `frontend/.env.local` (see `frontend/.env.local.example`):

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` / `CLERK_SECRET_KEY`
- `BACKEND_URL=http://<your-aws-ip>:8001` (private network/VPN if possible)
- `PROXY_SHARED_SECRET` — same value as the backend's

Then `npm run build && npm start`, or deploy to Vercel with those env vars.

## How auth and keys work in production

- Clerk authenticates the browser; the Next proxy forwards identity headers
  plus `X-Proxy-Secret`. The backend maps the Clerk id to its own `u_<hex>` id
  in `data/users.json`.
- **Users bring their own AI keys** (OpenRouter required, Gemini optional),
  saved per-account from the sidebar "AI keys" panel. Your server-side
  `OPENROUTER_API_KEY` is only used in open dev mode (no Clerk configured) —
  signed-in users can never spend it.
- `/admin` shows users + analytics to anyone who enters `ADMIN_PASSWORD` —
  it is deliberately independent of Clerk sign-in.

## Checklist

- [ ] `PROXY_SHARED_SECRET` set to the same value on both sides
- [ ] Clerk keys set (frontend) — app locks itself the moment they exist
- [ ] `ADMIN_PASSWORD` set to a long random value
- [ ] `FRONTEND_ORIGIN` points at the public frontend URL
- [ ] Chromium/Chrome present on the backend host (PDF + chart export)
- [ ] `data/` on a persistent disk and in your backup rotation
- [ ] Port 8001 not publicly exposed (or firewalled to the frontend host)
