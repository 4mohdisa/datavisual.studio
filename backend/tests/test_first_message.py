"""Go-Live Phase 0e — test what a real person types FIRST.

Every prior golden test was a data query drawn from a plan ("total MRR",
"customers in June"). Nobody tested the messages a stranger actually sends first
into an assistant they've never used — and "what is this about?" was a hard 500.

Every message here must produce a USEFUL, non-erroring reply, on both a data
dashboard and a record with no dataset (the research/empty case). These are the
regression guard for the meta-intent fix.
"""
import json

import pandas as pd
import pytest

from backend.query import run_query_spec

SALES = (
    "region,month,revenue,units\n"
    "North,2026-01,120,10\nSouth,2026-01,90,8\nNorth,2026-02,150,12\n"
    "South,2026-02,110,9\nEast,2026-01,70,6\nWest,2026-02,200,15\n"
)

# What people actually type first. Split into two groups by the assertion they earn.
META_MESSAGES = [
    "what is this about?", "what can you do?", "explain this dashboard",
    "summarise this", "what data is this?", "help", "hello", "hi",
]
EDGE_MESSAGES = ["", "?", "revenue", "what is the churn rate?", "asdfghjkl", "you are useless"]

_HARD_ERROR = ("internal server error", "traceback", "edit failed",
               "not json serializable", "none of the")


# The no-AI-key path (query_model → None) is now enforced globally by the
# `hermetic_no_outbound` autouse fixture in conftest.py, so these tests need no
# per-file stub. The meta handler must still answer from context; the query path
# must degrade to a helpful redirect, never a 500.


def _make_dashboard(client):
    fid = client.post("/api/upload", files={"file": ("sales.csv", SALES.encode(), "text/csv")}).json()["file_id"]
    r = client.post("/api/dashboard", json={"file_id": fid})
    assert r.status_code == 200, r.text
    return r.json()["conversation_id"]


def _empty_record(client):
    """A conversation with no dataset — stands in for a research/empty record
    (no pandas path). dashboard_chat migrates it to a spec on first touch."""
    cid = "meta-empty"
    r = client.post("/api/conversations/create", json={"conversation_id": cid, "title": "Market research"})
    assert r.status_code == 200, r.text
    return cid


def _chat(client, cid, message):
    return client.post(f"/api/dashboard/{cid}/chat", json={"message": message})


@pytest.mark.parametrize("message", META_MESSAGES + EDGE_MESSAGES)
def test_first_message_never_errors_on_data_dashboard(client, message):
    cid = _make_dashboard(client)
    r = _chat(client, cid, message)
    assert r.status_code == 200, f"{message!r} → HTTP {r.status_code}: {r.text[:300]}"
    reply = (r.json().get("dashboard", {}).get("history") or [{}])[-1].get("content", "")
    assert reply.strip(), f"{message!r} → empty reply"
    low = reply.lower()
    assert not any(e in low for e in _HARD_ERROR), f"{message!r} → hard error: {reply[:200]}"


@pytest.mark.parametrize("message", META_MESSAGES)
def test_meta_message_is_useful_not_a_key_prompt(client, message):
    """Meta questions are answered from context the backend already holds, so they
    work even with no AI key (the hermetic default). They must NOT fall through to
    'add your API key' or a bare failure."""
    cid = _make_dashboard(client)
    reply = (_chat(client, cid, message).json().get("dashboard", {}).get("history") or [{}])[-1].get("content", "").lower()
    assert "api key" not in reply and "unavailable" not in reply, f"{message!r} → {reply[:200]}"
    # It should reference something real: a column, the row count, a widget, or the app's abilities.
    assert any(w in reply for w in ("region", "revenue", "column", "row", "chart", "metric", "dashboard", "research", "ask")), \
        f"{message!r} → not useful: {reply[:200]}"


@pytest.mark.parametrize("message", META_MESSAGES + EDGE_MESSAGES)
def test_first_message_never_errors_on_empty_record(client, message):
    cid = _empty_record(client)
    r = _chat(client, cid, message)
    assert r.status_code == 200, f"{message!r} (empty) → HTTP {r.status_code}: {r.text[:300]}"


def test_query_result_rows_are_json_serializable_with_dates():
    """The 500 behind the bug: a query result that includes a datetime column had
    raw pandas Timestamps in its rows, which json.dumps (used to build the answer
    prompt) can't serialize. Every result must be JSON-safe."""
    df = pd.DataFrame({"month": pd.to_datetime(["2026-01-01", "2026-02-01"]), "revenue": [120, 150]})
    result = run_query_spec(df, {"select": ["month", "revenue"]})
    json.dumps(result["rows"])  # must not raise
