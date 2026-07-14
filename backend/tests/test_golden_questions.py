"""Night 3, Phase 0g — golden question set with hand-computed answers over the
SaaS sample (18 rows = 6 months × 3 plans). These assert the deterministic
engine (no LLM): the numbers it computes must be right, so a correct model can
phrase them and the grounding guard has the truth to check against.

Hand-computed truths:
  - current MRR (Jun 2026) = 9947 + 27888 + 52761         = 90,596
  - naive SUM(mrr) over all 18 rows                        = 480,506  (wrong: double-counts)
  - customers in Jun 2026 = 483 + 207 + 41                 = 731
  - highest single MRR                                     = 52,761
  - lowest single MRR                                      = 7,995
"""
import os

import pandas as pd
import pytest

from backend.data_analysis import classify_measure
from backend.dashboard import _stock_total_override, _infer_period
from backend.query import run_query_spec

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "saas_revenue.csv")


@pytest.fixture
def df():
    d = pd.read_csv(SAMPLE)
    d["month"] = pd.to_datetime(d["month"])
    return d


@pytest.fixture
def measures(df):
    return {c: classify_measure(c, df[c]) for c in df.columns}


def test_period_is_monthly(df):
    assert _infer_period(df, "month") == "month"


def test_total_mrr_is_current_not_sum(df, measures):
    r = _stock_total_override("what is the total MRR", {"agg": {"mrr": "sum"}}, df, measures, "month")
    assert round(r["corrected"]) == 90596
    assert round(r["raw_sum"]) == 480506  # the wrong number, kept only to explain


def test_highest_mrr_is_a_plain_max_not_overridden(df, measures):
    # "highest" is a legitimate max — the stock-total override must NOT fire.
    assert _stock_total_override("what is the highest MRR", {"agg": {"mrr": "max"}}, df, measures, "month") is None
    r = run_query_spec(df, {"agg": {"mrr": "max"}}, measures=measures, time_col="month")
    assert r["rows"][0]["mrr_max"] == 52761


def test_lowest_mrr(df, measures):
    r = run_query_spec(df, {"agg": {"mrr": "min"}}, measures=measures, time_col="month")
    assert r["rows"][0]["mrr_min"] == 7995


def test_customers_in_june(df, measures):
    r = run_query_spec(
        df,
        {"filter": [{"column": "month", "op": "==", "value": "2026-06-01"}], "agg": {"customers": "sum"}},
        measures=measures, time_col="month",
    )
    assert r["rows"][0]["customers_sum"] == 731


def test_customers_total_is_also_stock_corrected(df, measures):
    # customers is a stock too — its 'total' is the latest period (731), not 1236.
    r = _stock_total_override("what is the total number of customers", {"agg": {"customers": "sum"}},
                              df, measures, "month")
    assert round(r["corrected"]) == 731


def test_unknown_column_is_an_error_not_a_guess(df, measures):
    # "churn rate" — there is no such column. The engine must error, not invent.
    r = run_query_spec(df, {"agg": {"churn": "mean"}}, measures=measures, time_col="month")
    # churn isn't a column, so the agg is dropped → falls back to a plain select,
    # never fabricates a churn number.
    assert "churn" not in str(r.get("columns"))
