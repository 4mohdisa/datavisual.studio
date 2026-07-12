"""Phase 1a — atomic writes + per-conversation locking.

`data/` is the database; a torn write loses real data and a lost update drops a
freshly-minted share link. These tests fail without the atomic write / lock.
"""

import json
import os
import threading

import pytest

from backend import atomic, storage


def _conv(cid, **extra):
    return {"id": cid, "created_at": "t", "title": cid, "messages": [], **extra}


def test_atomic_write_leaves_no_partial_file(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    atomic.atomic_write_json(target, {"a": 1})
    assert json.loads(target.read_text()) == {"a": 1}

    # A crash at os.replace must leave the original intact and no .tmp behind.
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        atomic.atomic_write_json(target, {"a": 2})
    assert json.loads(target.read_text()) == {"a": 1}
    assert [p.name for p in tmp_path.iterdir() if ".tmp." in p.name] == []


def test_concurrent_conversation_writers():
    """20 threads each load→append→save on ONE id. Without the lock+re-read this
    loses updates; update_conversation must keep all 20."""
    cid = "concurrencyid"
    storage.save_conversation(_conv(cid, items=[]))

    def worker(n):
        storage.update_conversation(cid, lambda c: c.setdefault("items", []).append(n))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(storage.get_conversation(cid)["items"]) == list(range(20))


def test_share_mint_survives_concurrent_dashboard_save():
    """The audit's worst case: mint a share while a dashboard save races. Both
    take the per-conversation lock, so the share_id must survive either order."""
    cid = "shareraceid"
    storage.save_conversation(_conv(cid, dashboard={"widgets": []}))
    barrier = threading.Barrier(2)

    def mint():
        barrier.wait()
        storage.create_share(cid)

    def dashboard_save():
        barrier.wait()
        storage.update_conversation(cid, lambda c: c.__setitem__("dashboard", {"widgets": [{"id": "w1"}]}))

    t1, t2 = threading.Thread(target=mint), threading.Thread(target=dashboard_save)
    t1.start(); t2.start(); t1.join(); t2.join()

    conv = storage.get_conversation(cid)
    assert conv.get("share_id"), "share_id was clobbered by the concurrent dashboard save"
    assert storage.get_shared_conversation(conv["share_id"]) is not None
    assert conv["dashboard"]["widgets"] == [{"id": "w1"}]
