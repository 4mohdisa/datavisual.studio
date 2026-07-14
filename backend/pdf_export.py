"""Report/dashboard export: WeasyPrint → headless Chrome → HTML fallback."""

import asyncio
import os

# WeasyPrint depends on native libraries (Pango, Cairo). If those are missing the
# import itself raises (often OSError). Capture that here so importing this module
# never crashes the app — export_report falls back to HTML instead.
try:
    from weasyprint import HTML
except Exception:  # ImportError or OSError when native deps are absent
    HTML = None


def _chrome_path() -> str | None:
    """Locate a Chrome/Chromium binary — the same one kaleido uses for chart
    PNGs, so PDF export needs no extra dependency."""
    import shutil
    env_path = os.getenv("BROWSER_PATH")  # explicit override (Docker image sets this)
    if env_path and os.path.exists(env_path):
        return env_path
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    for p in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ):
        if os.path.exists(p):
            return p
    return None


def _html_to_pdf_chrome(html: str, pdf_path: str) -> bool:
    """Render HTML to PDF with headless Chrome. Returns False on any failure
    so the caller can fall back to shipping the HTML file."""
    import subprocess
    import tempfile

    chrome = _chrome_path()
    if not chrome:
        return False
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(html)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-pdf-header-footer", "--print-to-pdf-no-header",
             f"--print-to-pdf={pdf_path}", f"file://{tmp_path}"],
            capture_output=True, timeout=90,
        )
        return result.returncode == 0 and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0
    except Exception as e:
        print(f"[export] chrome pdf failed: {e}", flush=True)
        return False
    finally:
        os.unlink(tmp_path)


def pdf_available() -> bool:
    """True when either PDF path works: WeasyPrint (native libs) or headless
    Chrome (already present for chart rendering)."""
    return HTML is not None or _chrome_path() is not None


async def export_report(conversation: dict, base_path_no_ext: str, fmt: str | None = None,
                        mode: str | None = None) -> dict:
    """Produce a downloadable report file from ONE structured light layout.

    `mode="dashboard"` renders the visual dashboard export; otherwise the full
    report. `fmt` is 'pdf', 'html', or None (= pdf when any renderer exists).
    PDF chain: WeasyPrint → headless Chrome → HTML fallback.
    Returns {path, media_type, extension, kind}.
    """
    builder = _build_dashboard_html if mode == "dashboard" else _build_html_export
    html = builder(conversation)

    if fmt != "html":
        pdf_path = base_path_no_ext + ".pdf"
        if HTML is not None:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: HTML(string=html).write_pdf(pdf_path)
                )
                return {"path": pdf_path, "media_type": "application/pdf", "extension": "pdf", "kind": "pdf"}
            except Exception as e:
                print(f"[export] WeasyPrint failed, trying Chrome: {e}", flush=True)
        ok = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _html_to_pdf_chrome(html, pdf_path)
        )
        if ok:
            return {"path": pdf_path, "media_type": "application/pdf", "extension": "pdf", "kind": "pdf"}
        if fmt == "pdf":
            print("[export] no PDF renderer succeeded — shipping HTML instead", flush=True)

    html_path = base_path_no_ext + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return {"path": html_path, "media_type": "text/html", "extension": "html", "kind": "html"}


