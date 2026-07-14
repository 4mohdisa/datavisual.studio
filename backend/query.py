"""Deterministic data-query engine for the assistant.

The assistant's LLM emits a **query spec** — it never computes numbers itself.
The backend executes the spec against the dataframe with pandas and returns a
small result table; the LLM then phrases an answer *from that executed result*.
So every number in an answer is computed, not generated (Hard Rule 7), and the
same spec can be pinned as a widget via the existing add_chart / add_metric ops.

Spec shape (all keys optional):
    {
      "filter":   [{"column": "region", "op": "==", "value": "West"}],
      "group_by": ["region"],
      "agg":      {"revenue": "sum", "units": "mean"},
      "select":   ["region", "revenue"],      # used only when there is no agg
      "sort":     {"column": "revenue_sum", "dir": "desc"},
      "limit":    10
    }
"""

import math
from typing import Any, Optional

import numpy as np
import pandas as pd

_NUMERIC_AGGS = {"sum", "mean", "median", "std"}
_ALL_AGGS = _NUMERIC_AGGS | {"min", "max", "count", "nunique"}
_MAX_ROWS = 100


def _clean(v: Any) -> Any:
    if isinstance(v, float):
        return None if (math.isnan(v) or math.isinf(v)) else round(v, 4)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)
    return v


def run_query_spec(df: Optional[pd.DataFrame], spec: dict,
                   *, measures: Optional[dict] = None, time_col: Optional[str] = None) -> dict:
    """Execute a query spec. Returns {columns, rows, row_count} or {error}.

    `measures` (col → identifier|category|timestamp|flow|stock|ratio) and
    `time_col` enable the stock-sum guard (Phase 0b/0c): summing a *stock* (MRR,
    headcount, balance…) across a time dimension double-counts, so the result is
    annotated with a `warning` and the correct `corrected` value (the latest
    period), rather than silently handing back a nonsense total."""
    if df is None or getattr(df, "empty", True):
        return {"error": "No dataset is attached, so there's nothing to compute from."}
    if not isinstance(spec, dict):
        return {"error": "Could not understand the question as a data query."}

    cols = {str(c) for c in df.columns}
    work = df

    # --- filters --------------------------------------------------------------
    for f in (spec.get("filter") or []):
        c, op, val = str(f.get("column", "")), f.get("op", "=="), f.get("value")
        if c not in cols:
            return {"error": f"Unknown column '{c}'."}
        s = work[c]
        try:
            if op == "==":
                work = work[s == val]
            elif op == "!=":
                work = work[s != val]
            elif op in (">", ">=", "<", "<="):
                num = pd.to_numeric(s, errors="coerce")
                thr = float(val)
                work = work[{">": num > thr, ">=": num >= thr, "<": num < thr, "<=": num <= thr}[op]]
            elif op == "in":
                work = work[s.isin(val if isinstance(val, list) else [val])]
            elif op == "not in":
                work = work[~s.isin(val if isinstance(val, list) else [val])]
            elif op == "contains":
                work = work[s.astype(str).str.contains(str(val), case=False, na=False)]
            else:
                return {"error": f"Unsupported filter op '{op}'."}
        except Exception as e:
            return {"error": f"Filter on '{c}' failed: {e}"}

    group_by = [str(c) for c in (spec.get("group_by") or []) if str(c) in cols]

    # normalize agg → {column: func}
    agg = spec.get("agg") or {}
    if isinstance(agg, dict) and "column" in agg and "func" in agg:
        agg = {str(agg["column"]): agg["func"]}
    agg = {str(k): ("mean" if str(v).lower() == "avg" else str(v).lower())
           for k, v in (agg.items() if isinstance(agg, dict) else [])
           if str(k) in cols and (str(v).lower() == "avg" or str(v).lower() in _ALL_AGGS)}

    try:
        if group_by and agg:
            res = (work.groupby(group_by, dropna=False)
                       .agg(**{f"{c}_{f}": (c, f) for c, f in agg.items()})
                       .reset_index())
        elif agg:
            row = {}
            for c, f in agg.items():
                s = work[c]
                if f == "count":
                    row[f"{c}_{f}"] = int(s.count())
                elif f == "nunique":
                    row[f"{c}_{f}"] = int(s.nunique())
                else:
                    series = pd.to_numeric(s, errors="coerce") if f in _NUMERIC_AGGS else s
                    row[f"{c}_{f}"] = getattr(series, f)()
            res = pd.DataFrame([row])
        else:
            sel = [str(c) for c in (spec.get("select") or []) if str(c) in cols] or list(df.columns)
            res = work[sel]
    except Exception as e:
        return {"error": f"Could not compute the result: {e}"}

    # --- sort -----------------------------------------------------------------
    sort = spec.get("sort")
    if sort:
        by, asc = [], []
        for so in (sort if isinstance(sort, list) else [sort]):
            c = str(so.get("column", ""))
            if c in res.columns:
                by.append(c)
                asc.append(str(so.get("dir", "desc")).lower() != "desc")
        if by:
            res = res.sort_values(by=by, ascending=asc)

    limit = spec.get("limit")
    n = limit if isinstance(limit, int) and 0 < limit < _MAX_ROWS else _MAX_ROWS
    res = res.head(n).replace({np.nan: None})

    rows = [{k: _clean(v) for k, v in r.items()} for r in res.to_dict(orient="records")]
    result = {"columns": [str(c) for c in res.columns], "rows": rows, "row_count": len(rows)}

    warning, corrected, corrected_label = _stock_sum_guard(work, agg, group_by, measures, time_col)
    if warning:
        result["warning"] = warning
        if corrected is not None:
            result["corrected"] = corrected
            result["corrected_label"] = corrected_label
    return result


