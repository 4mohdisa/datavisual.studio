"""Threshold alerts on metric widgets — the actionable half of the living monitor.

Alerts are OWNER-ONLY (Hard Rule 4): they live on the dashboard record but are
NOT part of the public share allowlist, so they never reach /api/public. They're
evaluated deterministically on every sync (manual or, later, scheduled) against
the metric values the dashboard already holds — respecting a per-alert cooldown
so a flapping metric doesn't fire twenty times.

Alert shape (dashboard["alerts"][i]):
    {id, widget_id, label, op: pct_drop|pct_rise|pct_change|lt|gt,
     threshold, enabled, cooldown_hours, last_triggered_at, last_value}
"""

from datetime import datetime, timezone
from typing import Optional

_OPS = {"pct_drop", "pct_rise", "pct_change", "lt", "gt"}


def _num(v) -> Optional[float]:
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def _hours_since(iso: Optional[str], now: datetime) -> float:
    if not iso:
        return 1e9
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (now - t).total_seconds() / 3600.0
    except ValueError:
        return 1e9


def _fires(op: str, old: Optional[float], new: float, threshold: float) -> bool:
    if op == "gt":
        return new > threshold
    if op == "lt":
        return new < threshold
    if old is None or old == 0:
        return False
    pct = (new - old) / abs(old) * 100.0
    if op == "pct_rise":
        return pct >= threshold
    if op == "pct_drop":
        return -pct >= threshold
    if op == "pct_change":
        return abs(pct) >= threshold
    return False


def evaluate_alerts(dashboard: dict, now: Optional[datetime] = None) -> list[str]:
    """Check each enabled alert against its metric widget's current value.
    Updates alert state in place; prunes alerts whose widget is gone. Returns
    human-readable trigger messages (respecting cooldown)."""
    now = now or datetime.now(timezone.utc)
    alerts = dashboard.get("alerts")
    if not alerts:
        return []
    widgets = {w.get("id"): w for w in dashboard.get("widgets", []) if w.get("kind") == "metric"}

    fired: list[str] = []
    kept: list[dict] = []
    for a in alerts:
        w = widgets.get(a.get("widget_id"))
        if w is None:
            continue  # widget deleted → prune the alert, don't crash
        kept.append(a)
        new = _num(w.get("value"))
        if new is None or not a.get("enabled", True) or a.get("op") not in _OPS:
            if new is not None:
                a["last_value"] = new
            continue
        old = a.get("last_value")
        old = _num(old) if old is not None else None
        if _fires(a["op"], old, new, _num(a.get("threshold")) or 0) and \
                _hours_since(a.get("last_triggered_at"), now) >= (a.get("cooldown_hours") or 0):
            label = a.get("label") or w.get("label") or "metric"
            fired.append(f"🔔 Alert: **{label}** {a['op'].replace('_', ' ')} {a.get('threshold')} — now {w.get('value')}")
            a["last_triggered_at"] = now.isoformat()
        a["last_value"] = new

    dashboard["alerts"] = kept
    return fired
