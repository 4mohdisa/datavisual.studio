"""Dashboard engine — the core artifact of datavisual.studio.

A dashboard is a persistent *widget spec* stored on the conversation record:

    conversation["dashboard"] = {
        "title": str,
        "widgets": [
            {"id", "kind": "metric",  "label", "value", "sub", "spec": {column, agg}},
            {"id", "kind": "chart",   "title", "chart_type", "plotly_json", "spec": {...}},
            {"id", "kind": "insight", "title", "text", "sources": [{title, url}]},
            {"id", "kind": "comparison"},   # entity radar (frontend-rendered)
            {"id", "kind": "table"},        # raw data table (frontend-rendered)
        ],
        "history": [{"role", "content"}, ...],   # dashboard-assistant chat
        "updated_at": iso,
    }

Two layers:
  1. Deterministic engine — build_dashboard_spec (initial spec from an analysed
     dataset + optional research/AI insights) and build_chart_from_spec (a
     structured chart spec → Plotly JSON). No LLM involved.
  2. Chat editor — one LLM call turns a user request into structured ops
     (add/update/remove widgets, add research insight); apply_ops mutates the
     EXISTING spec in place. The LLM never draws charts, it only emits specs.
"""

import json
import re
import uuid
from datetime import datetime
from typing import Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .config import DEBUG, get_fast_model
from .data_analysis import _fig_json, _pick_entity_column, _pick_primary_numeric


def _wid() -> str:
    return "w" + uuid.uuid4().hex[:8]


def _fmt_value(v: Any) -> str:
    if v is None:
        return "–"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f) and abs(f) < 1e15:
        return f"{int(f):,}"
    return f"{f:,.2f}"


# ---------------------------------------------------------------------------
# Initial spec
# ---------------------------------------------------------------------------

def default_chart_specs(df: pd.DataFrame, columns_info: list[dict],
                        focus: Optional[str] = None) -> list[dict]:
    """Derive a rich set of chart specs from the dataset's column types —
    time series, category totals, share, distribution, spread and correlation.
    Every spec is rebuildable, so the chat editor AND connection refresh can
    regenerate these charts."""
    dt = [c["name"] for c in columns_info if c["type"] == "datetime"]
    nums = [c["name"] for c in columns_info if c["type"] == "numeric"]
    cats = [c["name"] for c in columns_info if c["type"] == "categorical"]
    # A user-chosen focus column leads every chart's y-axis.
    if focus and focus in nums:
        nums = [focus] + [n for n in nums if n != focus]
    # A categorical is chartable when it groups rows (not an id) and stays legible.
    good_cats = [c for c in cats if c in df.columns and 2 <= df[c].nunique(dropna=True) <= 30]

    t = dt[0] if dt else None
    g = good_cats[0] if good_cats else None
    g2 = good_cats[1] if len(good_cats) > 1 else None
    specs: list[dict] = []

    if t:
        for y in nums[:2]:
            specs.append({"chart_type": "line", "x": t, "y": y, "group_by": g, "agg": "mean",
                          "title": f"{y} over time" + (f" by {g}" if g else "")})
    if g and nums:
        specs.append({"chart_type": "bar", "x": g, "y": nums[0], "agg": "sum",
                      "title": f"Total {nums[0]} by {g}"})
    if nums and (g2 or g):
        pie_cat = g2 or g
        pie_val = nums[0] if g2 else (nums[1] if len(nums) > 1 else nums[0])
        specs.append({"chart_type": "pie", "x": pie_cat, "y": pie_val, "agg": "sum",
                      "title": f"{pie_val} share by {pie_cat}"})
    if nums:
        specs.append({"chart_type": "histogram", "x": nums[0],
                      "title": f"Distribution of {nums[0]}"})
    if g and nums:
        specs.append({"chart_type": "box", "y": nums[0], "group_by": g,
                      "title": f"{nums[0]} spread by {g}"})
    if len(nums) > 2:
        specs.append({"chart_type": "heatmap", "title": "Correlation heatmap"})
    if len(nums) >= 2 and not t:
        specs.append({"chart_type": "scatter", "x": nums[0], "y": nums[1], "group_by": g,
                      "title": f"{nums[1]} vs {nums[0]}"})
    return specs


# Generation templates: how much the initial dashboard includes. The chat
# assistant and manual tools can always add more afterwards.
TEMPLATES = {
    "minimal":  {"max_charts": 2,  "comparison": False, "table": True,  "extra_metrics": False},
    "overview": {"max_charts": 6,  "comparison": True,  "table": True,  "extra_metrics": False},
    "full":     {"max_charts": 12, "comparison": True,  "table": True,  "extra_metrics": True},
    # KPI board: numbers-first — totals/averages for every key column, few charts.
    "kpi":      {"max_charts": 3,  "comparison": False, "table": False, "extra_metrics": True},
    # Visual board: charts-first — no table, maximum visualisations.
    "visual":   {"max_charts": 10, "comparison": True,  "table": False, "extra_metrics": False},
}


