"""Dashboard engine: deterministic chart builder, templates, and the in-place
ops protocol (the LLM only emits these ops — the engine is what actually runs)."""

import asyncio

import pytest

from backend import dashboard as D


# --- chart builder ------------------------------------------------------------

@pytest.mark.parametrize("ctype,spec", [
    ("bar", {"chart_type": "bar", "x": "region", "y": "revenue", "agg": "sum"}),
    ("line", {"chart_type": "line", "x": "month", "y": "revenue", "group_by": "region"}),
    ("scatter", {"chart_type": "scatter", "x": "revenue", "y": "units"}),
    ("histogram", {"chart_type": "histogram", "x": "revenue"}),
    ("pie", {"chart_type": "pie", "x": "region", "y": "revenue"}),
    ("box", {"chart_type": "box", "y": "revenue"}),
    ("area", {"chart_type": "area", "x": "month", "y": "revenue"}),
    ("treemap", {"chart_type": "treemap", "x": "region", "y": "revenue"}),
])
def test_build_chart_each_type(sample_df, ctype, spec):
    w = D.build_chart_from_spec(sample_df, spec)
    assert w["kind"] == "chart"
    assert w["plotly_json"]["data"]  # produced at least one trace
    assert w["spec"]["chart_type"] == ctype


def test_build_chart_rejects_unknown_type(sample_df):
    with pytest.raises(ValueError):
        D.build_chart_from_spec(sample_df, {"chart_type": "spiral", "x": "region", "y": "revenue"})


def test_build_chart_rejects_missing_column(sample_df):
    with pytest.raises(ValueError):
        D.build_chart_from_spec(sample_df, {"chart_type": "bar", "x": "region", "y": "does_not_exist"})


def test_build_metric_aggregations(sample_df):
    total = D.build_metric_from_spec(sample_df, {"column": "revenue", "agg": "sum", "label": "Total"})
    assert total["kind"] == "metric"
    # 120+90+150+110+70+200 = 740
    assert "740" in total["value"].replace(",", "")


# --- templates ----------------------------------------------------------------

def _summary(sample_df):
    from backend.data_analysis import analyse_df
    return analyse_df(sample_df)["data_summary"]


@pytest.mark.parametrize("template", list(D.TEMPLATES))
def test_build_dashboard_spec_every_template(sample_df, template):
    spec = D.build_dashboard_spec(_summary(sample_df), [], title="T", df=sample_df, template=template)
    kinds = {w["kind"] for w in spec["widgets"]}
    tpl = D.TEMPLATES[template]
    assert "metric" in kinds
    charts = [w for w in spec["widgets"] if w["kind"] == "chart"]
    assert len(charts) <= tpl["max_charts"]
    assert ("table" in kinds) == tpl["table"]


def test_focus_column_leads_metrics(sample_df):
    spec = D.build_dashboard_spec(_summary(sample_df), [], title="T", df=sample_df, focus="units")
    first_metric = next(w for w in spec["widgets"] if w["kind"] == "metric")
    assert first_metric["spec"]["column"] == "units"


# --- ops protocol (apply_ops mutates the spec in place) -----------------------

def _run(dashboard, ops, df=None, summary=None):
    return asyncio.run(D.apply_ops(dashboard, ops, df=df, data_summary=summary))


def test_add_and_remove_chart(sample_df):
    dash = {"widgets": []}
    notes = _run(dash, [{"op": "add_chart", "chart_type": "bar", "x": "region", "y": "revenue"}], df=sample_df)
    assert notes == [] and len(dash["widgets"]) == 1
    wid = dash["widgets"][0]["id"]
    _run(dash, [{"op": "remove_widget", "id": wid}], df=sample_df)
    assert dash["widgets"] == []


def test_add_metric_and_update_metric(sample_df):
    dash = {"widgets": []}
    _run(dash, [{"op": "add_metric", "column": "revenue", "agg": "sum", "label": "Total"}], df=sample_df)
    m = dash["widgets"][0]
    _run(dash, [{"op": "update_metric", "id": m["id"], "agg": "mean", "label": "Avg"}], df=sample_df)
    assert dash["widgets"][0]["label"] == "Avg"