def _build_dashboard_html(conversation: dict) -> str:
    """Structured dashboard export: header, metrics grid, charts as embedded
    PNGs in a two-column grid, insight cards with rendered markdown + sources,
    and a data sample. Prefers the live widget spec; legacy records fall back
    to the pipeline charts."""
    from datetime import datetime as _dt

    pipeline = conversation.get("pipeline", {})
    summary = pipeline.get("data_summary", {}) or {}
    spec = conversation.get("dashboard") or {}
    widgets = spec.get("widgets", [])
    title = spec.get("title") or conversation.get("title", "Dashboard")

    metric_cards = [(w.get("label", ""), w.get("value"), w.get("sub")) for w in widgets if w.get("kind") == "metric"]
    charts = [w for w in widgets if w.get("kind") == "chart" and w.get("plotly_json")]
    insights = [w for w in widgets if w.get("kind") == "insight"]
    if not charts:
        charts = pipeline.get("charts", []) or pipeline.get("report", {}).get("sections", {}).get("visualisations", {}).get("charts", [])

    meta_bits = []
    if summary.get("row_count") is not None:
        meta_bits.append(f"{summary['row_count']:,} rows · {summary.get('column_count', '?')} columns")
    meta_bits.append("Exported " + _dt.utcnow().strftime("%B %d, %Y at %H:%M UTC"))

    parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<title>{_esc(title)}</title><style>{_EXPORT_CSS}"
        ".metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:20px 0}"
        ".metric{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px}"
        ".metric .l{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.04em}"
        ".metric .v{font-size:24px;font-weight:700;color:#0f172a;margin-top:6px}"
        ".metric .s{font-size:11px;color:#94a3b8;margin-top:2px}"
        ".grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}"
        ".card{background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;padding:16px}"
        ".card h3{margin:0 0 10px 0}"
        ".card img{max-width:100%;border-radius:6px}"
        ".insight{background:#f8fafc;border:1px solid #dbeafe;border-radius:10px;padding:18px;margin-bottom:14px}"
        ".insight h3{margin:0 0 10px 0;color:#1e40af}"
        ".insight .body{font-size:13px;color:#334155}"
        ".insight .body p{margin:0 0 10px 0}"
        ".insight .body ul,.insight .body ol{padding-left:20px;margin:0 0 10px 0}"
        ".footer{margin-top:32px;padding-top:14px;border-top:1px solid #e2e8f0;color:#94a3b8;font-size:12px}"
        "@media print{.grid2{grid-template-columns:1fr 1fr}}"
        "</style></head><body>"
        f"<h1>{_esc(title)}</h1>"
        f"<p class='muted'>{_esc(' · '.join(meta_bits))}</p>"
    ]

    if metric_cards:
        parts.append('<div class="metrics">')
        for label, val, sub in metric_cards:
            vs = f"{val:,}" if isinstance(val, (int, float)) else _esc(str(val))
            sub_html = f'<div class="s">{_esc(str(sub))}</div>' if sub else ""
            parts.append(f'<div class="metric"><div class="l">{_esc(label)}</div><div class="v">{vs}</div>{sub_html}</div>')
        parts.append("</div>")

    if charts:
        parts.append('<div class="section"><h2>Charts</h2>')
        rendered = []
        can_render = _kaleido_available()
        for c in charts:
            ttl = _esc(c.get("title", "")) if isinstance(c, dict) else ""
            png = _chart_png_html(c) if can_render else ""
            title_html = f"<h3>{ttl}</h3>" if ttl else ""
            body = png or '<p class="muted">Chart could not be rendered server-side — view it in the interactive dashboard.</p>'
            rendered.append(f'<div class="card">{title_html}{body}</div>')
        parts.append(f'<div class="grid2">{"".join(rendered)}</div>')
        parts.append("</div>")

    # Text notes (Phase 1d — "some components" is not an export).
    text_widgets = [w for w in widgets if w.get("kind") == "text"]
    if text_widgets:
        parts.append('<div class="section"><h2>Notes</h2>')
        for t in text_widgets:
            parts.append('<div class="insight">')
            if t.get("title"):
                parts.append(f"<h3>{_esc(t['title'])}</h3>")
            parts.append(f'<div class="body">{_md(t.get("text", ""))}</div></div>')
        parts.append("</div>")

    if insights:
        parts.append('<div class="section"><h2>Insights</h2>')
        for ins in insights:
            parts.append('<div class="insight">')
            parts.append(f"<h3>{_esc(ins.get('title', 'Insight'))}</h3>")
            parts.append(f'<div class="body">{_md(ins.get("text", ""))}</div>')
            srcs = (ins.get("sources") or [])[:8]
            if srcs:
                parts.append("<div>")
                for sx in srcs:
                    url = _esc(sx.get("url", ""))
                    parts.append(f'<div class="source-item">• <a href="{url}">{_esc(sx.get("title", url))}</a></div>')
                parts.append("</div>")
            parts.append("</div>")
        parts.append("</div>")

    # Data sample table.
    file_info = conversation.get("file") or {}
    path = file_info.get("path")
    if path and os.path.exists(path):
        try:
            from .data_analysis import _load
            df = _load(path).head(50)
            parts.append('<div class="section"><h2>Data sample (first 50 rows)</h2>')
            parts.append(_html_table_from_rows(df.to_dict(orient="records")))
            parts.append("</div>")
        except Exception:
            pass

    parts.append('<div class="footer">Generated by datavisual.studio</div>')
    parts.append("</body></html>")
    return "".join(parts)



