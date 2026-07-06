"""Report builder — comparison tables, enriched prompt, structured report."""

from typing import Any
from datetime import datetime
from .config import DEBUG


# ---------------------------------------------------------------------------
# Enriched prompt
# ---------------------------------------------------------------------------

# Keep the council prompt small. The full data summary and internet findings are
# stored in the conversation JSON for the frontend — they do not need to live in
# the prompt in full. An over-long prompt (>~4k tokens / ~16k chars) makes models
# fail or return malformed rankings. We therefore include only the most relevant
# slice of the dataset and a truncated research summary.
_TOP_NUMERIC_COLS = 5
_MAX_QUALITY_NOTES = 3
_MAX_FINDINGS_WORDS = 500


def _select_top_numeric_columns(statistics: dict) -> list[str]:
    """Pick the most informative numeric columns.

    We don't have the raw dataframe here, only summary stats, so we approximate
    'highest variance / most relevant' using the distinct-value count as the
    primary signal (continuous, high-cardinality columns carry more information
    and binary flags like is_host fall to the bottom), with the absolute range as
    a tie-breaker. Returns up to _TOP_NUMERIC_COLS column names.
    """
    scored = []
    for col, s in statistics.items():
        mn, mx = s.get("min"), s.get("max")
        if mn is None or mx is None:
            continue
        unique = s.get("unique_count", 0) or 0
        spread = (mx - mn)
        scored.append((unique, spread, col))
    scored.sort(reverse=True)
    return [col for _, _, col in scored[:_TOP_NUMERIC_COLS]]


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " …[truncated]"


def build_enriched_prompt(
    question: str,
    data_summary: dict | None,
    internet_findings: dict | None,
    data_excerpt: str | None = None,
    dataset_baseline: list[dict] | None = None,
    event_status: str = "",
    dataset_method: str = "",
    n_simulations: int = 1000,
    confirmed_facts: str = "",
) -> str:
    parts = []

    # Confirmed facts (Fix 3b) go FIRST — the very first thing the model reads —
    # as non-negotiable ground truth it is not allowed to contradict.
    if confirmed_facts:
        parts.append(
            "=== CONFIRMED FACTS — THESE ARE NOT NEGOTIABLE ===\n"
            f"{confirmed_facts}\n\n"
            "These facts come from verified internet sources. You MUST treat them "
            "as ground truth. You are NOT allowed to contradict them. You are NOT "
            "allowed to say these events have not happened. If a source says 'USA "
            "routs Paraguay 4-1 to start 2026 FIFA World Cup', then the 2026 World "
            "Cup HAS STARTED and USA beat Paraguay 4-1.\n"
            "================================================="
        )

    if data_summary:
        notes = data_summary.get("quality_notes", [])[:_MAX_QUALITY_NOTES]
        notes_text = "\n".join(f"  - {n}" for n in notes) or "  (none)"

        if data_excerpt:
            # Inject ACTUAL rows/values so the council reasons over the uploaded
            # dataset, not from training knowledge. This is the whole point of the
            # data-upload feature.
            parts.append(
                f"DATASET CONTEXT (reason ONLY from these actual values, not prior knowledge)\n"
                f"Rows: {data_summary['row_count']} | Columns: {data_summary['column_count']}\n\n"
                f"{data_excerpt}\n\n"
                f"Data quality notes:\n{notes_text}"
            )
        else:
            # Fallback: aggregate stats only (no dataframe / excerpt available).
            statistics = data_summary.get("statistics", {})
            top_cols = _select_top_numeric_columns(statistics)
            stat_lines = [
                f"  - {col}: min={statistics[col]['min']}, max={statistics[col]['max']}, "
                f"mean={statistics[col]['mean']}, unique={statistics[col]['unique_count']}"
                for col in top_cols
            ]
            stat_text = "\n".join(stat_lines) if stat_lines else "  (none)"
            parts.append(
                f"DATASET CONTEXT\n"
                f"Rows: {data_summary['row_count']} | Columns: {data_summary['column_count']}\n"
                f"Most relevant numeric columns (by spread):\n{stat_text}\n"
                f"Data quality notes:\n{notes_text}"
            )

    # Dataset-based prediction (Fix 1) — always injected when computed, so the
    # council starts from the algorithm's numbers and never refuses to predict.
    baseline_block = _render_dataset_baseline_block(dataset_baseline, dataset_method, n_simulations)
    if baseline_block:
        parts.append(baseline_block)

    # Anomaly note (6.5) — flag entities with anomalous values for the council.
    if data_summary and data_summary.get("anomalies"):
        anoms = data_summary["anomalies"][:8]
        listed = ", ".join(f"{a['entity']} ({a['column']}={a['value']})" for a in anoms)
        parts.append(
            "ANOMALIES DETECTED — the following entities have anomalous values that "
            f"may affect predictions: {listed}"
        )

    # Event-status check (Fix 2) — placed immediately after the dataset context so
    # the council can't claim the event "hasn't started" when sources prove it has.
    if event_status:
        parts.append(f"EVENT STATUS CHECK:\n{event_status}")

    # Inject internet research as three clearly-labelled sections (one per search).
    research_block = _render_research_block(internet_findings)
    if research_block:
        parts.append(research_block)

    if parts:
        context_block = "\n\n".join(parts)
        today_date = datetime.utcnow().strftime("%B %d, %Y")
        prompt = (
            f"Today's date is {today_date}. The internet research section below contains "
            f"live data gathered today — use it to ground your analysis in the current state "
            f"of this subject and prefer it over any prior knowledge that may be out of date.\n\n"
            f"The following context has been gathered to help you answer the question:\n\n"
            f"{context_block}\n\n"
            f"Using the above context and your own knowledge, answer this question:\n{question}"
        )
    else:
        prompt = question

    prompt = prompt + _PREDICTION_INSTRUCTION

    # Step 1c — print what actually gets injected into the council prompt.
    if DEBUG:
        print(f"\n[PROMPT] First 1000 chars:\n{prompt[:1000]}", flush=True)
        print(f"[PROMPT] Total length: {len(prompt)} chars", flush=True)
        print(f"[PROMPT] Confirmed facts block present: {'CONFIRMED FACTS' in prompt}", flush=True)
        print(f"[PROMPT] Dataset baseline present: {'ALGORITHMIC PREDICTIONS' in prompt}", flush=True)

    return prompt


