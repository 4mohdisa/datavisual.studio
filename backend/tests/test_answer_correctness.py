"""Night 3, Phase 0 — the assistant must never state a number it can't defend.

Two of the owner's five bugs live here:
  BUG 1 (wrong number): summed MRR (a stock) across a 6-month × 3-plan series →
         480506, counting the same recurring revenue 6×. Real MRR ≈ 91k.
  BUG 2 (invented unit): restated 480506 as "weekly earnings" with no conversion.

These are written to FAIL against today's code and pass once Phase 0 lands.
"""
import os

import pandas as pd
import pytest

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "saas_revenue.csv")


@pytest.fixture
def saas_df():
    df = pd.read_csv(SAMPLE)
    df["month"] = pd.to_datetime(df["month"])
    return df


# --- BUG 1: summing a stock across time is wrong; total of a stock = latest ---

def test_measure_classification_marks_mrr_a_stock(saas_df):
    from backend.data_analysis import classify_measure
    assert classify_measure("mrr", saas_df["mrr"]) == "stock"
    assert classify_measure("customers", saas_df["customers"]) == "stock"
    assert classify_measure("month", saas_df["month"]) == "timestamp"
    assert classify_measure("plan", saas_df["plan"]) == "category"


def test_sum_of_stock_across_time_is_flagged_and_corrected(saas_df):
    from backend.query import run_query_spec
    # "total MRR" → SUM(mrr) with no group-by. The raw sum is still computed,
    # but the result must WARN that summing a stock double-counts, and expose the
    # correct current value (latest month across plans = 90596).
    result = run_query_spec(
        saas_df, {"agg": {"mrr": "sum"}},
        measures={"mrr": "stock", "customers": "stock"}, time_col="month",
    )
    assert result["warning"], "summing a stock across time must warn"
    assert "recurring" in result["warning"].lower() or "stock" in result["warning"].lower()
    assert abs(result["corrected"] - 90596) < 1, "current MRR = latest month total"


def test_stock_total_override_is_deterministic(saas_df):
    from backend.dashboard import _stock_total_override
    measures = {"mrr": "stock", "customers": "stock"}
    # Whatever aggregation the model picked (sum, max, or nothing), a "total MRR"
    # question resolves to the latest-period total — never 480506, never 52761.
    for spec in ({"agg": {"mrr": "sum"}}, {"agg": {"mrr": "max"}}, {}):
        r = _stock_total_override("what is the total MRR", spec, saas_df, measures, "month")
        assert r is not None, spec
        assert abs(r["corrected"] - 90596) < 1
        assert r["rows"][0][r["columns"][0]] == pytest.approx(90596, abs=1)


def test_stock_total_override_skips_non_total_questions(saas_df):
    from backend.dashboard import _stock_total_override
    # "highest MRR" is a legitimate max, not a total — don't override it.
    r = _stock_total_override("what is the highest MRR", {"agg": {"mrr": "max"}},
                              saas_df, {"mrr": "stock"}, "month")
    assert r is None


# --- BUG 2: the numeric-grounding + unit guard ------------------------------

def test_weekly_restatement_is_refused():
    from backend.answer_guard import check_answer
    # The exact transcript. 480506 is a monthly-sum figure; calling it "weekly"
    # with no arithmetic shown is an invented unit → the guard must reject it.
    result = {"columns": ["mrr_sum"], "rows": [{"mrr_sum": 480506}]}
    ok, reason = check_answer("how much weekly am I making",
                              "Based on the mrr_sum of 480506, your weekly earnings are 480506.",
                              result)
    assert ok is False
    assert "week" in reason.lower() or "unit" in reason.lower() or "deriv" in reason.lower()


def test_hallucinated_number_is_refused():
    from backend.answer_guard import check_answer
    # A number not in the result and not derived → ungrounded.
    result = {"columns": ["mrr_sum"], "rows": [{"mrr_sum": 90596}]}
    ok, reason = check_answer("what is the current MRR",
                              "Your current MRR is 250000.", result)
    assert ok is False


def test_grounded_answer_passes():
    from backend.answer_guard import check_answer
    result = {"columns": ["mrr_sum"], "rows": [{"mrr_sum": 90596}]}
    ok, _ = check_answer("what is the current MRR",
                         "Your current MRR is 90596.", result)
    assert ok is True


def test_explicit_conversion_passes():
    from backend.answer_guard import check_answer
    # A shown derivation is allowed even though 20922 isn't in the result.
    result = {"columns": ["mrr_sum"], "rows": [{"mrr_sum": 90596}]}
    ok, _ = check_answer("how much weekly",
                         "Monthly MRR is 90596; weekly ≈ 90596 ÷ 4.33 = 20922.", result)
    assert ok is True
