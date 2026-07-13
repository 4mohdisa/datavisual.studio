"""FastAPI backend for Datavisual.studio."""

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
import os
import re
from datetime import datetime
from pathlib import Path

from . import storage
from .ratelimit import RateLimiter
from .users import current_user_ctx, update_user_settings, user_from_request, user_settings
from .council import generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings
from . import config
from .config import DEBUG
from .data_analysis import analyse_file
from .research import plan_searches, run_single_search, combine_findings, detect_event_status, extract_confirmed_facts
from .report_builder import build_enriched_prompt, build_report, extract_predictions
from .prediction_engine import (
    build_dataset_models,
    extract_internet_probs,
    extract_council_probs,
    compute_prediction,
    predictions_to_table,
    probs_to_prediction_results,
    format_chairman_prediction_block,
    generate_prediction_charts,
    build_match_features,
    train_xgboost_model,
    run_monte_carlo_xgboost,
    xgboost_available,
    xgboost_feature_importance,
)


# ---------------------------------------------------------------------------
# Activity events — granular SSE events for the frontend Activity Panel.
# These are ADDITIONS; all existing event types remain unchanged.
# ---------------------------------------------------------------------------

_CHART_LABELS = {
    "line": "Line chart",
    "bar": "Bar chart",
    "scatter": "Scatter plot",
    "histogram": "Histogram",
    "heatmap": "Heatmap",
}


def _activity_payload(event: str, detail: str, reasoning: str = "", links: list | None = None) -> dict:
    """Build an activity event payload. `reasoning` is a 1–2 sentence first-person
    description of what the AI is doing/why, shown in the Research Activity tab."""
    return {
        "type": "activity",
        "event": event,
        "detail": detail,
        "reasoning": reasoning,
        "links": links or [],
        "ts": datetime.utcnow().isoformat() + "Z",
    }


def _model_display(model: str) -> str:
    return model.split("/")[-1]

# Monte-Carlo tournament runs for the dataset ELO baseline. Surfaced verbatim in
# the council prompt, the prediction charts, and the frontend explainer box.
_N_SIMULATIONS = 10000

UPLOADS_DIR = "data/uploads"
EXPORTS_DIR = "data/exports"

Path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
Path(EXPORTS_DIR).mkdir(parents=True, exist_ok=True)

from contextlib import asynccontextmanager


def _assert_identity_trust_safe() -> None:
    """Boot guard (Phase 0g). The backend trusts `x-clerk-user-id` from the
    proxy to scope every user's data. Without PROXY_SHARED_SECRET the
    proxy-secret guard is a no-op, so anyone who can reach the backend could
    forge that header and impersonate any user. In a deployed environment
    (FRONTEND_ORIGIN set) refuse to start rather than trust the internet's idea
    of who the caller is. docker-compose already requires the secret; this
    catches a direct/bare run that skipped it."""
    if os.getenv("FRONTEND_ORIGIN") and not os.getenv("PROXY_SHARED_SECRET"):
        raise RuntimeError(
            "PROXY_SHARED_SECRET is required in production. FRONTEND_ORIGIN is set "
            "(a deployed environment) but PROXY_SHARED_SECRET is not — the backend "
            "would trust a forgeable X-Clerk-User-Id header from anyone and allow "
            "user impersonation. Generate one (`openssl rand -hex 32`) and set it "
            "identically on the backend and the Next proxy, then restart."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Boot guards that MUST stop the server (never swallowed): a production
    # identity-trust misconfig (0g) and an undecryptable key set (0e).
    _assert_identity_trust_safe()
    from .crypto import verify_key_decryptable
    verify_key_decryptable()
    # Encrypt any plaintext BYO API keys on boot (idempotent). Best-effort — a
    # failure here must never stop the API from starting.
    try:
        from .crypto import migrate_user_keys
        migrate_user_keys()
    except Exception as e:  # pragma: no cover
        print(f"⚠️  key migration skipped: {e}")
    # Fail interrupted pipelines from a previous process so their pollers stop.
    n = _sweep_orphaned_jobs()
    if n:
        print(f"↻ swept {n} interrupted pipeline(s) to error on boot")
    yield


app = FastAPI(
    title="Datavisual.studio API",
    version="1.0.0",
    description="Multi-model AI prediction platform API",
    lifespan=lifespan,
)

# Compress responses (5.2) — large report/dataset payloads shrink significantly.
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS (0j). Env-driven allowlist, NEVER a wildcard. In prod set ALLOWED_ORIGINS
# (comma-separated) to your exact origins; it fully replaces the dev defaults so
# localhost isn't trusted in production. Otherwise fall back to the dev origins
# plus FRONTEND_ORIGIN. Only /api/upload-direct is actually hit cross-origin by
# the browser; everything else goes through the same-origin Next proxy.
_env_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
_allowed_origins = _env_origins or [o for o in [
    "http://localhost:5173", "http://localhost:3000", os.getenv("FRONTEND_ORIGIN"),
] if o]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    """Baseline security response headers on the API (the browser mostly talks to
    the Next proxy, which adds its own; these cover direct-to-backend calls like
    the upload carve-out)."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


@app.middleware("http")
async def _proxy_secret_guard(request: Request, call_next):
    """When PROXY_SHARED_SECRET is set, only the Next.js proxy (which attaches
    the matching X-Proxy-Secret header) may reach the API — so a publicly
    hosted backend isn't an open endpoint. Unset = open local dev."""
    secret = os.getenv("PROXY_SHARED_SECRET")
    # /api/upload-direct is the deliberate browser→backend carve-out: it carries
    # no proxy secret (it never goes through the proxy) and is gated by its own
    # HMAC upload ticket instead.
    if secret and request.url.path.startswith("/api") and request.url.path != "/api/upload-direct":
        if request.headers.get("x-proxy-secret") != secret:
            return JSONResponse({"detail": "Forbidden"}, status_code=403)
    # Bind the request identity for the whole call tree (incl. SSE generators),
    # so per-user AI keys resolve inside every deep LLM call.
    token = current_user_ctx.set(user_from_request(request))
    try:
        return await call_next(request)
    finally:
        current_user_ctx.reset(token)


# Rate limiter for the expensive endpoints (per-user AND per-IP). Single replica.
_rate_limiter = RateLimiter(
    capacity=int(os.getenv("RATE_LIMIT_BURST", "20")),
    refill_per_min=int(os.getenv("RATE_LIMIT_PER_MIN", "20")),
)
_RATE_LIMITED = ("/api/analyse", "/api/upload", "/api/upload-direct", "/api/connect", "/api/sample-dashboard")

# Behind a proxy (Caddy/Cloudflare/Vercel) every request shares one socket IP,
# so keying the limiter on the socket rate-limits the whole userbase as one
# client. Trust the last N X-Forwarded-For entries (the ones our own proxies
# appended); everything left of them is client-supplied and spoofable.
_TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "1"))


def _client_ip(request: Request) -> str:
    """Real client IP for rate-limiting, XFF-aware. With hops=1 the rightmost
    XFF entry (appended by our single trusted proxy) is authoritative; a
    client-forged prefix is ignored. hops=0 → no proxy, trust only the socket."""
    if _TRUSTED_PROXY_HOPS > 0:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            if parts:
                # The entry our outermost trusted proxy appended sits `hops` from
                # the right; clamp for a shorter-than-expected chain.
                return parts[max(0, len(parts) - _TRUSTED_PROXY_HOPS)]
    return request.client.host if request.client else "?"


@app.middleware("http")
async def _rate_limit(request: Request, call_next):
    path = request.url.path
    # Status polling (GET /api/conversations/{id}/status, ~40/min for a long
    # pipeline) is deliberately NOT here and the limiter fires on POST only, so
    # a running analysis can never rate-limit its own poller. Guarded by a test.
    limited = (path.endswith("/chat") and path.startswith("/api/dashboard")) or path in _RATE_LIMITED
    if request.method == "POST" and limited:
        ip = _client_ip(request)
        user = request.headers.get("x-clerk-user-id") or "anon"
        if not _rate_limiter.check(f"u:{user}", f"ip:{ip}"):
            return JSONResponse({"detail": "Too many requests — slow down a moment."}, status_code=429)
    return await call_next(request)


def _owned(conversation_id: str, http_request: Request) -> dict:
    """Load a conversation and enforce per-user ownership.

    With an authenticated identity present (forwarded by the proxy), only the
    owner sees the record — anything else, including ownerless legacy records,
    is a 404 so ids can't be probed. Without identity (open dev mode) all
    records are visible, matching the pre-auth behaviour."""
    conv = storage.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    user = user_from_request(http_request)
    if user is not None and conv.get("owner_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _stamp_owner(conv: dict, http_request: Request) -> None:
    """Record our internal user id on a newly created conversation."""
    user = user_from_request(http_request)
    if user is not None:
        conv["owner_id"] = user["id"]


from . import analytics
_ANALYTICS_PATH = analytics.ANALYTICS_PATH  # back-compat alias (tests patch both)


def _track(http_request: Request, event: str, props: dict | None = None) -> None:
    """Append one product-analytics event (1c). anon_id/session_id/path come
    from headers `lib/api.js` attaches, so server-side events stitch to the same
    first-party visitor as the client-side funnel events. Best-effort."""
    try:
        user = user_from_request(http_request)
        h = http_request.headers
        analytics.record_event(
            event,
            user_id=user["id"] if user else None,
            anon_id=h.get("x-anon-id"),
            session_id=h.get("x-session-id"),
            path=h.get("x-page-path") or h.get("referer"),
            props=props,
        )
    except Exception:
        pass


def _is_first_dashboard(user_id: str | None) -> bool:
    """True if this user has no dashboard-mode conversation yet — for the
    `first_dashboard_created` activation event. Anonymous (open dev) → skip."""
    if not user_id:
        return False
    try:
        return not any(
            c.get("owner_id") == user_id and c.get("mode") == "dashboard"
            for c in storage.list_conversations()
        )
    except Exception:
        return False


# Dedicated per-IP limiter for the public event sink: keying it on the shared
# `u:anon` bucket would let one anonymous visitor's events starve everyone
# else's. Generous — events are cheap appends; this only stops log-flooding.
_events_limiter = RateLimiter(
    capacity=int(os.getenv("EVENTS_BURST", "60")),
    refill_per_min=int(os.getenv("EVENTS_PER_MIN", "120")),
)


class EventRequest(BaseModel):
    event: str
    anon_id: Optional[str] = None
    session_id: Optional[str] = None
    path: Optional[str] = None
    referrer: Optional[str] = None
    utm: Optional[Dict[str, Any]] = None
    props: Optional[Dict[str, Any]] = None


@app.post("/api/events")
async def ingest_event(request: EventRequest, http_request: Request):
    """First-party analytics ingest (1c). Funnel events (landing_view, demo_view,
    signup_*, identify, error_shown) arrive here from lib/analytics.js via the
    dedicated Next /api/events route. record_event's allowlist drops unknown
    names; props are cleaned to flat scalars so a dataset value can't leak in."""
    if not _events_limiter.allow(f"ip:{_client_ip(http_request)}"):
        return JSONResponse({"ok": False}, status_code=429)
    user = user_from_request(http_request)
    analytics.record_event(
        request.event,
        user_id=user["id"] if user else None,
        anon_id=request.anon_id or http_request.headers.get("x-anon-id"),
        session_id=request.session_id or http_request.headers.get("x-session-id"),
        path=request.path,
        referrer=request.referrer,
        utm=request.utm,
        props=request.props,
    )
    return {"ok": True}


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int
    mode: str = "chat"  # "chat" | "dashboard" — dashboards route to /dashboard/[id]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Datavisual.studio API"}


@app.get("/health")
async def health():
    """Liveness probe for the load balancer / deploy runbook first-boot check.
    Exempt from the proxy-secret guard so an uptime monitor can reach it."""
    return {"status": "ok", "version": app.version}


class ErrorLogRequest(BaseModel):
    """A client-side error report (7.2)."""
    message: str
    stack: Optional[str] = None
    component_stack: Optional[str] = None


@app.post("/api/error-log")
async def error_log(request: ErrorLogRequest):
    """Append a client error to data/error.log (simple file append, no database).

    Example body: {"message": "x is undefined", "stack": "...", "component_stack": "..."}
    """
    try:
        Path("data").mkdir(parents=True, exist_ok=True)
        with open("data/error.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.utcnow().isoformat() + "Z",
                "message": request.message,
                "stack": request.stack,
                "component_stack": request.component_stack,
            }) + "\n")
    except Exception:
        pass  # logging must never fail the request
    return {"logged": True}


