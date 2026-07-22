"""Deterministic period-over-period growth (the leashed answer to
'which plan grew fastest'). Growth is computed in pandas from the first vs last
period per group — the model never free-hands it. See `_growth_override`.
"""
from io import StringIO

import pandas as pd

from backend.dashboard import _growth_override

CSV = (
    "plan,month,mrr,customers,region\n"
    "Basic,2026-01,1200,400,North\n"
    "Pro,2026-01,3500,220,North\n"
    "Enterprise,2026-01,8000,60,East\n"
    "Basic,2026-06,1600,500,North\n"
    "Pro,2026-06,5000,300,South\n"
    "Enterprise,2026-06,15000,110,West\n"
)


def _df():
    return pd.read_csv(StringIO(CSV))


def test_growth_override_ranks_fastest_grower():
    # Enterprise: 8000 -> 15000 = +7000 (+87.5%), the largest gain.
    res = _growth_override("which plan grew fastest", {"group_by": ["plan"]},
                           _df(), {"mrr": "stock", "customers": "stock"}, "month")
    assert res is not None, "growth override must fire on a growth question with a group + time axis"
    assert res["growth"]["group"] == "plan"
    assert res["growth"]["measure"] == "mrr"      # the headline/stock measure, unnamed in the question
    top = res["rows"][0]
    assert top["plan"] == "Enterprise"
    assert round(top["start"]) == 8000 and round(top["end"]) == 15000
    assert round(top["change"]) == 7000
    assert round(top["change_pct"], 1) == 87.5


def test_growth_override_respects_named_measure_and_ranks_by_rate():
    # "in customers" -> rank by customers growth RATE. Basic 400->500=+25%,
    # Pro 220->300=+36%, Enterprise 60->110=+83% — Enterprise is fastest by rate.
    res = _growth_override("which plan grew fastest in customers", {"group_by": ["plan"]},
                           _df(), {"mrr": "stock", "customers": "stock"}, "month")
    assert res is not None and res["growth"]["measure"] == "customers"
    assert res["rows"][0]["plan"] == "Enterprise"
    assert round(res["rows"][0]["change_pct"]) == 83


def test_growth_override_none_without_growth_words():
    assert _growth_override("total mrr", {"group_by": ["plan"]}, _df(),
                            {"mrr": "stock"}, "month") is None


def test_growth_override_none_without_time_axis():
    assert _growth_override("which plan grew fastest", {"group_by": ["plan"]},
                            _df(), {"mrr": "stock"}, None) is None


def test_growth_override_none_without_group():
    # No group_by and no group named in the question -> can't rank; return None.
    assert _growth_override("did it grow", {}, _df(), {"mrr": "stock"}, "month") is None