def _render_dataset_baseline_block(
    dataset_baseline: list[dict] | None,
    dataset_method: str,
    n_simulations: int,
) -> str:
    """Render the always-on dataset prediction block injected into the council
    prompt (Fix 1). Returns '' when there is no baseline (e.g. text mode)."""
    if not dataset_baseline:
        return ""

    rows = "\n".join(f"  {p['entity']}: {p['low_pct']}-{p['high_pct']}%" for p in dataset_baseline)

    # Only the ELO path actually runs a Monte-Carlo tournament; the softmax
    # fallback gets accurate wording instead of claiming a simulation it didn't run.
    if dataset_method.startswith("elo"):
        method_line = (
            "The following probabilities have been computed deterministically from "
            f"the uploaded dataset using Monte Carlo simulation ({n_simulations} runs)."
        )
    else:
        method_line = (
            "The following probabilities have been computed deterministically from "
            "the uploaded dataset."
        )

    return (
        "=== ALGORITHMIC PREDICTIONS — DO NOT MODIFY ===\n"
        f"{method_line}\n\n"
        f"{rows}\n\n"
        "YOU MUST INCLUDE THESE EXACT NUMBERS in your response in a clearly "
        "formatted table.\n"
        "If internet data shows some teams are eliminated, adjust your narrative "
        "accordingly but these numbers are your baseline.\n"
        "DO NOT say you cannot provide estimates.\n"
        "DO NOT say you need more data.\n"
        "THESE NUMBERS ARE ALREADY COMPUTED FOR YOU. You just need to explain them.\n"
        "================================================="
    )


# Narrow-range instruction appended to every council prompt (Part 4c).
_PREDICTION_INSTRUCTION = (
    "\n\nWhen giving probability estimates, always express them as a percentage range "
    "with a maximum spread of 3 percentage points (e.g. 18-21%). Never give a range "
    "wider than 3 points. Never say 'roughly' or 'approximately' — give a specific "
    "range. Every prediction must have a number."
)

_RESEARCH_LABELS = {
    "existing_research": "EXISTING RESEARCH AND EXPERT ANALYSES",
    "live_data": "CURRENT LIVE DATA",
    "consensus": "PROBABILITY ESTIMATES AND CONSENSUS",
}