class SettingsRequest(BaseModel):
    """Partial settings update — omitted/None fields are left unchanged."""
    openrouter_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    council_models: Optional[List[str]] = None
    chairman_model: Optional[str] = None
    research_model: Optional[str] = None
    fast_model: Optional[str] = None


@app.get("/api/settings")
async def get_settings():
    """Current settings with the API key masked."""
    return config.get_settings_view()


@app.post("/api/settings")
async def update_settings(request: SettingsRequest):
    """Save user settings (API key, council/chairman/research models)."""
    patch = {
        "openrouter_api_key": (request.openrouter_api_key or "").strip() or None,
        "gemini_api_key": (request.gemini_api_key or "").strip() or None,
        "council_models": [m.strip() for m in (request.council_models or []) if m.strip()] or None,
        "chairman_model": (request.chairman_model or "").strip() or None,
        "research_model": (request.research_model or "").strip() or None,
        "fast_model": (request.fast_model or "").strip() or None,
    }
    config.save_settings(patch)
    return config.get_settings_view()


@app.post("/api/settings/validate")
async def validate_api_key(request: SettingsRequest):
    """Check a key (or the saved one) against OpenRouter without saving it."""
    import httpx

    key = (request.openrouter_api_key or "").strip() or config.get_api_key()
    if not key:
        return {"valid": False, "error": "No API key configured"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/key",
                headers={"Authorization": f"Bearer {key}"},
            )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            return {"valid": True, "label": data.get("label"), "usage": data.get("usage")}
        return {"valid": False, "error": f"OpenRouter rejected the key (HTTP {resp.status_code})"}
    except Exception as e:
        return {"valid": False, "error": f"Could not reach OpenRouter: {e}"}


class AccountSettingsRequest(BaseModel):
    """Per-user AI keys — omitted/None fields are left unchanged."""
    openrouter_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None


def _mask(key: str | None) -> str:
    key = key or ""
    return f"{key[:8]}…{key[-4:]}" if len(key) > 14 else ("•" * len(key))


@app.get("/api/account/settings")
async def get_account_settings(http_request: Request):
    """The signed-in user's own AI-key configuration, masked. In open dev mode
    reports the effective global keys so the UI shows an accurate state."""
    user = user_from_request(http_request)
    if user is None:
        return {
            "scope": "global",
            "openrouter_key_set": bool(config.get_api_key()),
            "openrouter_key_masked": _mask(config.get_api_key()),
            "gemini_key_set": bool(config.get_gemini_api_key()),
        }
    from .crypto import decrypt
    settings = user_settings(user)
    openrouter = decrypt(settings.get("openrouter_api_key"))
    return {
        "scope": "user",
        "openrouter_key_set": bool(openrouter),
        "openrouter_key_masked": _mask(openrouter),
        "gemini_key_set": bool(decrypt(settings.get("gemini_api_key"))),
    }


@app.post("/api/account/settings")
async def update_account_settings(request: AccountSettingsRequest, http_request: Request):
    """Save the user's own keys (stored on their record in data/users.json)."""
    user = user_from_request(http_request)
    if user is None:
        raise HTTPException(status_code=400, detail="No signed-in user (open dev mode uses the backend .env keys)")
    update_user_settings(user["clerk_id"], {
        "openrouter_api_key": (request.openrouter_api_key or "").strip() or None,
        "gemini_api_key": (request.gemini_api_key or "").strip() or None,
    })
    return await get_account_settings(http_request)


@app.post("/api/account/validate")
async def validate_account_key(request: AccountSettingsRequest, http_request: Request):
    """Check an OpenRouter key (provided, or the user's saved one) live."""
    import httpx

    from .crypto import decrypt
    user = user_from_request(http_request)
    key = (request.openrouter_api_key or "").strip() or decrypt(user_settings(user).get("openrouter_api_key"))
    if not key and user is None:
        key = config.get_api_key()
    if not key:
        return {"valid": False, "error": "No API key to validate"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://openrouter.ai/api/v1/key",
                                    headers={"Authorization": f"Bearer {key}"})
        if resp.status_code == 200:
            return {"valid": True, "usage": resp.json().get("data", {}).get("usage")}
        return {"valid": False, "error": f"OpenRouter rejected the key (HTTP {resp.status_code})"}
    except Exception as e:
        return {"valid": False, "error": f"Could not reach OpenRouter: {e}"}


# ---------------------------------------------------------------------------
# Super admin — users + project analytics from the local disk. Gated by a
# single ADMIN_PASSWORD (backend .env) supplied as the X-Admin-Password
# header; no account needed. Unset password = open dev mode only.
# ---------------------------------------------------------------------------

def _require_admin(http_request: Request) -> None:
    import secrets

    password = os.getenv("ADMIN_PASSWORD", "")
    if not password:
        if user_from_request(http_request) is None:
            return  # open dev mode, nothing configured
        raise HTTPException(status_code=403, detail="Admin is disabled — set ADMIN_PASSWORD on the backend")
    supplied = http_request.headers.get("x-admin-password") or ""
    if not secrets.compare_digest(supplied, password):
        raise HTTPException(status_code=403, detail="Admin password required")


@app.get("/api/admin/overview")
async def admin_overview(http_request: Request):
    _require_admin(http_request)
    from collections import Counter, defaultdict

    # Users from the registry.
    try:
        registry = json.loads(Path("data/users.json").read_text())
    except Exception:
        registry = {}

    # Conversations grouped per owner.
    convs = storage.list_conversations()
    per_owner: dict = defaultdict(lambda: {"research": 0, "dashboards": 0, "last_active": None})
    totals = Counter()
    for c in convs:
        kind = "dashboards" if c.get("mode") == "dashboard" else "research"
        totals[kind] += 1
        o = per_owner[c.get("owner_id")]
        o[kind] += 1
        if not o["last_active"] or c["created_at"] > o["last_active"]:
            o["last_active"] = c["created_at"]

    # Events: totals by event + daily activity. Capped at 30 days / tail so the
    # ever-growing jsonl never bloats the admin request (1c).
    events_by_kind = Counter()
    daily = Counter()
    per_user_events = Counter()
    for e in analytics.read_events(since_days=30):
        events_by_kind[e.get("event")] += 1
        daily[(e.get("ts") or "")[:10]] += 1
        per_user_events[e.get("user_id")] += 1

    users = []
    for u in registry.values():
        stats = per_owner.get(u["id"], {})
        users.append({
            "id": u["id"], "name": u.get("name"), "email": u.get("email"),
            "created_at": u.get("created_at"),
            "has_keys": bool((u.get("settings") or {}).get("openrouter_api_key")),
            "research": stats.get("research", 0),
            "dashboards": stats.get("dashboards", 0),
            "events": per_user_events.get(u["id"], 0),
            "last_active": stats.get("last_active"),
        })
    users.sort(key=lambda x: x.get("last_active") or "", reverse=True)

    from datetime import timedelta
    today = datetime.utcnow().date()
    activity = [{"day": (today - timedelta(days=i)).isoformat(),
                 "events": daily.get((today - timedelta(days=i)).isoformat(), 0)}
                for i in range(13, -1, -1)]

    return {
        "totals": {
            "users": len(registry),
            "research": totals.get("research", 0),
            "dashboards": totals.get("dashboards", 0),
            "events": sum(events_by_kind.values()),
        },
        "events_by_kind": dict(events_by_kind),
        "activity": activity,
        "users": users,
    }


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations(http_request: Request):
    """List conversations (metadata only), scoped to the signed-in user when
    an identity is present. Ownerless legacy records stay hidden per-user."""
    items = storage.list_conversations()
    user = user_from_request(http_request)
    if user is not None:
        items = [c for c in items if c.get("owner_id") == user["id"]]
    return items


class CreateConversationWithIdRequest(BaseModel):
    """Create a conversation with a client-generated id (used by the router flow)."""
    conversation_id: str
    title: Optional[str] = None
    file_id: Optional[str] = None
    match_history_file_id: Optional[str] = None


@app.post("/api/conversations/create")
async def create_conversation_with_id(request: CreateConversationWithIdRequest, http_request: Request):
    """Create the initial conversation JSON for a client-generated id.

    The frontend generates the uuid, navigates to /chat/{id}, then calls this
    before opening the SSE stream. Idempotent: an existing conversation that
    already has messages is left untouched.
    """
    if not storage.is_valid_id(request.conversation_id):
        raise HTTPException(status_code=400, detail="Invalid conversation id")
    existing = storage.get_conversation(request.conversation_id)
    if existing and existing.get("messages"):
        return {"conversation_id": request.conversation_id}

    conversation = {
        "id": request.conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": request.title or "New conversation",
        "messages": [],
        "pipeline": {},
        "status": "pending",
        "current_stage": "pending",
        "error_message": None,
    }
    _stamp_owner(conversation, http_request)
    if request.file_id:
        conversation["file_id"] = request.file_id
    if request.match_history_file_id:
        conversation["match_history_file_id"] = request.match_history_file_id
    storage.save_conversation(conversation)
    return {"conversation_id": request.conversation_id}


