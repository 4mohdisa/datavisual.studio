"""Internet research layer — three targeted Perplexity Sonar searches.

The pipeline runs three sequential searches, each with a distinct purpose:
  1. existing_research — established research / expert analyses
  2. live_data         — the most current information (injects today's date)
  3. consensus         — probability estimates, odds, market consensus

main.py drives the loop so it can emit per-search activity events; this module
provides the search plan, the single-search call, and the combiner.
"""

import re
from datetime import datetime
from .openrouter import query_model
from .config import DEBUG, get_research_model

_SYSTEM_MSG = (
    "You are a web research assistant with live internet access. Search the web "
    "for current, authoritative information and ground your answer in real, citable "
    "web sources."
)


def build_search_plan(question: str, entities: list[str] | None = None) -> list[dict]:
    """Return the ordered list of searches to run, each with its query, the
    human-readable reasoning shown in the Activity Panel, and a per-search system
    instruction that pushes the research model to return concrete numbers.

    The plan is topic-GENERIC (current facts → established research → forecasts)
    so deep research works for any subject, not one domain. Today's date is
    injected so the model grounds answers in the current state of the world
    rather than stale training knowledge. When `entities` (the top dataset
    entities) are supplied they are appended to the forecast search so the model
    targets the actual subjects of the data."""
    topic = question.strip()
    now = datetime.utcnow()
    today_date = now.strftime("%B %d, %Y")
    # Up to 6 entity names appended to the targeted forecast search.
    ent = " ".join((entities or [])[:6]).strip()
    ent_suffix = f" {ent}" if ent else ""
    return [
        # Search 1 — the current state of the subject.
        {
            "purpose": "live_data",
            "query": f"{topic} latest data news {today_date}",
            "system": (
                "Find the most current, dated facts and figures on this subject. "
                "Include concrete numbers, recent events, results and dates. "
                "Report exactly what you find."
            ),
            "started_reasoning": (
                "Searching for the latest data and news to ground the analysis in the current state of the subject."
            ),
            "complete_reasoning": (
                "Gathered the current picture. Now looking for established research and expert analysis."
            ),
        },
        # Search 2 — established research and expert analyses.
        {
            "purpose": "existing_research",
            "query": f"{topic} analysis expert research findings",
            "system": (
                "Find established research, expert analyses and studies on this "
                "subject. Prefer sources with concrete numbers, statistics and "
                "clear conclusions."
            ),
            "started_reasoning": (
                "Searching for expert analyses and published research on the subject."
            ),
            "complete_reasoning": (
                "Compiled expert findings. Now gathering forecasts and consensus estimates."
            ),
        },
        # Search 3 — forecasts / probabilities / market consensus.
        {
            "purpose": "consensus",
            "query": f"{topic} forecast projections estimates {now.year}{ent_suffix}",
            "system": (
                "Find forecasts, projections, probability estimates or market "
                "consensus for this subject. Numbers required — return all "
                "percentages and figures you find."
            ),
            "started_reasoning": (
                "Gathering forecasts and consensus estimates to cross-reference with the dataset."
            ),
            "complete_reasoning": (
                "Compiled forecast and consensus estimates from the available sources."
            ),
        },
    ]


async def plan_searches(question: str, entities: list[str] | None = None,
                        data_hint: str = "") -> list[dict]:
    """Upgrade the static plan with LLM-crafted queries: the fast model writes
    three targeted web-search queries for THIS question (and dataset), which
    beats keyword-mashing the raw question. The static skeleton keeps its
    purposes, system prompts and activity reasonings; only the query strings
    are replaced. Any failure falls back to the static plan untouched."""
    from .openrouter import query_model
    from .config import get_fast_model
    import json as _json

    plan = build_search_plan(question, entities)
    prompt = (
        "Write exactly 3 web search queries (plain keyword queries, no operators) "
        "to research this question. Query 1: the CURRENT state / latest news. "
        "Query 2: established research and expert analysis. Query 3: forecasts / "
        "projections / consensus estimates.\n"
        f"Question: {question}\n"
        + (f"The user's dataset covers: {data_hint}\n" if data_hint else "")
        + (f"Key entities: {', '.join(entities[:6])}\n" if entities else "")
        + 'Return ONLY a JSON array of 3 strings.'
    )
    try:
        resp = await query_model(get_fast_model(), [{"role": "user", "content": prompt}],
                                 timeout=25.0, max_tokens=300)
        raw = (resp or {}).get("content", "") if resp else ""
        m = re.search(r"\[.*\]", raw, flags=re.DOTALL)
        queries = _json.loads(m.group(0)) if m else []
        queries = [str(q).strip() for q in queries if isinstance(q, str) and q.strip()]
        if len(queries) == 3:
            for step, q in zip(plan, queries):
                step["query"] = q
            if DEBUG:
                print(f"[research] planner queries: {queries}", flush=True)
    except Exception as e:
        if DEBUG:
            print(f"[research] planner failed, using static plan: {e}", flush=True)
    return plan


