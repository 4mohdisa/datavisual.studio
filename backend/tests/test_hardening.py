"""Phase 6 — launch hardening: rate limiting, disk GC, zero-key onboarding."""

import os
import time

from backend import gc
from backend.ratelimit import RateLimiter


# --- rate limiter -------------------------------------------------------------

def test_token_bucket_allows_then_blocks():
    rl = RateLimiter(capacity=3, refill_per_min=0)  # no refill
    assert [rl.check("u:a") for _ in range(3)] == [True, True, True]
    assert rl.check("u:a") is False  # bucket empty


def test_token_bucket_refills():
    rl = RateLimiter(capacity=1, refill_per_min=6000)  # 100/sec
    assert rl.check("k") is True
    assert rl.check("k") is False
    time.sleep(0.05)  # ~5 tokens refilled
    assert rl.check("k") is True


def test_check_is_all_or_nothing():
    rl = RateLimiter(capacity=1, refill_per_min=0)
    rl.check("ip:x")             # spend the IP bucket
    before = rl._tokens.get("u:y", 1)
    assert rl.check("u:y", "ip:x") is False  # ip:x is empty → denied
    assert rl._tokens.get("u:y", 1) == before  # user bucket NOT spent


def test_disabled_limiter_always_allows():
    rl = RateLimiter(capacity=1, refill_per_min=0)
    rl.enabled = False
    assert all(rl.check("k") for _ in range(10))


# --- disk GC ------------------------------------------------------------------

def test_gc_removes_old_orphans_keeps_referenced_and_recent(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"; uploads.mkdir(exist_ok=True)
    exports = tmp_path / "exports"; exports.mkdir(exist_ok=True)
    old_orphan = uploads / "fid_old.csv"; old_orphan.write_text("x")
    recent_orphan = uploads / "fid_recent.csv"; recent_orphan.write_text("x")
    referenced = uploads / "fid_ref.csv"; referenced.write_text("x")
    old_export = exports / "report.pdf"; old_export.write_text("x")

    # age the old files 40 days
    old = time.time() - 40 * 86400
    os.utime(old_orphan, (old, old))
    os.utime(old_export, (old, old))

    monkeypatch.setattr(gc.storage, "list_conversations", lambda: [{"id": "c1"}])
    monkeypatch.setattr(gc.storage, "get_conversation", lambda cid: {"file": {"save_name": "fid_ref.csv"}})

    removed = gc.sweep(str(uploads), str(exports), max_age_days=30)

    assert str(old_orphan) in removed and not old_orphan.exists()
    assert str(old_export) in removed and not old_export.exists()
    assert recent_orphan.exists()   # too new to GC
    assert referenced.exists()      # a conversation points at it


# --- zero-key onboarding ------------------------------------------------------

def test_sample_dashboard_needs_no_key(client):
    r = client.post("/api/sample-dashboard", json={"sample": "sales"})
    assert r.status_code == 200, r.text
    cid = r.json()["conversation_id"]
    conv = client.get(f"/api/conversations/{cid}").json()
    assert conv["mode"] == "dashboard" and conv.get("is_sample") is True
    assert {w["kind"] for w in conv["dashboard"]["widgets"]} & {"metric", "chart"}


def test_samples_are_listed(client):
    keys = {s["key"] for s in client.get("/api/samples").json()["samples"]}
    assert {"saas", "sales", "marketing"} <= keys
