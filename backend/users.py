"""Local user registry — identity lives with the data, not in a third-party DB.

Clerk authenticates the browser session; the Next.js proxy verifies it and
forwards the identity as trusted headers. This module maps that external
identity to OUR OWN generated user id (`u_<hex>`), stored in data/users.json on
the same machine as everything else. Nothing downstream (conversation owner_id,
exports, future features) ever references the Clerk id directly, so swapping
auth providers later means changing exactly one lookup.

Trust model: when PROXY_SHARED_SECRET is set (backend .env), every /api request
must carry the matching X-Proxy-Secret header — so a publicly reachable AWS
backend only accepts traffic from your Next server. Unset = open dev mode.
"""

import json
import threading
import uuid
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Request

# Request-scoped identity, set by the middleware in main.py. Deep call sites
# (config.get_api_key etc.) read it without any parameter threading — the
# whole reason users' own AI keys apply to every LLM call automatically.
current_user_ctx: ContextVar[Optional[dict]] = ContextVar("current_user", default=None)

USERS_PATH = Path("data/users.json")
_lock = threading.Lock()

# Headers attached by the authenticated Next.js proxy.
H_CLERK_ID = "x-clerk-user-id"
H_EMAIL = "x-user-email"
H_NAME = "x-user-name"


def _load() -> dict:
    try:
        return json.loads(USERS_PATH.read_text())
    except Exception:
        return {}


def _save(users: dict) -> None:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    USERS_PATH.write_text(json.dumps(users, indent=2))


def get_or_create_user(clerk_id: str, email: Optional[str] = None, name: Optional[str] = None) -> dict:
    """Resolve an external (Clerk) identity to our internal user record,
    creating it on first sight. Keyed by clerk_id; the record's `id` is ours."""
    with _lock:
        users = _load()
        user = users.get(clerk_id)
        if user is None:
            user = {
                "id": "u_" + uuid.uuid4().hex[:12],
                "clerk_id": clerk_id,
                "email": email,
                "name": name,
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            users[clerk_id] = user
            _save(users)
        elif (email and user.get("email") != email) or (name and user.get("name") != name):
            # Keep profile details current without a separate update path.
            user["email"] = email or user.get("email")
            user["name"] = name or user.get("name")
            _save(users)
        return user


def update_user_settings(clerk_id: str, patch: dict) -> dict:
    """Merge non-None fields into the user's private settings (their own AI
    keys live here, on the same local disk as everything else)."""
    with _lock:
        users = _load()
        user = users.get(clerk_id)
        if user is None:
            raise KeyError(clerk_id)
        settings = user.setdefault("settings", {})
        settings.update({k: v for k, v in patch.items() if v is not None})
        _save(users)
        return user


def user_settings(user: Optional[dict]) -> dict:
    return (user or {}).get("settings") or {}


def user_from_request(request: Request) -> Optional[dict]:
    """The per-request identity, resolved from the proxy's trusted headers.
    Returns None in open mode (no identity forwarded — e.g. local dev without
    Clerk keys), which disables ownership scoping entirely."""
    clerk_id = request.headers.get(H_CLERK_ID)
    if not clerk_id:
        return None
    return get_or_create_user(
        clerk_id,
        email=request.headers.get(H_EMAIL) or None,
        name=request.headers.get(H_NAME) or None,
    )