# Patterns that signal an event is already under way — scored results, knockout
# language, etc. Matched against source titles returned by the searches.
_LIVE_INDICATORS = [
    r"\d+[-–]\d+",        # scores like 4-1
    r"results?",
    r"eliminat",
    r"knocked out",
    r"advanced to",
    r"group stage",
    r"round of \d",
    r"quarter.final",
    r"semi.final",
    r"winner",
    r"beat|defeated|lost to",
]


# Matches "<entity> N-M <entity>" style scorelines inside a source title, e.g.
# "USA routs Paraguay 4-1 to start 2026 FIFA World Cup".
_SCORE_PATTERN = r"(\w[\w\s]+?)\s+(\d+)[-–](\d+)\s+(\w[\w\s]+)"

# Result-indicator keywords (Fix C). The audit showed the score-only regex missed
# clear result headlines like "2026 World Cup Odds: USA, Morocco Surge After
# Openers" because the score isn't in the title. These keywords catch match
# outcomes/elimination language in titles. We deliberately exclude ambiguous
# words like "win"/"score"/"goal" — they over-match preview/odds headlines such
# as "who will win" and "top scorers", which are NOT confirmed results.
_RESULT_KEYWORDS = (
    "rout", "beat", "defeat", "thrash", "eliminat", "knocked out",
    "advance", "qualif", "surge", "opener", "full-time", "final score",
    "draw with", "held to",
)


def extract_confirmed_facts(searches: list[dict]) -> str:
    """Pull concrete match results / outcomes out of the source titles.

    These are treated as non-negotiable ground truth and injected at the very top
    of the council prompt so the models can't claim the event hasn't happened.
    Matches either an explicit scoreline OR a result-indicator keyword. Returns ''
    when nothing is found."""
    facts: list[str] = []
    seen: set[str] = set()
    for search in searches:
        for source in search.get("sources", []):
            title = (source.get("title") or "").strip()
            url = source.get("url", "") or ""
            if not title or title in seen:
                continue
            low = title.lower()
            if re.search(_SCORE_PATTERN, title, re.IGNORECASE) or any(k in low for k in _RESULT_KEYWORDS):
                seen.add(title)
                facts.append(f"CONFIRMED: {title}" + (f" [source: {url}]" if url else ""))
    return "\n".join(facts[:8])


# Domain authority tiers for source quality scoring (3.2).
_AUTHORITATIVE_DOMAINS = (
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "theguardian.com",
    "ft.com", "economist.com", "bloomberg.com", "wsj.com", "nytimes.com",
    "statista.com", "oecd.org", "worldbank.org", "imf.org", "nature.com",
    ".gov", "fifa.com", "espn.com", "skysports.com", "uefa.com",
)


def score_source_quality(url: str) -> str:
    """Classify a source URL as 'authoritative', 'standard', or 'unknown' (3.2)."""
    if not url:
        return "unknown"
    u = url.lower()
    if any(d in u for d in _AUTHORITATIVE_DOMAINS):
        return "authoritative"
    if u.startswith("http"):
        return "standard"
    return "unknown"


# Scoreline within prose content: "Spain beat/defeated/... Germany 2-1" or
# "Spain 2-1 Germany". Used to surface confirmed live results (3.4).
_CONTENT_SCORE_PATTERNS = [
    r"([A-Z][A-Za-z .'-]{1,28}?)\s+(\d{1,2})\s*[-–:]\s*(\d{1,2})\s+([A-Z][A-Za-z .'-]{1,28})",
    r"([A-Z][A-Za-z .'-]{1,28}?)\s+(?:beat|defeated|edged|thrashed|routed)\s+([A-Z][A-Za-z .'-]{1,28}?)\s+(\d{1,2})\s*[-–:]\s*(\d{1,2})",
]


