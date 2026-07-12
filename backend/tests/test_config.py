"""BYO-key policy: a signed-in user's own key is used, never the platform owner's."""

from backend import config
from backend.users import current_user_ctx


def test_open_mode_falls_back_to_settings(monkeypatch):
    monkeypatch.setattr(config, "_settings", {"openrouter_api_key": "sk-global"})
    token = current_user_ctx.set(None)  # open mode (no identity)
    try:
        assert config.get_api_key() == "sk-global"
    finally:
        current_user_ctx.reset(token)


def test_signed_in_user_uses_own_key_not_owner_key(monkeypatch):
    # Even with a global owner key configured, an identified user's own key wins,
    # and the owner key is NEVER returned for that user.
    monkeypatch.setattr(config, "_settings", {"openrouter_api_key": "sk-owner"})
    user = {"id": "u_1", "settings": {"openrouter_api_key": "sk-user"}}
    token = current_user_ctx.set(user)
    try:
        assert config.get_api_key() == "sk-user"
    finally:
        current_user_ctx.reset(token)


def test_signed_in_user_without_key_gets_none_not_owner_key(monkeypatch):
    monkeypatch.setattr(config, "_settings", {"openrouter_api_key": "sk-owner"})
    user = {"id": "u_1", "settings": {}}
    token = current_user_ctx.set(user)
    try:
        assert config.get_api_key() is None  # hard-stops the pipeline, never spends owner's
    finally:
        current_user_ctx.reset(token)


def test_gemini_key_same_policy(monkeypatch):
    monkeypatch.setattr(config, "_settings", {"gemini_api_key": "g-owner"})
    user = {"id": "u_1", "settings": {"gemini_api_key": "g-user"}}
    token = current_user_ctx.set(user)
    try:
        assert config.get_gemini_api_key() == "g-user"
    finally:
        current_user_ctx.reset(token)


def test_settings_view_masks_key(monkeypatch):
    monkeypatch.setattr(config, "_settings", {"openrouter_api_key": "sk-or-v1-abcdef1234567890"})
    token = current_user_ctx.set(None)
    try:
        view = config.get_settings_view()
        assert view["api_key_set"] is True
        assert "sk-or-v1-abcdef1234567890" not in view["api_key_masked"]
    finally:
        current_user_ctx.reset(token)
