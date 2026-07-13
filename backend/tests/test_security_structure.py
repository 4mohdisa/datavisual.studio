"""Phase 2d — structural security. Catches the mistake not yet made: a new
endpoint added without a conscious auth decision. Worth more than twenty
hand-written cases, because it fails the build on the NEXT forgotten `_owned()`.
"""
from fastapi.routing import APIRoute

import backend.main as main

# Every backend route must be classified into exactly ONE posture. A new route
# absent from all sets FAILS `test_every_route_is_classified` — forcing whoever
# adds it to decide its auth on purpose, in this file, under review.

OWNER_SCOPED = {  # enforce per-conversation ownership via _owned()
    "/api/conversations/{conversation_id}",
    "/api/conversations/{conversation_id}/status",
    "/api/conversations/{conversation_id}/share",      # POST + DELETE
    "/api/dashboard/{conversation_id}/suggestions",
    "/api/dashboard/{conversation_id}/chat",
    "/api/dashboard/{conversation_id}/sync",
    "/api/dataset/{conversation_id}",
    "/api/export/{conversation_id}",
    "/api/analyse",        # conversation_id in body → _owned()
    "/api/reanalyse",      # conversation_id in body → _owned()
}
IDENTITY_SCOPED = {  # act on the current user (list/create/account/upload)
    "/api/conversations",
    "/api/conversations/create",
    "/api/dashboard",
    "/api/upload",
    "/api/upload-direct",   # HMAC upload ticket is the capability
    "/api/connect",
    "/api/sample-dashboard",
    "/api/account/settings",
    "/api/account/validate",
}
PUBLIC = {  # intentionally unauthenticated
    "/", "/health",
    "/api/public/{share_id}",   # the share token is the capability
    "/api/demo", "/api/samples",
    "/api/events", "/api/error-log", "/api/export-format",
}
ADMIN = {"/api/admin/overview"}          # X-Admin-Password gated
OWNER_CONFIG = {"/api/settings", "/api/settings/validate"}  # blocked at the proxy

CLASSIFIED = OWNER_SCOPED | IDENTITY_SCOPED | PUBLIC | ADMIN | OWNER_CONFIG


def _route_paths():
    return {r.path for r in main.app.routes if isinstance(r, APIRoute)}


def test_every_route_is_classified():
    unclassified = _route_paths() - CLASSIFIED
    assert not unclassified, (
        f"Unclassified route(s): {sorted(unclassified)}. Add each to exactly one "
        f"posture set in test_security_structure.py — decide its auth on purpose."
    )


def test_no_stale_classifications():
    # Keep the lists honest: nothing classified that no longer exists.
    stale = CLASSIFIED - _route_paths()
    assert not stale, f"Classified paths that no longer exist: {sorted(stale)}"


def test_public_payloads_leak_no_owner_only_fields(client, upload_csv):
    """Deny-scan: serialise public payloads and assert none of the owner-only
    fields appear anywhere (string scan, so nothing hides nested)."""
    forbidden = ("owner_id", "\"file\"", "\"source\"", "\"history\"", "schedule",
                 "alerts", "alert_log", "digests", "unsub_token", "clerk_id",
                 "openrouter_api_key", "gemini_api_key")

    # Demo (public, prebuilt)
    demo_blob = str(client.get("/api/demo").json())
    for f in forbidden:
        assert f not in demo_blob, f"/api/demo leaked {f!r}"

    # A real share payload
    fid = upload_csv()
    cid = client.post("/api/dashboard", json={"file_id": fid}).json()["conversation_id"]
    token = client.post(f"/api/conversations/{cid}/share").json()["share_id"]
    share_blob = str(client.get(f"/api/public/{token}").json())
    for f in forbidden:
        assert f not in share_blob, f"/api/public leaked {f!r}"