# Progress percentage for each pipeline stage (Part 2b).
_PROGRESS_PCT = {
    "pending": 0,
    "data_analysis": 15,
    "research": 30,
    "council_stage1": 50,
    "council_stage2": 65,
    "council_stage3": 80,
    "synthesis": 90,
    "done": 100,
    "complete": 100,
}


def update_conversation_status(
    conversation_id: str,
    status: str,
    stage: str | None = None,
    error_message: str | None = None,
):
    """Load → update → save the conversation's status/stage fields. Used at every
    major pipeline transition so a reloaded client can poll for progress."""
    conv = storage.get_conversation(conversation_id)
    if conv is None:
        return
    conv["status"] = status
    if stage is not None:
        conv["current_stage"] = stage
    if error_message is not None:
        conv["error_message"] = error_message
    storage.save_conversation(conv)


def _sweep_orphaned_jobs() -> int:
    """Phase 0d — a background pipeline task (asyncio.create_task) dies with the
    process. After a restart, any conversation left in a non-terminal `running`
    state would sit there forever and the frontend would poll it forever. On
    boot, flip those to `error` so the poller stops with an honest message.
    Returns the count swept."""
    swept = 0
    try:
        for meta in storage.list_conversations():
            conv = storage.get_conversation(meta["id"])
            if conv and conv.get("status") == "running":
                update_conversation_status(
                    meta["id"], "error",
                    error_message="This run was interrupted by a server restart — please run it again.",
                )
                swept += 1
    except Exception as e:  # pragma: no cover
        print(f"⚠️  orphaned-job sweep skipped: {e}")
    return swept


@app.get("/api/conversations/{conversation_id}/status")
async def get_conversation_status(conversation_id: str, http_request: Request):
    """Poll endpoint — current pipeline status/stage/progress for a conversation."""
    conv = _owned(conversation_id, http_request)

    status = conv.get("status", "pending")
    stage = conv.get("current_stage", "pending")
    has_report = bool((conv.get("pipeline") or {}).get("report"))
    progress_pct = 100 if status == "complete" else _PROGRESS_PCT.get(stage, 0)

    return {
        "status": status,
        "current_stage": stage,
        "error_message": conv.get("error_message"),
        "has_report": has_report,
        "progress_pct": progress_pct,
    }


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, http_request: Request):
    """Get a specific conversation with all its messages.

    Returns the raw stored dict (no response_model) so the frontend also receives
    pipeline data — including the persisted `activity` log and `file` info — which
    a strict response_model would otherwise strip out.
    """
    return _owned(conversation_id, http_request)


def _dataset_payload(conversation: dict, limit: int = 2000) -> Optional[dict]:
    """Columns + JSON-safe rows for a conversation's dataset (capped), or None
    when there is no readable file. Shared by the owner dataset endpoint and the
    public share view."""
    file_info = conversation.get("file")
    if not file_info or not file_info.get("path") or not os.path.exists(file_info["path"]):
        return None
    from .data_analysis import _load
    import numpy as np
    try:
        df = _load(file_info["path"])
    except Exception:
        return None
    total = len(df)
    df = df.head(max(1, min(limit, 5000)))
    df = df.replace({np.nan: None})
    return {
        "columns": [str(c) for c in df.columns],
        "rows": df.to_dict(orient="records"),
        "total_rows": total,
        "returned_rows": len(df),
    }


@app.get("/api/dataset/{conversation_id}")
async def get_dataset_rows(conversation_id: str, http_request: Request, limit: int = 2000):
    """Return the raw rows of a conversation's uploaded dataset (capped) for the
    interactive dashboard data table. Columns + records, JSON-safe."""
    conversation = _owned(conversation_id, http_request)
    payload = _dataset_payload(conversation, limit)
    if payload is None:
        raise HTTPException(status_code=404, detail="No dataset file for this conversation")
    return payload


# ---------------------------------------------------------------------------
# Public sharing — the owner toggles a share link; anyone with the token gets a
# read-only view (no auth). The public payload is an explicit ALLOWLIST so that
# server-only fields (file paths, connector credentials in file.source,
# owner_id) can never leak.
# ---------------------------------------------------------------------------

@app.post("/api/conversations/{conversation_id}/share")
async def create_share_link(conversation_id: str, http_request: Request):
    _owned(conversation_id, http_request)  # 404 for non-owners
    token = storage.create_share(conversation_id)
    if not token:
        raise HTTPException(status_code=404, detail="Conversation not found")
    _track(http_request, "dashboard_shared", {"conversation_id": conversation_id})
    return {"shared": True, "share_id": token}


@app.delete("/api/conversations/{conversation_id}/share")
async def delete_share_link(conversation_id: str, http_request: Request):
    _owned(conversation_id, http_request)  # 404 for non-owners
    storage.delete_share(conversation_id)
    return {"shared": False}


@app.get("/api/public/{share_id}")
async def get_public_share(share_id: str, http_request: Request):
    """Read-only public view for a share token. No identity, no ownership —
    the token IS the capability. Returns only presentation data."""
    conv = storage.get_shared_conversation(share_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="This shared link is unavailable.")
    # share_viewed — viewers are non-owners (public link, no session); the viral
    # coefficient. Never leaks who: no owner id in the event.
    _track(http_request, "share_viewed", {})
    dash = conv.get("dashboard") or {}
    widgets = dash.get("widgets", [])
    # Data minimization: the raw row-level dataset is only rendered by a table or
    # comparison widget. If the owner curated the share down to aggregate charts,
    # don't ship the full file (which may hold un-charted columns like PII).
    shows_rows = any(w.get("kind") in ("table", "comparison") for w in widgets)
    return {
        "shared": True,
        "mode": conv.get("mode"),
        "title": dash.get("title") or conv.get("title") or "Dashboard",
        "created_at": conv.get("created_at"),
        # Allowlist: only presentation fields. `history` (assistant chat) and
        # `file.source` (connector credentials) are deliberately excluded.
        "dashboard": {
            "title": dash.get("title"),
            "widgets": widgets,
            "last_synced": dash.get("last_synced"),
        },
        "dataset": _dataset_payload(conv) if shows_rows else None,
    }


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------

class AnalyseRequest(BaseModel):
    question: str
    file_id: Optional[str] = None
    match_history_file_id: Optional[str] = None
    conversation_id: str


class ReanalyseRequest(BaseModel):
    conversation_id: str
    filters: Dict[str, Any]


_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


