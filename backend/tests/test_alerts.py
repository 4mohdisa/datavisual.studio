"""Phase 7 — threshold alerts (deterministic) + owner-only-field safety.

Alerts live on the dashboard record but must NEVER appear in the public share
payload (Hard Rule 4).
"""

import asyncio
from datetime import datetime, timedelta, timezone

from backend.alerts import evaluate_alerts
from backend.dashboard import apply_ops


def _dash(value, op, threshold, **alert):
    a = {"id": "a1", "widget_id": "m1", "label": "Revenue", "op": op,
         "threshold": threshold, "enabled": True, "cooldown_hours": 24,
         "last_value": None, "last_triggered_at": None, **alert}
    return {"widgets": [{"id": "m1", "kind": "metric", "label": "Revenue", "value": value}], "alerts": [a]}


def test_gt_alert_fires():
    fired = evaluate_alerts(_dash("1,200", "gt", 1000))
    assert fired and "Revenue" in fired[0]


def test_lt_alert_does_not_fire_when_above():
    assert evaluate_alerts(_dash("1,200", "lt", 1000)) == []


def test_pct_drop_fires_on_second_eval():
    d = _dash("100", "pct_drop", 10)
    assert evaluate_alerts(d) == []          # first eval only records baseline
    d["widgets"][0]["value"] = "80"          # -20%
    assert evaluate_alerts(d)                # 20% drop >= 10% threshold


def test_cooldown_suppresses_repeat():
    d = _dash("2000", "gt", 1000, last_triggered_at=datetime.now(timezone.utc).isoformat())
    assert evaluate_alerts(d) == []          # within cooldown
    d["alerts"][0]["last_triggered_at"] = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    assert evaluate_alerts(d)                # cooldown elapsed


def test_alert_on_deleted_widget_is_pruned_not_crashed():
    d = {"widgets": [], "alerts": [{"id": "a1", "widget_id": "gone", "op": "gt", "threshold": 1, "enabled": True}]}
    assert evaluate_alerts(d) == []
    assert d["alerts"] == []                 # pruned


def test_add_and_remove_alert_ops():
    dash = {"widgets": [{"id": "m1", "kind": "metric", "label": "MRR", "value": "5000"}]}
    asyncio.run(apply_ops(dash, [{"op": "add_alert", "widget_id": "m1", "alert_op": "pct_drop", "threshold": 15}], None))
    assert len(dash["alerts"]) == 1 and dash["alerts"][0]["op"] == "pct_drop"
    aid = dash["alerts"][0]["id"]
    asyncio.run(apply_ops(dash, [{"op": "remove_alert", "id": aid}], None))
    assert dash["alerts"] == []


def test_alerts_never_leak_into_public_share(client, upload_csv):
    fid = upload_csv()
    cid = client.post("/api/dashboard", json={"file_id": fid}).json()["conversation_id"]
    metric = next(w for w in client.get(f"/api/conversations/{cid}").json()["dashboard"]["widgets"] if w["kind"] == "metric")
    client.post(f"/api/dashboard/{cid}/chat", json={"ops": [
        {"op": "add_alert", "widget_id": metric["id"], "alert_op": "pct_drop", "threshold": 10},
    ]})
    token = client.post(f"/api/conversations/{cid}/share").json()["share_id"]
    pub = client.get(f"/api/public/{token}").json()
    blob = str(pub)
    assert "alerts" not in blob and "schedule" not in blob and "alert_log" not in blob
    assert pub["dashboard"]["widgets"]  # but the dashboard itself is still shared
