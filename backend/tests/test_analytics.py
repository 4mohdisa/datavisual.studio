"""Phase 1c — first-party event instrumentation: allowlist, privacy (no dataset
values leak), capped read, and the /api/events ingest + anon→user stitch."""
import json

from backend import analytics


def _events():
    return [json.loads(l) for l in analytics.ANALYTICS_PATH.read_text().splitlines()]


def test_allowlist_drops_unknown_events():
    analytics.record_event("not_a_real_event", anon_id="a_1")
    assert not analytics.ANALYTICS_PATH.exists() or _events() == []


def test_record_event_shape():
    analytics.record_event("landing_view", anon_id="a_1", session_id="s_1",
                           path="/", referrer="https://x", utm={"source": "tw"})
    e = _events()[-1]
    assert e["event"] == "landing_view" and e["anon_id"] == "a_1"
    assert e["session_id"] == "s_1" and e["utm"] == {"source": "tw"}


def test_props_never_carry_dataset_values():
    # A nested payload (e.g. rows) must be stripped; only flat scalar metadata.
    analytics.record_event("upload_completed", anon_id="a_1", props={
        "rows": 100, "cols": 4, "sample_row": {"ssn": "123-45-6789"},
        "cells": [1, 2, 3], "long": "x" * 5000,
    })
    props = _events()[-1]["props"]
    assert props["rows"] == 100 and props["cols"] == 4
    assert "sample_row" not in props and "cells" not in props  # nested dropped
    assert len(props["long"]) <= 200                            # truncated


def test_read_events_caps_by_age():
    analytics.record_event("landing_view", anon_id="a_old")
    # Rewrite that record with an ancient ts.
    lines = analytics.ANALYTICS_PATH.read_text().splitlines()
    old = json.loads(lines[-1]); old["ts"] = "2000-01-01T00:00:00+00:00"
    analytics.ANALYTICS_PATH.write_text("\n".join(lines[:-1] + [json.dumps(old)]) + "\n")
    analytics.record_event("demo_view", anon_id="a_new")
    events = analytics.read_events(since_days=30)
    assert any(e["event"] == "demo_view" for e in events)
    assert not any(e.get("anon_id") == "a_old" for e in events)  # aged out


def test_read_events_normalises_legacy_shape():
    analytics.ANALYTICS_PATH.write_text(json.dumps({
        "ts": "2999-01-01T00:00:00+00:00", "kind": "share", "meta": {"x": 1},
    }) + "\n")
    e = analytics.read_events(since_days=30)[0]  # future ts is within cutoff
    assert e["event"] == "share" and e["props"] == {"x": 1}


# --- the ingest endpoint + stitch -----------------------------------------

def test_events_endpoint_records_and_stitches(client):
    r = client.post("/api/events", json={
        "event": "signup_completed", "anon_id": "a_visitor", "session_id": "s_1",
        "path": "/sign-up",
    })
    assert r.status_code == 200 and r.json()["ok"]
    # identify stitches anon → user
    client.post("/api/events", json={
        "event": "identify", "anon_id": "a_visitor", "props": {"user_id": "u_42"},
    })
    evs = _events()
    assert any(e["event"] == "signup_completed" and e["anon_id"] == "a_visitor" for e in evs)
    assert any(e["event"] == "identify" and e["anon_id"] == "a_visitor" for e in evs)


def test_events_endpoint_rejects_unknown_event(client):
    r = client.post("/api/events", json={"event": "evil_event", "anon_id": "a"})
    assert r.status_code == 200          # accepted but…
    assert not any(e["event"] == "evil_event" for e in _events()) if analytics.ANALYTICS_PATH.exists() else True
