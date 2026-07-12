"""JSON-based storage for conversations."""

import json
import os
import re
import secrets
import threading
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR

# Conversation ids are used to build file paths (here and in the export
# endpoint), so they must never contain path separators or other junk. This is
# the single trust-boundary check every caller routes through.
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def is_valid_id(conversation_id: str) -> bool:
    """True when the id is safe to embed in a filesystem path. The charset is
    restricted AND `..` is refused outright, so an id can never be a parent-dir
    reference even where it's used as a path component without a suffix."""
    if not conversation_id or ".." in conversation_id:
        return False
    return bool(_SAFE_ID.match(conversation_id))


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """Get the file path for a conversation."""
    if not is_valid_id(conversation_id):
        raise ValueError(f"Invalid conversation id: {conversation_id!r}")
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found (or the id is malformed)
    """
    if not is_valid_id(conversation_id):
        return None
    path = get_conversation_path(conversation_id)

    if not os.path.exists(path):
        return None

    with open(path, 'r') as f:
        return json.load(f)


def save_conversation(conversation: Dict[str, Any]):
    """
    Save a conversation to storage.

    Args:
        conversation: Conversation dict to save
    """
    ensure_data_dir()

    path = get_conversation_path(conversation['id'])
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)


def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts
    """
    ensure_data_dir()

    conversations = []
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith('.json'):
            continue
        path = os.path.join(DATA_DIR, filename)
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # A truncated/corrupt file (e.g. an interrupted write) must not take
            # down the whole list — skip it.
            continue
        # Skip any stray/index file that isn't a conversation record.
        if not isinstance(data, dict) or "id" not in data or "messages" not in data:
            continue
        conversations.append({
            "id": data["id"],
            "created_at": data["created_at"],
            "title": data.get("title", "New Conversation"),
            "message_count": len(data["messages"]),
            "mode": data.get("mode", "chat"),
            "owner_id": data.get("owner_id"),
        })

    # Sort by creation time, newest first
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

    return conversations


def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "user",
        "content": content
    })

    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation)


# ---------------------------------------------------------------------------
# Public sharing — an unguessable token maps to a conversation so anyone with
# the link can VIEW it read-only, without the token ever being a file path
# (the mapped conversation_id is the only thing that touches the filesystem,
# and it is already validated). The index (data/shares.json) gives O(1)
# lookup; the token is also mirrored onto the record so a stale index can't
# resurrect a revoked share.
# ---------------------------------------------------------------------------

# Kept in data/ (the parent of the conversations dir) alongside sources.json,
# NOT inside DATA_DIR — list_conversations iterates every .json in DATA_DIR.
SHARES_PATH = os.path.join(os.path.dirname(DATA_DIR) or ".", "shares.json")
_shares_lock = threading.Lock()


def _load_shares() -> Dict[str, str]:
    try:
        with open(SHARES_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_shares(shares: Dict[str, str]) -> None:
    ensure_data_dir()
    with open(SHARES_PATH, "w") as f:
        json.dump(shares, f, indent=2)


def create_share(conversation_id: str) -> Optional[str]:
    """Enable public sharing for a conversation, returning its share token.
    Idempotent — an already-shared conversation returns its existing token."""
    with _shares_lock:
        conv = get_conversation(conversation_id)
        if conv is None:
            return None
        token = conv.get("share_id")
        if not token:
            token = secrets.token_urlsafe(9)  # ~12 url-safe chars
            conv["share_id"] = token
            save_conversation(conv)
            shares = _load_shares()
            shares[token] = conversation_id
            _save_shares(shares)
        return token


def delete_share(conversation_id: str) -> None:
    """Revoke public sharing — drops the token from the index and the record."""
    with _shares_lock:
        conv = get_conversation(conversation_id)
        if conv is None:
            return
        token = conv.get("share_id")
        if token:
            shares = _load_shares()
            shares.pop(token, None)
            _save_shares(shares)
            conv.pop("share_id", None)
            save_conversation(conv)


def get_shared_conversation(share_id: str) -> Optional[Dict[str, Any]]:
    """Resolve a share token to its conversation, or None if the token is
    unknown/revoked. `share_id` is validated because it feeds the same id
    grammar; the record's own token must still match (revocation safety)."""
    if not is_valid_id(share_id):
        return None
    cid = _load_shares().get(share_id)
    if not cid:
        return None
    conv = get_conversation(cid)
    if conv is None or conv.get("share_id") != share_id:
        return None
    return conv