# An export is a document, not a screenshot of the dark app (Night 3, Phase 1b).
# LIGHT + print-designed. `print-color-adjust: exact` is load-bearing: without it
# Chrome's --print-to-pdf and WeasyPrint drop every background colour, which is
# what turned the old dark export into a near-blank white page.
_EXPORT_CSS = """
  @page { size: A4; margin: 12mm; }
  @media print {
    .section, .metric, .card, .insight { page-break-inside: avoid; }
    h2 { page-break-after: avoid; }
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { background: #ffffff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
         color: #1f2937; line-height: 1.6; padding: 40px; text-align: left; font-size: 14px; }
  h1 { color: #0f172a; font-size: 26px; margin-bottom: 6px; }
  .section { margin-bottom: 32px; }
  .section > * + * { margin-top: 16px; }
  h2 { color: #0f172a; font-size: 18px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; }
  h3 { color: #1e293b; font-size: 15px; }
  p, li { color: #334155; }
  ul { padding-left: 20px; }
  a { color: #1d4ed8; text-decoration: none; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; border: 1px solid #e2e8f0; }
  th { background: #f1f5f9; color: #0f172a; text-align: left; padding: 8px 10px; border: 1px solid #e2e8f0; }
  td { padding: 8px 10px; border: 1px solid #eef2f6; color: #334155; vertical-align: top; }
  tbody tr:nth-child(even) { background: #f8fafc; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }
  .high { background: #dcfce7; color: #15803d; }
  .medium { background: #fef9c3; color: #a16207; }
  .low { background: #fee2e2; color: #b91c1c; }
  .search-label { font-weight: 600; color: #475569; text-transform: uppercase;
                  font-size: 12px; letter-spacing: 0.05em; margin-bottom: 6px; }
  .conf-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
  .dot-high { background: #22c55e; } .dot-medium { background: #eab308; } .dot-low { background: #ef4444; }
  .prob { text-align: center; }
  .source-item { font-size: 13px; }
  .muted { color: #64748b; font-style: italic; }
"""


def _kaleido_available() -> bool:
    """True when static PNG export of Plotly charts is possible. kaleido 1.3
    drives the SAME Chrome as the PDF step, so require both — otherwise the guard
    passes but `to_image` throws and charts silently vanish."""
    try:
        import kaleido  # noqa: F401
    except Exception:
        return False
    return _chrome_path() is not None


def _chart_png_html(chart: dict) -> str:
    """Render one prediction chart as an embedded PNG (requires kaleido). Returns
    '' on any failure so the caller can fall back to a single note."""
    spec = chart.get("plotly_json")
    if not spec:
        return ""
    title = _esc(chart.get("title", "Chart"))
    try:
        import json as _json
        import base64
        import plotly.io as pio
        fig = pio.from_json(_json.dumps(spec))
        # Print-designed: recolour the (dark-themed) figure to light so charts
        # match the light export document instead of sitting in black boxes.
        fig.update_layout(template="plotly_white", paper_bgcolor="white",
                          plot_bgcolor="white", font_color="#1f2937")
        png = pio.to_image(fig, format="png", width=900, height=int(chart.get("height") or 400))
        b64 = base64.b64encode(png).decode()
        return (
            f'<div style="margin:16px 0"><div style="font-weight:600;margin-bottom:6px">{title}</div>'
            f'<img src="data:image/png;base64,{b64}" style="max-width:100%"/></div>'
        )
    except Exception:
        return ""


