"""Phase 2c — pathological data corpus. Every input yields a clean analysis OR
a clear error dict — NEVER an unhandled exception, never a hang. Failures here
are real ingestion bugs; fix them at the root in data_analysis.py.

Two levels:
  A. analyse_file() on inputs pandas can parse → assert the dict contract holds.
  B. the upload→dashboard ENDPOINT on malformed files → assert never a 500.
"""
import io

import pandas as pd
import pytest

from backend.data_analysis import analyse_df, analyse_file


def _write(tmp_path, name, content):
    p = tmp_path / name
    if isinstance(content, bytes):
        p.write_bytes(content)
    else:
        p.write_text(content, encoding="utf-8")
    return str(p)


def _assert_contract(result):
    """analyse_* must return a dict that is EITHER an error OR a real analysis."""
    assert isinstance(result, dict)
    assert "error" in result or "data_summary" in result
    if "data_summary" in result:
        assert isinstance(result["data_summary"].get("columns"), list)


# --- A. shapes pandas can parse: analyse_file must never raise ---------------

_SIX_DATES = "d\n2026-01-02\n01/02/2026\n2026-01-02T10:00:00\nJan 2 2026\n2026.01.02\n02-Jan-2026\n"

CSV_CASES = {
    "header_only": "a,b,c\n",
    "one_row": "a,b\n1,2\n",
    "one_column": "only\n1\n2\n3\n",
    "all_null_column": "a,b\n1,\n2,\n3,\n",
    "duplicate_columns": "a,a,b\n1,2,3\n4,5,6\n",
    "mixed_types": "a\n1\ntwo\n3.5\nTrue\n\n7\n",
    "unicode_emoji_headers": "naïve,收入,🚀rate\n1,2,3\n4,5,6\n",
    "long_column_name": ("x" * 300) + ",y\n1,2\n3,4\n",
    "column_named_index": "index,value\n10,100\n20,200\n",
    "currency_strings": 'revenue,qty\n"$1,200.50",3\n"$980.00",8\n',
    "negatives_in_parens": "pnl\n(500)\n1200\n(75)\n",
    "scientific_notation": "v\n1e5\n2.5e-3\n3E4\n",
    "crlf_endings": "a,b\r\n1,2\r\n3,4\r\n",
    "six_date_formats": _SIX_DATES,
    "leading_trailing_space": " a , b \n 1 , 2 \n 3 , 4 \n",
    "bools_and_blanks": "flag,n\nTrue,1\nFalse,\n,3\n",
    "single_cell": "x\n1\n",
    "all_same_value": "c\n5\n5\n5\n5\n",
    "high_cardinality": "id\n" + "\n".join(str(i) for i in range(500)) + "\n",
}


@pytest.mark.parametrize("name", list(CSV_CASES))
def test_csv_shapes_hold_contract(tmp_path, name):
    path = _write(tmp_path, f"{name}.csv", CSV_CASES[name])
    _assert_contract(analyse_file(path))  # must not raise


def test_many_columns(tmp_path):
    header = ",".join(f"c{i}" for i in range(200))
    row = ",".join("1" for _ in range(200))
    _assert_contract(analyse_file(_write(tmp_path, "wide.csv", f"{header}\n{row}\n{row}\n")))


def test_many_rows_samples_not_hangs(tmp_path):
    # 50k rows must analyse (via the 10k sample) quickly, not hang.
    body = "a,b\n" + "".join(f"{i},{i*2}\n" for i in range(50_000))
    r = analyse_file(_write(tmp_path, "tall.csv", body))
    _assert_contract(r)
    assert r["data_summary"]["row_count"] == 50_000


def test_bom_utf8(tmp_path):
    content = ("﻿" + "a,b\n1,2\n3,4\n").encode("utf-8")
    _assert_contract(analyse_file(_write(tmp_path, "bom.csv", content)))


def test_analyse_df_direct_edge_frames():
    # Frames that never touch the CSV reader still must hold the contract.
    _assert_contract(analyse_df(pd.DataFrame()))                       # empty
    _assert_contract(analyse_df(pd.DataFrame({"a": [None, None]})))    # all-null
    _assert_contract(analyse_df(pd.DataFrame({"a": [1], "b": [2]})))   # one row


# --- B. malformed FILES through the endpoint: never a 500 -------------------

def _upload_status(client, name, content):
    files = {"file": (name, content if isinstance(content, bytes) else content.encode(), "text/csv")}
    return client.post("/api/upload", files=files)


ENDPOINT_CASES = {
    "empty_file": b"",
    "html_renamed_csv": b"<!doctype html><html><body><h1>not a csv</h1></body></html>",
    "zip_renamed_csv": b"PK\x03\x04\x14\x00\x00\x00\x08\x00garbagebinary\x00\xff\xfe",
    "json_object_not_array": '{"a": 1, "b": 2}',
    "deeply_nested_json": '[{"a": {"b": {"c": {"d": 1}}}}, {"a": {"b": {"c": {"d": 2}}}}]',
    "only_commas": ",,,\n,,,\n",
    "ragged_rows": "a,b,c\n1,2\n3,4,5,6,7\n",
    "nul_bytes": b"a,b\n1,2\n\x00\x00,3\n",
}


@pytest.mark.parametrize("name", list(ENDPOINT_CASES))
def test_malformed_files_never_500(client, name):
    content = ENDPOINT_CASES[name]
    ext = ".json" if "json" in name else ".csv"
    r = _upload_status(client, f"{name}{ext}", content)
    assert r.status_code != 500, f"{name}: upload 500'd — {r.text[:200]}"
    # If the upload was accepted, building a dashboard from it must not 500 either.
    if r.status_code == 200 and r.json().get("file_id"):
        d = client.post("/api/dashboard", json={"file_id": r.json()["file_id"]})
        assert d.status_code != 500, f"{name}: dashboard build 500'd — {d.text[:200]}"