def _render_research_block(internet_findings: dict | None) -> str:
    """Build the labelled three-search research block for the council prompt.

    Falls back to the old single-`content` shape for backward compatibility.
    """
    if not internet_findings or internet_findings.get("error"):
        return ""

    searches = internet_findings.get("searches")
    as_of = internet_findings.get("as_of", "")

    if searches:
        blocks = []
        for s in searches:
            content = (s.get("content") or "").strip()
            if not content:
                continue
            label = _RESEARCH_LABELS.get(s.get("purpose"), "RESEARCH")
            if s.get("purpose") == "live_data" and as_of:
                label = f"{label} (as of {as_of})"
            blocks.append(f"{label}:\n{_truncate_words(content, _MAX_FINDINGS_WORDS)}")
        return "\n\n".join(blocks)

    # Backward-compatible single-search shape.
    content = (internet_findings.get("content") or internet_findings.get("combined_summary") or "").strip()
    if not content:
        return ""
    return f"CURRENT INTERNET RESEARCH (summary)\n{_truncate_words(content, _MAX_FINDINGS_WORDS)}"


# ---------------------------------------------------------------------------
# Prediction engine (Part 4a) — extract + normalise probabilities
# ---------------------------------------------------------------------------

_PREDICTION_EXTRACT_INSTRUCTION = (
    "From the following response, extract every probability estimate mentioned. "
    "Normalise each to a specific percentage range with a maximum gap of 3 percentage "
    "points (e.g. 17-20%, not 15-25%). If a model gave a point estimate, convert it to "
    "a range of ±1.5% (e.g. 17% becomes 15.5-18.5%, rounded to 16-19%). If no "
    "probabilities were mentioned, return an empty array. "
    'Return ONLY JSON in this exact form: '
    '[{"entity": "string", "low_pct": number, "high_pct": number, '
    '"confidence": "high|medium|low"}]'
)


async def extract_predictions(text: str) -> list[dict]:
    """Run a lightweight gpt-4o-mini call to extract normalised predictions.

    Returns [] on empty input or any failure (never raises)."""
    if not text or not text.strip():
        return []

    from .openrouter import query_model
    import json as _json
    import re as _re

    messages = [
        {"role": "user", "content": f"{_PREDICTION_EXTRACT_INSTRUCTION}\n\nRESPONSE:\n{text}"}
    ]
    try:
        from .config import get_fast_model
        resp = await query_model(get_fast_model(), messages, timeout=60.0, max_tokens=1200)
    except Exception as e:
        print(f"[predictions] extraction failed: {e}", flush=True)
        return []
    if not resp:
        return []

    raw = (resp.get("content") or "").strip()
    # Strip code fences if present.
    raw = _re.sub(r"^```(?:json)?|```$", "", raw, flags=_re.MULTILINE).strip()
    # Grab the JSON array if the model wrapped it in prose.
    m = _re.search(r"\[.*\]", raw, flags=_re.DOTALL)
    if m:
        raw = m.group(0)
    try:
        data = _json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []

    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        entity = item.get("entity")
        low, high = item.get("low_pct"), item.get("high_pct")
        if entity is None or low is None or high is None:
            continue
        conf = str(item.get("confidence", "medium")).lower()
        if conf not in ("high", "medium", "low"):
            conf = "medium"
        out.append({
            "entity": str(entity),
            "low_pct": low,
            "high_pct": high,
            "confidence": conf,
        })
    return out


async def generate_follow_ups(question: str, synthesis: str) -> list[str]:
    """Suggest 3 sharper follow-up research questions that build on this run.
    Fast model, cheap. Returns [] on any failure."""
    if not (question or "").strip():
        return []
    from .openrouter import query_model
    from .config import get_fast_model
    import json as _json
    import re as _re

    prompt = (
        "Given this research question and its answer, propose exactly 3 concise, "
        "specific follow-up questions that would deepen the analysis. Return ONLY a "
        'JSON array of 3 strings, e.g. ["...","...","..."]. No prose.\n\n'
        f"QUESTION: {question}\n\nANSWER (excerpt): {(synthesis or '')[:1500]}"
    )
    try:
        resp = await query_model(get_fast_model(), [{"role": "user", "content": prompt}], timeout=40.0, max_tokens=400)
    except Exception:
        return []
    raw = (resp or {}).get("content", "") if resp else ""
    m = _re.search(r"\[.*\]", raw, flags=_re.DOTALL)
    if not m:
        return []
    try:
        items = _json.loads(m.group(0))
    except Exception:
        return []
    return [str(x).strip() for x in items if isinstance(x, str) and x.strip()][:3]