def _explainer_box_html(meta: dict, dark: bool = False) -> str:
    """The 'How this prediction was calculated' explainer box (Part 5)."""
    sims = f"{int(meta.get('n_simulations', 10000)):,}"
    n_sources = meta.get("n_sources", 0)
    n_council = meta.get("n_council", 0)
    today = _esc(meta.get("today_date", ""))
    if dark:
        box = "background:#f8fafc;border-left:3px solid #2563eb;padding:12px 16px;margin:12px 0;font-size:13px;color:#334155"
        head = "color:#0f172a"
    else:
        box = "background:#f5f5f5;border-left:3px solid #333;padding:12px 16px;margin:12px 0;font-size:12px;color:#333"
        head = "color:#111"
    src_line = f" searched on {today}" if today else ""
    return (
        f'<div style="{box}">'
        f'<div style="font-weight:bold;margin-bottom:6px;{head}">How this prediction was calculated</div>'
        f"<p><strong>Dataset (40%):</strong> Monte Carlo simulation of {sims} tournament runs using "
        f"ELO ratings from your uploaded data.</p>"
        f'<p style="margin-top:6px"><strong>Internet (35%):</strong> Probability estimates extracted '
        f"from {n_sources} web sources{src_line}.</p>"
        f'<p style="margin-top:6px"><strong>Council (25%):</strong> Agreement extracted from '
        f"{n_council} AI model responses, weighted by peer review ranking.</p>"
        f"</div>"
    )


def _pred_table_light_html(predictions: list) -> str:
    """Light-theme prediction table (Entity | Probability | Confidence badge)."""
    if not predictions:
        return ""
    rows = ["<table><tr><th>Team / Entity</th><th>Probability</th><th>Confidence</th></tr>"]
    for p in predictions:
        conf = str(p.get("confidence", "medium")).lower()
        if conf not in ("high", "medium", "low"):
            conf = "medium"
        prob = f"{p.get('low_pct', '?')}–{p.get('high_pct', '?')}%"
        rows.append(
            f"<tr><td>{_esc(str(p.get('entity', '')))}</td><td>{_esc(prob)}</td>"
            f'<td><span class="badge {conf}">{conf.upper()}</span></td></tr>'
        )
    rows.append("</table>")
    return "".join(rows)


def _prediction_section_html(conversation: dict, dark: bool = False) -> str:
    """Assemble the full prediction section (Part 5): heading, explainer box,
    prediction table, the five charts as PNGs (or a single note when kaleido is
    absent). The chairman's synthesis text is rendered by its own section after."""
    pipeline = conversation.get("pipeline", {})
    report = pipeline.get("report", {})
    sections = report.get("sections", {})
    cs = sections.get("chairman_synthesis", {})

    predictions = cs.get("prediction_table") or report.get("prediction_table") or []
    charts = (
        cs.get("prediction_charts")
        or pipeline.get("prediction_charts")
        or report.get("prediction_charts")
        or []
    )
    meta = cs.get("prediction_meta") or report.get("prediction_meta") or {}
    if not predictions and not charts:
        return ""

    parts = ['<div class="section">', '<h2 style="font-size:16pt">Prediction</h2>']
    parts.append(_explainer_box_html(meta, dark=dark))
    if predictions:
        parts.append(_pred_table_light_html(predictions))
    if charts:
        rendered = []
        if _kaleido_available():
            rendered = [h for h in (_chart_png_html(c) for c in charts) if h]
        if rendered:
            parts.extend(rendered)
        else:
            note_color = "#888" if dark else "#666"
            parts.append(f'<p style="color:{note_color};font-style:italic">Charts available in the web report.</p>')
    parts.append("</div>")
    return "".join(parts)


def _html_table_from_rows(rows: list) -> str:
    if not rows:
        return ""
    headers = list(rows[0].keys())
    out = ["<table><tr>"]
    out += [f"<th>{_esc(str(h))}</th>" for h in headers]
    out.append("</tr>")
    for r in rows:
        out.append("<tr>" + "".join(f"<td>{_esc(str(r.get(h, '–')))}</td>" for h in headers) + "</tr>")
    out.append("</table>")
    return "".join(out)


