"""Dataset profiling — the deterministic read the whole pipeline builds on."""

from backend.data_analysis import analyse_df


def test_analyse_df_profiles_columns_and_stats(sample_df):
    result = analyse_df(sample_df)
    summary = result["data_summary"]
    assert summary["row_count"] == 6
    assert summary["column_count"] == 4
    by_name = {c["name"]: c for c in summary["columns"]}
    assert by_name["revenue"]["type"] == "numeric"
    assert by_name["region"]["type"] == "categorical"
    # numeric stats present for revenue
    assert "revenue" in summary["statistics"]
    rev = summary["statistics"]["revenue"]
    assert rev["min"] == 70 and rev["max"] == 200


def test_analyse_df_builds_charts(sample_df):
    result = analyse_df(sample_df)
    assert isinstance(result["charts"], list)
    # each chart carries a plotly json payload
    for c in result["charts"]:
        assert "plotly_json" in c and "type" in c


def test_analyse_df_carries_dataframe_for_rebuilds(sample_df):
    result = analyse_df(sample_df)
    assert result.get("dataframe") is not None