def _stock_sum_guard(work, agg, group_by, measures, time_col):
    """Detect SUM of a stock across a time dimension. Returns
    (warning, corrected_value, corrected_label) or (None, None, None)."""
    if not measures or not isinstance(agg, dict):
        return None, None, None
    # Auto-detect the time column if the caller didn't name one.
    if not time_col:
        time_col = next((c for c in work.columns
                         if pd.api.types.is_datetime64_any_dtype(work[c])), None)
    if not time_col or time_col not in work.columns:
        return None, None, None
    try:
        periods = work[time_col].dropna().nunique()
    except Exception:
        return None, None, None
    if periods <= 1 or time_col in (group_by or []):
        return None, None, None  # single period, or time kept as a group → fine

    for col, func in agg.items():
        if func != "sum" or measures.get(col) != "stock":
            continue
        try:
            latest = work[work[time_col] == work[time_col].max()]
            non_time_groups = [g for g in (group_by or []) if g != time_col]
            if non_time_groups:
                corrected = None  # per-group corrected is ambiguous; just warn
            else:
                corrected = float(pd.to_numeric(latest[col], errors="coerce").sum())
            raw = float(pd.to_numeric(work[col], errors="coerce").sum())
            label = str(pd.Timestamp(work[time_col].max()).date())
            msg = (f"‘{col}’ is a stock (a level, not a per-period flow), so summing it "
                   f"across {periods} periods counts the same value repeatedly. ")
            if corrected is not None:
                msg += (f"The latest-period total ({label}) is {corrected:,.0f}; "
                        f"the raw sum is {raw:,.0f}.")
            else:
                msg += f"The raw sum across all periods is {raw:,.0f} and is not meaningful."
            return msg, corrected, label
        except Exception:
            return None, None, None
    return None, None, None


def spec_to_widget_op(spec: dict) -> Optional[dict]:
    """Turn a query spec into a dashboard op so an answer can be pinned. A
    grouped aggregate → a bar chart; a whole-frame aggregate → a metric."""
    agg = spec.get("agg") or {}
    if isinstance(agg, dict) and "column" in agg and "func" in agg:
        col, func = str(agg["column"]), str(agg["func"]).lower()
        agg = {col: func}
    if not isinstance(agg, dict) or not agg:
        return None
    col, func = next(iter(agg.items()))
    func = "mean" if str(func).lower() == "avg" else str(func).lower()
    group_by = [str(c) for c in (spec.get("group_by") or [])]
    if group_by:
        return {"op": "add_chart", "type": "bar", "x": group_by[0], "y": str(col),
                "agg": func, "title": f"{func.title()} of {col} by {group_by[0]}"}
    return {"op": "add_metric", "column": str(col), "agg": func,
            "label": f"{func.title()} {col}"}


if __name__ == "__main__":  # pragma: no cover — runnable self-check
    df = pd.DataFrame({"region": ["N", "S", "N", "W"], "revenue": [10, 20, 30, 40], "units": [1, 2, 3, 4]})
    r = run_query_spec(df, {"group_by": ["region"], "agg": {"revenue": "sum"}, "sort": {"column": "revenue_sum", "dir": "desc"}})
    assert r["rows"][0] == {"region": "N", "revenue_sum": 40}, r
    assert run_query_spec(df, {"agg": {"revenue": "sum"}})["rows"][0]["revenue_sum"] == 100
    assert "error" in run_query_spec(df, {"filter": [{"column": "nope", "op": "==", "value": 1}]})
    assert spec_to_widget_op({"group_by": ["region"], "agg": {"revenue": "sum"}})["op"] == "add_chart"
    print("query.py self-check OK")