def _build_html_export(conversation: dict) -> str:
    """Self-contained dark-theme HTML report (fallback when PDF is unavailable).

    Sections in order: Dataset Overview, Internet Research (3 labelled searches),
    Prediction Table, Council Opinions (per model), Chairman Synthesis, Sources.
    Missing/empty sections are skipped.
    """
    title = conversation.get("title", "Report")
    pipeline = conversation.get("pipeline", {})
    report = pipeline.get("report", {})
    sections = report.get("sections", {})
    mode = conversation.get("mode", "text")

    parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<title>{_esc(title)}</title>"
        f"<style>{_EXPORT_CSS}</style></head><body>"
        f"<h1>{_esc(title)}</h1>"
    ]

    # 1 — Dataset Overview
    if mode == "data" and "dataset_overview" in sections:
        ds = sections["dataset_overview"].get("data_summary", {})
        parts.append('<div class="section"><h2>Dataset Overview</h2>')
        parts.append(
            f"<p>Rows: <strong>{ds.get('row_count', '–')}</strong> &nbsp;|&nbsp; "
            f"Columns: <strong>{ds.get('column_count', '–')}</strong></p>"
        )
        cols = ds.get("columns", [])
        if cols:
            parts.append(_html_table_from_rows([
                {"Column": c["name"], "Type": c["type"], "Nulls": c["null_count"]} for c in cols
            ]))
        notes = sections["dataset_overview"].get("quality_notes", [])
        if notes:
            parts.append("<h3>Quality notes</h3><ul>")
            parts += [f"<li>{_esc(n)}</li>" for n in notes]
            parts.append("</ul>")
        parts.append("</div>")

    # 2 — Internet Research (three labelled searches)
    if "internet_research" in sections:
        ir = sections["internet_research"]
        available = ir.get("available", bool(ir.get("findings")))
        parts.append('<div class="section"><h2>Internet Research</h2>')
        if available:
            searches = ir.get("searches", [])
            if searches:
                for s in searches:
                    content = (s.get("content") or "").strip()
                    if not content:
                        continue
                    label = _SEARCH_LABELS.get(s.get("purpose"), "Research")
                    parts.append(f'<div><div class="search-label">{_esc(label)}</div>{_md(content)}</div>')
            elif ir.get("findings"):
                parts.append(_md(ir["findings"]))
        else:
            parts.append('<p class="muted">Internet research was unavailable for this query.</p>')
        parts.append("</div>")

    # 3 — Prediction (heading, explainer box, table, charts/note)
    parts.append(_prediction_section_html(conversation, dark=True))

    # 4 — Council Opinions (one sub-section per model)
    if "council_opinions" in sections:
        co = sections["council_opinions"]
        parts.append('<div class="section"><h2>Council Opinions</h2>')
        if co.get("agreement"):
            parts.append(f'<p class="muted">{_esc(co["agreement"])}</p>')
        for model, content in co.get("responses", {}).items():
            text = content.get("stage1", "") if isinstance(content, dict) else str(content)
            parts.append(f"<div><h3>{_esc(model)}</h3><p>{_esc(text)}</p></div>")
        parts.append("</div>")

    # 5 — Chairman Synthesis
    if "chairman_synthesis" in sections:
        cs = sections["chairman_synthesis"]
        parts.append('<div class="section"><h2>Chairman Synthesis</h2>')
        conf = cs.get("confidence", "")
        if conf:
            parts.append(f'<p>Confidence: <span class="badge {conf}">{conf.upper()}</span></p>')
        if cs.get("content"):
            parts.append(_md(cs["content"]))
        if cs.get("caveats"):
            parts.append("<h3>Caveats</h3><ul>")
            parts += [f"<li>{_esc(c)}</li>" for c in cs["caveats"]]
            parts.append("</ul>")
        parts.append("</div>")

    # 6 — Sources (all, deduplicated)
    ir = sections.get("internet_research", {})
    all_sources = ir.get("sources", [])
    if all_sources:
        parts.append('<div class="section"><h2>Sources</h2>')
        for s in all_sources:
            url = _esc(s.get("url", ""))
            parts.append(f'<div class="source-item">• <a href="{url}">{_esc(s.get("title", url))}</a></div>')
        parts.append("</div>")

    parts.append("</body></html>")
    return "".join(parts)


_SEARCH_LABELS = {
    "existing_research": "Existing research and expert analyses",
    "live_data": "Current live data",
    "consensus": "Probability estimates and consensus",
}


def _md(text: str) -> str:
    """Render markdown to HTML for exports (bold, lists, tables, links).
    Falls back to escaped text with <br> if the markdown lib is unavailable."""
    try:
        import markdown as _markdown
        return _markdown.markdown(text or "", extensions=["tables", "nl2br"])
    except Exception:
        return "<p>" + _esc(text or "").replace("\n", "<br>") + "</p>"


def _esc(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
