"""First-party product analytics (Overnight Plan 2, 1c).

Append-only events in `data/analytics.jsonl`. The whole point is the anon→user
stitch: a first-party `anon_id` cookie set on first visit, carried through
signup, so we can answer "did the landing visit become a signup?". Without it a
visitor is *permanently* unattributable — the one thing in the plan that can't
be backfilled, which is why it ships in the gate.

Privacy (get it right now, not after):
- Props are METADATA ONLY — row counts, column types, chart kinds, durations.
  Never a dataset cell value; a cell in an analytics log is a data leak.
- Never log question text by default — log intent + length. The one exception
  (an error/empty answer) is passed explicitly by the caller, not decided here.
- First-party only, no third-party trackers.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Path is overridable (tests + main.py keep their own reference in sync).
ANALYTICS_PATH = Path("data/analytics.jsonl")

# Allowlist — the public ingest endpoint rejects anything else, so a caller
# can't spam the log with arbitrary event names. Backend-emitted events are in
# the same vocabulary so the admin funnel is coherent.
EVENT_NAMES = frozenset({
    # funnel
    "landing_view", "demo_view", "demo_interact", "signup_started",
    "signup_completed", "identify", "first_dashboard_created", "key_added",
    "first_research_run", "dashboard_shared", "share_viewed",
    "returned_d1", "returned_d7", "error_shown",
    # usage
    "upload_completed", "connector_used", "chart_added", "assistant_message",
    "sync_run", "alert_created", "alert_fired", "export_run",
    "sample_data_used", "dashboard_created", "research_run",
})

# A hard ceiling on props size so a client can't smuggle a dataset into a prop.
_MAX_PROP_STR = 200


def _clean_props(props) -> dict:
    """Metadata only. Truncate strings, drop nested/oversized values — a prop is
    never a place for dataset contents."""
    out = {}
    if not isinstance(props, dict):
        return out
    for k, v in list(props.items())[:30]:
        if isinstance(v, str):
            out[str(k)[:60]] = v[:_MAX_PROP_STR]
        elif isinstance(v, (int, float, bool)) or v is None:
            out[str(k)[:60]] = v
        # dicts/lists are dropped: metadata is flat scalars, not payloads.
    return out


def record_event(event, *, user_id=None, anon_id=None, session_id=None,
                 path=None, referrer=None, utm=None, props=None) -> None:
    """Append one event. Best-effort — must never raise into a request."""
    if event not in EVENT_NAMES:
        return
    try:
        ANALYTICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "user_id": user_id,
            "anon_id": (anon_id or None) and str(anon_id)[:40],
            "session_id": (session_id or None) and str(session_id)[:40],
            "path": (path or None) and str(path)[:200],
            "referrer": (referrer or None) and str(referrer)[:200],
            "utm": _clean_props(utm) or None,
            "props": _clean_props(props) or None,
        }
        with open(ANALYTICS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def read_events(since_days: int = 30, limit: int = 50_000) -> list[dict]:
    """Recent events, capped by age AND count — the file grows forever and
    /admin reads it, so never load the whole thing. Handles legacy `{kind,meta}`
    records by normalising them to `{event,props}`."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=min(since_days, 36500))).isoformat()
    out: list[dict] = []
    try:
        with open(ANALYTICS_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return out
    for line in lines[-limit:]:
        try:
            e = json.loads(line)
        except Exception:
            continue
        if (e.get("ts") or "") < cutoff:
            continue
        # Normalise legacy shape.
        if "event" not in e and "kind" in e:
            e["event"] = e.get("kind")
            e["props"] = e.get("meta")
        out.append(e)
    return out