async def _process_upload(file: UploadFile) -> dict:
    """Sanitise, size-cap, persist and profile an uploaded file. Shared by the
    proxied /api/upload and the direct /api/upload-direct paths."""
    # Path(...).name strips any client-supplied directory components so the
    # filename can't traverse out of UPLOADS_DIR.
    filename = Path(file.filename or "upload").name
    allowed_extensions = {".csv", ".xls", ".xlsx", ".json"}
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    file_id = str(uuid.uuid4())
    save_name = f"{file_id}_{filename}"
    save_path = os.path.join(UPLOADS_DIR, save_name)

    written = 0
    with open(save_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > _MAX_UPLOAD_BYTES:
                f.close()
                os.unlink(save_path)
                raise HTTPException(status_code=413, detail="File too large (max 50 MB)")
            f.write(chunk)

    try:
        result = analyse_file(save_path)
    except Exception as e:
        os.unlink(save_path)
        raise HTTPException(status_code=422, detail=f"Could not read file: {e}")

    if result.get("error"):
        os.unlink(save_path)
        raise HTTPException(status_code=422, detail=result["error"])
    summary = result["data_summary"]

    return {
        "file_id": file_id,
        "filename": filename,
        "save_name": save_name,
        "rows": summary["row_count"],
        "columns": summary["column_count"],
        "column_names": [c["name"] for c in summary["columns"] if c["type"] == "numeric"],
    }


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Accept a CSV/Excel/JSON file upload (via the Next proxy) and return metadata."""
    return await _process_upload(file)


# --- Direct browser→backend upload (Vercel path) -----------------------------
# A 50 MB file cannot cross a serverless proxy function, so on the split host the
# browser POSTs directly to the backend origin, authorized by a short-lived HMAC
# ticket minted by the AUTHENTICATED Next proxy. Deliberate carve-out from "the
# browser never calls FastAPI directly" — treated with share-token paranoia.
_used_upload_nonces: set = set()


def _verify_upload_ticket(ticket: str) -> Optional[str]:
    """Return the ticket's user_id if it is valid, unexpired, and unused; else
    None. Ticket = ``user_id.exp.nonce.hmac`` signed with PROXY_SHARED_SECRET."""
    import hashlib
    import hmac as _hmac
    import time as _time

    secret = os.getenv("PROXY_SHARED_SECRET")
    if not secret or not ticket:
        return None
    parts = ticket.split(".")
    if len(parts) != 4:
        return None
    user_id, exp_s, nonce, mac = parts
    # Paranoia: no traversal characters anywhere in the identity/nonce.
    if any(("/" in p or ".." in p or not p) for p in (user_id, nonce)):
        return None
    try:
        exp = int(exp_s)
    except ValueError:
        return None
    if exp < int(_time.time()):
        return None
    expected = _hmac.new(secret.encode(), f"{user_id}.{exp_s}.{nonce}".encode(), hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(expected, mac):
        return None
    if nonce in _used_upload_nonces:  # single use
        return None
    _used_upload_nonces.add(nonce)
    return user_id


@app.post("/api/upload-direct")
async def upload_file_direct(http_request: Request, file: UploadFile = File(...)):
    """Direct upload authorized by an HMAC ticket (exempt from the proxy-secret
    guard; the ticket is the capability). Same cap/sanitisation as /api/upload."""
    if _verify_upload_ticket(http_request.headers.get("x-upload-ticket", "")) is None:
        raise HTTPException(status_code=401, detail="Invalid or expired upload ticket")
    return await _process_upload(file)


# --- Zero-key onboarding: instant dashboard from a bundled sample -------------
# Instant dashboards cost nothing and need NO AI key. The fastest path to value
# for a new visitor, before any "add your key" friction.
_SAMPLES = {
    "saas": ("saas_revenue.csv", "SaaS revenue"),
    "sales": ("store_sales.csv", "Store sales"),
    "marketing": ("marketing.csv", "Marketing spend"),
}


class SampleDashboardRequest(BaseModel):
    sample: Optional[str] = None


@app.get("/api/samples")
async def list_samples():
    return {"samples": [{"key": k, "label": v[1]} for k, v in _SAMPLES.items()]}


@app.post("/api/sample-dashboard")
async def sample_dashboard(request: SampleDashboardRequest, http_request: Request):
    """Build an instant dashboard from a bundled sample dataset — no upload, no
    AI key, no cost."""
    import shutil
    from .dashboard import build_dashboard_spec

    fname, label = _SAMPLES.get(request.sample or "sales", _SAMPLES["sales"])
    src = os.path.join(os.path.dirname(__file__), "samples", fname)
    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail="Sample dataset not found")

    file_id = str(uuid.uuid4())
    save_name = f"{file_id}_{fname}"
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    dst = os.path.join(UPLOADS_DIR, save_name)
    shutil.copyfile(src, dst)

    result = analyse_file(dst)
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    data_summary = result["data_summary"]
    charts = [{"title": c["title"], "type": c["type"], "plotly_json": c["plotly_json"]} for c in result["charts"]]

    cid = str(uuid.uuid4())
    new_conv = {
        "id": cid, "created_at": datetime.utcnow().isoformat(),
        "title": f"{label} (sample)", "mode": "dashboard", "messages": [],
        "file": {"id": file_id, "name": save_name, "path": dst,
                 "rows": data_summary["row_count"], "columns": data_summary["column_count"]},
        "pipeline": {"data_summary": data_summary, "charts": charts},
        "dashboard": build_dashboard_spec(data_summary, charts, title=f"{label} (sample)",
                                          df=result.get("dataframe"), template="overview"),
        "status": "complete", "current_stage": "done", "is_sample": True,
    }
    _stamp_owner(new_conv, http_request)
    storage.save_conversation(new_conv)
    _track(http_request, "sample_data_used", {"sample": request.sample or "sales"})
    return {"conversation_id": cid}


_demo_cache: dict | None = None


@app.get("/api/demo")
async def get_demo():
    """Public zero-friction demo (1b): a prebuilt sample dashboard in the exact
    read-only shape `SharedView` renders — no auth, no key, no writes, no
    persistence. Built once from a bundled sample and cached in memory. The
    landing CTA points here so a stranger sees the value before committing."""
    global _demo_cache
    if _demo_cache is not None:
        return _demo_cache
    from .dashboard import build_dashboard_spec

    fname, label = _SAMPLES["saas"]
    src = os.path.join(os.path.dirname(__file__), "samples", fname)
    result = analyse_file(src)
    if result.get("error"):
        raise HTTPException(status_code=500, detail="Demo dataset unavailable")
    data_summary = result["data_summary"]
    charts = [{"title": c["title"], "type": c["type"], "plotly_json": c["plotly_json"]} for c in result["charts"]]
    conv = {
        "id": "demo", "created_at": datetime.utcnow().isoformat(),
        "title": f"{label} (demo)", "mode": "dashboard",
        "file": {"id": "demo", "name": fname, "path": src,
                 "rows": data_summary["row_count"], "columns": data_summary["column_count"]},
        "pipeline": {"data_summary": data_summary, "charts": charts},
        "dashboard": build_dashboard_spec(data_summary, charts, title=f"{label} (demo)",
                                          df=result.get("dataframe"), template="overview"),
    }
    dash = conv["dashboard"]
    widgets = dash.get("widgets", [])
    shows_rows = any(w.get("kind") in ("table", "comparison") for w in widgets)
    _demo_cache = {
        "shared": True, "mode": "dashboard", "title": conv["title"],
        "created_at": conv["created_at"], "is_demo": True,
        "dashboard": {"title": dash.get("title"), "widgets": widgets, "last_synced": None},
        "dataset": _dataset_payload(conv) if shows_rows else None,
    }
    return _demo_cache


class CreateDashboardRequest(BaseModel):
    """file_id → create a new standalone dashboard from an upload.
    conversation_id → (re)build the widget spec on an existing record in place
    (used to migrate records that predate the spec)."""
    file_id: Optional[str] = None
    conversation_id: Optional[str] = None
    title: Optional[str] = None
    template: Optional[str] = "overview"  # minimal | overview | full | kpi | visual
    focus: Optional[str] = None           # numeric column to emphasise


@app.post("/api/dashboard")
async def create_dashboard(request: CreateDashboardRequest, http_request: Request):
    """Create (or rebuild in place) a web dashboard widget spec — no AI
    pipeline, no cost. Records live in the conversation store with
    mode="dashboard" so the /dashboard/[id] page and dataset endpoints work
    unchanged."""
    from .dashboard import build_dashboard_spec

    if request.conversation_id:
        conv = _owned(request.conversation_id, http_request)
        pipeline = conv.get("pipeline", {})
        data_summary = pipeline.get("data_summary")
        charts = pipeline.get("charts", [])
        df = None
        file_info = conv.get("file")
        if file_info and file_info.get("path") and os.path.exists(file_info["path"]):
            try:
                df = analyse_file(file_info["path"]).get("dataframe")
            except Exception:
                df = None
        conv["dashboard"] = build_dashboard_spec(
            data_summary, charts, title=conv.get("title", "Dashboard"),
            has_rows=bool(conv.get("file")), df=df,
        )
        storage.save_conversation(conv)
        return {"conversation_id": conv["id"]}

    file_record = _find_upload(request.file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="Uploaded file not found")

    result = analyse_file(file_record["path"])
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    data_summary = result["data_summary"]
    charts = [{"title": c["title"], "type": c["type"], "plotly_json": c["plotly_json"]} for c in result["charts"]]

    conversation_id = str(uuid.uuid4())
    display_name = file_record["filename"].split("_", 1)[-1]
    title = request.title or f"Dashboard — {display_name}"
    new_conv = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": title,
        "mode": "dashboard",
        "messages": [],
        "file": {
            "id": request.file_id,
            "name": file_record["filename"],
            "path": file_record["path"],
            "rows": data_summary["row_count"],
            "columns": data_summary["column_count"],
            "source": _load_sources().get(request.file_id),
        },
        "pipeline": {"data_summary": data_summary, "charts": charts},
        "dashboard": build_dashboard_spec(data_summary, charts, title=title, df=result.get("dataframe"), template=request.template or "overview", focus=request.focus),
        "status": "complete",
        "current_stage": "done",
    }
    _stamp_owner(new_conv, http_request)
    # Activation event: check BEFORE saving (after save this one exists).
    _owner = user_from_request(http_request)
    first = _is_first_dashboard(_owner["id"] if _owner else None)
    storage.save_conversation(new_conv)
    _track(http_request, "dashboard_created", {"conversation_id": conversation_id, "template": request.template})
    if first:
        _track(http_request, "first_dashboard_created", {"conversation_id": conversation_id})
    return {"conversation_id": conversation_id}


class DashboardChatRequest(BaseModel):
    """Either a natural-language `message` (LLM turns it into ops) or direct
    `ops` (e.g. the ✕ button removing a widget — no LLM round-trip)."""
    message: Optional[str] = None
    ops: Optional[List[Dict[str, Any]]] = None


@app.post("/api/dashboard/{conversation_id}/chat")
async def dashboard_chat(conversation_id: str, request: DashboardChatRequest, http_request: Request):
    """Edit the EXISTING dashboard in place — never rebuilds it. Returns the
    assistant reply plus the updated spec."""
    from .dashboard import apply_ops, build_dashboard_spec, run_editor_turn, classify_intent, run_query_turn

    conv = _owned(conversation_id, http_request)

    pipeline = conv.get("pipeline", {})
    data_summary = pipeline.get("data_summary")

    # The chart/metric engine needs the raw dataframe when the record has one.
    df = None
    file_info = conv.get("file")
    if file_info and file_info.get("path") and os.path.exists(file_info["path"]):
        from .data_analysis import _clean_numeric_strings, _load, _try_parse_datetime
        try:
            df, _ = _clean_numeric_strings(_load(file_info["path"]))
            df = _try_parse_datetime(df)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not read dataset: {e}")

    # Migrate records that predate the widget spec.
    if not conv.get("dashboard"):
        conv["dashboard"] = build_dashboard_spec(
            data_summary, pipeline.get("charts", []),
            title=conv.get("title", "Dashboard"), has_rows=bool(conv.get("file")), df=df,
        )
    dashboard = conv["dashboard"]

    pin_op = None
    if request.ops:
        notes = await apply_ops(dashboard, request.ops, df, data_summary)
        reply = "Done." if not notes else "; ".join(notes)
    elif request.message and request.message.strip():
        msg = request.message.strip()
        # Route by intent: questions are answered from a deterministic data query,
        # edits emit ops, 'both' does both. This is the fix for the "asked a
        # question, got nothing" bug — the editor prompt only knew how to edit.
        intent = await classify_intent(msg)
        parts: list[str] = []
        if intent in ("question", "both"):
            q = await run_query_turn(msg, dashboard, data_summary, df)
            if q.get("reply"):
                parts.append(q["reply"])
            pin_op = q.get("pin_op")
        if intent in ("edit", "both"):
            parts.append(await run_editor_turn(msg, dashboard, data_summary, df))
        answered = any(p for p in parts if p)
        reply = "\n\n".join(p for p in parts if p) or (
            "I couldn't find an answer or an edit to make — try naming a column, or ask me to add a chart."
        )
        # Privacy: log intent + length, NOT the text — except when the answer was
        # empty, where the text is exactly the signal needed to fix the assistant.
        _track(http_request, "assistant_message", {
            "intent": intent, "len": len(msg),
            **({"empty": True, "text": msg[:200]} if not answered else {}),
        })
    else:
        raise HTTPException(status_code=400, detail="Provide a message or ops")

    # Persist under the per-conversation lock, re-reading the freshest record so
    # a concurrent write (e.g. a share mint) isn't clobbered. The async work
    # above is finished, so the lock is held only for a fast sync save.
    def _apply(fresh: dict) -> None:
        fresh["dashboard"] = dashboard
        fresh["title"] = dashboard.get("title", fresh.get("title"))
    storage.update_conversation(conversation_id, _apply)
    return {"reply": reply, "dashboard": dashboard, "pin_op": pin_op}


class ConnectSourceRequest(BaseModel):
    """One-shot data import from an external source. Credentials are used for
    this single fetch and never persisted."""
    type: str  # "database" | "api"
    name: Optional[str] = None
    connection_string: Optional[str] = None  # database: SQLAlchemy URL
    query: Optional[str] = None              # database: SELECT query
    url: Optional[str] = None                # api: endpoint returning JSON records
    headers: Optional[Dict[str, str]] = None  # api: optional request headers


_CONNECT_MAX_ROWS = 100_000

# Data-modifying SQL keywords + dangerous functions that must never appear in a
# read-only import query. Word-boundary matched, so a column named `update_time`
# or `created_at` is fine. `replace`/`set` are deliberately absent — they are
# common string functions / clause words and REPLACE INTO is already caught by
# `into`.
_SQL_WRITE_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "create", "truncate", "grant",
    "revoke", "merge", "call", "exec", "execute", "copy", "into", "vacuum", "attach",
)
_SQL_DANGER_FUNCS = (
    "pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "lo_import",
    "lo_export", "dblink", "load_file", "benchmark", "sleep", "waitfor",
)
_SQL_WRITE_RE = re.compile(
    r"\b(" + "|".join(_SQL_WRITE_KEYWORDS + _SQL_DANGER_FUNCS) + r")\b", re.IGNORECASE)


def _is_readonly_sql(query: str) -> bool:
    """True only for a SINGLE read-only SELECT/WITH statement. Blocks the
    bypasses a 'starts with SELECT' check misses: a data-modifying CTE
    (WITH x AS (INSERT …) SELECT …), a stacked query (SELECT 1; DROP TABLE),
    SELECT … INTO, and any write keyword anywhere. Errs strict — a false reject
    is an import that doesn't run; a false accept could delete the user's data.
    ponytail: regex heuristic, not a full SQL parser; add sqlparse only if a real
    bypass this word-matching misses ever appears (no new dep until then)."""
    if not isinstance(query, str):
        return False
    q = query.strip()
    if not re.match(r"(?is)^(select|with)\b", q):
        return False
    body = q.rstrip().rstrip(";")      # a single trailing ; is fine…
    if ";" in body:                    # …any other ; means stacked statements
        return False
    return not _SQL_WRITE_RE.search(body)


# Connector configs are persisted (locally, gitignored) so dashboards backed by
# a database/API can be refreshed with one click — the Power BI model.
_SOURCES_PATH = Path("data/sources.json")


def _load_sources() -> dict:
    try:
        return json.loads(_SOURCES_PATH.read_text())
    except Exception:
        return {}


def _save_source(file_id: str, cfg: dict) -> None:
    from .atomic import atomic_write_json
    sources = _load_sources()
    sources[file_id] = cfg
    atomic_write_json(_SOURCES_PATH, sources)


def _run_source_import(cfg: dict):
    """Fetch a dataframe from a connector config ({type, connection_string,
    query} or {type, url, headers}). Shared by /api/connect and refresh.
    Raises HTTPException with an actionable message on failure."""
    import pandas as pd

    if cfg.get("type") == "database":
        if not cfg.get("connection_string") or not cfg.get("query"):
            raise HTTPException(status_code=400, detail="connection_string and query are required")
        # Import-only guard: this reads data, it must never mutate the user's
        # database. A "starts with SELECT/WITH" check is NOT enough — a
        # data-modifying CTE (WITH x AS (INSERT … RETURNING *) SELECT …) starts
        # with WITH but writes, and a stacked `SELECT 1; DROP TABLE` starts with
        # SELECT but runs two statements. See _is_readonly_sql.
        if not _is_readonly_sql(cfg["query"]):
            raise HTTPException(
                status_code=400,
                detail="Only a single read-only SELECT (or WITH … SELECT) query is allowed. "
                       "Stacked statements, data-modifying keywords and SELECT … INTO are rejected.",
            )
        from .ssrf import validate_sql_host, SSRFError
        try:
            validate_sql_host(cfg["connection_string"])
        except SSRFError as e:
            raise HTTPException(status_code=400, detail=f"Refused to connect to that database host: {e}")
        try:
            from sqlalchemy import create_engine
            engine = create_engine(cfg["connection_string"])
            try:
                return pd.read_sql(cfg["query"], engine)
            finally:
                engine.dispose()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Database import failed: {e}")

    if cfg.get("type") == "api":
        if not cfg.get("url"):
            raise HTTPException(status_code=400, detail="url is required")
        from .ssrf import guarded_get, SSRFError
        try:
            resp = guarded_get(cfg["url"], headers=cfg.get("headers") or {})
            resp.raise_for_status()
            payload = resp.json()
        except SSRFError as e:
            raise HTTPException(status_code=400, detail=f"Refused to fetch that URL: {e}")
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"API request failed: {e}")
        # Accept a bare array, or the first array value inside an object
        # (covers the common {"data": [...]} / {"results": [...]} shapes).
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            records = next((v for v in payload.values() if isinstance(v, list)), None)
        else:
            records = None
        if not records:
            raise HTTPException(status_code=422, detail="Response JSON contains no array of records")
        try:
            return pd.json_normalize(records)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not tabulate API response: {e}")

    raise HTTPException(status_code=400, detail="type must be 'database' or 'api'")


@app.post("/api/connect")
def connect_source(request: ConnectSourceRequest, http_request: Request):
    """Import data from a SQL database or a REST API and materialise it as an
    uploaded dataset (CSV in data/uploads). Downstream everything — AI analysis,
    dashboards, predictions — treats it exactly like a file upload. The
    connector config is stored locally so dashboards can Refresh from it.

    Declared sync (`def`) on purpose: FastAPI runs it in a threadpool, so the
    blocking pd.read_sql / httpx call doesn't stall the event loop."""
    cfg = {
        "type": request.type,
        "name": request.name,
        "connection_string": request.connection_string,
        "query": request.query,
        "url": request.url,
        "headers": request.headers,
    }
    df = _run_source_import(cfg)
    if df is None or len(df) == 0:
        raise HTTPException(status_code=422, detail="The source returned no rows")
    df = df.head(_CONNECT_MAX_ROWS)

    source_name = request.name or ("database_import" if request.type == "database" else "api_import")
    safe_name = re.sub(r"[^\w-]+", "_", source_name).strip("_") or "import"
    file_id = str(uuid.uuid4())
    save_name = f"{file_id}_{safe_name}.csv"
    save_path = os.path.join(UPLOADS_DIR, save_name)
    df.to_csv(save_path, index=False)

    result = analyse_file(save_path)
    if result.get("error"):
        os.unlink(save_path)
        raise HTTPException(status_code=422, detail=result["error"])
    summary = result["data_summary"]

    _save_source(file_id, cfg)
    _track(http_request, "connector_used", {"kind": "sql" if request.type == "database" else "rest"})

    return {
        "file_id": file_id,
        "filename": f"{safe_name}.csv",
        "save_name": save_name,
        "rows": summary["row_count"],
        "columns": summary["column_count"],
        "column_names": [c["name"] for c in summary["columns"] if c["type"] == "numeric"],
        "source": request.type,
    }


@app.get("/api/dashboard/{conversation_id}/suggestions")
def dashboard_suggestions(conversation_id: str, http_request: Request):
    """Prebuilt components (charts/metrics/sections) computed from the dataset,
    minus what the dashboard already shows. One click on the frontend applies
    the returned op directly — no LLM, no regeneration."""
    from .dashboard import component_suggestions

    conv = _owned(conversation_id, http_request)
    df = None
    file_info = conv.get("file")
    if file_info and file_info.get("path") and os.path.exists(file_info["path"]):
        try:
            df = analyse_file(file_info["path"]).get("dataframe")
        except Exception:
            df = None
    return {"suggestions": component_suggestions(
        df, conv.get("pipeline", {}).get("data_summary"), conv.get("dashboard") or {},
    )}


@app.post("/api/dashboard/{conversation_id}/sync")
async def sync_dashboard_endpoint(conversation_id: str, http_request: Request):
    """The 'Update' action — the living-monitor core. Re-pulls connector data
    (if any) AND re-runs every pinned research query, rebuilding the affected
    widgets in place, then returns a human-readable list of WHAT CHANGED. Works
    with data only, research only, or both."""
    from .dashboard import sync_dashboard

    conv = _owned(conversation_id, http_request)
    dashboard = conv.get("dashboard")
    if not dashboard:
        raise HTTPException(status_code=400, detail="This conversation has no dashboard to sync")

    file_info = conv.get("file") or {}
    source = file_info.get("source") or _load_sources().get(file_info.get("id", ""))
    has_research = any(w.get("kind") == "insight" and w.get("query") for w in dashboard.get("widgets", []))
    if not source and not has_research:
        raise HTTPException(
            status_code=400,
            detail="Nothing to sync — connect a data source or pin a research topic first.",
        )

    # Re-pull connector data when the dashboard is source-backed.
    fresh_df = None
    data_summary = conv.get("pipeline", {}).get("data_summary")
    if source:
        df = _run_source_import(source)
        if df is None or len(df) == 0:
            raise HTTPException(status_code=422, detail="The source returned no rows")
        df = df.head(_CONNECT_MAX_ROWS)
        df.to_csv(file_info["path"], index=False)
        result = analyse_file(file_info["path"])
        if result.get("error"):
            raise HTTPException(status_code=422, detail=result["error"])
        data_summary = result["data_summary"]
        fresh_df = result["dataframe"]
        conv["file"]["rows"] = data_summary["row_count"]
        conv["file"]["columns"] = data_summary["column_count"]
        conv.setdefault("pipeline", {})["data_summary"] = data_summary

    changes = await sync_dashboard(dashboard, fresh_df, data_summary)
    # Threshold alerts fire off the freshly-updated metric values (owner-only).
    from .alerts import evaluate_alerts
    changes = evaluate_alerts(dashboard) + changes
    storage.save_conversation(conv)
    _track(http_request, "sync_run", {"conversation_id": conversation_id, "changes": len(changes), "trigger": "manual"})
    return {"dashboard": dashboard, "changes": changes, "synced_at": dashboard.get("last_synced")}


# Strong refs to in-flight background pipeline tasks (default polling mode) so
# the event loop doesn't garbage-collect them mid-run.
_pipeline_tasks: set = set()


@app.post("/api/analyse")
async def analyse(request: AnalyseRequest, http_request: Request):
    """
    Main pipeline endpoint. Default = job kickoff + polling; ?stream=1 = SSE.

    First message: full pipeline (data analysis → internet research → council → report)
    Follow-up: chairman only (or full re-run if message starts with !council)
    """
    conversation = _owned(request.conversation_id, http_request)
    _track(http_request, "research_run", {"conversation_id": request.conversation_id})

    is_first_message = len(conversation["messages"]) == 0
    force_council = request.question.strip().startswith("!council")
    actual_question = request.question.strip().removeprefix("!council").strip() if force_council else request.question

    async def event_generator():
        current_stage = "initialising"
        # Accumulate activity events so they can be persisted with the conversation
        # and replayed in the Activity Panel after a reload.
        activity_events: list = []

        def act(event: str, detail: str, reasoning: str = "", links: list | None = None) -> str:
            payload = _activity_payload(event, detail, reasoning, links)
            activity_events.append(payload)
            return f"data: {json.dumps(payload)}\n\n"

        def _advance(name: str) -> None:
            # Persist the stage so a POLLING client (the default, Vercel-safe
            # transport) sees the same progress a streaming client sees live.
            nonlocal current_stage
            current_stage = name
            update_conversation_status(request.conversation_id, "running", name)

        try:
            _advance("initialising")
            storage.add_user_message(request.conversation_id, request.question)

            # ----------------------------------------------------------------
            # FIRST MESSAGE or forced council re-run
            # ----------------------------------------------------------------
            if is_first_message or force_council:
                title_task = None
                if is_first_message:
                    title_task = asyncio.create_task(generate_conversation_title(actual_question))

                # Determine mode
                mode = "data" if request.file_id else "text"

                # Mark the conversation as running so a reloaded client can poll.
                update_conversation_status(request.conversation_id, "running", "data_analysis")

                # Data analysis
                data_summary = None
                charts = []
                data_excerpt = None
                data_df = None  # in-memory dataframe — fuels the prediction engine
                if mode == "data":
                    _advance("data analysis")
                    yield f"data: {json.dumps({'type': 'analysis_start'})}\n\n"
                    file_record = _find_upload(request.file_id)
                    if file_record is None:
                        yield act("stage_error", "data analysis: uploaded file not found")
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Uploaded file not found'})}\n\n"
                        return
                    analysis_result = analyse_file(file_record["path"])
                    # Surface a structured error from data analysis (empty/malformed file)
                    if isinstance(analysis_result, dict) and analysis_result.get("error"):
                        msg = analysis_result["error"]
                        yield act("stage_error", f"data analysis: {msg}")
                        yield f"data: {json.dumps({'type': 'error', 'message': msg})}\n\n"
                        return
                    data_summary = analysis_result["data_summary"]
                    charts = analysis_result["charts"]
                    data_excerpt = analysis_result.get("data_excerpt")
                    data_df = analysis_result.get("dataframe")
                    yield f"data: {json.dumps({'type': 'analysis_complete', 'data': {'data_summary': data_summary, 'charts': charts}})}\n\n"

                    # Activity: dataset analysed + charts generated
                    chart_titles = ", ".join(c["title"] for c in charts)
                    yield act(
                        "dataset_analysed",
                        f"{data_summary['row_count']:,} rows · {data_summary['column_count']} columns · "
                        f"{len(charts)} charts detected" + (f" ({chart_titles})" if chart_titles else ""),
                        reasoning="Profiling the uploaded dataset to understand its structure and surface the actual values the council should reason over.",
                    )
                    if charts:
                        labels = []
                        for c in charts:
                            lbl = _CHART_LABELS.get(c.get("type"), f"{str(c.get('type', '')).capitalize()} chart")
                            if lbl not in labels:
                                labels.append(lbl)
                        yield act(
                            "charts_generated",
                            " · ".join(labels),
                            reasoning="Auto-generating visualisations to reveal the key trends and distributions in the data.",
                        )

                # ----------------------------------------------------------------
                # Phase 1 — run the mathematical models (Model A = ELO Monte Carlo,
                # Model B = ELO-Poisson/Dixon-Coles). Their ensemble is the dataset
                # baseline: ALWAYS produced when numeric data exists, injected into
                # the council prompt, and the guaranteed fallback for the final table.
                # ----------------------------------------------------------------
                dataset_models = build_dataset_models(
                    data_df, data_summary.get("columns", []) if data_summary else [],
                    n_simulations=_N_SIMULATIONS,
                )
                model_a_probs = dataset_models["model_a_probs"]
                model_b_probs = dataset_models["model_b_probs"]
                ensemble_probs = dataset_models["ensemble_probs"]
                model_a_results = dataset_models["model_a_results"]
                model_b_results = dataset_models["model_b_results"]
                ensemble_results = dataset_models["ensemble_results"]
                entity_names = dataset_models["entity_names"]
                dataset_method = dataset_models["method"]
                agreement = dataset_models.get("agreement", {})

                # ----------------------------------------------------------------
                # Model C — XGBoost, only when a match-history file was uploaded.
                # Degrades gracefully (skip events) if xgboost/OpenMP is missing,
                # there's no match data, or there aren't enough rows to train on.
                # ----------------------------------------------------------------
                model_c_results = []
                model_c_match_count = 0
                model_c_features = []
                model_c_status = "no_file"  # no_file | unavailable | insufficient | trained | failed
                match_record = _find_upload(request.match_history_file_id) if request.match_history_file_id else None
                if match_record and dataset_models.get("elo_dict"):
                    if not xgboost_available():
                        model_c_status = "unavailable"
                        yield act(
                            "model_c_skipped",
                            "XGBoost unavailable in this environment",
                            reasoning="Model C requires xgboost and the OpenMP runtime (e.g. `brew install libomp`).",
                        )
                    else:
                        match_analysis = analyse_file(match_record["path"])
                        match_df = match_analysis.get("dataframe") if isinstance(match_analysis, dict) else None
                        X, y = build_match_features(
                            match_df, data_df, dataset_models["entity_col"], dataset_models["time_col"]
                        ) if match_df is not None else ([], [])
                        if len(X) >= 100:
                            xgb_model = train_xgboost_model(X, y)
                            if xgb_model is not None:
                                model_c_probs = run_monte_carlo_xgboost(
                                    dataset_models["elo_dict"], xgb_model,
                                    dataset_models["form_indices"], _N_SIMULATIONS,
                                )
                                model_c_results = probs_to_prediction_results(model_c_probs, 10, ["dataset"])
                                model_c_match_count = len(X)
                                model_c_features = xgboost_feature_importance(xgb_model)
                                model_c_status = "trained"
                                # Re-form the ensemble as the mean of A, B and C.
                                ensemble_probs = {
                                    t: (model_a_probs.get(t, 0) + model_b_probs.get(t, 0) + model_c_probs.get(t, 0)) / 3
                                    for t in set(model_a_probs) | set(model_b_probs) | set(model_c_probs)
                                }
                                ensemble_results = probs_to_prediction_results(ensemble_probs, 10, ["dataset"])
                                for r in ensemble_results:
                                    r.model_agreement = round(agreement.get(r.entity, 1.0), 3)
                                yield act(
                                    "model_c_trained",
                                    f"XGBoost trained on {len(X)} matches",
                                    reasoning=(
                                        f"Trained on {len(X)} historical match records with 8 features. "
                                        "Model C predictions now included in the ensemble alongside Models A and B."
                                    ),
                                )
                            else:
                                model_c_status = "failed"
                                yield act(
                                    "model_c_skipped",
                                    "XGBoost training failed",
                                    reasoning="The match-history features could not train a usable model; using Models A and B only.",
                                )
                        else:
                            model_c_status = "insufficient"
                            yield act(
                                "model_c_skipped",
                                f"Not enough match data ({len(X)} rows, need ≥100)",
                            )

                dataset_probs = ensemble_probs  # ensemble (incl. Model C if trained) drives the combined prediction
                dataset_baseline_results = ensemble_results
                dataset_baseline_table = predictions_to_table(dataset_baseline_results)

                # Surface model calibration in the activity log.
                if dataset_models.get("rho_fitted"):
                    yield act(
                        "model_b_calibrated",
                        f"Dixon-Coles rho fitted from data: {dataset_models['rho']:.4f}",
                        reasoning=(
                            "Calibrated Model B's low-scoring-game correction from the dataset's "
                            f"actual scorelines ({dataset_models['rho_n_matches']} matches) instead of "
                            "the default 1997 value."
                        ),
                    )
                if dataset_models.get("form_applied"):
                    yield act(
                        "form_index_computed",
                        f"Form index computed for {dataset_models['form_count']} entities",
                        reasoning=(
                            "Recent match performance weighted more heavily than historical averages. "
                            "Entities with strong recent form receive a small probability boost."
                        ),
                    )
                # Home advantage (2.2) + stability check (2.5) activity events.
                if dataset_models.get("host_entity"):
                    yield act(
                        "host_advantage",
                        f"Host advantage applied to {dataset_models['host_entity']} (+{int(dataset_models.get('host_boost', 65))} ELO)",
                        reasoning="The host nation receives the empirically-derived +65 ELO home-advantage boost in all match simulations.",
                    )
                if dataset_models.get("stability_note"):
                    yield act(
                        "prediction_validated",
                        dataset_models["stability_note"],
                        reasoning="A separate validation run confirms the Monte Carlo result is stable; otherwise the simulation count is increased automatically.",
                    )

                # Internet research — three targeted searches in sequence.
                _advance("internet research")
                update_conversation_status(request.conversation_id, "running", "research")
                yield f"data: {json.dumps({'type': 'research_start'})}\n\n"
                searches = []
                data_hint = ", ".join(c["name"] for c in (data_summary or {}).get("columns", [])[:10])
                for step in await plan_searches(actual_question, entity_names, data_hint):
                    yield act("search_started", step["query"], reasoning=step["started_reasoning"])
                    res = await run_single_search(step["query"], step.get("system"))
                    search = {
                        "query": step["query"],
                        "purpose": step["purpose"],
                        "content": res.get("content", ""),
                        "sources": res.get("sources", []),
                    }
                    searches.append(search)
                    yield act(
                        "search_complete",
                        f"Found {len(search['sources'])} sources",
                        reasoning=step["complete_reasoning"],
                        links=[{"title": s.get("title", ""), "url": s.get("url", "")} for s in search["sources"]],
                    )
                internet_findings = combine_findings(searches)
                if not any(s.get("sources") for s in searches):
                    yield act(
                        "research_warning",
                        "Web research returned no sources",
                        reasoning="The analysis will rely on the dataset and model knowledge. Check the research model in Settings if this keeps happening.",
                    )
                yield f"data: {json.dumps({'type': 'research_complete', 'data': internet_findings})}\n\n"

                # Event-status check (Fix 2) — scan the search results for evidence
                # the event is already in progress, so the council can't claim it
                # "hasn't started" when sources prove otherwise.
                today_date = datetime.utcnow().strftime("%B %d, %Y")
                event_status = detect_event_status(searches, today_date)
                # Confirmed scored results (Fix 3a) — injected at the very top of the
                # prompt as non-negotiable ground truth.
                confirmed_facts = extract_confirmed_facts(searches)

                update_conversation_status(request.conversation_id, "running", "council_stage1")

                # Build enriched prompt (injects confirmed facts + dataset baseline + event status)
                enriched_prompt = build_enriched_prompt(
                    actual_question,
                    data_summary,
                    internet_findings,
                    data_excerpt,
                    dataset_baseline=dataset_baseline_table,
                    event_status=event_status,
                    dataset_method=dataset_method,
                    confirmed_facts=confirmed_facts,
                    n_simulations=_N_SIMULATIONS,
                )
                approx_tokens = len(enriched_prompt) // 4
                if DEBUG:
                    print(
                        f"[analyse] enriched prompt: {len(enriched_prompt)} chars "
                        f"(~{approx_tokens} tokens)"
                        + ("  WARNING: exceeds 16000-char budget" if len(enriched_prompt) > 16000 else ""),
                        flush=True,
                    )
                    print(f"[DEBUG] Prompt first 800 chars: {enriched_prompt[:800]}", flush=True)

                # Stage 1
                _advance("stage 1")
                yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
                # Activity: one querying event per council model. (Council querying is
                # parallel inside council.py, so these are emitted up front rather than
                # interleaved with each response.)
                for m in config.get_council_models():
                    yield act(
                        "model_querying",
                        f"Querying {_model_display(m)}...",
                        reasoning="Asking each council model to analyse the data and research independently, so their conclusions stay unbiased by one another.",
                    )
                stage1_results = await stage1_collect_responses(enriched_prompt)
                # Hard stop when the council is completely unavailable — a report
                # synthesised from nothing is worse than a clear error.
                if not stage1_results:
                    msg = ("All council models failed to respond. Check your OpenRouter "
                           "API key, credit balance, and council model ids in Settings.")
                    update_conversation_status(request.conversation_id, "error", error_message=msg)
                    yield act("stage_error", msg)
                    yield f"data: {json.dumps({'type': 'error', 'message': msg})}\n\n"
                    return
                if len(stage1_results) == 1:
                    yield act(
                        "council_degraded",
                        "Only 1 council model responded — peer review is skipped-in-effect",
                        reasoning="The report will rely on a single model's analysis. Check the other council model ids in Settings.",
                    )
                yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"
                # Activity: one responded event per model that answered, with char count.
                for r in stage1_results:
                    yield act(
                        "model_responded",
                        f"{_model_display(r['model'])} · {len(r.get('response', ''))} chars",
                        reasoning="Received an independent analysis to weigh against the other models' reasoning.",
                    )

                # Stage 2
                _advance("stage 2")
                update_conversation_status(request.conversation_id, "running", "council_stage2")
                yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
                yield act(
                    "peer_review_started",
                    "Models reviewing each other's responses",
                    reasoning="Each model now reviews the others' answers anonymously and ranks them, so the strongest reasoning rises to the top.",
                )
                stage2_results, label_to_model = await stage2_collect_rankings(enriched_prompt, stage1_results)
                aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
                metadata = {"label_to_model": label_to_model, "aggregate_rankings": aggregate_rankings}
                yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': metadata})}\n\n"

                # ----------------------------------------------------------------
                # Phase 2 — combined prediction (Fix 1). If internet or council
                # produced any numbers, blend all three sources with the normal
                # 40/35/25 weighting; otherwise fall back to the dataset-only
                # baseline so a prediction is ALWAYS produced when numeric data
                # exists. Computed BEFORE the chairman runs and fed into its prompt.
                # ----------------------------------------------------------------
                _advance("prediction engine")
                internet_probs = extract_internet_probs(internet_findings, entity_names)
                council_probs = extract_council_probs(stage1_results, entity_names, aggregate_rankings)

                # Combined = ensemble (dataset) + internet + council. With empty
                # internet/council this reduces to the ensemble baseline, so it is
                # always defined.
                combined_results = compute_prediction(dataset_probs, internet_probs, council_probs)
                prediction_results = combined_results or dataset_baseline_results
                prediction_table = predictions_to_table(prediction_results)

                # Assemble the full model suite (Change 3) for the report + chairman.
                prediction_suite = {
                    "model_a": predictions_to_table(model_a_results),
                    "model_a_label": "ELO Monte Carlo",
                    "model_a_description": f"Simulates tournament outcome using ELO win probability formula. {_N_SIMULATIONS:,} runs.",
                    "model_b": predictions_to_table(model_b_results),
                    "model_b_label": "ELO-Poisson / Dixon-Coles",
                    "model_b_description": f"Simulates actual scorelines using Poisson distribution with low-score correction (rho={dataset_models.get('rho', -0.107):.3f}). {_N_SIMULATIONS:,} runs.",
                    "model_c": predictions_to_table(model_c_results),
                    "model_c_features": model_c_features,
                    "model_c_label": "XGBoost",
                    "model_c_description": (
                        f"Gradient-boosted trees trained on {model_c_match_count:,} historical matches."
                        if model_c_status == "trained"
                        else "XGBoost unavailable in this environment. Model C requires: brew install libomp"
                        if model_c_status == "unavailable"
                        else "Requires a match history CSV. Not available for this dataset."
                    ),
                    "ensemble": predictions_to_table(ensemble_results),
                    "ensemble_description": "Average of all available mathematical models.",
                    "combined": predictions_to_table(combined_results),
                    "combined_description": "Ensemble (40%) + internet research (35%) + AI council (25%)",
                    # Per-entity breakdown for the "Combined Prediction" table (Section 2):
                    # ensemble + internet + council → final range, per entity.
                    "source_breakdown": [
                        {
                            "entity": r.entity,
                            "ensemble_pct": round(dataset_probs.get(r.entity, 0) * 100, 1),
                            "internet_pct": (round(internet_probs.get(r.entity, 0) * 100, 1)
                                             if internet_probs.get(r.entity) else None),
                            "council_pct": (round(council_probs.get(r.entity, 0) * 100, 1)
                                            if council_probs.get(r.entity) else None),
                            "low_pct": r.low_pct,
                            "high_pct": r.high_pct,
                        }
                        for r in combined_results[:10]
                    ],
                }

                # Step 1d — print what the prediction engine extracted from each source.
                if DEBUG:
                    print(f"\n[PREDICTION] Dataset probs: {dataset_probs}", flush=True)
                    print(f"[PREDICTION] Internet probs: {internet_probs}", flush=True)
                    print(f"[PREDICTION] Council probs: {council_probs}", flush=True)
                    print(
                        "[PREDICTION] Final results: "
                        f"{[(r.entity, r.low_pct, r.high_pct) for r in prediction_results[:5]]}",
                        flush=True,
                    )

                # Prediction explanation charts (Part 3) + the meta the explainer box needs.
                prediction_charts = generate_prediction_charts(
                    prediction_results,
                    dataset_probs,
                    internet_probs,
                    council_probs,
                    df=data_df,
                    columns_info=(data_summary.get("columns") if data_summary else None),
                    model_a_probs=dataset_models.get("model_a_probs"),
                    model_b_probs=dataset_models.get("model_b_probs"),
                    agreement=dataset_models.get("agreement"),
                )
                prediction_meta = {
                    "n_sources": len((internet_findings or {}).get("sources", [])),
                    "n_council": len(stage1_results),
                    "today_date": today_date,
                    "n_simulations": _N_SIMULATIONS,
                    "dataset_method": dataset_method,
                    "rho": dataset_models.get("rho", -0.107),
                    "rho_fitted": dataset_models.get("rho_fitted", False),
                    "model_c_match_count": model_c_match_count,
                    "model_c_status": model_c_status,
                    "host_entity": dataset_models.get("host_entity"),
                    "host_boost": dataset_models.get("host_boost", 0),
                    "stability_note": dataset_models.get("stability_note"),
                    "n_simulations_used": dataset_models.get("n_simulations_used", _N_SIMULATIONS),
                    "computed_at": datetime.utcnow().isoformat() + "Z",
                }

                if prediction_table:
                    yield act(
                        "predictions_computed",
                        f"Algorithm computed predictions from {len(dataset_probs)} dataset entries, "
                        f"{len(internet_probs)} internet sources, {len(council_probs)} council responses",
                        reasoning=(
                            "Combining ELO simulation (40%), internet research consensus (35%), and "
                            "model agreement (25%) into a single deterministic probability."
                        ),
                    )

                prediction_context = format_chairman_prediction_block(prediction_table, suite=prediction_suite)

                # Stage 3
                _advance("stage 3")
                update_conversation_status(request.conversation_id, "running", "council_stage3")
                yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
                yield act(
                    "synthesis_started",
                    "Chairman synthesising final answer",
                    reasoning="The chairman weighs every model's analysis alongside the research to produce one calibrated, final answer.",
                )
                stage3_result = await stage3_synthesize_final(
                    enriched_prompt, stage1_results, stage2_results, prediction_context
                )
                yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

                # If the deterministic engine produced nothing (e.g. text mode),
                # fall back to extracting predictions from the chairman's prose.
                if not prediction_table:
                    prediction_table = await extract_predictions(
                        stage3_result.get("response", "") if stage3_result else ""
                    )

                # Build structured report
                _advance("report")
                update_conversation_status(request.conversation_id, "running", "synthesis")
                report = build_report(
                    question=actual_question,
                    data_summary=data_summary,
                    charts=charts,
                    internet_findings=internet_findings,
                    council_responses=stage1_results,
                    stage2_results=stage2_results,
                    chairman_synthesis=stage3_result,
                    metadata=metadata,
                    mode=mode,
                    prediction_table=prediction_table,
                    prediction_charts=prediction_charts,
                    prediction_meta=prediction_meta,
                    prediction_suite=prediction_suite,
                )
                # Suggested deeper questions the user can one-click into a new run.
                from .report_builder import generate_follow_ups
                report["follow_ups"] = await generate_follow_ups(
                    actual_question, stage3_result.get("response", "") if stage3_result else ""
                )
                yield f"data: {json.dumps({'type': 'report_complete', 'data': report})}\n\n"
                yield act(
                    "report_built",
                    f"Report ready · {len(report.get('sections', {}))} sections",
                    reasoning="Assembling the final structured report with the prediction table, comparison tables, and cited sources.",
                )

                # Persist enriched conversation JSON
                _save_enriched_conversation(
                    conversation_id=request.conversation_id,
                    mode=mode,
                    file_id=request.file_id,
                    data_summary=data_summary,
                    charts=charts,
                    internet_findings=internet_findings,
                    stage1_results=stage1_results,
                    stage2_results=stage2_results,
                    stage3_result=stage3_result,
                    report=report,
                    activity=activity_events,
                    prediction_charts=prediction_charts,
                    df=data_df,
                )

                # Pipeline finished — mark complete so polling clients stop.
                update_conversation_status(request.conversation_id, "complete", "done")

                if title_task:
                    title = await title_task
                    storage.update_conversation_title(request.conversation_id, title)
                    yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

                yield f"data: {json.dumps({'type': 'complete'})}\n\n"

            # ----------------------------------------------------------------
            # FOLLOW-UP — chairman only
            # ----------------------------------------------------------------
            else:
                yield f"data: {json.dumps({'type': 'followup_start'})}\n\n"

                # Build context from stored conversation
                pipeline = conversation.get("pipeline", {})
                context_prompt = _build_followup_prompt(actual_question, conversation, pipeline)

                from .openrouter import query_model
                chairman = config.get_chairman_model()
                response = await query_model(chairman, [{"role": "user", "content": context_prompt}])

                if response is None:
                    response = {"content": "Error: Chairman unavailable."}

                chairman_response = {"model": chairman, "response": response.get("content", "")}

                # Persist followup as a lightweight assistant message
                conv = storage.get_conversation(request.conversation_id)
                conv["messages"].append({
                    "role": "assistant",
                    "type": "chairman_followup",
                    "stage3": chairman_response,
                })
                storage.save_conversation(conv)

                yield f"data: {json.dumps({'type': 'followup_complete', 'data': chairman_response})}\n\n"
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            update_conversation_status(request.conversation_id, "error", error_message=str(e))
            yield act("stage_error", f"{current_stage}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    # Streaming (SSE) is opt-in behind ?stream=1 — a long-lived stream times out
    # on serverless functions. The DEFAULT is job kickoff + polling: return
    # immediately and run the pipeline as a background task that persists status
    # (which GET /api/conversations/{id}/status reports). asyncio.create_task
    # captures the current context, so the user's BYO key still resolves inside
    # the task even after the request's identity is unbound.
    if http_request.query_params.get("stream") == "1":
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    async def _drain():
        gen = event_generator()
        try:
            async for _ in gen:  # drive the pipeline to completion (events discarded)
                pass
        except Exception as e:  # pragma: no cover — generator handles its own errors
            update_conversation_status(request.conversation_id, "error", error_message=str(e))
        finally:
            _pipeline_tasks.discard(task)

    task = asyncio.create_task(_drain())
    _pipeline_tasks.add(task)  # keep a strong ref so the task isn't GC'd mid-run
    update_conversation_status(request.conversation_id, "running", "initialising")
    return JSONResponse({"conversation_id": request.conversation_id, "status": "running"})


@app.post("/api/reanalyse")
async def reanalyse(request: ReanalyseRequest, http_request: Request):
    """Re-run data analysis on filtered dataset. Returns updated charts and data segments only."""
    import pandas as pd

    conversation = _owned(request.conversation_id, http_request)

    pipeline = conversation.get("pipeline", {})
    file_info = conversation.get("file")
    if not file_info:
        raise HTTPException(status_code=400, detail="Conversation has no uploaded dataset")

    file_path = file_info.get("path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk")

    # Chart caching (5.4): if the filter state matches the last fingerprint, return
    # the cached charts immediately instead of recomputing from the full dataset.
    import hashlib
    fingerprint = hashlib.sha256(json.dumps(request.filters, sort_keys=True, default=str).encode()).hexdigest()[:16]
    cached = pipeline.get("chart_cache")
    if cached and cached.get("fingerprint") == fingerprint:
        return cached["result"]

    # Load and filter
    result = analyse_file(file_path)
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    df = result["dataframe"]
    filters = request.filters

    if "date_range" in filters and filters["date_range"]:
        dr = filters["date_range"]
        date_cols = [c["name"] for c in result["data_summary"]["columns"] if c["type"] == "datetime"]
        if date_cols and len(dr) == 2:
            col = date_cols[0]
            df[col] = pd.to_datetime(df[col])
            df = df[(df[col] >= dr[0]) & (df[col] <= dr[1])]

    if "categories" in filters and filters["categories"]:
        for col, values in filters["categories"].items():
            if values and col in df.columns:
                df = df[df[col].isin(values)]

    if "numeric_ranges" in filters and filters["numeric_ranges"]:
        for col, rng in filters["numeric_ranges"].items():
            if rng and col in df.columns and len(rng) == 2:
                df = df[(df[col] >= rng[0]) & (df[col] <= rng[1])]

    # Re-run analysis on the filtered dataframe in memory.
    from .data_analysis import analyse_df
    filtered_result = analyse_df(df.reset_index(drop=True))

    if filtered_result.get("error"):
        raise HTTPException(status_code=400, detail="No rows match the selected filters")

    from .report_builder import _build_data_segments_table
    data_segments = _build_data_segments_table(filtered_result["data_summary"])

    response = {
        "charts": filtered_result["charts"],
        "data_segments_table": data_segments,
        "data_summary": filtered_result["data_summary"],
    }

    # Persist active filters + cache the result under its filter fingerprint (5.4).
    conv = storage.get_conversation(request.conversation_id)
    if "pipeline" not in conv:
        conv["pipeline"] = {}
    conv["pipeline"]["active_filters"] = filters
    conv["pipeline"]["chart_cache"] = {"fingerprint": fingerprint, "result": response}
    storage.save_conversation(conv)

    return response


@app.get("/api/export-format")
async def export_format():
    """Report which export format the server can produce so the UI can label the
    download button correctly ('Download PDF Report' vs 'Download HTML Report')."""
    from .pdf_export import pdf_available
    return {"format": "pdf" if pdf_available() else "html"}


@app.get("/api/export/{conversation_id}")
async def export_report_endpoint(conversation_id: str, http_request: Request, format: Optional[str] = None, mode: Optional[str] = None):
    """Generate and return the stored report as a PDF, or an HTML file when the
    PDF toolchain (WeasyPrint/Pango/Cairo) is unavailable.

    Pass ?format=html for a shareable HTML snapshot (6.3), or ?mode=dashboard for
    the more-visual dashboard export — metrics, charts and data table (4.7)."""
    from .pdf_export import export_report

    conversation = _owned(conversation_id, http_request)

    base = os.path.join(EXPORTS_DIR, conversation_id + ("-dashboard" if mode == "dashboard" else ""))
    try:
        result = await export_report(conversation, base, fmt=format, mode=mode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")

    if not os.path.exists(result["path"]):
        raise HTTPException(status_code=500, detail="Export failed (no output produced)")

    return FileResponse(
        result["path"],
        media_type=result["media_type"],
        filename=f"report-{conversation_id[:8]}.{result['extension']}",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_upload(file_id: str) -> dict | None:
    """Locate an uploaded file by file_id prefix."""
    if not file_id or not storage.is_valid_id(file_id):
        return None
    for name in os.listdir(UPLOADS_DIR):
        if name.startswith(file_id):
            return {"path": os.path.join(UPLOADS_DIR, name), "filename": name}
    return None


def _build_followup_prompt(question: str, conversation: dict, pipeline: dict) -> str:
    parts = [f"You are the chairman of an AI council. Answer a follow-up question using the stored context below.\n"]

    if pipeline.get("data_summary"):
        s = pipeline["data_summary"]
        parts.append(f"Dataset: {s['row_count']} rows, {s['column_count']} columns.")

    if pipeline.get("internet_findings"):
        findings = pipeline["internet_findings"]
        parts.append(f"Internet research summary:\n{findings.get('content', '')}")

    if pipeline.get("chairman_synthesis"):
        parts.append(f"Previous council synthesis:\n{pipeline['chairman_synthesis']}")

    parts.append(f"\nFollow-up question: {question}")
    return "\n\n".join(parts)


def _save_enriched_conversation(
    conversation_id: str,
    mode: str,
    file_id: str | None,
    data_summary: dict | None,
    charts: list,
    internet_findings: dict | None,
    stage1_results: list,
    stage2_results: list,
    stage3_result: dict,
    report: dict,
    activity: list | None = None,
    prediction_charts: list | None = None,
    df=None,
):
    conv = storage.get_conversation(conversation_id)
    conv["mode"] = mode

    if file_id:
        file_record = _find_upload(file_id)
        if file_record:
            conv["file"] = {
                "id": file_id,
                "name": file_record["filename"],
                "path": file_record["path"],
                "rows": data_summary["row_count"] if data_summary else 0,
                "columns": data_summary["column_count"] if data_summary else 0,
            }

    council_responses_dict = {}
    for r in stage1_results:
        council_responses_dict[r["model"]] = {"stage1": r.get("response", "")}
    for r in stage2_results:
        m = r.get("model")
        if m in council_responses_dict:
            council_responses_dict[m]["stage2_review"] = r.get("ranking", "")
            council_responses_dict[m]["stage2_ranking"] = r.get("parsed_ranking", [])

    # Strip non-serialisable dataframe before saving charts
    serialisable_charts = [{"title": c["title"], "type": c["type"], "plotly_json": c["plotly_json"]} for c in charts]

    # Guarantee a flat, deduplicated top-level source list so the frontend Sources
    # tab can be restored on reload even if the activity log is missing its links.
    if isinstance(internet_findings, dict):
        flat_sources = list(internet_findings.get("sources") or [])
        if not flat_sources:
            seen = set()
            for s in internet_findings.get("searches", []) or []:
                for src in s.get("sources", []) or []:
                    url = src.get("url")
                    if url and url not in seen:
                        seen.add(url)
                        flat_sources.append(src)
        internet_findings = {**internet_findings, "all_sources": flat_sources}

    conv["pipeline"] = {
        "data_summary": data_summary,
        "charts": serialisable_charts,
        "active_filters": {},
        "internet_findings": internet_findings,
        "live_scores": (internet_findings or {}).get("live_scores", []),
        "council_responses": council_responses_dict,
        "chairman_synthesis": stage3_result.get("response", "") if stage3_result else "",
        "comparison_tables": report.get("comparison_tables", {}),
        "report": report,
        "activity": activity or [],
        "prediction_charts": prediction_charts or [],
    }

    # Every research/AI run also produces a live dashboard: auto charts + the
    # research findings and chairman synthesis pinned as insight widgets. The
    # user then iterates on it via the dashboard assistant (update-in-place).
    # An existing dashboard is preserved — its edits must never be clobbered.
    if not conv.get("dashboard"):
        from .dashboard import augment_with_research_analytics, build_dashboard_spec, insights_from_pipeline
        conv["dashboard"] = build_dashboard_spec(
            data_summary,
            serialisable_charts,
            title=conv.get("title", "Dashboard"),
            insights=insights_from_pipeline(internet_findings, stage3_result),
            has_rows=bool(conv.get("file")),
            df=df,
        )
        # Pin the run's own analytics: source/council/confidence metric cards
        # and the prediction summary. This is what makes a research dashboard
        # more than a data dashboard.
        augment_with_research_analytics(conv["dashboard"], internet_findings, stage1_results, report)
        # Data-mode runs also get a deterministic statistical read of the dataset.
        if df is not None and data_summary:
            from .dashboard import analyze_dataset, _upsert_insight
            stat_text = analyze_dataset(df, data_summary.get("columns", []), data_summary.get("statistics", {}))
            if stat_text:
                _upsert_insight(conv["dashboard"]["widgets"], "Statistical analysis", stat_text)

    # Also add a full assistant message (strips dataframe from charts already done above)
    conv["messages"].append({
        "role": "assistant",
        "type": "full_report",
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "report": report,
    })

    storage.save_conversation(conv)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
