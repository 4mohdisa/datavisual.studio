"""Phase 1b — BYO API keys encrypted at rest.

Users' OpenRouter/Gemini keys cost them money; plaintext in users.json is a
launch blocker. Keys must be ciphertext on disk and only decrypt in memory.
"""

import json

from backend import crypto, users


def test_encrypt_decrypt_roundtrip():
    ct = crypto.encrypt("sk-or-v1-secret")
    assert ct.startswith("enc:v1:") and ct != "sk-or-v1-secret"
    assert crypto.decrypt(ct) == "sk-or-v1-secret"


def test_encrypt_is_idempotent():
    ct = crypto.encrypt("x")
    assert crypto.encrypt(ct) == ct  # already encrypted → unchanged


def test_decrypt_plaintext_passthrough():
    assert crypto.decrypt("legacy-plaintext") == "legacy-plaintext"
    assert crypto.decrypt(None) is None
    assert crypto.encrypt(None) is None


def test_decrypt_with_wrong_secret_returns_none(monkeypatch):
    ct = crypto.encrypt("secret")
    monkeypatch.setattr(crypto, "_secret_cache", None)
    monkeypatch.setenv("SECRET_KEY", "a-totally-different-secret")
    assert crypto.decrypt(ct) is None  # degraded, not a crash


def test_user_keys_stored_encrypted_on_disk():
    users.get_or_create_user("clerk_enc", "e@x.com", "E")
    users.update_user_settings("clerk_enc", {"openrouter_api_key": "sk-or-plaintext"})
    raw = users.USERS_PATH.read_text()
    assert "sk-or-plaintext" not in raw          # never plaintext at rest
    assert "enc:v1:" in raw


def test_migrate_user_keys_encrypts_in_place_and_is_idempotent():
    users.USERS_PATH.write_text(json.dumps({
        "clerk_m": {"id": "u_m", "clerk_id": "clerk_m",
                     "settings": {"openrouter_api_key": "sk-plain", "gemini_api_key": "g-plain"}},
    }))
    assert crypto.migrate_user_keys() == 2
    raw = users.USERS_PATH.read_text()
    assert "sk-plain" not in raw and "g-plain" not in raw
    assert crypto.migrate_user_keys() == 0        # idempotent — nothing left to do
