"""Encrypt users' BYO API keys at rest.

`data/users.json` holds each user's OpenRouter / Gemini keys. Those keys cost
*users* real money, so plaintext at rest (a volume snapshot, a box compromise)
is a launch blocker. We encrypt them with Fernet (AES-128-CBC + HMAC) keyed off
a `SECRET_KEY` env var. Losing `SECRET_KEY` means users must re-enter their keys
— degraded, not catastrophic; the app keeps working, it just can't read the old
ciphertext (decrypt returns None, treated as "no key set").

Stored form: ``enc:v1:<fernet-token>``. The prefix makes migration idempotent
and lets plaintext (pre-migration) pass through decrypt unchanged.
"""

import base64
import hashlib
import json
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken

_PREFIX = "enc:v1:"
_secret_cache: str | None = None


def get_secret_key() -> str:
    """Resolve SECRET_KEY. Present → use it. Missing in prod (PROXY_SHARED_SECRET
    set) → refuse to start. Missing in dev → generate one, persist to .env, warn."""
    global _secret_cache
    if _secret_cache:
        return _secret_cache
    val = os.getenv("SECRET_KEY")
    if val:
        _secret_cache = val
        return val
    if os.getenv("PROXY_SHARED_SECRET"):
        raise RuntimeError(
            "SECRET_KEY is required in production — it encrypts users' API keys. "
            "Generate one (`openssl rand -hex 32`), set it, and restart."
        )
    # Dev convenience: mint one and persist it so keys survive a restart.
    val = secrets.token_urlsafe(32)
    try:
        with open(".env", "a", encoding="utf-8") as f:
            f.write(f"\nSECRET_KEY={val}\n")
    except OSError:
        pass
    os.environ["SECRET_KEY"] = val
    _secret_cache = val
    print("⚠️  SECRET_KEY was not set — generated a dev key and appended it to .env. "
          "Set SECRET_KEY explicitly in production.")
    return val


def _fernet() -> Fernet:
    # Any-length secret → a valid 32-byte urlsafe Fernet key.
    key = base64.urlsafe_b64encode(hashlib.sha256(get_secret_key().encode()).digest())
    return Fernet(key)


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(_PREFIX)


def encrypt(value: str | None) -> str | None:
    if not value or is_encrypted(value):
        return value
    return _PREFIX + _fernet().encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str | None:
    """Ciphertext → plaintext. Plaintext (pre-migration) passes through. Wrong
    SECRET_KEY / corrupt token → None (treated as 'no key')."""
    if not value or not is_encrypted(value):
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode()).decode()
    except InvalidToken:
        return None


def migrate_user_keys() -> int:
    """Encrypt any plaintext ``*_api_key`` in users.json in place (idempotent).
    Returns the number of keys migrated. Called once at backend startup."""
    from . import users
    from .atomic import atomic_write_json

    try:
        data = json.loads(users.USERS_PATH.read_text())
    except Exception:
        return 0
    migrated = 0
    for user in data.values():
        settings = user.get("settings") or {}
        for k, v in list(settings.items()):
            if k.endswith("_api_key") and v and not is_encrypted(v):
                settings[k] = encrypt(v)
                migrated += 1
    if migrated:
        atomic_write_json(users.USERS_PATH, data)
        print(f"🔒 Encrypted {migrated} plaintext API key(s) in users.json at boot.")
    return migrated
