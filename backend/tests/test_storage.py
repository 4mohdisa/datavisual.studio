"""Storage trust boundary + share lifecycle."""

import json

import pytest

from backend import storage


# --- is_valid_id: the single path-traversal guard every id routes through -----

@pytest.mark.parametrize("good", ["abc", "u_1a2b3c", "a.b-c_d", "OftzOVkH_e_I", "123"])
def test_is_valid_id_accepts_safe(good):
    assert storage.is_valid_id(good)


@pytest.mark.parametrize("bad", [
    "", "../etc/passwd", "a/b", "a\\b", "..", "a b", "a;b", "a%2fb", None,
    "../../api/conversations",
])
def test_is_valid_id_rejects_unsafe(bad):
    assert not storage.is_valid_id(bad)


def test_get_conversation_bad_id_returns_none():
    assert storage.get_conversation("../secrets") is None


def test_get_conversation_path_rejects_bad_id():
    with pytest.raises(ValueError):
        storage.get_conversation_path("../x")


# --- save / load / list -------------------------------------------------------

def _conv(cid="c1", **extra):
    return {"id": cid, "created_at": "2026-01-01T00:00:00", "title": "T", "messages": [], **extra}


def test_save_and_load_roundtrip():
    storage.save_conversation(_conv("c1", mode="dashboard"))
    got = storage.get_conversation("c1")
    assert got["id"] == "c1" and got["mode"] == "dashboard"


def test_list_conversations_returns_metadata():
    storage.save_conversation(_conv("c1"))
    storage.save_conversation(_conv("c2", owner_id="u_x"))
    items = {c["id"]: c for c in storage.list_conversations()}
    assert set(items) == {"c1", "c2"}
    assert items["c2"]["owner_id"] == "u_x"


def test_list_conversations_skips_corrupt_file():
    """A truncated/corrupt .json must not 500 the whole list (availability)."""
    storage.save_conversation(_conv("good"))
    Path = storage.Path
    (Path(storage.DATA_DIR) / "broken.json").write_text("{ this is not json")
    ids = [c["id"] for c in storage.list_conversations()]
    assert ids == ["good"]


def test_list_conversations_skips_non_conversation_json():
    storage.save_conversation(_conv("good"))
    (storage.Path(storage.DATA_DIR) / "index.json").write_text(json.dumps({"not": "a conversation"}))
    ids = [c["id"] for c in storage.list_conversations()]
    assert ids == ["good"]


# --- share lifecycle ----------------------------------------------------------

def test_create_share_is_idempotent_and_indexed():
    storage.save_conversation(_conv("c1"))
    t1 = storage.create_share("c1")
    t2 = storage.create_share("c1")
    assert t1 and t1 == t2  # idempotent
    assert storage.is_valid_id(t1)
    # token is recorded both on the record and in the index
    assert storage.get_conversation("c1")["share_id"] == t1
    index = json.loads(storage.Path(storage.SHARES_PATH).read_text())
    assert index[t1] == "c1"


def test_get_shared_conversation_resolves_and_rejects_bad_token():
    storage.save_conversation(_conv("c1"))
    token = storage.create_share("c1")
    assert storage.get_shared_conversation(token)["id"] == "c1"
    assert storage.get_shared_conversation("nope") is None
    assert storage.get_shared_conversation("../../api/conversations") is None  # traversal-safe


def test_delete_share_revokes_index_and_record():
    storage.save_conversation(_conv("c1"))
    token = storage.create_share("c1")
    storage.delete_share("c1")
    assert storage.get_shared_conversation(token) is None
    assert "share_id" not in storage.get_conversation("c1")
    assert json.loads(storage.Path(storage.SHARES_PATH).read_text()) == {}


def test_stale_index_cannot_resurrect_revoked_share():
    """If the record's token no longer matches, the index alone can't leak it."""
    storage.save_conversation(_conv("c1"))
    token = storage.create_share("c1")
    # Simulate a stale index entry pointing at a record whose token changed.
    conv = storage.get_conversation("c1")
    conv["share_id"] = "different"
    storage.save_conversation(conv)
    assert storage.get_shared_conversation(token) is None


def test_create_share_missing_conversation_returns_none():
    assert storage.create_share("does-not-exist") is None
