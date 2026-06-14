"""PDF export using WeasyPrint."""

import asyncio

# WeasyPrint depends on native libraries (Pango, Cairo). If those are missing the
# import itself raises (often OSError). Capture that here so importing this module
# never crashes the app — we surface a clear, actionable error only when the user
# actually tries to export.
_DEP_INSTALL_HINT = (
    "PDF export requires the WeasyPrint system libraries (Pango, Cairo). "
    "Install them with:\n"
    "  macOS:  brew install pango cairo\n"
    "  Linux:  apt-get install libpango-1.0-0 libcairo2"
)

try:
    from weasyprint import HTML
    _WEASYPRINT_IMPORT_ERROR = None
except Exception as e:  # ImportError or OSError when native deps are absent
    HTML = None
    _WEASYPRINT_IMPORT_ERROR = e


class PDFExportError(Exception):
    """Raised when a PDF cannot be generated, with a user-facing message."""


async def generate_pdf(conversation: dict, output_path: str):
    """Generate a PDF report from a stored conversation and write to output_path.

    Renders whatever sections are available; sections with errors or empty data
    are simply skipped (see _build_html). Raises PDFExportError with an
    actionable message if WeasyPrint or its native deps are unavailable.
    """
    if HTML is None:
        raise PDFExportError(f"{_DEP_INSTALL_HINT}\n\n(Underlying error: {_WEASYPRINT_IMPORT_ERROR})")

    try:
        html = _build_html(conversation)
    except Exception as e:
        raise PDFExportError(f"Failed to assemble report HTML: {e}")

    try:
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: HTML(string=html).write_pdf(output_path)
        )
    except Exception as e:
        # WeasyPrint can also fail at render time if native libs are partially
        # installed — surface the same install hint.
        raise PDFExportError(f"PDF rendering failed. {_DEP_INSTALL_HINT}\n\n(Underlying error: {e})")


def pdf_available() -> bool:
    """True when WeasyPrint (and its native deps) imported successfully."""
    return HTML is not None


async def export_report(conversation: dict, base_path_no_ext: str) -> dict:
    """Produce a downloadable report file.

    Option A (preferred): render a PDF with WeasyPrint. Option B (automatic
    fallback): if WeasyPrint is unavailable or rendering fails, write a
    self-contained dark-theme HTML file instead — the user still gets their
    report rather than an error. Returns {path, media_type, extension, kind}.
    """
    if HTML is not None:
        pdf_path = base_path_no_ext + ".pdf"
        try:
            html = _build_html(conversation)
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: HTML(string=html).write_pdf(pdf_path)
            )
            return {"path": pdf_path, "media_type": "application/pdf", "extension": "pdf", "kind": "pdf"}
        except Exception as e:
            print(f"[export] PDF generation failed, falling back to HTML: {e}", flush=True)

    # Option B — self-contained HTML fallback
    html_path = base_path_no_ext + ".html"
    html = _build_html_export(conversation)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return {"path": html_path, "media_type": "text/html", "extension": "html", "kind": "html"}