def test_move_widget_reorders_within_kind(sample_df):
    dash = {"widgets": []}
    _run(dash, [
        {"op": "add_metric", "column": "revenue", "agg": "sum", "label": "A"},
        {"op": "add_metric", "column": "units", "agg": "sum", "label": "B"},
    ], df=sample_df)
    a, b = dash["widgets"][0]["id"], dash["widgets"][1]["id"]
    _run(dash, [{"op": "move_widget", "id": b, "direction": "up"}], df=sample_df)
    assert [w["id"] for w in dash["widgets"]] == [b, a]


def test_add_table_and_comparison_are_singletons(sample_df):
    dash = {"widgets": []}
    _run(dash, [{"op": "add_table"}, {"op": "add_table"}, {"op": "add_comparison"}], df=sample_df)
    kinds = [w["kind"] for w in dash["widgets"]]
    assert kinds.count("table") == 1 and kinds.count("comparison") == 1


def test_add_and_update_text():
    dash = {"widgets": []}
    _run(dash, [{"op": "add_text", "text": "hello"}])
    wid = dash["widgets"][0]["id"]
    _run(dash, [{"op": "update_text", "id": wid, "text": "world"}])
    assert dash["widgets"][0]["text"] == "world"


def test_rename_dashboard():
    dash = {"widgets": [], "title": "Old"}
    _run(dash, [{"op": "rename_dashboard", "title": "New"}])
    assert dash["title"] == "New"


def test_bad_op_returns_note_without_crashing(sample_df):
    dash = {"widgets": []}
    notes = _run(dash, [{"op": "update_chart", "id": "nope"}], df=sample_df)
    assert notes and dash["widgets"] == []


def test_add_chart_without_dataframe_is_reported():
    dash = {"widgets": []}
    notes = _run(dash, [{"op": "add_chart", "chart_type": "bar", "x": "region", "y": "revenue"}], df=None)
    assert notes and dash["widgets"] == []


# --- Phase 2b (slice): malformed model output must DEGRADE, never 500 ---------
# The part that actually breaks is applying model output. apply_ops wraps each
# op, so a bad op becomes a note, not a crash. These lock that in.

@pytest.mark.parametrize("bad_op", [
    {"op": "totally_unknown_kind"},                                  # unknown op kind
    {"op": "add_chart", "chart_type": "bar", "x": "no_such_col", "y": "revenue"},  # missing column
    {"op": "add_chart", "chart_type": "not_a_chart", "x": "region", "y": "revenue"},  # bad type
    {"op": "add_metric", "column": "no_such_col", "agg": "sum"},     # missing column
    {"op": "add_metric", "column": "revenue", "agg": "bogus_agg"},   # bad aggregation
    {"op": "update_chart", "id": "ghost"},                           # nonexistent target
    {"op": "remove_widget"},                                         # missing id
    {"op": "add_chart"},                                             # missing required fields
    {},                                                              # empty op
])
def test_malformed_single_op_degrades_gracefully(sample_df, bad_op):
    dash = {"widgets": []}
    notes = _run(dash, [bad_op], df=sample_df)  # must not raise
    assert isinstance(notes, list)  # a note (or silent no-op), never a crash


def test_empty_and_huge_op_lists(sample_df):
    dash = {"widgets": []}
    assert _run(dash, [], df=sample_df) == []           # [] → no-op
    # A 300-op response must not blow up (loops, not recursion).
    many = [{"op": "add_metric", "column": "revenue", "agg": "sum"}] * 300
    notes = _run(dash, many, df=sample_df)
    assert isinstance(notes, list) and len(dash["widgets"]) >= 1


@pytest.mark.parametrize("junk", [[None], ["not-an-op"], [123], [None, {"op": "add_metric", "column": "revenue", "agg": "sum"}]])
def test_non_dict_ops_are_survivable(sample_df, junk):
    # A model returning null/strings/numbers inside the ops array must degrade to
    # a note, never crash — and valid ops alongside the junk still apply.
    dash = {"widgets": []}
    notes = _run(dash, junk, df=sample_df)  # must not raise
    assert isinstance(notes, list)
