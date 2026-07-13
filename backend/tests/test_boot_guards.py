"""Phase 0e/0g — boot guards that must STOP the server on an unsafe config:
undecryptable key set (0e) and forgeable identity in a deployed env (0g)."""
import json

import pytest

import backend.main as main
from backend import crypto, users


# --- 0e: SECRET_KEY-mismatch refusal ---------------------------------------

def _write_user_with_key(enc_value):
    users.USERS_PATH.write_text(json.dumps({
        "clerk_1": {"id": "u_1", "settings": {"openrouter_api_key": enc_value}},
    }))


def test_verify_noop_without_registry():
    crypto.verify_key_decryptable()  # no users.json → nothing to verify


def test_verify_passes_when_key_matches():
    _write_user_with_key(crypto.encrypt("sk-real-key"))
    crypto.verify_key_decryptable()  # encrypted under the current key → fine


def test_verify_passes_with_plaintext_key():
    # Pre-migration plaintext isn't ciphertext; migrate handles it, don't refuse.
    _write_user_with_key("sk-plaintext")
    crypto.verify_key_decryptable()


def test_verify_refuses_on_key_mismatch(monkeypatch):
    enc = crypto.encrypt("sk-real-key")          # under the hermetic test key
    _write_user_with_key(enc)
    monkeypatch.setenv("SECRET_KEY", "a-totally-different-secret")
    crypto._secret_cache = None                  # force re-resolve of the new key
    with pytest.raises(RuntimeError, match="does not match"):
        crypto.verify_key_decryptable()


# --- 0g: identity-trust boot guard -----------------------------------------

def test_identity_guard_refuses_open_prod(monkeypatch):
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://datavisual.studio")
    monkeypatch.delenv("PROXY_SHARED_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="PROXY_SHARED_SECRET"):
        main._assert_identity_trust_safe()


def test_identity_guard_ok_with_secret(monkeypatch):
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://datavisual.studio")
    monkeypatch.setenv("PROXY_SHARED_SECRET", "s")
    main._assert_identity_trust_safe()  # secret present → safe


def test_identity_guard_ok_in_local_dev(monkeypatch):
    monkeypatch.delenv("FRONTEND_ORIGIN", raising=False)
    monkeypatch.delenv("PROXY_SHARED_SECRET", raising=False)
    main._assert_identity_trust_safe()  # no deploy marker → open dev is fine


# --- 0g: forged identity header is refused at the proxy-secret guard --------

def test_forged_identity_header_refused(client, monkeypatch):
    monkeypatch.setenv("PROXY_SHARED_SECRET", "topsecret")
    # Attacker forges the identity header but has no proxy secret.
    r = client.get("/api/conversations", headers={"x-clerk-user-id": "u_attacker"})
    assert r.status_code == 403


def test_proxy_secret_allows_through(client, monkeypatch):
    monkeypatch.setenv("PROXY_SHARED_SECRET", "topsecret")
    r = client.get("/api/conversations", headers={"x-proxy-secret": "topsecret"})
    assert r.status_code == 200