def _build_html(conversation: dict) -> str:
    title = conversation.get("title", "Report")
    pipeline = conversation.get("pipeline", {})
    report = pipeline.get("report", {})
    sections = report.get("sections", {})
    mode = conversation.get("mode", "text")

    parts = [f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{_esc(title)}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 40px; color: #111; }}
  h1 {{ color: #1a1a2e; }}
  h2 {{ color: #16213e; border-bottom: 2px solid #4a90e2; padding-bottom: 4px; }}
  h3 {{ color: #333; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  th {{ background: #4a90e2; color: white; padding: 8px; text-align: left; }}
  td {{ padding: 8px; border: 1px solid #ddd; }}
  tr:nth-child(even) {{ background: #f5f5f5; }}
  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
  .high {{ background: #d4edda; color: #155724; }}
  .medium {{ background: #fff3cd; color: #856404; }}
  .low {{ background: #f8d7da; color: #721c24; }}
  .section {{ margin-bottom: 32px; }}
  .source-item {{ margin: 4px 0; font-size: 13px; }}
</style>
</head>
<body>
<h1>{_esc(title)}</h1>
"""]

    # Dataset overview
    if mode == "data" and "dataset_overview" in sections:
        ds = sections["dataset_overview"].get("data_summary", {})
        parts.append('<div class="section"><h2>Dataset Overview</h2>')
        parts.append(f"<p>Rows: <strong>{ds.get('row_count', '–')}</strong> | Columns: <strong>{ds.get('column_count', '–')}</strong></p>")
        cols = ds.get("columns", [])
        if cols:
            parts.append('<table><tr><th>Column</th><th>Type</th><th>Nulls</th></tr>')
            for c in cols:
                parts.append(f"<tr><td>{_esc(c['name'])}</td><td>{c['type']}</td><td>{c['null_count']}</td></tr>")
            parts.append('</table>')
        notes = sections["dataset_overview"].get("quality_notes", [])
        if notes:
            parts.append('<h3>Quality Notes</h3><ul>')
            for n in notes:
                parts.append(f"<li>{_esc(n)}</li>")
            parts.append('</ul>')
        parts.append('</div>')

    # Internet research
    if "internet_research" in sections:
        ir = sections["internet_research"]
        parts.append('<div class="section"><h2>Internet Research</h2>')
        findings = ir.get("findings", "")
        # ir.get("available") is False when research failed; older reports without
        # the flag fall back to checking findings content.
        available = ir.get("available", bool(findings))
        if available and findings:
            parts.append(f"<p>{_esc(findings)}</p>")
            sources = ir.get("sources", [])
            if sources:
                parts.append('<h3>Sources</h3>')
                for s in sources:
                    url = _esc(s.get("url", ""))
                    label = _esc(s.get("title", url))
                    parts.append(f'<div class="source-item">• <a href="{url}">{label}</a></div>')
        else:
            parts.append('<p><em>Internet research was unavailable for this query.</em></p>')
        parts.append('</div>')

    # Council opinions
    if "council_opinions" in sections:
        co = sections["council_opinions"]
        parts.append('<div class="section"><h2>Council Opinions</h2>')
        agreement = co.get("agreement", "")
        if agreement:
            parts.append(f"<p><em>{_esc(agreement)}</em></p>")
        responses = co.get("responses", {})
        for model, content in responses.items():
            parts.append(f"<h3>{_esc(model)}</h3>")
            text = content.get("stage1", "") if isinstance(content, dict) else str(content)
            parts.append(f"<p>{_esc(text[:1500])}{'…' if len(text) > 1500 else ''}</p>")
        parts.append('</div>')

    # Prediction (heading, explainer box, table, charts) — before the synthesis text.
    parts.append(_prediction_section_html(conversation, dark=False))

    # Chairman synthesis
    if "chairman_synthesis" in sections:
        cs = sections["chairman_synthesis"]
        parts.append('<div class="section"><h2>Chairman Synthesis</h2>')
        confidence = cs.get("confidence", "")
        if confidence:
            parts.append(f'<p>Confidence: <span class="badge {confidence}">{confidence.upper()}</span></p>')
        content = cs.get("content", "")
        if content:
            parts.append(f"<p>{_esc(content)}</p>")
        caveats = cs.get("caveats", [])
        if caveats:
            parts.append('<h3>Caveats</h3><ul>')
            for c in caveats:
                parts.append(f"<li>{_esc(c)}</li>")
            parts.append('</ul>')
        parts.append('</div>')

    parts.append('</body></html>')
    return "".join(parts)


_DARK_EXPORT_CSS = """
  /* --- reset --- */
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { background: #0f0f0f; }
  /* --- base --- */
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
         color: #e8e8e8; line-height: 1.6; padding: 40px; text-align: left; font-size: 14px; }
  h1 { color: #fff; font-size: 26px; margin-bottom: 24px; }
  .section { margin-bottom: 32px; }
  .section > * + * { margin-top: 16px; }
  h2 { color: #fff; font-size: 18px; border-bottom: 1px solid #333; padding-bottom: 8px; }
  h3 { color: #cfcfcf; font-size: 15px; }
  p, li { color: #cfcfcf; }
  ul { padding-left: 20px; }
  a { color: #6aa8ff; text-decoration: none; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; border: 1px solid #333; }
  th { background: #1c2a44; color: #fff; text-align: left; padding: 8px 10px; border: 1px solid #333; }
  td { padding: 8px 10px; border: 1px solid #2a2a2a; color: #d6d6d6; vertical-align: top; }
  tbody tr:nth-child(even) { background: #161616; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }
  .high { background: #14361f; color: #5ad08a; }
  .medium { background: #3a3413; color: #e3c34d; }
  .low { background: #3a1717; color: #e36a6a; }
  .search-label { font-weight: 600; color: #9bb0cc; text-transform: uppercase;
                  font-size: 12px; letter-spacing: 0.05em; margin-bottom: 6px; }
  .conf-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
  .dot-high { background: #5ad08a; } .dot-medium { background: #e3c34d; } .dot-low { background: #e36a6a; }
  .prob { text-align: center; }
  .source-item { font-size: 13px; }
  .muted { color: #888; font-style: italic; }
"""


def _render_chart_html(chart: dict) -> str:
    """Render a chart as a static PNG (if kaleido is available) or a placeholder."""
    title = _esc(chart.get("title", "Chart"))
    spec = chart.get("plotly_json")
    if spec:
        try:
            import json as _json
            import base64
            import plotly.io as pio
            fig = pio.from_json(_json.dumps(spec))
            png = pio.to_image(fig, format="png", width=900, height=450)  # requires kaleido
            b64 = base64.b64encode(png).decode()
            return (
                f'<div class="chart"><div class="chart-title">{title}</div>'
                f'<img src="data:image/png;base64,{b64}" style="max-width:100%"/></div>'
            )
        except Exception:
            pass
    return (
        f'<div class="chart"><div class="chart-title">{title}</div>'
        f'<div class="chart-ph">Chart data available — interactive chart not rendered in static export.</div></div>'
    )


def _kaleido_available() -> bool:
    """True when static PNG export of Plotly charts is possible."""
    try:
        import kaleido  # noqa: F401
        return True
    except Exception:
        return False


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
        box = "background:#161616;border-left:3px solid #6aa8ff;padding:12px 16px;margin:12px 0;font-size:13px;color:#cfcfcf"
        head = "color:#fff"
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


def _prediction_table_html(predictions: list) -> str:
    """Render the prediction table: Entity | Probability | Confidence (coloured dot)."""
    if not predictions:
        return ""
    rows = ["<table><tr><th>Team / Entity</th><th class='prob'>Probability</th><th>Confidence</th></tr>"]
    for p in predictions:
        conf = str(p.get("confidence", "medium")).lower()
        if conf not in ("high", "medium", "low"):
            conf = "medium"
        prob = f"{p.get('low_pct', '?')}–{p.get('high_pct', '?')}%"
        rows.append(
            f"<tr><td>{_esc(str(p.get('entity', '')))}</td>"
            f"<td class='prob'>{_esc(prob)}</td>"
            f"<td><span class='conf-dot dot-{conf}'></span>{conf.capitalize()}</td></tr>"
        )
    rows.append("</table>")
    return "".join(rows)


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
        f"<style>{_DARK_EXPORT_CSS}</style></head><body>"
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
                    parts.append(f'<div><div class="search-label">{_esc(label)}</div><p>{_esc(content)}</p></div>')
            elif ir.get("findings"):
                parts.append(f"<p>{_esc(ir['findings'])}</p>")
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
            parts.append(f"<p>{_esc(cs['content'])}</p>")
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


def _esc(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
