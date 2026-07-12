"""Phase 2b — the direct-upload HMAC ticket.

The carve-out that lets a >4.5 MB file skip the serverless proxy. The ticket is
the only auth on /api/upload-direct, so it's treated with share-token paranoia:
signed with PROXY_SHARED_SECRET, expiring, single-use, traversal-rejecting.
"""

import hashlib
import hmac
import time

from backend import main

CSV = b"region,revenue,units\nNorth,120,10\nSouth,90,8\n"


def _mint(user_id, secret, *, exp=None, nonce="nonce-abc"):
    exp = exp if exp is not None else int(time.time()) + 300
    mac = hmac.new(secret.encode(), f"{user_id}.{exp}.{nonce}".encode(), hashlib.sha256).hexdigest()
    return f"{user_id}.{exp}.{nonce}.{mac}"


def _post(client, ticket):
    return client.post("/api/upload-direct", headers={"x-upload-ticket": ticket},
                       files={"file": ("sales.csv", CSV, "text/csv")})


def test_valid_ticket_uploads(client, monkeypatch):
    monkeypatch.setenv("PROXY_SHARED_SECRET", "sekret")
    main._used_upload_nonces.clear()
    r = _post(client, _mint("user_1", "sekret", nonce="ok"))
    assert r.status_code == 200, r.text
    assert r.json()["file_id"]


def test_tampered_ticket_rejected(client, monkeypatch):
    monkeypatch.setenv("PROXY_SHARED_SECRET", "sekret")
    assert _post(client, _mint("user_1", "WRONG-secret", nonce="t")).status_code == 401


def test_expired_ticket_rejected(client, monkeypatch):
    monkeypatch.setenv("PROXY_SHARED_SECRET", "sekret")
    assert _post(client, _mint("user_1", "sekret", exp=int(time.time()) - 5, nonce="e")).status_code == 401


def test_ticket_is_single_use(client, monkeypatch):
    monkeypatch.setenv("PROXY_SHARED_SECRET", "sekret")
    main._used_upload_nonces.clear()
    t = _mint("user_1", "sekret", nonce="replay")
    assert _post(client, t).status_code == 200
    assert _post(client, t).status_code == 401  # nonce already consumed


def test_traversal_nonce_rejected(client, monkeypatch):
    monkeypatch.setenv("PROXY_SHARED_SECRET", "sekret")
    # Even a correctly-signed ticket is refused if the nonce carries a slash.
    assert _post(client, _mint("user_1", "sekret", nonce="a/b")).status_code == 401


def test_direct_upload_disabled_without_secret(client, monkeypatch):
    monkeypatch.delenv("PROXY_SHARED_SECRET", raising=False)
    assert _post(client, _mint("user_1", "anything", nonce="x")).status_code == 401
