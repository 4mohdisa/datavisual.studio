"""Data analysis layer — pandas profiling and Plotly chart generation."""

import json
import re
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
from pathlib import Path
from typing import Any

# Explicit date formats tried when pandas' automatic parse doesn't reach the
# confidence threshold.
_DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y", "%b %d, %Y"]

# Large-file sampling threshold.
_MAX_ROWS = 50000
_SAMPLE_ROWS = 10000

_DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgb(15,15,15)",
    plot_bgcolor="rgb(15,15,15)",
    font=dict(color="rgb(235,235,235)"),
)
_GRID = dict(gridcolor="rgb(35,35,35)", zerolinecolor="rgb(35,35,35)")


def _read_csv_robust(path: str) -> pd.DataFrame:
    """Read a CSV, detecting encoding and falling back utf-8 → latin-1 → cp1252."""
    encodings: list[str] = []
    # Prefer charset_normalizer's detection if available (transitive dep).
    try:
        from charset_normalizer import from_path
        best = from_path(path).best()
        if best and best.encoding:
            encodings.append(best.encoding)
    except Exception:
        pass
    for enc in ("utf-8", "latin-1", "cp1252"):
        if enc not in encodings:
            encodings.append(enc)

    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception:
            # A non-encoding error (e.g. parser error) won't be fixed by another
            # encoding — re-raise it.
            raise
    raise ValueError("Could not detect file encoding. Save as UTF-8 CSV and try again.")


def _load(path: str) -> pd.DataFrame:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".csv":
        return _read_csv_robust(path)
    if ext in (".xls", ".xlsx"):
        return pd.read_excel(path)
    if ext == ".json":
        return pd.read_json(path)
    raise ValueError(f"Unsupported file type: {ext}")