# ---------------------------------------------------------------------------
# Comparison tables
# ---------------------------------------------------------------------------

def _build_data_segments_table(data_summary: dict | None) -> list[dict]:
    if not data_summary:
        return []
    stats = data_summary.get("statistics", {})
    columns_info = data_summary.get("columns", [])
    cat_cols = [c["name"] for c in columns_info if c["type"] == "categorical"]
    num_cols = list(stats.keys())

    if not num_cols:
        return []

    rows = []
    # Show every numeric column — no artificial limit (previously capped at 4).
    for col in num_cols:
        s = stats[col]
        rows.append({
            "metric": col,
            "min": s["min"],
            "max": s["max"],
            "mean": s["mean"],
            "unique_values": s["unique_count"],
        })
    return rows


def _extract_predictions(text: str) -> list[str]:
    """Pull out numeric-looking claims or short factual statements from model text."""
    import re
    numbers = re.findall(r'\b\d[\d,\.]+\s*(?:%|percent|billion|million|trillion|USD|units?|kg|km|m\b)?', text)
    return numbers[:5]


def _internet_content(internet_findings: dict | None) -> str:
    """The combined research text, supporting both the new multi-search shape
    (combined_summary) and the old single-search shape (content)."""
    if not internet_findings:
        return ""
    return (internet_findings.get("combined_summary") or internet_findings.get("content") or "").strip()


def _has_internet_data(internet_findings: dict | None) -> bool:
    """True only when internet research actually produced usable content."""
    if not internet_findings:
        return False
    if internet_findings.get("error"):
        return False
    return bool(_internet_content(internet_findings))


def _snippet(text: str, max_chars: int = 120) -> str:
    text = " ".join(text.split())
    return text if len(text) <= max_chars else text[:max_chars].rstrip() + "…"


def _build_internet_vs_council_table(
    internet_findings: dict | None,
    council_responses: list[dict],
    chairman_synthesis: dict | None,
) -> list[dict]:
    # If internet research is unavailable or failed, hide the table entirely
    # rather than filling it with placeholder text (Fix 6).
    if not _has_internet_data(internet_findings):
        return []
    if not council_responses and not chairman_synthesis:
        return []

    _ic = _internet_content(internet_findings)
    internet_preds = _extract_predictions(_ic)
    internet_cell = "; ".join(internet_preds) if internet_preds else _snippet(_ic)

    rows = []
    for resp in council_responses:
        model_preds = _extract_predictions(resp.get("response", ""))
        rows.append({
            "model": resp.get("model", "unknown"),
            "internet_finding": internet_cell,
            "model_position": "; ".join(model_preds) if model_preds else _snippet(resp.get("response", "")),
        })

    if chairman_synthesis and chairman_synthesis.get("response"):
        chair_preds = _extract_predictions(chairman_synthesis.get("response", ""))
        rows.append({
            "model": f"{chairman_synthesis.get('model', 'Chairman')} (synthesis)",
            "internet_finding": internet_cell,
            "model_position": "; ".join(chair_preds) if chair_preds else _snippet(chairman_synthesis.get("response", "")),
        })

    return rows


def _build_model_vs_model_table(council_responses: list[dict]) -> list[dict]:
    if len(council_responses) < 2:
        return []

    rows = []
    for resp in council_responses:
        preds = _extract_predictions(resp.get("response", ""))
        rows.append({
            "model": resp.get("model", "unknown"),
            "key_claims": "; ".join(preds) if preds else "No numeric claims extracted",
            "response_length": len(resp.get("response", "")),
        })
    return rows


# ---------------------------------------------------------------------------
# Main report builder
# ---------------------------------------------------------------------------

