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
from .config import DEBUG

# perplexity/sonar-pro is the most capable general online/search model on
# OpenRouter that still returns plain prose. Verified present in the catalogue.
_MODEL = "perplexity/sonar-pro"

_SYSTEM_MSG = (
    "You are a web research assistant with live internet access. Search the web "
    "for current, authoritative information and ground your answer in real, citable "
    "web sources."
)


def build_search_plan(question: str, entities: list[str] | None = None) -> list[dict]:
    """Return the ordered list of searches to run, each with its query, the
    human-readable reasoning shown in the Activity Panel, and a per-search system
    instruction that pushes Perplexity to return concrete numbers.

    Today's date is injected into every query and live-data search so the model
    grounds answers in the current state of the world rather than stale training
    knowledge — the recurring failure mode was the model claiming it had "no live
    data". When `entities` (e.g. the top dataset entities) are supplied they are
    appended to the probability/results searches so the model targets the actual
    contenders rather than parsing the raw question (query enrichment, 3.1)."""
    topic = question.strip()
    now = datetime.utcnow()
    today_date = now.strftime("%B %d, %Y")
    today_month = now.strftime("%B")
    today_year = now.year
    # Up to 6 entity names appended to targeted searches.
    ent = " ".join((entities or [])[:6]).strip()
    ent_suffix = f" {ent}" if ent else ""
    return [
        # Search 1 — live scores and results (Fix 3).
        {
            "purpose": "live_data",
            "query": f"{topic} scores results today {today_date} latest{ent_suffix}",
            "system": (
                "Find the actual scores and results for this subject played so far. "
                "Include scorelines and figures. Even a YouTube title with a score "
                "counts as evidence. Report exactly what you find."
            ),
            "started_reasoning": (
                "Searching for live scores and results to confirm the current state of play right now."
            ),
            "complete_reasoning": (
                "Gathered live scores. Now checking which entities have been eliminated or advanced."
            ),
        },
        # Search 2 — eliminated and advancing entities (Fix 3).
        {
            "purpose": "existing_research",
            "query": f"{topic} eliminated qualified advancing {today_month} {today_year}",
            "system": (
                "Which specific entities have been eliminated and which have advanced? "
                "Report names and round. Use any available source including YouTube, "
                "Reddit, and news sites."
            ),
            "started_reasoning": (
                "Searching for which entities are eliminated and which have advanced to later rounds."
            ),
            "complete_reasoning": (
                "Compiled the eliminated/advancing picture. Now gathering current win probabilities."
            ),
        },
        # Search 3 — current win probabilities / odds (Fix 3).
        {
            "purpose": "consensus",
            "query": f"{topic} win probability odds {today_date} who will win{ent_suffix}",
            "system": (
                "Find specific win probability percentages or betting odds for each entity. "
                "Numbers required. Return all percentages you find."
            ),
            "started_reasoning": (
                "Gathering expert win probabilities and market odds to cross-reference with the dataset."
            ),
            "complete_reasoning": (
                "Compiled probability estimates and consensus forecasts from the available sources."
            ),
        },
        # Search 4 — live match data from real-time aggregator sites (Fix 2).
        {
            "purpose": "live_aggregator",
            "query": f"{topic} results {today_date} sofascore fotmob soccerway livescore",
            "system": (
                "Search specifically on live football data sites like SofaScore, "
                "FotMob, Soccerway, or LiveScore for match results and standings. "
                "These sites update in real time. Return any match scores, group "
                "standings, or results you find. Even partial data is valuable."
            ),
            "started_reasoning": (
                "Checking real-time football data aggregators (SofaScore, FotMob, Soccerway, "
                "LiveScore) for live scores and standings the official sources may lag on."
            ),
            "complete_reasoning": (
                "Gathered live match data from real-time aggregator sites."
            ),
        },
    ]


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
    "fifa.com", "espn.com", "bbc.com", "bbc.co.uk", "reuters.com",
    "apnews.com", "skysports.com", "theguardian.com", "uefa.com",
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
            f"CONFIRMED: The event is currently in progress as of {today_date}. "
            f"Evidence from internet sources:\n"
            + "\n".join(confirmed_evidence[:5])
            + "\n\nYou MUST acknowledge this in your response. Do NOT state the "
            "event has not started when evidence above proves it has."
        )
    return (
        f"Internet sources did not return clear live results for {today_date}. "
        f"However, always provide your best analysis from the dataset."
    )


async def run_single_search(query: str, system: str | None = None) -> dict:
    """Run one Perplexity search. Always returns a structured dict; on failure it
    returns empty content + error=True so the pipeline continues.

    `system` optionally overrides/augments the default system message so each
    search can demand the specific kind of numbers it needs."""
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
        response = await query_model(_MODEL, messages, timeout=60.0)
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
    "live_aggregator": "LIVE MATCH DATA (AGGREGATOR SITES)",
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
