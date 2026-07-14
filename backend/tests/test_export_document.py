"""Night 3, Phase 1 — export is broken. BUG 3 (blank/partial export): the PDF
came out white with only some components (Chrome strips backgrounds without
print-color-adjust; comparison/table/text widgets were never rendered).

Tested at the HTML-builder level so it's deterministic (no Chrome needed): the
export HTML must be light/print-safe and contain every widget.
"""
import pytest


def _sample_dashboard(client):
    cid = client.post("/api/sample-dashboard", json={"sample": "saas"}).json()["conversation_id"]
    widgets = client.get(f"/api/conversations/{cid}").json()["dashboard"]["widgets"]
    return cid, widgets


def test_export_html_is_light_and_print_safe(client):
    cid, _ = _sample_dashboard(client)
    r = client.get(f"/api/export/{cid}", params={"format": "html", "mode": "dashboard"})
    assert r.status_code == 200, r.text
    html = r.text
    # Print-color-adjust is the whole white-PDF fix: without it Chrome/WeasyPrint
    # drop backgrounds. A print document must declare it.
    assert "print-color-adjust" in html
    # And it must NOT be the old dark canvas (a dark PDF reads as broken on paper).
    assert "#0f0f0f" not in html


def test_export_html_contains_every_widget(client):
    cid, widgets = _sample_dashboard(client)
    html = client.get(f"/api/export/{cid}", params={"format": "html", "mode": "dashboard"}).text
    for w in widgets:
        title = w.get("title") or w.get("label")
        if title:
            assert title in html, f"export omitted widget {w.get('kind')}: {title!r}"


def test_export_html_embeds_chart_images(client):
    from backend import pdf_export
    if not pdf_export._kaleido_available():
        pytest.skip("server-side chart PNGs need kaleido + Chrome (absent on this runner)")
    cid, widgets = _sample_dashboard(client)
    if not any(w.get("kind") == "chart" for w in widgets):
        pytest.skip("no chart widgets in sample")
    html = client.get(f"/api/export/{cid}", params={"format": "html", "mode": "dashboard"}).text
    # Charts must be server-rendered PNGs, never client-side Plotly in a print
    # context — a data: image proves the chart is actually on the page.
    assert "data:image/png" in html, "charts are not embedded as PNGs"