def build_report(
    question: str,
    data_summary: dict | None,
    charts: list[dict],
    internet_findings: dict | None,
    council_responses: list[dict],
    stage2_results: list[dict],
    chairman_synthesis: dict | None,
    metadata: dict,
    mode: str,
    prediction_table: list | None = None,
    prediction_charts: list | None = None,
    prediction_meta: dict | None = None,
    prediction_suite: dict | None = None,
) -> dict:
    data_segments = _build_data_segments_table(data_summary)
    internet_vs_council = _build_internet_vs_council_table(
        internet_findings, council_responses, chairman_synthesis
    )
    model_vs_model = _build_model_vs_model_table(council_responses)

    # Build council opinions structure
    responses_dict = {
        r["model"]: {
            "stage1": r.get("response", ""),
        }
        for r in council_responses
    }
    for r in stage2_results:
        model = r.get("model")
        if model in responses_dict:
            responses_dict[model]["stage2_review"] = r.get("ranking", "")
            responses_dict[model]["stage2_ranking"] = r.get("parsed_ranking", [])

    # Agreement summary: find models that share top-ranked response
    top_ranked = [r.get("parsed_ranking", [None])[0] for r in stage2_results if r.get("parsed_ranking")]
    from collections import Counter
    if top_ranked:
        most_common, count = Counter(top_ranked).most_common(1)[0]
        agreement = f"{count} of {len(stage2_results)} models ranked {most_common} as best."
    else:
        agreement = "No consensus ranking detected."

    # Confidence heuristic: if all models agree on top → high, majority → medium, else → low
    if top_ranked:
        top_count = Counter(top_ranked).most_common(1)[0][1]
        ratio = top_count / len(top_ranked) if top_ranked else 0
        confidence = "high" if ratio >= 0.75 else "medium" if ratio >= 0.5 else "low"
    else:
        confidence = "low"

    # Available filters (for DataFilters component)
    available_filters: dict[str, Any] = {}
    if data_summary:
        cols = data_summary.get("columns", [])
        datetime_cols = [c["name"] for c in cols if c["type"] == "datetime"]
        cat_cols = [c["name"] for c in cols if c["type"] == "categorical"]
        num_cols = [c["name"] for c in cols if c["type"] == "numeric"]
        if datetime_cols:
            available_filters["date_range"] = {"column": datetime_cols[0]}
        if cat_cols:
            available_filters["categories"] = cat_cols
        if num_cols:
            available_filters["numeric_ranges"] = num_cols

    sections: dict[str, Any] = {}

    if mode == "data" and data_summary:
        sections["dataset_overview"] = {
            "data_summary": {
                k: v for k, v in data_summary.items()
            },
            "quality_notes": data_summary.get("quality_notes", []),
        }
        sections["data_filters"] = {
            "available_filters": available_filters,
        }
        sections["visualisations"] = {
            "charts": charts,
            "data_segments_table": data_segments,
        }

    internet_available = _has_internet_data(internet_findings)
    sections["internet_research"] = {
        "available": internet_available,
        "findings": _internet_content(internet_findings) if internet_available else "",
        "sources": internet_findings.get("sources", []) if internet_available else [],
        "searches": internet_findings.get("searches", []) if internet_available else [],
        "as_of": internet_findings.get("as_of", "") if internet_findings else "",
        # Phase 3: live results (3.4) + research summary digest (3.5).
        "live_scores": internet_findings.get("live_scores", []) if internet_findings else [],
        "summary": internet_findings.get("summary", {}) if internet_findings else {},
        "internet_vs_council_table": internet_vs_council,
    }

    sections["council_opinions"] = {
        "models": [r["model"] for r in council_responses],
        "responses": responses_dict,
        "agreement": agreement,
        "disagreement": "",
        "model_comparison_table": model_vs_model,
        "aggregate_rankings": metadata.get("aggregate_rankings", []),
        "label_to_model": metadata.get("label_to_model", {}),
    }

    sections["chairman_synthesis"] = {
        "content": chairman_synthesis.get("response", "") if chairman_synthesis else "",
        "model": chairman_synthesis.get("model", "") if chairman_synthesis else "",
        "confidence": confidence,
        "caveats": [],
        "prediction_table": prediction_table or [],
        "prediction_charts": prediction_charts or [],
        "prediction_meta": prediction_meta or {},
        "prediction_suite": prediction_suite or {},
        "sources": internet_findings.get("sources", []) if internet_available else [],
    }

    return {
        "type": "full_report",
        "mode": mode,
        "question": question,
        "prediction_table": prediction_table or [],
        "prediction_charts": prediction_charts or [],
        "prediction_meta": prediction_meta or {},
        "prediction_suite": prediction_suite or {},
        "sections": sections,
        "comparison_tables": {
            "data_segments": data_segments,
            "internet_vs_council": internet_vs_council,
            "model_vs_model": model_vs_model,
        },
    }