def build_dashboard_spec(
    data_summary: Optional[dict],
    charts: Optional[list],
    title: str,
    insights: Optional[list] = None,
    has_rows: bool = True,
    df: Optional[pd.DataFrame] = None,
    template: str = "overview",
    focus: Optional[str] = None,
) -> dict:
    """Assemble the initial widget spec for a dataset (and/or research insights).

    With `df` available the charts are built from default_chart_specs — a
    richer set where every chart carries a rebuildable spec. Otherwise the
    pre-rendered `charts` ({title, type, plotly_json}) are used as-is (those
    can only be removed/replaced by the editor, not updated).
    """
    widgets: list[dict] = []

    stats = (data_summary or {}).get("statistics", {})
    columns = (data_summary or {}).get("columns", [])
    num_cols = [c["name"] for c in columns if c["type"] == "numeric" and c["name"] in stats]
    tpl = TEMPLATES.get(template, TEMPLATES["overview"])
    if num_cols:
        primary = focus if focus in num_cols else next(
            (c for c in num_cols if re.search(r"revenue|sales|amount|value|elo|rating|score|points", c, re.I)),
            num_cols[0],
        )
        p = stats[primary]
        # Labels live in the spec too, so a connection refresh rebuilds the
        # metric with the same wording (and "Rows" stays current).
        widgets += [
            {"id": _wid(), "kind": "metric", "label": f"Highest {primary}", "value": _fmt_value(p.get("max")),
             "sub": None, "spec": {"column": primary, "agg": "max", "label": f"Highest {primary}"}},
            {"id": _wid(), "kind": "metric", "label": f"Lowest {primary}", "value": _fmt_value(p.get("min")),
             "sub": None, "spec": {"column": primary, "agg": "min", "label": f"Lowest {primary}"}},
            {"id": _wid(), "kind": "metric", "label": f"Mean {primary}", "value": _fmt_value(p.get("mean")),
             "sub": None, "spec": {"column": primary, "agg": "mean", "label": f"Mean {primary}"}},
            {"id": _wid(), "kind": "metric", "label": "Rows", "value": _fmt_value((data_summary or {}).get("row_count")),
             "sub": None, "spec": {"column": primary, "agg": "count", "label": "Rows"}},
        ]
        # Numbers-first templates: totals + averages for the other key columns too.
        if tpl["extra_metrics"] and df is not None:
            for col in [c for c in num_cols if c != primary][:3]:
                for agg, label in (("sum", f"Total {col}"), ("mean", f"Avg {col}")):
                    try:
                        widgets.append(build_metric_from_spec(df, {"column": col, "agg": agg, "label": label}))
                    except Exception:
                        pass

    chart_widgets: list[dict] = []
    if df is not None and data_summary:
        for spec in default_chart_specs(df, columns, focus=focus)[: tpl["max_charts"]]:
            try:
                chart_widgets.append(build_chart_from_spec(df, spec))
            except Exception as e:  # one bad spec must not sink the dashboard
                if DEBUG:
                    print(f"[dashboard] default chart {spec.get('title')} failed: {e}", flush=True)
    if not chart_widgets:
        chart_widgets = [{
            "id": _wid(), "kind": "chart", "title": c.get("title", "Chart"),
            "chart_type": c.get("type", "chart"), "plotly_json": c.get("plotly_json"),
            "spec": None,
        } for c in charts or []]
    widgets.extend(chart_widgets)

    for ins in insights or []:
        widgets.append({
            "id": _wid(), "kind": "insight",
            "title": ins.get("title", "Insight"),
            "text": ins.get("text", ""),
            "sources": ins.get("sources", []),
        })

    if has_rows and data_summary:
        cat_cols = [c for c in columns if c["type"] == "categorical"]
        if tpl["comparison"] and cat_cols and len(num_cols) >= 2:
            widgets.append({"id": _wid(), "kind": "comparison"})
        if tpl["table"]:
            widgets.append({"id": _wid(), "kind": "table"})

    return {
        "title": title,
        "widgets": widgets,
        "history": [],
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# Deterministic chart engine — spec → Plotly JSON
# ---------------------------------------------------------------------------

_AGGS = ("sum", "mean", "count", "min", "max", "median")
CHART_TYPES = ("line", "bar", "scatter", "histogram", "pie", "box", "heatmap", "area", "treemap")


def _require_cols(df: pd.DataFrame, *cols):
    for c in cols:
        if c and c not in df.columns:
            raise ValueError(f"Column '{c}' does not exist in the dataset")


def build_chart_from_spec(df: pd.DataFrame, spec: dict) -> dict:
    """Build a chart widget from a structured spec. Raises ValueError with a
    human-readable message on a bad spec — the chat endpoint surfaces it."""
    ctype = spec.get("chart_type")
    if ctype not in CHART_TYPES:
        raise ValueError(f"Unsupported chart_type '{ctype}' (use one of {', '.join(CHART_TYPES)})")

    x, y = spec.get("x"), spec.get("y")
    group_by = spec.get("group_by")
    agg = (spec.get("agg") or "mean").lower()
    if agg not in _AGGS:
        agg = "mean"
    _require_cols(df, x, y, group_by)

    if ctype == "line":
        if not (x and y):
            raise ValueError("A line chart needs x and y columns")
        fig = go.Figure()
        if group_by:
            top = df.groupby(group_by)[y].mean().sort_values(ascending=False).head(8).index
            for g in top:
                sub = df[df[group_by] == g].groupby(x, as_index=False)[y].agg(agg).sort_values(x)
                fig.add_trace(go.Scatter(x=sub[x], y=sub[y], mode="lines+markers", name=str(g)))
        else:
            sub = df.groupby(x, as_index=False)[y].agg(agg).sort_values(x)
            fig.add_trace(go.Scatter(x=sub[x], y=sub[y], mode="lines", line=dict(color="rgb(100,160,255)")))
        fig.update_layout(xaxis_title=x, yaxis_title=y)

    elif ctype == "bar":
        if not (x and y):
            raise ValueError("A bar chart needs x (category) and y (numeric) columns")
        if group_by:
            sub = df.groupby([x, group_by], as_index=False)[y].agg(agg)
            fig = px.bar(sub, x=x, y=y, color=group_by, barmode="group")
        else:
            sub = df.groupby(x, as_index=False)[y].agg(agg).sort_values(y, ascending=False).head(20)
            fig = px.bar(sub, x=x, y=y)
            fig.update_traces(marker_color="rgb(100,200,150)")
        fig.update_layout(xaxis_title=x, yaxis_title=f"{agg} {y}")

    elif ctype == "scatter":
        if not (x and y):
            raise ValueError("A scatter plot needs x and y columns")
        fig = px.scatter(df, x=x, y=y, color=group_by if group_by else None)

    elif ctype == "histogram":
        if not x:
            raise ValueError("A histogram needs an x column")
        fig = px.histogram(df, x=x, nbins=30, color_discrete_sequence=["rgb(100,160,255)"])

    elif ctype == "pie":
        if not (x and y):
            raise ValueError("A pie chart needs x (names) and y (values) columns")
        sub = df.groupby(x, as_index=False)[y].agg(agg).sort_values(y, ascending=False).head(10)
        fig = px.pie(sub, names=x, values=y, hole=0.45)

    elif ctype == "box":
        if not y:
            raise ValueError("A box plot needs a y (numeric) column")
        fig = px.box(df, x=group_by if group_by else None, y=y, points="outliers")

    elif ctype == "area":
        if not (x and y):
            raise ValueError("An area chart needs x and y columns")
        if group_by:
            sub = df.groupby([x, group_by], as_index=False)[y].agg(agg).sort_values(x)
            fig = px.area(sub, x=x, y=y, color=group_by)
        else:
            sub = df.groupby(x, as_index=False)[y].agg(agg).sort_values(x)
            fig = px.area(sub, x=x, y=y)
        fig.update_layout(xaxis_title=x, yaxis_title=y)

    elif ctype == "treemap":
        if not (x and y):
            raise ValueError("A treemap needs x (category) and y (values) columns")
        path = [x, group_by] if group_by else [x]
        sub = df.groupby([c for c in path], as_index=False)[y].agg(agg)
        sub = sub[sub[y] > 0]
        fig = px.treemap(sub, path=path, values=y)

    else:  # heatmap — correlation of numeric columns
        nums = df.select_dtypes("number")
        if nums.shape[1] < 2:
            raise ValueError("A correlation heatmap needs at least two numeric columns")
        corr = nums.corr()
        fig = go.Figure(go.Heatmap(z=corr.values, x=list(corr.columns), y=list(corr.index),
                                   colorscale="RdBu", zmid=0,
                                   text=corr.round(2).values, texttemplate="%{text}"))

    title = spec.get("title") or f"{ctype} chart"
    fig.update_layout(title=title)
    return {
        "id": _wid(), "kind": "chart", "title": title, "chart_type": ctype,
        "plotly_json": _fig_json(fig),
        "spec": {"chart_type": ctype, "x": x, "y": y, "group_by": group_by, "agg": agg, "title": title},
    }


def build_metric_from_spec(df: pd.DataFrame, spec: dict) -> dict:
    column, agg = spec.get("column"), (spec.get("agg") or "mean").lower()
    if agg not in _AGGS:
        agg = "mean"
    _require_cols(df, column)
    if column is None:
        raise ValueError("A metric needs a column")
    value = getattr(df[column], agg)() if agg != "count" else df[column].count()
    label = spec.get("label") or f"{agg} {column}"
    return {"id": _wid(), "kind": "metric", "label": label, "value": _fmt_value(value),
            "sub": None, "spec": {"column": column, "agg": agg, "label": label}}


# ---------------------------------------------------------------------------
# Analysis engine — turns charts into findings.
#   analyze_dataset      : deterministic statistical read of the data (no LLM)
#   generate_key_findings: AI narrative bullets over the data excerpt (fast model)
# Both render as `insight` widgets, so they reuse the existing frontend card.
# ---------------------------------------------------------------------------

def analyze_dataset(df: pd.DataFrame, columns_info: list[dict], statistics: dict) -> str:
    """Compute a plain-language statistical read of the dataset — trends, top and
    bottom movers, outliers and the strongest correlation — as markdown. Pure
    pandas, instant and free. Returns '' when nothing meaningful can be said."""
    # _pick_entity_column / _pick_primary_numeric are already imported at module
    # top; only the time helpers need a local import here.
    from .data_analysis import _pick_time_column, _latest_snapshot
    cat_cols = [c["name"] for c in columns_info if c["type"] == "categorical"]
    num_cols = [c["name"] for c in columns_info if c["type"] == "numeric" and c["name"] in df.columns]
    if not num_cols:
        return ""
    lines: list[str] = []

    entity = _pick_entity_column(df, cat_cols)
    primary = _pick_primary_numeric(df, num_cols)
    time_col, time_kind = _pick_time_column(df, columns_info)

    # --- Trend over time (first period → last period, on the primary metric).
    # Group by the actual time value so intra-year (e.g. monthly) trends show. ---
    if primary and time_col:
        try:
            d = df[[primary, time_col]].dropna()
            period = (pd.to_datetime(d[time_col], errors="coerce") if time_kind == "datetime"
                      else pd.to_numeric(d[time_col], errors="coerce"))
            grouped = d.assign(_p=period).dropna(subset=["_p"]).groupby("_p")[primary].mean().sort_index()
            if len(grouped) >= 2:
                first, last = grouped.iloc[0], grouped.iloc[-1]
                def _period_label(v):
                    return v.date().isoformat() if hasattr(v, "date") else (str(int(v)) if float(v).is_integer() else str(v))
                if first:
                    pct = (last - first) / abs(first) * 100
                    arrow = "rose" if pct >= 0 else "fell"
                    lines.append(
                        f"- **Trend:** average **{primary}** {arrow} **{pct:+.1f}%** "
                        f"from {_period_label(grouped.index[0])} ({_fmt_value(first)}) to "
                        f"{_period_label(grouped.index[-1])} ({_fmt_value(last)})."
                    )
        except Exception:
            pass

    # --- Top / bottom movers on the primary metric, per entity ---
    if primary and entity:
        try:
            snap = _latest_snapshot(df, entity, time_col)
            ranked = snap.groupby(entity)[primary].mean().sort_values(ascending=False)
            if len(ranked) >= 2:
                n = min(3, len(ranked) // 2)  # avoid top/bottom overlap on small sets
                top = ranked.head(n)
                lines.append(
                    "- **Leaders:** " + ", ".join(f"{e} ({_fmt_value(v)})" for e, v in top.items())
                    + f" lead on {primary}."
                )
                if len(ranked) > n:
                    bottom = ranked.tail(min(3, len(ranked) - n))
                    lines.append(
                        "- **Laggards:** " + ", ".join(f"{e} ({_fmt_value(v)})" for e, v in bottom.items())
                        + "."
                    )
                gap = ranked.iloc[0] - ranked.iloc[-1]
                lines.append(
                    f"- **Spread:** the gap between the top and bottom {entity} is "
                    f"**{_fmt_value(gap)}** on {primary}."
                )
        except Exception:
            pass

    # --- Strongest correlation among numeric columns ---
    if len(num_cols) >= 2:
        try:
            corr = df[num_cols].corr().abs()
            import numpy as np
            np.fill_diagonal(corr.values, 0)
            i, j = divmod(int(corr.values.argmax()), corr.shape[1])
            r = df[num_cols].corr().iloc[i, j]
            if abs(r) >= 0.5:
                rel = "positively" if r > 0 else "negatively"
                lines.append(
                    f"- **Correlation:** **{corr.columns[i]}** and **{corr.columns[j]}** move "
                    f"{rel} together (r = {r:.2f})."
                )
        except Exception:
            pass

    # --- Outliers (reuse the IQR anomaly detector) ---
    try:
        from .data_analysis import _detect_anomalies
        anomalies = _detect_anomalies(df, columns_info, num_cols, max_total=5)
        if anomalies:
            listed = ", ".join(f"{a['entity']} ({a['column']} = {_fmt_value(a['value'])})" for a in anomalies[:4])
            lines.append(f"- **Outliers:** unusual values detected — {listed}.")
    except Exception:
        pass

    if not lines:
        return ""
    return "Automated statistical read of the current data:\n\n" + "\n".join(lines)


async def generate_key_findings(df: pd.DataFrame, data_summary: dict) -> str:
    """AI narrative: 4–6 bullet findings about the DATA itself (not the web).
    Uses the fast model over a compact data excerpt. Returns '' on failure."""
    from .data_analysis import build_data_excerpt
    from .openrouter import query_model

    excerpt = build_data_excerpt(df, data_summary.get("columns", []), data_summary.get("statistics", {}))
    if not excerpt:
        return ""
    prompt = (
        "You are a data analyst. From the dataset excerpt below, write 4-6 concise "
        "bullet findings a decision-maker would care about — patterns, standouts, "
        "risks, and what the numbers imply. Be specific and cite actual figures from "
        "the data. Markdown bullets only, no preamble, no headings.\n\n"
        f"{excerpt}"
    )
    resp = await query_model(get_fast_model(), [{"role": "user", "content": prompt}], max_tokens=700)
    return (resp or {}).get("content", "").strip() if resp else ""


def _insight_widget(title: str, text: str, sources: Optional[list] = None) -> dict:
    return {"id": _wid(), "kind": "insight", "title": title, "text": text, "sources": sources or []}


def _upsert_insight(widgets: list[dict], title: str, text: str) -> None:
    """Replace an existing same-titled insight in place, else append — so
    re-running an analysis refreshes rather than duplicates."""
    for i, w in enumerate(widgets):
        if w.get("kind") == "insight" and w.get("title") == title:
            widgets[i] = {**w, "text": text}
            return
    widgets.append(_insight_widget(title, text))


# ---------------------------------------------------------------------------
# Chat editor — LLM emits ops, apply_ops mutates the spec in place
# ---------------------------------------------------------------------------

_EDITOR_INSTRUCTIONS = """You are the editor of a data dashboard. Turn the user's request into edit operations.

Respond with ONLY a JSON object, no prose and no code fences:
{"reply": "<one or two sentences confirming what you did or answering the question>", "ops": [...]}

Available ops:
- {"op": "add_chart", "chart_type": "line|bar|scatter|histogram|pie|box|heatmap|area|treemap", "x": "<col>", "y": "<col>", "group_by": "<col or null>", "agg": "sum|mean|count|min|max|median", "title": "<short title>"}
- {"op": "update_chart", "id": "<widget id>", ...same fields as add_chart, only include what changes}
- {"op": "remove_widget", "id": "<widget id>"}
- {"op": "add_metric", "column": "<col>", "agg": "sum|mean|count|min|max|median", "label": "<short label>"}
- {"op": "update_metric", "id": "<widget id>", ...same fields as add_metric, only include what changes}
- {"op": "move_widget", "id": "<widget id>", "direction": "up|down"}
- {"op": "add_table"}        ← (re)adds the raw data table section
- {"op": "add_comparison"}   ← (re)adds the entity comparison radar section
- {"op": "add_analysis"}     ← computes a statistical read of the data (trends, top/bottom, outliers, correlations)
- {"op": "add_key_findings"} ← AI-written narrative bullets about what the data shows
- {"op": "add_text", "title": "<optional>", "text": "<markdown note>"}  ← adds a text note/heading to annotate the dashboard
- {"op": "add_insight", "query": "<web search query>", "title": "<short title>"}  ← runs live internet research and pins the findings to the dashboard
- {"op": "rename_dashboard", "title": "<new title>"}

Vocabulary — users speak informally; map their words to widgets:
- "KPI cards", "KPIs", "stat cards", "tiles", "numbers", "big numbers", "summary cards" → metric widgets
- "graph", "plot", "visual", "viz", "diagram", "trend" → chart widgets
- "analyse", "analyze", "insights", "key findings", "summarise the data", "what does this show", "tell me about the data" → add_analysis and/or add_key_findings (data-driven, NOT web research)
- "research", "look up", "find online", "web search", "what's the latest on X" → add_insight (web research)
- "note", "text", "heading", "comment", "explanation", "write" → add_text
- "breakdown", "split", "share" → pie/treemap; "over time", "trend" → line/area; "compare categories" → bar

Rules:
- BE FORGIVING of typos, shorthand and vague phrasing ("koi cards" means KPI cards, "grpah" means graph). Infer the most likely intent and ACT on it — state your interpretation briefly in "reply" (e.g. "Added 3 more KPI metric cards (read 'koi' as KPI)."). Only return empty ops with a clarifying question when the request genuinely cannot be interpreted.
- Use EXACT column names from DATASET COLUMNS. Never invent columns.
- If the user asks a question about the data instead of an edit, answer it in "reply" with "ops": [].
- Prefer a small number of high-value ops. For "add more charts/KPIs" style requests, add up to 3-4 varied, non-duplicate widgets (check CURRENT WIDGETS to avoid repeats).
- update_chart / update_metric only work on widgets marked (rebuildable); otherwise remove + add a new one."""


def _columns_block(data_summary: Optional[dict]) -> str:
    if not data_summary:
        return "No dataset is attached — chart and metric ops are unavailable."
    lines = []
    stats = data_summary.get("statistics", {})
    for c in data_summary.get("columns", []):
        line = f"- {c['name']} ({c['type']})"
        s = stats.get(c["name"])
        if s:
            line += f" min={s.get('min')} max={s.get('max')} mean={s.get('mean')}"
        lines.append(line)
    return "\n".join(lines)


def _widgets_block(dashboard: dict) -> str:
    lines = []
    for w in dashboard.get("widgets", []):
        label = w.get("title") or w.get("label") or w["kind"]
        editable = " (rebuildable)" if w.get("spec") and w["kind"] == "chart" else ""
        lines.append(f"- {w['id']} | {w['kind']} | {label}{editable}")
    return "\n".join(lines) or "(dashboard is empty)"


def build_editor_prompt(message: str, dashboard: dict, data_summary: Optional[dict]) -> str:
    history = dashboard.get("history", [])[-6:]
    history_block = "\n".join(f"{h['role']}: {h['content']}" for h in history)
    return (
        f"{_EDITOR_INSTRUCTIONS}\n\n"
        f"DATASET COLUMNS:\n{_columns_block(data_summary)}\n\n"
        f"CURRENT WIDGETS:\n{_widgets_block(dashboard)}\n\n"
        + (f"RECENT CONVERSATION:\n{history_block}\n\n" if history_block else "")
        + f"USER REQUEST: {message}"
    )


def parse_editor_response(raw: str) -> tuple[str, list[dict]]:
    """Extract {reply, ops} from the model output. Never raises — a parse
    failure degrades to (raw text, no ops)."""
    text = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return (raw or "").strip() or "I couldn't process that request.", []
    try:
        data = json.loads(m.group(0))
    except Exception:
        return (raw or "").strip(), []
    reply = str(data.get("reply") or "Done.")
    ops = data.get("ops") if isinstance(data.get("ops"), list) else []
    return reply, [op for op in ops if isinstance(op, dict)]


async def apply_ops(
    dashboard: dict,
    ops: list[dict],
    df: Optional[pd.DataFrame],
    data_summary: Optional[dict] = None,
) -> list[str]:
    """Apply ops to the dashboard spec IN PLACE. Returns human-readable notes
    for ops that could not be applied. Research/analysis ops call the live
    research layer or the fast model, hence async."""
    from .research import run_single_search

    notes: list[str] = []
    widgets: list[dict] = dashboard.setdefault("widgets", [])

    def find(wid):
        return next((w for w in widgets if w.get("id") == wid), None)

    for op in ops:
        kind = op.get("op")
        try:
            if kind == "add_chart":
                if df is None:
                    raise ValueError("No dataset attached to this dashboard")
                widgets.append(build_chart_from_spec(df, op))

            elif kind == "update_chart":
                w = find(op.get("id"))
                if w is None or w.get("kind") != "chart":
                    raise ValueError(f"Chart '{op.get('id')}' not found")
                if not w.get("spec"):
                    raise ValueError("This chart was auto-generated and can't be edited — remove it and add a new one")
                if df is None:
                    raise ValueError("No dataset attached to this dashboard")
                merged = {**w["spec"], **{k: v for k, v in op.items() if k not in ("op", "id") and v is not None}}
                rebuilt = build_chart_from_spec(df, merged)
                rebuilt["id"] = w["id"]
                widgets[widgets.index(w)] = rebuilt

            elif kind == "remove_widget":
                w = find(op.get("id"))
                if w is None:
                    raise ValueError(f"Widget '{op.get('id')}' not found")
                widgets.remove(w)

            elif kind == "move_widget":
                # Swap with the previous/next widget OF THE SAME KIND, since the
                # frontend renders widgets grouped by kind (metrics strip, chart
                # grid, insights) — order within the group is what the user sees.
                w = find(op.get("id"))
                if w is None:
                    raise ValueError(f"Widget '{op.get('id')}' not found")
                direction = op.get("direction")
                if direction not in ("up", "down"):
                    raise ValueError("move_widget direction must be 'up' or 'down'")
                same = [i for i, x in enumerate(widgets) if x.get("kind") == w["kind"]]
                pos = same.index(widgets.index(w))
                target = pos - 1 if direction == "up" else pos + 1
                if 0 <= target < len(same):
                    i, j = same[pos], same[target]
                    widgets[i], widgets[j] = widgets[j], widgets[i]

            elif kind == "update_metric":
                w = find(op.get("id"))
                if w is None or w.get("kind") != "metric":
                    raise ValueError(f"Metric '{op.get('id')}' not found")
                if df is None:
                    raise ValueError("No dataset attached to this dashboard")
                merged = {**(w.get("spec") or {}), **{k: v for k, v in op.items() if k not in ("op", "id") and v is not None}}
                rebuilt = build_metric_from_spec(df, merged)
                rebuilt["id"] = w["id"]
                widgets[widgets.index(w)] = rebuilt

            elif kind == "add_metric":
                if df is None:
                    raise ValueError("No dataset attached to this dashboard")
                # Metrics live at the top — insert after the last existing metric.
                metric = build_metric_from_spec(df, op)
                idx = max((i for i, w in enumerate(widgets) if w["kind"] == "metric"), default=-1)
                widgets.insert(idx + 1, metric)

            elif kind == "add_insight":
                query = op.get("query") or ""
                if not query.strip():
                    raise ValueError("add_insight needs a query")
                res = await run_single_search(query)
                if res.get("error") or not (res.get("content") or "").strip():
                    raise ValueError(f"Research for '{query}' returned nothing")
                widgets.append({
                    "id": _wid(), "kind": "insight",
                    "title": op.get("title") or f"Research: {query[:60]}",
                    "text": res["content"],
                    "sources": res.get("sources", [])[:8],
                    # query + as_of make this insight refreshable by the sync
                    # engine — the "watch this topic" mechanism.
                    "query": query,
                    "as_of": datetime.utcnow().isoformat() + "Z",
                })

            elif kind == "add_table":
                if not any(x.get("kind") == "table" for x in widgets):
                    widgets.append({"id": _wid(), "kind": "table"})

            elif kind == "add_comparison":
                if not any(x.get("kind") == "comparison" for x in widgets):
                    widgets.append({"id": _wid(), "kind": "comparison"})

            elif kind == "add_analysis":
                if df is None or not data_summary:
                    raise ValueError("No dataset attached to analyse")
                text = analyze_dataset(df, data_summary.get("columns", []), data_summary.get("statistics", {}))
                if not text:
                    raise ValueError("Not enough data to produce a statistical read")
                _upsert_insight(widgets, "Statistical analysis", text)

            elif kind == "add_key_findings":
                if df is None or not data_summary:
                    raise ValueError("No dataset attached to analyse")
                text = await generate_key_findings(df, data_summary)
                if not text:
                    raise ValueError("Could not generate key findings")
                _upsert_insight(widgets, "Key findings", text)

            elif kind == "add_text":
                widgets.append({"id": _wid(), "kind": "text",
                                "title": op.get("title") or "",
                                "text": op.get("text") or "New note — click to edit."})

            elif kind == "update_text":
                w = find(op.get("id"))
                if w is None or w.get("kind") != "text":
                    raise ValueError(f"Text note '{op.get('id')}' not found")
                if op.get("text") is not None:
                    w["text"] = op["text"]
                if op.get("title") is not None:
                    w["title"] = op["title"]

            elif kind == "rename_dashboard":
                title = (op.get("title") or "").strip()
                if not title:
                    raise ValueError("rename_dashboard needs a title")
                dashboard["title"] = title

            else:
                raise ValueError(f"Unknown op '{kind}'")

        except ValueError as e:
            notes.append(str(e))
        except Exception as e:  # never let one bad op kill the edit
            notes.append(f"{kind} failed: {e}")
            if DEBUG:
                print(f"[dashboard] op {op} failed: {e}", flush=True)

    dashboard["updated_at"] = datetime.utcnow().isoformat() + "Z"
    return notes


async def run_editor_turn(
    message: str,
    dashboard: dict,
    data_summary: Optional[dict],
    df: Optional[pd.DataFrame],
) -> str:
    """One full assistant turn: LLM → ops → apply in place → reply text.
    Mutates `dashboard` (widgets, title, history)."""
    from .openrouter import query_model

    prompt = build_editor_prompt(message, dashboard, data_summary)
    # The editor is a structured-ops task — the fast model (Gemini Flash via
    # the direct API) handles it well at a fraction of the chairman's cost.
    response = await query_model(get_fast_model(), [{"role": "user", "content": prompt}], max_tokens=1500)
    if response is None:
        reply, ops = "The editor model is unavailable — check your API key in Settings.", []
    else:
        reply, ops = parse_editor_response(response.get("content") or "")

    notes = await apply_ops(dashboard, ops, df, data_summary)
    if notes:
        reply = f"{reply}\n\nNotes: " + "; ".join(notes)

    history = dashboard.setdefault("history", [])
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    del history[:-30]  # keep the last 30 turns
    return reply


# ---------------------------------------------------------------------------
# Sync engine — the "living monitor". Re-runs every refreshable widget against
# fresh data AND fresh web research, then reports what actually changed. This is
# what turns a dashboard from a one-time snapshot into something worth revisiting.
# ---------------------------------------------------------------------------

def _delta_str(old: Any, new: Any) -> Optional[str]:
    """Human-readable change between two metric values, or None if unchanged.
    Understands the '1,234' / '45.6' formatting produced by _fmt_value."""
    def num(v):
        try:
            return float(str(v).replace(",", ""))
        except (TypeError, ValueError):
            return None
    o, n = num(old), num(new)
    if o is None or n is None:
        return None if str(old) == str(new) else f"{old} → {new}"
    if abs(n - o) < 1e-9:
        return None
    pct = ((n - o) / abs(o) * 100) if o else None
    arrow = "▲" if n > o else "▼"
    return f"{_fmt_value(o)} → {_fmt_value(n)} ({arrow}{abs(pct):.1f}%)" if pct is not None else f"{_fmt_value(o)} → {_fmt_value(n)}"


async def sync_dashboard(
    dashboard: dict,
    df: Optional[pd.DataFrame],
    data_summary: Optional[dict],
) -> list[str]:
    """Refresh every refreshable widget IN PLACE and return the list of changes.

    - When `df` is given (a fresh data pull), rebuilds spec'd charts/metrics and
      records metric value deltas.
    - Re-runs the query behind every pinned research insight and records new
      sources / freshness.
    Appends a snapshot to dashboard['watch_log'] and stamps last_synced. The
    change list is deliberately human-readable — it's the "what changed" feed."""
    from .research import run_single_search

    widgets: list[dict] = dashboard.setdefault("widgets", [])
    changes: list[str] = []
    now = datetime.utcnow().isoformat() + "Z"

    # 1) Data widgets — rebuild spec'd charts/metrics, diff metric values.
    if df is not None:
        charts_updated = 0
        for i, w in enumerate(widgets):
            spec = w.get("spec")
            if not spec:
                continue
            try:
                if w["kind"] == "metric":
                    old_val = w.get("value")
                    rebuilt = build_metric_from_spec(df, spec)
                    rebuilt["id"] = w["id"]
                    d = _delta_str(old_val, rebuilt["value"])
                    if d:
                        rebuilt["sub"] = d  # surface the delta on the card
                        changes.append(f"**{rebuilt.get('label')}**: {d}")
                    widgets[i] = rebuilt
                elif w["kind"] == "chart":
                    rebuilt = build_chart_from_spec(df, spec)
                    rebuilt["id"] = w["id"]
                    widgets[i] = rebuilt
                    charts_updated += 1
            except ValueError:
                continue
        if charts_updated:
            changes.append(f"{charts_updated} chart{'s' if charts_updated != 1 else ''} refreshed with the latest data")

    # 2) Research insights — re-run each pinned query, diff sources/freshness.
    for w in widgets:
        if w.get("kind") != "insight" or not w.get("query"):
            continue
        try:
            res = await run_single_search(w["query"])
        except Exception:
            continue
        if res.get("error") or not (res.get("content") or "").strip():
            continue
        old_urls = {s.get("url") for s in (w.get("sources") or [])}
        new_sources = res.get("sources", [])[:8]
        added = [s for s in new_sources if s.get("url") not in old_urls]
        w["text"] = res["content"]
        w["sources"] = new_sources
        w["as_of"] = now
        if added:
            changes.append(f"**{w.get('title')}**: {len(added)} new source{'s' if len(added) != 1 else ''} found")
        else:
            changes.append(f"**{w.get('title')}**: research re-checked, no new sources")

    dashboard["last_synced"] = now
    dashboard["updated_at"] = now
    # Keep a rolling log of the last 20 syncs for the "what changed" history.
    log = dashboard.setdefault("watch_log", [])
    log.append({"at": now, "changes": changes or ["No changes detected"]})
    del log[:-20]
    return changes


# ---------------------------------------------------------------------------
# Pipeline integration — research/AI runs produce dashboard insights
# ---------------------------------------------------------------------------

def component_suggestions(
    df: Optional[pd.DataFrame],
    data_summary: Optional[dict],
    dashboard: dict,
) -> list[dict]:
    """Prebuilt components the user can add with one click — computed from the
    dataset's actual columns, minus what the dashboard already shows. Each item
    is {label, kind, detail, op} where op feeds straight into apply_ops (no LLM)."""
    if df is None or not data_summary:
        return []
    widgets = dashboard.get("widgets", [])
    existing_titles = {(w.get("title") or "").lower() for w in widgets}
    existing_labels = {(w.get("label") or "").lower() for w in widgets}
    columns = data_summary.get("columns", [])
    num_cols = [c["name"] for c in columns if c["type"] == "numeric"]
    items: list[dict] = []

    for spec in default_chart_specs(df, columns):
        if (spec.get("title") or "").lower() in existing_titles:
            continue
        items.append({"label": spec["title"], "kind": "chart",
                      "detail": spec["chart_type"], "op": {"op": "add_chart", **spec}})

    # A couple of extra chart shapes the defaults may not include.
    cats = [c["name"] for c in columns if c["type"] == "categorical"]
    good_cat = next((c for c in cats if c in df.columns and 2 <= df[c].nunique(dropna=True) <= 30), None)
    dt = [c["name"] for c in columns if c["type"] == "datetime"]
    if good_cat and num_cols:
        title = f"{num_cols[0]} treemap by {good_cat}"
        if title.lower() not in existing_titles:
            items.append({"label": title, "kind": "chart", "detail": "treemap",
                          "op": {"op": "add_chart", "chart_type": "treemap", "x": good_cat,
                                 "y": num_cols[0], "group_by": None, "agg": "sum", "title": title}})
        if dt:
            title = f"Stacked {num_cols[0]} area by {good_cat}"
            if title.lower() not in existing_titles:
                items.append({"label": title, "kind": "chart", "detail": "area",
                              "op": {"op": "add_chart", "chart_type": "area", "x": dt[0],
                                     "y": num_cols[0], "group_by": good_cat, "agg": "sum", "title": title}})

    for col in num_cols[:4]:
        for agg, label in (("sum", f"Total {col}"), ("mean", f"Avg {col}"), ("count", f"Count of {col}")):
            if label.lower() in existing_labels:
                continue
            items.append({"label": label, "kind": "metric", "detail": f"{agg}({col})",
                          "op": {"op": "add_metric", "column": col, "agg": agg, "label": label}})

    if "statistical analysis" not in existing_titles:
        items.append({"label": "Statistical analysis", "kind": "analysis",
                      "detail": "trends, movers, outliers · instant", "op": {"op": "add_analysis"}})
    if "key findings" not in existing_titles:
        items.append({"label": "AI key findings", "kind": "analysis",
                      "detail": "narrative summary of the data", "op": {"op": "add_key_findings"}})
    items.append({"label": "Text note", "kind": "section", "detail": "markdown heading or comment",
                  "op": {"op": "add_text", "text": "New note — click to edit."}})
    if not any(w.get("kind") == "table" for w in widgets):
        items.append({"label": "Data table", "kind": "section", "detail": "sortable raw rows",
                      "op": {"op": "add_table"}})
    if not any(w.get("kind") == "comparison" for w in widgets) and good_cat and len(num_cols) >= 2:
        items.append({"label": "Entity comparison", "kind": "section", "detail": "radar + stat cards",
                      "op": {"op": "add_comparison"}})
    return items


def insights_from_pipeline(internet_findings: Optional[dict], stage3_result: Optional[dict]) -> list[dict]:
    """Distil a pipeline run into insight widgets: one for the internet
    research findings (with sources), one for the chairman synthesis."""
    insights = []
    if internet_findings and (internet_findings.get("combined_summary") or "").strip():
        insights.append({
            "title": "Internet research",
            "text": internet_findings["combined_summary"],
            "sources": (internet_findings.get("sources") or [])[:8],
        })
    text = (stage3_result or {}).get("response", "")
    if text.strip():
        insights.append({"title": "AI council synthesis", "text": text, "sources": []})
    return insights


def augment_with_research_analytics(
    dashboard: dict,
    internet_findings: Optional[dict],
    stage1_results: Optional[list],
    report: Optional[dict],
) -> None:
    """Pin the research run's OWN analytics onto the dashboard, in place:
    metric cards for sources/council/confidence and a prediction-summary card
    when the run produced a prediction table. Skips anything already present
    (safe to call more than once)."""
    widgets = dashboard.setdefault("widgets", [])
    have = {w.get("label") for w in widgets if w.get("kind") == "metric"}
    have |= {w.get("title") for w in widgets if w.get("kind") == "insight"}

    def add_metric(label, value, sub=None):
        if label in have or value in (None, "", 0, "0"):
            return
        # Static analytics of this run — no spec, so refresh leaves them alone.
        metric = {"id": _wid(), "kind": "metric", "label": label, "value": _fmt_value(value), "sub": sub, "spec": None}
        idx = max((i for i, w in enumerate(widgets) if w["kind"] == "metric"), default=-1)
        widgets.insert(idx + 1, metric)

    sources = (internet_findings or {}).get("sources") or []
    if sources:
        n_auth = sum(1 for s in sources if s.get("quality") == "authoritative")
        add_metric("Web sources", len(sources), f"{n_auth} authoritative" if n_auth else None)
    if stage1_results:
        add_metric("AI council models", len(stage1_results))
    confidence = ((report or {}).get("sections", {}).get("chairman_synthesis", {}) or {}).get("confidence")
    if confidence:
        add_metric("Council consensus", str(confidence).capitalize())

    pred = (report or {}).get("prediction_table") or []
    if pred and "Prediction summary" not in have:
        lines = ["| Entity | Probability | Confidence |", "|---|---|---|"]
        for p in pred[:8]:
            lines.append(f"| {p.get('entity', '')} | {p.get('low_pct', '?')}–{p.get('high_pct', '?')}% | {str(p.get('confidence', '')).capitalize()} |")
        widgets.append({
            "id": _wid(), "kind": "insight", "title": "Prediction summary",
            "text": "\n".join(lines), "sources": [],
        })

    dashboard["updated_at"] = datetime.utcnow().isoformat() + "Z"