def extract_live_scores(searches: list[dict]) -> list[dict]:
    """Scan source titles AND content for scorelines and return structured live
    results (3.4): [{home_team, away_team, home_goals, away_goals}]. Deduplicated."""
    out: list[dict] = []
    seen: set[tuple] = set()

    def add(home, away, hg, ag):
        home, away = home.strip(" .'-"), away.strip(" .'-")
        if not home or not away or home.lower() == away.lower():
            return
        try:
            hg, ag = int(hg), int(ag)
        except (TypeError, ValueError):
            return
        if hg > 20 or ag > 20:  # not a football score
            return
        key = (home.lower(), away.lower(), hg, ag)
        if key in seen:
            return
        seen.add(key)
        out.append({"home_team": home, "away_team": away, "home_goals": hg, "away_goals": ag})

    for search in searches:
        texts = [search.get("content", "") or ""]
        texts += [s.get("title", "") or "" for s in search.get("sources", [])]
        for text in texts:
            for m in re.finditer(_CONTENT_SCORE_PATTERNS[0], text):
                add(m.group(1), m.group(4), m.group(2), m.group(3))
            for m in re.finditer(_CONTENT_SCORE_PATTERNS[1], text):
                add(m.group(1), m.group(2), m.group(3), m.group(4))
    return out[:10]


def detect_event_status(searches: list[dict], today_date: str) -> str:
    """Scan search results for evidence the event is currently in progress.

    Returns a status string to inject into the council prompt. When live evidence
    is found it instructs the models not to claim the event hasn't started; when
    none is found it still directs them to analyse from the dataset.
    """
    confirmed_evidence = []
    for search in searches:
        for source in search.get("sources", []):
            title = source.get("title", "") or ""
            url = source.get("url", "") or ""
            for pattern in _LIVE_INDICATORS:
                if re.search(pattern, title, re.IGNORECASE):
                    confirmed_evidence.append(f"- {title} ({url})")
                    break

    if confirmed_evidence:
        return (
            f"CONFIRMED: There are current, dated developments on this subject as of {today_date}. "
            f"Evidence from internet sources:\n"
            + "\n".join(confirmed_evidence[:5])
            + "\n\nGround your analysis in this current evidence. Do NOT claim "
            "nothing has happened yet when the evidence above shows otherwise."
        )
    return (
        f"Internet sources did not return clearly dated current results for {today_date}. "
        f"However, always provide your best analysis from the dataset."
    )


async def run_single_search(query: str, system: str | None = None) -> dict:
    """Run one web search with a single retry on failure/empty response.
    Always returns a structured dict; on repeated failure it returns empty
    content + error=True so the pipeline continues.

    `system` optionally overrides/augments the default system message so each
    search can demand the specific kind of numbers it needs."""
    result = await _search_once(query, system)
    if result.get("error"):
        if DEBUG:
            print(f"[SEARCH] retrying failed search: {query[:80]}", flush=True)
        result = await _search_once(query, system)
    return result


async def _search_once(query: str, system: str | None = None) -> dict:
    prompt = (
        f"Search the web and summarise current, factual information for this query:\n\n{query}\n\n"
        "Provide a concise summary of the most relevant findings, including any statistics, "
        "trends, odds, or expert opinions. Then list your sources.\n\n"
        "Format your response as:\nFINDINGS:\n[findings]\n\nSOURCES:\n- [title] | [url]"
    )
    system_msg = f"{_SYSTEM_MSG} {system}" if system else _SYSTEM_MSG
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]
    # Step 1a — print the actual query + system instruction being sent.
    if DEBUG:
        print(f"\n[SEARCH] Query: {query}", flush=True)
        print(f"[SEARCH] System: {system_msg[:200]}", flush=True)
    try:
        response = await query_model(get_research_model(), messages, timeout=60.0)
    except Exception as e:
        print(f"[research] search failed: {e}", flush=True)
        return {"content": "", "sources": [], "error": True}

    if response is None:
        if DEBUG:
            print("[SEARCH] Response: None (request failed)", flush=True)
        return {"content": "", "sources": [], "error": True}

    raw = response.get("content") or ""
    if not raw.strip():
        if DEBUG:
            print("[SEARCH] Response: empty content", flush=True)
        return {"content": "", "sources": [], "error": True}

    try:
        content, text_sources = _parse_response(raw)
    except Exception:
        content, text_sources = raw, []

    sources = _sources_from_response(response) or text_sources
    # Step 1b — print raw response stats + citations.
    if DEBUG:
        print(f"[SEARCH] Response length: {len(content)} chars", flush=True)
        print(f"[SEARCH] First 500 chars: {content[:500]}", flush=True)
        print(f"[SEARCH] Citations found: {len(sources)}", flush=True)
        for c in sources[:5]:
            print(f"  - {c.get('title', '')} | {c.get('url', '')}", flush=True)
    return {"content": content, "sources": sources, "error": False}


