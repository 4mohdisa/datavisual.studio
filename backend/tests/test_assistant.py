"""Phase 3 — assistant: deterministic query engine + intent router.

The query engine computes real numbers (never LLM-guessed); the router decides
question vs edit vs both via a keyword fast-path (LLM only when ambiguous — not
exercised here, keeping these hermetic).
"""

import asyncio

import pandas as pd
import pytest

from backend import query
from backend.dashboard import classify_intent


@pytest.fixture
def df():
    return pd.DataFrame({
        "region": ["North", "South", "North", "South", "East", "West"],
        "month": ["2026-01", "2026-01", "2026-02", "2026-02", "2026-01", "2026-02"],
        "revenue": [120, 90, 150, 110, 70, 200],
        "units": [10, 8, 12, 9, 6, 15],
    })


# --- query engine -------------------------------------------------------------

def test_group_by_sum_sorted(df):
    r = query.run_query_spec(df, {"group_by": ["region"], "agg": {"revenue": "sum"},
                                  "sort": {"column": "revenue_sum", "dir": "desc"}})
    assert r["columns"] == ["region", "revenue_sum"]
    assert r["rows"][0] == {"region": "North", "revenue_sum": 270}  # 120+150


def test_whole_frame_aggregate(df):
    r = query.run_query_spec(df, {"agg": {"revenue": "sum", "units": "mean"}})
    assert r["rows"][0]["revenue_sum"] == 740
    assert r["rows"][0]["units_mean"] == pytest.approx(10.0)


def test_filter_then_aggregate(df):
    r = query.run_query_spec(df, {"filter": [{"column": "region", "op": "==", "value": "North"}],
                                  "agg": {"revenue": "sum"}})
    assert r["rows"][0]["revenue_sum"] == 270


def test_select_and_limit(df):
    r = query.run_query_spec(df, {"select": ["region", "revenue"], "limit": 2})
    assert r["row_count"] == 2 and r["columns"] == ["region", "revenue"]


def test_unknown_column_is_graceful_error(df):
    assert "error" in query.run_query_spec(df, {"filter": [{"column": "nope", "op": "==", "value": 1}]})


def test_no_dataset_is_error():
    assert "error" in query.run_query_spec(None, {"agg": {"x": "sum"}})


def test_spec_to_widget_op(df):
    assert query.spec_to_widget_op({"group_by": ["region"], "agg": {"revenue": "sum"}})["op"] == "add_chart"
    assert query.spec_to_widget_op({"agg": {"revenue": "sum"}})["op"] == "add_metric"
    assert query.spec_to_widget_op({"select": ["region"]}) is None


# --- intent router (keyword fast-path — no LLM) -------------------------------

@pytest.mark.parametrize("msg,expected", [
    ("what is the total revenue?", "question"),
    ("which region has the highest revenue?", "question"),
    ("add a bar chart of revenue by region", "edit"),
    ("remove the histogram", "edit"),
    ("rename the dashboard to Q1", "edit"),
    ("add a metric and tell me the average units", "both"),
])
def test_classify_intent_fast_path(msg, expected):
    assert asyncio.run(classify_intent(msg)) == expected