def _clean_numeric_strings(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Strip currency symbols ($, £, €, A$) and thousands separators from string
    columns that are really numeric, converting them to float. Returns the
    (possibly copied) dataframe and the list of cleaned column names."""
    cleaned: list[str] = []
    for col in df.columns:
        if df[col].dtype != object:
            continue
        as_str = df[col].astype(str)
        has_symbol = as_str.str.contains(r"A\$|[£€$,]", regex=True, na=False).any()
        if not has_symbol:
            continue
        stripped = (
            as_str.str.replace("A$", "", regex=False)
            .str.replace(r"[£€$,]", "", regex=True)
            .str.strip()
        )
        converted = pd.to_numeric(stripped, errors="coerce")
        nonnull = int(df[col].notna().sum())
        # Only adopt the conversion if ~all non-null values became numbers, so we
        # don't accidentally wreck a genuine text column that happens to use commas.
        if nonnull > 0 and int(converted.notna().sum()) >= nonnull * 0.9:
            df = df.copy()
            df[col] = converted
            cleaned.append(col)
    return df, cleaned


def _col_type(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    return "categorical"


# Measure semantics (Night 3, Phase 0b). Stocks/flows/ratios are NOT the same
# thing under aggregation: a flow (revenue-in-period, units, count) is additive
# across time; a stock (MRR, ARR, headcount, balance, inventory, price) is NOT —
# summing it across periods double-counts; a ratio (%, rate, average) is not
# additive at all. Name heuristics; substring match, lowercased.
_STOCK_NAMES = (
    "mrr", "arr", "balance", "inventory", "headcount", "customer", "subscriber",
    "active", "seat", "price", "stock", "level", "aum", "cash", "backlog",
    "population", "membership", "member",
)
_RATIO_NAMES = (
    "rate", "ratio", "pct", "percent", "margin", "conversion", "avg", "average",
    "mean", "per_", "share", "cpc", "cpm", "ctr", "churn", "yield", "utilization",
)
_FLOW_NAMES = (
    "revenue", "sales", "unit", "count", "amount", "spend", "cost", "qty",
    "quantity", "order", "click", "impression", "session", "signup", "new_",
    "volume", "gmv", "booking", "transaction", "profit", "income", "expense",
)
_ID_NAMES = ("id", "uuid", "guid", "code", "sku")


def classify_measure(name: str, series: pd.Series) -> str:
    """Classify a column's role for aggregation safety:
    identifier | category | timestamp | flow | stock | ratio.
    Name-heuristic first (a stable, explainable signal); the caller may refine
    stocks from data shape (a measure roughly stable per entity across periods)."""
    n = str(name).strip().lower()
    if pd.api.types.is_datetime64_any_dtype(series):
        return "timestamp"
    if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        return "category"
    # numeric — decide identifier / ratio / stock / flow (order matters).
    if any(re.search(rf"(^|[_\s]){k}([_\s]|$)", n) for k in _ID_NAMES):
        return "identifier"
    if any(k in n for k in _RATIO_NAMES):
        return "ratio"
    if any(k in n for k in _STOCK_NAMES):
        return "stock"
    if any(k in n for k in _FLOW_NAMES):
        return "flow"
    return "flow"  # additive is the conventional default for an unlabelled measure


def _try_parse_datetime(df: pd.DataFrame) -> pd.DataFrame:
    threshold = len(df) * 0.8
    for col in df.columns:
        if df[col].dtype != object:
            continue
        parsed = None
        # 1) automatic inference
        try:
            auto = pd.to_datetime(df[col], errors="coerce")
            if auto.notna().sum() > threshold:
                parsed = auto
        except Exception:
            pass
        # 2) explicit formats if automatic parse fell short
        if parsed is None:
            for fmt in _DATE_FORMATS:
                try:
                    cand = pd.to_datetime(df[col], format=fmt, errors="coerce")
                except Exception:
                    continue
                if cand.notna().sum() > threshold:
                    parsed = cand
                    break
        if parsed is not None:
            df = df.copy()
            df[col] = parsed
    return df


def _fig_json(fig: go.Figure) -> dict:
    fig.update_layout(**_DARK)
    for axis in ("xaxis", "yaxis"):
        if hasattr(fig.layout, axis):
            getattr(fig.layout, axis).update(**_GRID)
    return json.loads(pio.to_json(fig))


def _detect_and_build_charts(df: pd.DataFrame) -> list[dict]:
    datetime_cols = [c for c in df.columns if _col_type(df[c]) == "datetime"]
    numeric_cols = [c for c in df.columns if _col_type(df[c]) == "numeric"]
    categorical_cols = [c for c in df.columns if _col_type(df[c]) == "categorical"]

    charts = []

    # Time + numeric → line chart (one chart per numeric column, max 3).
    # With a categorical column present, draw one line per category (top 8 by
    # mean) instead of one line per raw row — otherwise multi-entity datasets
    # render as unreadable spaghetti.
    if datetime_cols and numeric_cols:
        time_col = datetime_cols[0]
        cat_col = categorical_cols[0] if categorical_cols else None
        for num_col in numeric_cols[:3]:
            fig = go.Figure()
            if cat_col:
                top_cats = df.groupby(cat_col)[num_col].mean().sort_values(ascending=False).head(8).index
                for cat in top_cats:
                    sub = df[df[cat_col] == cat].groupby(time_col, as_index=False)[num_col].mean().sort_values(time_col)
                    fig.add_trace(go.Scatter(x=sub[time_col], y=sub[num_col], mode="lines+markers", name=str(cat)))
                title = f"{num_col} over time by {cat_col}"
            else:
                series = df.groupby(time_col, as_index=False)[num_col].mean().sort_values(time_col)
                fig.add_trace(go.Scatter(
                    x=series[time_col], y=series[num_col], mode="lines",
                    name=num_col, line=dict(color="rgb(100,160,255)"),
                ))
                title = f"{num_col} over time"
            fig.update_layout(title=title, xaxis_title=time_col, yaxis_title=num_col)
            charts.append({"title": title, "type": "line", "plotly_json": _fig_json(fig)})
        return charts

    # Two numeric → scatter with correlation
    if len(numeric_cols) == 2:
        x, y = numeric_cols
        corr = df[[x, y]].corr().iloc[0, 1]
        # OLS trendline needs statsmodels; degrade to a plain scatter if it's absent
        # so a 2-numeric dataset never crashes the whole analysis.
        try:
            import statsmodels  # noqa: F401
            fig = px.scatter(df, x=x, y=y, trendline="ols", trendline_color_override="rgb(255,120,80)")
        except Exception:
            fig = px.scatter(df, x=x, y=y)
        fig.update_layout(title=f"{x} vs {y} (r={corr:.2f})")
        charts.append({"title": f"{x} vs {y}", "type": "scatter", "plotly_json": _fig_json(fig)})
        return charts

    # Categorical + numeric → ranked bar chart
    if categorical_cols and numeric_cols:
        cat_col = categorical_cols[0]
        num_col = numeric_cols[0]
        grouped = df.groupby(cat_col)[num_col].mean().sort_values(ascending=False).head(20)
        fig = go.Figure(go.Bar(
            x=grouped.index.astype(str),
            y=grouped.values,
            marker_color="rgb(100,200,150)",
        ))
        fig.update_layout(title=f"{num_col} by {cat_col}", xaxis_title=cat_col, yaxis_title=f"avg {num_col}")
        charts.append({"title": f"{num_col} by {cat_col}", "type": "bar", "plotly_json": _fig_json(fig)})

        if len(numeric_cols) > 1:
            num_col2 = numeric_cols[1]
            grouped2 = df.groupby(cat_col)[num_col2].mean().sort_values(ascending=False).head(20)
            fig2 = go.Figure(go.Bar(
                x=grouped2.index.astype(str),
                y=grouped2.values,
                marker_color="rgb(255,180,80)",
            ))
            fig2.update_layout(title=f"{num_col2} by {cat_col}", xaxis_title=cat_col, yaxis_title=f"avg {num_col2}")
            charts.append({"title": f"{num_col2} by {cat_col}", "type": "bar", "plotly_json": _fig_json(fig2)})
        return charts

    # Single numeric → histogram
    if len(numeric_cols) == 1:
        num_col = numeric_cols[0]
        fig = px.histogram(df, x=num_col, nbins=30, color_discrete_sequence=["rgb(100,160,255)"])
        fig.update_layout(title=f"Distribution of {num_col}")
        charts.append({"title": f"Distribution of {num_col}", "type": "histogram", "plotly_json": _fig_json(fig)})
        return charts

    # Multiple numeric → correlation heatmap
    if len(numeric_cols) > 2:
        corr_matrix = df[numeric_cols].corr()
        fig = go.Figure(go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns.tolist(),
            y=corr_matrix.index.tolist(),
            colorscale="RdBu",
            zmid=0,
            text=corr_matrix.round(2).values,
            texttemplate="%{text}",
        ))
        fig.update_layout(title="Correlation heatmap")
        charts.append({"title": "Correlation heatmap", "type": "heatmap", "plotly_json": _fig_json(fig)})
        return charts

    return charts


# ---------------------------------------------------------------------------
# Data excerpt — real rows/values injected into the council prompt so the models
# reason over the uploaded dataset rather than their training knowledge.
# ---------------------------------------------------------------------------

_PRIMARY_NUMERIC_NAMES = ("rating", "elo", "score", "points", "value")
_SECONDARY_PREF = ("rank", "wins", "losses", "draws", "goals_for", "goals_against", "matches_total")
_TIME_NAMES = ("year", "season", "yr")
_TOP_N = 15
_TABLE_COLS = 6


def _pick_entity_column(df: pd.DataFrame, cat_cols: list[str]) -> str | None:
    """First categorical column that looks like an entity (repeats, not a pure id)."""
    n = len(df)
    for c in cat_cols:
        card = df[c].nunique(dropna=True)
        if 2 <= card < n:
            return c
    return cat_cols[0] if cat_cols else None


def _pick_primary_numeric(df: pd.DataFrame, num_cols: list[str]) -> str | None:
    """Prefer a semantically important column (rating/score/…), else highest variance."""
    for name in _PRIMARY_NUMERIC_NAMES:
        for c in num_cols:
            if name in c.lower():
                return c
    best, best_var = None, -1.0
    for c in num_cols:
        try:
            v = float(df[c].var())
        except Exception:
            continue
        if v == v and v > best_var:  # v == v filters NaN
            best, best_var = c, v
    return best or (num_cols[0] if num_cols else None)


def _pick_time_column(df: pd.DataFrame, columns_info: list[dict]) -> tuple[str | None, str | None]:
    dt = [c["name"] for c in columns_info if c["type"] == "datetime"]
    if dt:
        return dt[0], "datetime"
    for c in columns_info:
        if c["type"] == "numeric" and c["name"].lower() in _TIME_NAMES:
            return c["name"], "year"
    return None, None


def _pick_table_columns(num_cols: list[str], primary: str) -> list[str]:
    cols = [primary]
    for name in _SECONDARY_PREF:
        for c in num_cols:
            if c.lower() == name and c not in cols:
                cols.append(c)
    for c in num_cols:
        if c not in cols and len(cols) < _TABLE_COLS:
            cols.append(c)
    return cols[:_TABLE_COLS]


def _latest_snapshot(df: pd.DataFrame, entity_col: str, time_col: str | None) -> pd.DataFrame:
    """One row per entity — its most recent record when a time column exists."""
    if not time_col:
        return df
    try:
        return df.sort_values(time_col).groupby(entity_col, as_index=False).tail(1)
    except Exception:
        return df


def _fmt_val(v: Any) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return "–"
    if isinstance(v, float):
        return f"{v:.0f}" if v == int(v) else f"{v:.2f}"
    return str(v)


def _ascii_table(headers: list[str], rows: list[list[Any]]) -> str:
    cells = [headers] + [[_fmt_val(v) for v in r] for r in rows]
    widths = [max(len(str(cells[r][c])) for r in range(len(cells))) for c in range(len(headers))]
    lines = []
    for r, row in enumerate(cells):
        lines.append(" | ".join(str(row[c]).ljust(widths[c]) for c in range(len(headers))))
        if r == 0:
            lines.append("-+-".join("-" * widths[c] for c in range(len(headers))))
    return "\n".join(lines)


def _build_top_entities(df, entity_col, table_cols, primary, time_col) -> str:
    latest = _latest_snapshot(df, entity_col, time_col)
    try:
        top = latest.sort_values(primary, ascending=False).head(_TOP_N)
    except Exception:
        top = latest.head(_TOP_N)
    headers = [entity_col] + table_cols
    rows = [[r[entity_col]] + [r.get(c) for c in table_cols] for _, r in top.iterrows()]
    snap = " (latest snapshot per entity)" if time_col else ""
    return (
        f"TOP {len(rows)} {entity_col.upper()} BY {primary.upper()}{snap} — actual values from the uploaded dataset:\n"
        + _ascii_table(headers, rows)
    )


def _build_time_trend(df, entity_col, primary, time_col, time_kind) -> str:
    import numpy as np
    d = df[[entity_col, primary, time_col]].dropna()
    if d.empty:
        return ""
    if time_kind == "datetime":
        d = d.assign(_period=pd.to_datetime(d[time_col]).dt.year)
    else:
        d = d.assign(_period=pd.to_numeric(d[time_col], errors="coerce"))
    d = d.dropna(subset=["_period"])
    d["_period"] = d["_period"].astype(int)
    periods = sorted(d["_period"].unique())
    if len(periods) < 2:
        return ""

    pivot = d.groupby([entity_col, "_period"])[primary].mean().unstack("_period")

    # 5 evenly spaced periods across the range
    idx = np.linspace(0, len(periods) - 1, min(5, len(periods))).round().astype(int)
    sel_periods = sorted({periods[i] for i in idx})

    # current value (last period) and first→last delta per entity
    deltas, current = {}, {}
    for ent, row in pivot.iterrows():
        s = row.dropna()
        if len(s) >= 1:
            current[ent] = s.iloc[-1]
        if len(s) >= 2:
            deltas[ent] = s.iloc[-1] - s.iloc[0]

    chosen = []
    if current:
        chosen.append(max(current, key=current.get))          # highest current
    if deltas:
        chosen.append(max(deltas, key=deltas.get))            # fastest growing
        chosen.append(min(deltas, key=deltas.get))            # largest decline
    chosen = list(dict.fromkeys(e for e in chosen if e is not None))
    if not chosen:
        return ""

    headers = [entity_col] + [str(p) for p in sel_periods]
    rows = []
    for ent in chosen:
        rows.append([ent] + [pivot.loc[ent].get(p) if ent in pivot.index else None for p in sel_periods])
    return (
        f"{primary.upper()} OVER TIME (selected entities: highest current, fastest rise, largest decline):\n"
        + _ascii_table(headers, rows)
    )


def _build_stats_with_context(df, entity_col, primary, table_cols, statistics, time_col) -> str:
    latest = _latest_snapshot(df, entity_col, time_col)
    lines = []
    for col in table_cols:
        if col not in statistics:
            continue
        s = statistics[col]
        ctx_max = ctx_min = ""
        try:
            imax, imin = df[col].idxmax(), df[col].idxmin()
            em, en = df.loc[imax, entity_col], df.loc[imin, entity_col]
            if time_col:
                pm = df.loc[imax, time_col]
                pn = df.loc[imin, time_col]
                pm = pm.year if hasattr(pm, "year") else pm
                pn = pn.year if hasattr(pn, "year") else pn
                ctx_max, ctx_min = f" ({em} in {pm})", f" ({en} in {pn})"
            else:
                ctx_max, ctx_min = f" ({em})", f" ({en})"
        except Exception:
            pass
        line = f"  {col}: min={_fmt_val(s['min'])}{ctx_min}, max={_fmt_val(s['max'])}{ctx_max}, mean={_fmt_val(s['mean'])}"
        if col == primary:
            try:
                lead = latest.sort_values(primary, ascending=False).iloc[0]
                line += f", current leader={lead[entity_col]} ({_fmt_val(lead[primary])})"
            except Exception:
                pass
        lines.append(line)
    return "KEY STATISTICS WITH CONTEXT (who holds each extreme):\n" + "\n".join(lines) if lines else ""


def build_data_excerpt(df: pd.DataFrame, columns_info: list[dict], statistics: dict) -> str:
    """Assemble a compact, factual excerpt of real values for the council prompt.

    Returns '' on any failure so the pipeline degrades to stats-only rather than
    crashing.
    """
    try:
        cat_cols = [c["name"] for c in columns_info if c["type"] == "categorical"]
        num_cols = [c["name"] for c in columns_info if c["type"] == "numeric"]
        if not num_cols:
            return ""
        entity_col = _pick_entity_column(df, cat_cols)
        primary = _pick_primary_numeric(df, num_cols)
        time_col, time_kind = _pick_time_column(df, columns_info)
        if not (entity_col and primary):
            return ""
        table_cols = _pick_table_columns(num_cols, primary)

        parts = [_build_top_entities(df, entity_col, table_cols, primary, time_col)]
        if time_col:
            trend = _build_time_trend(df, entity_col, primary, time_col, time_kind)
            if trend:
                parts.append(trend)
        stats = _build_stats_with_context(df, entity_col, primary, table_cols, statistics, time_col)
        if stats:
            parts.append(stats)
        return "\n\n".join(parts)
    except Exception as e:
        print(f"[data_analysis] failed to build data excerpt: {e}", flush=True)
        return ""


def _detect_anomalies(df, columns_info, numeric_cols, max_per_col: int = 5, max_total: int = 20) -> list[dict]:
    """Flag rows whose numeric value sits > 3 IQR from the column median (6.5).
    Returns [{entity, column, value}] tagged with an entity name when available."""
    cat_cols = [c["name"] for c in columns_info if c["type"] == "categorical"]
    entity_col = _pick_entity_column(df, cat_cols) if cat_cols else None
    out: list[dict] = []
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) <= 10:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        med = series.median()
        mask = (df[col] - med).abs() > 3 * iqr
        flagged = df[mask]
        for _, row in flagged.head(max_per_col).iterrows():
            try:
                val = float(row[col])
            except (TypeError, ValueError):
                continue
            out.append({
                "entity": str(row[entity_col]) if entity_col and entity_col in df.columns else f"row {row.name}",
                "column": col,
                "value": round(val, 2),
            })
            if len(out) >= max_total:
                return out
    return out


def analyse_file(path: str) -> dict[str, Any]:
    return analyse_df(_load(path))


def analyse_df(df: pd.DataFrame) -> dict[str, Any]:
    """Profile a dataframe: summary stats, quality notes, charts, data excerpt.
    Shared by the upload/analyse path (via analyse_file) and /api/reanalyse,
    which filters the dataframe in memory."""
    # Empty / malformed: no data rows after the header.
    if df is None or len(df) == 0:
        return {"error": "File appears empty or has no data rows"}

    # Clean currency/number-formatted string columns before profiling.
    df, cleaned_cols = _clean_numeric_strings(df)

    df = _try_parse_datetime(df)

    # Large-file handling: analyse a 10,000-row sample.
    total_rows = len(df)
    sample_note = None
    if total_rows > _MAX_ROWS:
        datetime_cols = [c for c in df.columns if _col_type(df[c]) == "datetime"]
        if datetime_cols:
            df = df.sort_values(datetime_cols[0], ascending=False).head(_SAMPLE_ROWS)
        else:
            df = df.sample(n=_SAMPLE_ROWS, random_state=42)
        sample_note = f"Large dataset — analysed on a {_SAMPLE_ROWS:,}-row sample ({total_rows:,} rows total)"

    columns_info = []
    statistics = {}
    quality_notes = []

    # Surface preprocessing notes first.
    if sample_note:
        quality_notes.append(sample_note)
    if cleaned_cols:
        quality_notes.append("Cleaned currency/number formatting in: " + ", ".join(cleaned_cols))

    for col in df.columns:
        col_type = _col_type(df[col])
        null_count = int(df[col].isna().sum())
        # measure role (Phase 0b) travels with the schema so the query engine and
        # the assistant can refuse to sum a stock across time.
        columns_info.append({
            "name": col, "type": col_type, "null_count": null_count,
            "measure": classify_measure(col, df[col]),
        })

        if null_count > 0:
            pct = round(null_count / len(df) * 100, 1)
            quality_notes.append(f"{col}: {null_count} null values ({pct}%)")

        if col_type == "numeric":
            series = df[col].dropna()
            statistics[col] = {
                "min": float(series.min()) if len(series) else None,
                "max": float(series.max()) if len(series) else None,
                "mean": round(float(series.mean()), 4) if len(series) else None,
                "unique_count": int(series.nunique()),
            }

    # Outlier detection for numeric columns
    numeric_cols = [c["name"] for c in columns_info if c["type"] == "numeric"]
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) > 10:
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            outlier_count = int(((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum())
            if outlier_count > 0:
                quality_notes.append(f"{col}: {outlier_count} potential outliers (IQR method)")

    # Anomaly detection (6.5): values > 3 IQR from the median, tagged with the
    # entity name so they can be surfaced in the report + council prompt.
    anomalies = _detect_anomalies(df, columns_info, numeric_cols)

    charts = _detect_and_build_charts(df)
    data_excerpt = build_data_excerpt(df, columns_info, statistics)

    return {
        "data_summary": {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": columns_info,
            "statistics": statistics,
            "quality_notes": quality_notes,
            "anomalies": anomalies,
        },
        "charts": charts,
        "data_excerpt": data_excerpt,  # real rows/values for the council prompt
        "dataframe": df,  # returned in-memory for filtering; not serialized to JSON
    }