_PURPOSE_LABELS = {
    "existing_research": "EXISTING RESEARCH AND EXPERT ANALYSES",
    "live_data": "CURRENT LIVE DATA",
    "consensus": "PROBABILITY ESTIMATES AND CONSENSUS",
}


def combine_findings(searches: list[dict]) -> dict:
    """Combine the per-search results into the internet_findings object stored in
    the conversation JSON and consumed by the report + enriched prompt."""
    # Dedupe sources across all searches; attach a quality tier to each (3.2).
    seen, sources = set(), []
    for s in searches:
        for src in s.get("sources", []):
            url = src.get("url")
            if url and url not in seen:
                seen.add(url)
                sources.append({**src, "quality": score_source_quality(url)})

    # A labelled, human-readable combined summary built from the three contents.
    blocks = []
    for s in searches:
        if (s.get("content") or "").strip():
            label = _PURPOSE_LABELS.get(s.get("purpose"), s.get("purpose", "FINDINGS"))
            blocks.append(f"{label}:\n{s['content'].strip()}")
    combined_summary = "\n\n".join(blocks)

    live_scores = extract_live_scores(searches)

    # Research summary block (3.5): a one-line digest shown at the top of the section.
    now = datetime.utcnow()
    pct_count = len(set(re.findall(r"(\d+(?:\.\d+)?)\s*%", combined_summary)))
    summary = {
        "n_searches": len(searches),
        "n_sources": len(sources),
        "n_authoritative": sum(1 for s in sources if s.get("quality") == "authoritative"),
        "n_live_scores": len(live_scores),
        "n_probability_values": pct_count,
        "as_of": now.strftime("%B %d, %Y at %-I:%M %p"),
    }

    return {
        "searches": searches,
        "combined_summary": combined_summary,
        "sources": sources,
        "live_scores": live_scores,
        "summary": summary,
        "as_of": now.strftime("%B %Y"),
        "error": not bool(combined_summary.strip()),
    }


def _sources_from_response(response: dict) -> list[dict]:
    """Pull real source URLs out of the OpenRouter/Perplexity response.

    Perplexity puts web citations in message.annotations as url_citation objects,
    and sometimes in a top-level citations[] list of URL strings.
    """
    sources: list[dict] = []
    seen: set[str] = set()

    for ann in (response.get("annotations") or []):
        if not isinstance(ann, dict):
            continue
        if ann.get("type") == "url_citation":
            uc = ann.get("url_citation", {}) or {}
            url = uc.get("url")
            if url and url not in seen:
                seen.add(url)
                sources.append({"title": uc.get("title") or url, "url": url})

    for url in (response.get("citations") or []):
        if isinstance(url, str) and url not in seen:
            seen.add(url)
            sources.append({"title": url, "url": url})

    return sources


def _parse_response(raw: str) -> tuple[str, list[dict]]:
    content = raw
    sources = []

    if "SOURCES:" in raw:
        parts = raw.split("SOURCES:", 1)
        content_part = parts[0]
        sources_part = parts[1]

        if "FINDINGS:" in content_part:
            content = content_part.split("FINDINGS:", 1)[1].strip()
        else:
            content = content_part.strip()

        for line in sources_part.strip().splitlines():
            line = line.strip().lstrip("-").strip()
            if not line:
                continue
            if "|" in line:
                title, url = line.split("|", 1)
                sources.append({"title": title.strip(), "url": url.strip()})
            elif line.startswith("http"):
                sources.append({"title": line, "url": line})
            else:
                sources.append({"title": line, "url": ""})
    elif "FINDINGS:" in raw:
        content = raw.split("FINDINGS:", 1)[1].strip()

    return content, sources
