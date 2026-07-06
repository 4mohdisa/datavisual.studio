"""Deterministic prediction engine.

This module computes the final probability estimates **algorithmically** — pure
math, no LLM calls. The council and the internet research feed numbers into it;
it combines them with fixed weights and returns a calibrated probability table.

Two layers live here:

  1. Pure primitives (exactly as specified): elo_win_probability,
     run_monte_carlo_tournament, extract_percentages, compute_prediction.
  2. Source-extraction helpers that turn the pipeline's three data sources
     (dataset / internet / council) into {entity: probability} dicts, plus a
     chairman-prompt formatter. These reuse the existing column-detection logic
     in data_analysis.py rather than re-deriving it.
"""

import re
import math
import random
from dataclasses import dataclass, asdict
from typing import Any, Optional

from .config import DEBUG


@dataclass
class PredictionResult:
    entity: str
    point_estimate: float   # e.g. 21.0
    low_pct: float          # e.g. 19.5
    high_pct: float         # e.g. 22.5
    confidence: str         # "high" | "medium" | "low"
    sources_used: list[str]  # which of the 3 sources contributed
    # How much Model A and Model B agree on this entity (0–1). 1.0 = full
    # agreement / not applicable (e.g. only one math model ran).
    model_agreement: float = 1.0


# ---------------------------------------------------------------------------
# Pure primitives
# ---------------------------------------------------------------------------

def elo_win_probability(elo_a: float, elo_b: float) -> float:
    """Standard ELO win expectancy formula."""
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))


# ---------------------------------------------------------------------------
# Tournament bracket simulation (group stage → knockout)
# ---------------------------------------------------------------------------

# Real tournaments run a group stage then a knockout bracket; the structure
# materially changes win probabilities. For <=48 entities we model that; above
# 48 we keep the simple random-shuffle elimination (no sensible group layout).
_BRACKET_MAX_TEAMS = 48


def simulate_group_stage(group: list[str], elos: dict[str, float]) -> list[str]:
    """Round-robin within a group. Returns the top 2 (by points then goal diff)."""
    points = {t: 0 for t in group}
    goal_diff = {t: 0 for t in group}

    # Each pair plays once.
    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            a, b = group[i], group[j]
            p_a = elo_win_probability(elos[a], elos[b])
            r = random.random()
            if r < p_a * 0.75:        # win for A (75% of p_a → rest is draw/upset)
                points[a] += 3
                goal_diff[a] += 1
                goal_diff[b] -= 1
            elif r < p_a * 0.75 + 0.15:  # draw
                points[a] += 1
                points[b] += 1
            else:                     # win for B
                points[b] += 3
                goal_diff[b] += 1
                goal_diff[a] -= 1

    ranked = sorted(group, key=lambda t: (points[t], goal_diff[t]), reverse=True)
    return ranked[:2]  # top 2 advance


def _choose_group_size(n: int) -> int:
    """Prefer groups of 4; fall back to 3 when that divides the field evenly."""
    if n % 4 == 0:
        return 4
    if n % 3 == 0:
        return 3
    return 4


def _make_groups(team_list: list[str], group_size: int) -> list[list[str]]:
    shuffled = team_list.copy()
    random.shuffle(shuffled)
    return [shuffled[i:i + group_size] for i in range(0, len(shuffled), group_size)]


def _make_groups_seeded(team_list: list[str], elos: dict[str, float], group_size: int) -> list[list[str]]:
    """Pot-based seeding (2.1): rank by ELO, split into `group_size` pots, then draw
    one team from each pot into every group — so the strongest teams can't all land
    in the same group. Matches how real World Cup draws separate seeds."""
    ranked = sorted(team_list, key=lambda t: elos.get(t, 1500), reverse=True)
    n_groups = max(1, math.ceil(len(ranked) / group_size))
    groups: list[list[str]] = [[] for _ in range(n_groups)]
    for pot_idx in range(group_size):
        pot = ranked[pot_idx * n_groups:(pot_idx + 1) * n_groups]
        random.shuffle(pot)  # randomise which group within the pot
        for gi, team in enumerate(pot):
            groups[gi % n_groups].append(team)
    return [g for g in groups if g]


def _knockout_elo(a: str, b: str, elos: dict[str, float]) -> str:
    """Resolve a knockout tie using the ELO win-probability formula (Model A)."""
    return a if random.random() < elo_win_probability(elos[a], elos[b]) else b


def _run_knockout(qualifiers: list[str], elos: dict[str, float], match_fn) -> Optional[str]:
    """Single-elimination over the qualifiers until one champion remains. Odd
    rounds give the last entrant a bye (matches the legacy behaviour)."""
    remaining = qualifiers.copy()
    random.shuffle(remaining)
    while len(remaining) > 1:
        next_round = []
        for i in range(0, len(remaining) - 1, 2):
            next_round.append(match_fn(remaining[i], remaining[i + 1], elos))
        if len(remaining) % 2 == 1:
            next_round.append(remaining[-1])
        remaining = next_round
    return remaining[0] if remaining else None


def _simulate_bracket_once(team_list: list[str], elos: dict[str, float], match_fn,
                           group_size: int, seeding: str = "seeded") -> Optional[str]:
    """One full tournament: group stage (top 2 advance) → knockout bracket."""
    if seeding == "random":
        groups = _make_groups(team_list, group_size)
    else:  # "seeded" or "historical" (no draw available → seeded)
        groups = _make_groups_seeded(team_list, elos, group_size)
    qualifiers: list[str] = []
    for group in groups:
        qualifiers.extend(simulate_group_stage(group, elos))
    return _run_knockout(qualifiers, elos, match_fn)


def _run_tournament(teams: dict[str, float], n_simulations: int, match_fn,
                    seeding: str = "seeded") -> dict[str, float]:
    """Shared driver. Uses bracket simulation for <=48 entities, else a plain
    random-shuffle elimination. `match_fn(a, b, elos) -> winner` resolves a tie."""
    team_list = list(teams.keys())
    if not team_list:
        return {}
    if len(team_list) == 1:
        return {team_list[0]: 1.0}

    use_bracket = len(team_list) <= _BRACKET_MAX_TEAMS
    group_size = _choose_group_size(len(team_list))
    wins = {team: 0 for team in teams}

    for _ in range(n_simulations):
        if use_bracket:
            champ = _simulate_bracket_once(team_list, teams, match_fn, group_size, seeding)
        else:
            champ = _run_knockout(team_list, teams, match_fn)
        if champ is not None:
            wins[champ] += 1

    total = sum(wins.values())
    if total == 0:
        return {t: 0.0 for t in teams}
    return {t: w / total for t, w in wins.items()}


def run_monte_carlo_tournament(
    teams: dict[str, float],  # {team_name: elo_rating}
    n_simulations: int = 1000,
    seeding: str = "seeded",
) -> dict[str, float]:
    """Simulate the tournament n times and return each team's win probability.

    Model A: group stage (round-robin, top 2 advance) followed by a knockout
    bracket where each tie is resolved by the ELO win-probability formula. Falls
    back to random-shuffle single elimination for fields larger than 48.
    """
    return _run_tournament(teams, n_simulations, _knockout_elo, seeding)


# ---------------------------------------------------------------------------
# Model B — ELO-Poisson with Dixon-Coles correction
# ---------------------------------------------------------------------------

try:
    from scipy.stats import poisson as _scipy_poisson
except Exception:  # scipy missing — fall back to a stdlib Poisson sampler
    _scipy_poisson = None


def _poisson_rvs(lam: float) -> int:
    """Sample a Poisson variate. Uses SciPy when available, else Knuth's algorithm
    so Model B still runs without scipy installed."""
    if _scipy_poisson is not None:
        return int(_scipy_poisson.rvs(lam))
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1


def elo_to_lambda(elo_a: float, elo_b: float, base_goals: float = 1.35) -> tuple[float, float]:
    """Convert ELO ratings to expected goals per team."""
    win_prob = elo_win_probability(elo_a, elo_b)
    # Higher win prob = more expected goals, less for opponent.
    lambda_a = base_goals * (win_prob / 0.5)
    lambda_b = base_goals * ((1 - win_prob) / 0.5)
    return lambda_a, lambda_b


def dixon_coles_weight(goals_a: int, goals_b: int, rho: float = -0.107) -> float:
    """Apply Dixon-Coles correction for low-scoring games."""
    if goals_a == 0 and goals_b == 0:
        return 1 - rho
    elif goals_a == 0 and goals_b == 1:
        return 1 + rho
    elif goals_a == 1 and goals_b == 0:
        return 1 + rho
    elif goals_a == 1 and goals_b == 1:
        return 1 - rho
    return 1.0


def simulate_match_poisson(elo_a: float, elo_b: float, rho: float = -0.107) -> tuple[int, int]:
    """Simulate a single match scoreline using Poisson + Dixon-Coles (`rho` may be
    data-fitted; defaults to the 1997 paper value)."""
    lambda_a, lambda_b = elo_to_lambda(elo_a, elo_b)
    goals_a = _poisson_rvs(lambda_a)
    goals_b = _poisson_rvs(lambda_b)
    # Apply Dixon-Coles weighting via accept-reject; resample once if rejected.
    weight = dixon_coles_weight(goals_a, goals_b, rho)
    if random.random() > weight:
        goals_a = _poisson_rvs(lambda_a)
        goals_b = _poisson_rvs(lambda_b)
    return goals_a, goals_b


def _knockout_poisson(a: str, b: str, elos: dict[str, float], rho: float = -0.107) -> str:
    """Resolve a knockout tie by simulating a scoreline (Model B); a draw goes to
    penalties (50/50)."""
    ga, gb = simulate_match_poisson(elos[a], elos[b], rho)
    if ga > gb:
        return a
    if gb > ga:
        return b
    return random.choice([a, b])


def run_monte_carlo_poisson(
    teams: dict[str, float],
    n_simulations: int = 10000,
    rho: float = -0.107,
    seeding: str = "seeded",
) -> dict[str, float]:
    """Simulate the tournament n times using Poisson scorelines (Model B).

    Same bracket structure as Model A (group stage → knockout for <=48 teams),
    but each match is resolved by a simulated scoreline rather than a direct win
    probability — so close/low-scoring patterns (governed by `rho`) shift the odds.
    """
    return _run_tournament(teams, n_simulations,
                           lambda a, b, elos: _knockout_poisson(a, b, elos, rho), seeding)


# --- Dixon-Coles rho fitting (Improvement 3) -------------------------------

# Per-match scoreline column names. Fitting rho needs ACTUAL match scorelines
# (0-0, 1-0 frequencies), not season aggregates — so we only fit when columns
# like these are present.
_HOME_GOAL_NAMES = ("home_goals", "goals_home", "home_score", "score_home", "hg")
_AWAY_GOAL_NAMES = ("away_goals", "goals_away", "away_score", "score_away", "ag")


def estimate_rho(match_data: list[tuple[int, int]]) -> float:
    """Fit the Dixon-Coles rho parameter from observed scorelines.

    match_data: list of (goals_home, goals_away) tuples. Returns rho in
    [-0.2, 0.0], or the default -0.107 when there isn't enough data."""
    if len(match_data) < 50:
        return -0.107  # fallback to default

    observed_00 = sum(1 for g in match_data if g == (0, 0))
    total = len(match_data)
    avg_home = sum(g[0] for g in match_data) / total
    avg_away = sum(g[1] for g in match_data) / total

    expected_00 = math.exp(-avg_home) * math.exp(-avg_away)
    if expected_00 > 0:
        rho = (observed_00 / total - expected_00) / expected_00
        return max(-0.2, min(0.0, rho))
    return -0.107


def extract_match_data(df: Any, columns_info: list[dict]) -> list[tuple[int, int]]:
    """Pull per-match (home_goals, away_goals) tuples from the dataset, if it has
    genuine scoreline columns. Season aggregates (goals_for/against per team) are
    NOT scorelines, so such datasets return [] and rho stays at the default."""
    if df is None or not columns_info:
        return []
    names = {c["name"].lower(): c["name"] for c in columns_info}
    home = next((names[n] for n in _HOME_GOAL_NAMES if n in names), None)
    away = next((names[n] for n in _AWAY_GOAL_NAMES if n in names), None)
    if not (home and away) or home not in df.columns or away not in df.columns:
        return []
    out: list[tuple[int, int]] = []
    for _, row in df.iterrows():
        try:
            out.append((int(row[home]), int(row[away])))
        except (TypeError, ValueError):
            continue
    return out


def fit_dixon_coles_rho(df: Any, columns_info: list[dict]) -> tuple[float, int, bool]:
    """Return (rho, n_matches, fitted). `fitted` is False (rho = default) when the
    dataset has no per-match scoreline data to fit from."""
    match_data = extract_match_data(df, columns_info)
    if len(match_data) < 50:
        return -0.107, len(match_data), False
    return estimate_rho(match_data), len(match_data), True


def extract_percentages(
    text: str,
    entity_names: list[str],
) -> dict[str, float]:
    """
    Extract percentage values near entity names.
    Returns probability (0-1) per entity.
    """
    results = {}
    if not text:
        return results
    for name in entity_names:
        pattern = rf"(?i){re.escape(name)}.{{0,300}}?(\d+(?:\.\d+)?)\s*%"
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        reverse = rf"(\d+(?:\.\d+)?)\s*%.{{0,100}}?(?i){re.escape(name)}"
        matches += re.findall(reverse, text, re.IGNORECASE | re.DOTALL)
        if matches:
            values = [float(m) for m in matches if 0.5 < float(m) < 99]
            if values:
                results[name] = (sum(values) / len(values)) / 100
    return results


def compute_prediction(
    dataset_probs: dict[str, float],
    internet_probs: dict[str, float],
    council_probs: dict[str, float],
    top_n: int = 10,
) -> list[PredictionResult]:
    """
    Combine three probability sources into a final
    deterministic prediction.
    Weights: dataset 40%, internet 35%, council 25%
    """
    WEIGHTS = {"dataset": 0.40, "internet": 0.35, "council": 0.25}
    all_entities = (
        set(dataset_probs)
        | set(internet_probs)
        | set(council_probs)
    )

    raw = {}
    sources_map = {}

    for entity in all_entities:
        d = dataset_probs.get(entity, 0)
        i = internet_probs.get(entity, 0)
        c = council_probs.get(entity, 0)

        present = {}
        if d > 0:
            present["dataset"] = d
        if i > 0:
            present["internet"] = i
        if c > 0:
            present["council"] = c

        if not present:
            continue

        total_weight = sum(WEIGHTS[k] for k in present)
        raw[entity] = sum(
            v * WEIGHTS[k] / total_weight
            for k, v in present.items()
        )
        sources_map[entity] = list(present.keys())

    if not raw:
        return []

    total = sum(raw.values())
    if total == 0:
        return []

    normalised = {e: v / total for e, v in raw.items()}

    results = []
    for entity, prob in sorted(
        normalised.items(), key=lambda x: -x[1]
    )[:top_n]:
        results.append(_result_from_prob(entity, prob, sources_map.get(entity, [])))

    return results


def _result_from_prob(entity: str, prob: float, sources: list[str]) -> PredictionResult:
    """Build one PredictionResult from a 0–1 probability (shared by
    compute_prediction and probs_to_prediction_results)."""
    pct = round(prob * 100, 1)
    low = round(max(0.1, pct - 1.5), 1)
    high = round(min(99.9, pct + 1.5), 1)
    confidence = "high" if pct > 12 else "medium" if pct > 4 else "low"
    return PredictionResult(
        entity=entity, point_estimate=pct, low_pct=low, high_pct=high,
        confidence=confidence, sources_used=sources,
    )


def probs_to_prediction_results(
    probs: dict[str, float],
    top_n: int = 10,
    sources: Optional[list[str]] = None,
) -> list[PredictionResult]:
    """Convert a single {entity: probability} distribution into ranked
    PredictionResults. Re-normalises (an ensemble average of two distributions
    may not sum to exactly 1) and keeps the top_n entities."""
    if not probs:
        return []
    total = sum(probs.values()) or 1.0
    norm = {e: v / total for e, v in probs.items()}
    return [
        _result_from_prob(e, p, list(sources or ["dataset"]))
        for e, p in sorted(norm.items(), key=lambda x: -x[1])[:top_n]
    ]


# ---------------------------------------------------------------------------
# Source extraction — dataset
# ---------------------------------------------------------------------------

# Numeric columns that mean "team strength" and should drive an ELO-style
# Monte-Carlo simulation. Matched case-insensitively, exact name first then
# substring.
_ELO_COLUMN_NAMES = ("elo", "rating", "strength", "points")

# Cap on entities fed into the simulation / distribution.
_DATASET_TOP_N = 48


def detect_elo_column(num_cols: list[str]) -> Optional[str]:
    """Return the numeric column that looks like an ELO/strength rating, or None."""
    lowered = {c: c.lower() for c in num_cols}
    # Exact name match wins.
    for name in _ELO_COLUMN_NAMES:
        for c, lc in lowered.items():
            if lc == name:
                return c
    # Substring fallback (e.g. "elo_rating", "world_points").
    for name in _ELO_COLUMN_NAMES:
        for c, lc in lowered.items():
            if name in lc:
                return c
    return None


def _softmax_normalise(values: dict[str, float]) -> dict[str, float]:
    """Turn arbitrary numeric values into a probability distribution.

    We standardise to z-scores before the softmax so the distribution doesn't
    collapse onto a single entity when the raw values have a large absolute
    scale (e.g. points in the thousands). With ~equal spacing this yields a
    sensible spread instead of a near-one-hot vector.
    """
    if not values:
        return {}
    vals = list(values.values())
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = math.sqrt(var) or 1.0
    exps = {k: math.exp((v - mean) / std) for k, v in values.items()}
    total = sum(exps.values()) or 1.0
    return {k: e / total for k, e in exps.items()}


def _dataset_distribution_inputs(
    df: Any,
    columns_info: list[dict],
    top_n: int = _DATASET_TOP_N,
) -> tuple[str, dict[str, float], str]:
    """Detect the entity column and the numeric column that drives the prediction.

    Returns (kind, values, col) where kind is 'elo' | 'softmax' | 'none':
      - 'elo'     → values is {entity: raw ELO rating} (top_n by rating)
      - 'softmax' → values is {entity: raw primary-numeric value}
      - 'none'    → no usable columns; values is {}
    Reuses data_analysis's column pickers + latest-snapshot logic.
    """
    if df is None or not columns_info:
        return "none", {}, ""

    # Imported lazily to avoid a hard import cycle at module load.
    from .data_analysis import (
        _pick_entity_column,
        _pick_primary_numeric,
        _pick_time_column,
        _latest_snapshot,
    )

    cat_cols = [c["name"] for c in columns_info if c["type"] == "categorical"]
    num_cols = [c["name"] for c in columns_info if c["type"] == "numeric"]
    if not num_cols:
        return "none", {}, ""

    entity_col = _pick_entity_column(df, cat_cols)
    if not entity_col or entity_col not in df.columns:
        return "none", {}, ""

    time_col, _ = _pick_time_column(df, columns_info)
    latest = _latest_snapshot(df, entity_col, time_col)

    elo_col = detect_elo_column(num_cols)
    col = elo_col if (elo_col and elo_col in df.columns) else _pick_primary_numeric(df, num_cols)
    if not col or col not in df.columns:
        return "none", {}, ""

    snap = latest.dropna(subset=[col]).sort_values(col, ascending=False).head(top_n)
    values: dict[str, float] = {}
    for _, row in snap.iterrows():
        try:
            values[str(row[entity_col])] = float(row[col])
        except (TypeError, ValueError):
            continue
    if not values:
        return "none", {}, ""

    kind = "elo" if (elo_col and elo_col in df.columns) else "softmax"
    return kind, values, col


# --- Form index (Improvement 5) --------------------------------------------

def _detect_form_columns(columns_info: list[dict]) -> Optional[tuple[str, str, str]]:
    """Return (wins, losses, draws) column names if all three are present."""
    names = {c["name"].lower(): c["name"] for c in columns_info}
    w, l, d = names.get("wins"), names.get("losses"), names.get("draws")
    return (w, l, d) if (w and l and d) else None


def compute_form_index(
    df: Any,
    entity_col: str,
    time_col: str,
    wins_col: str,
    losses_col: str,
    draws_col: str,
    n_periods: int = 5,
) -> dict[str, float]:
    """Compute a form index (0–1) per entity from its last n time periods, with
    recent periods weighted higher."""
    if df is None or not all(c in df.columns for c in [entity_col, time_col, wins_col, losses_col, draws_col]):
        return {}

    form: dict[str, float] = {}
    weights = [0.1, 0.15, 0.2, 0.25, 0.3]  # most recent = highest

    for entity in df[entity_col].unique():
        edf = df[df[entity_col] == entity].sort_values(time_col).tail(n_periods)
        if len(edf) == 0:
            continue

        scores = []
        for _, row in edf.iterrows():
            try:
                total = row[wins_col] + row[losses_col] + row[draws_col]
            except TypeError:
                continue
            if total > 0:
                win_rate = (row[wins_col] + 0.5 * row[draws_col]) / total
                scores.append(win_rate)

        if scores:
            w = weights[-len(scores):]
            w = [x / sum(w) for x in w]
            form[str(entity)] = sum(s * wt for s, wt in zip(scores, w))

    return form


def _apply_form(probs: dict[str, float], form: dict[str, float]) -> dict[str, float]:
    """Apply a ±10% form multiplier to ELO-derived probabilities, then renormalise.
    Entities with no form data use the neutral 0.5 (multiplier 1.0)."""
    if not probs:
        return probs
    adjusted = {e: p * (0.9 + form.get(e, 0.5) * 0.2) for e, p in probs.items()}
    total = sum(adjusted.values()) or 1.0
    return {e: v / total for e, v in adjusted.items()}


def _compute_agreement(model_a_probs: dict[str, float], model_b_probs: dict[str, float]) -> dict[str, float]:
    """Per-entity agreement (0–1) between Model A and Model B. 1.0 when only one
    model ran (no divergence to report)."""
    if not model_b_probs:
        return {e: 1.0 for e in model_a_probs}
    agreement: dict[str, float] = {}
    for e in set(model_a_probs) | set(model_b_probs):
        a, b = model_a_probs.get(e, 0), model_b_probs.get(e, 0)
        if a + b == 0:
            agreement[e] = 0.0
        else:
            mx = max(a, b)
            diff = abs(a - b) / mx if mx > 0 else 0.0
            agreement[e] = max(0.0, 1.0 - diff)
    return agreement


def _attach_agreement(results: list[PredictionResult], agreement: dict[str, float]) -> list[PredictionResult]:
    for r in results:
        r.model_agreement = round(agreement.get(r.entity, 1.0), 3)
    return results


# Empirically-derived host-nation ELO boost used by most academic football models (2.2).
HOME_ADVANTAGE_ELO = 65.0


def _detect_host_boost(df: Any, columns_info: list[dict], entity_col: Optional[str],
                       values: dict[str, float], boost: float = HOME_ADVANTAGE_ELO) -> Optional[str]:
    """If the dataset has an `is_host` column flagging an entity in `values`, add the
    home-advantage ELO boost to it in place and return the host name (2.2)."""
    host_col = next((c["name"] for c in columns_info if str(c["name"]).lower() == "is_host"), None)
    if not host_col or not entity_col or host_col not in df.columns or entity_col not in df.columns:
        return None
    try:
        flagged = df[df[host_col].astype(float) > 0][entity_col].astype(str).unique()
    except Exception:
        return None
    host = next((h for h in flagged if h in values), None)
    if host:
        values[host] = values[host] + boost
    return host


def _interval_for_agreement(agreement: float) -> float:
    """Confidence half-width (pp) keyed to Model A/B agreement (2.3): tight when the
    models agree, wide when they diverge — replacing the flat ±1.5%."""
    if agreement >= 0.85:
        return 1.0
    if agreement >= 0.65:
        return 1.5
    return 2.5


def _results_with_interval(probs: dict[str, float], agreement: dict[str, float],
                           top_n: int = 10) -> list[PredictionResult]:
    """Ranked PredictionResults whose interval width is derived from model agreement
    rather than a flat constant (2.3)."""
    if not probs:
        return []
    total = sum(probs.values()) or 1.0
    norm = {e: v / total for e, v in probs.items()}
    out = []
    for e, p in sorted(norm.items(), key=lambda x: -x[1])[:top_n]:
        pct = round(p * 100, 1)
        agr = agreement.get(e, 1.0)
        w = _interval_for_agreement(agr)
        out.append(PredictionResult(
            entity=e, point_estimate=pct,
            low_pct=round(max(0.1, pct - w), 1), high_pct=round(min(99.9, pct + w), 1),
            confidence="high" if pct > 12 else "medium" if pct > 4 else "low",
            sources_used=["dataset"], model_agreement=round(agr, 3),
        ))
    return out


def build_dataset_models(
    df: Any,
    columns_info: list[dict],
    n_simulations: int = 10000,
    top_n: int = 10,
) -> dict:
    """Run every available mathematical model on the dataset and return their
    probability dicts + ranked results, plus calibration metadata.

    Model A = ELO Monte Carlo, Model B = ELO-Poisson/Dixon-Coles (rho fitted from
    data when scorelines exist, else default). When the dataset has no ELO column,
    Model A falls back to the softmax distribution and Model B is empty. ELO-derived
    probabilities receive a small recent-form adjustment when form data covers >=50%
    of entities. The ensemble is the average of the available math models.

    Returns model_a/b/ensemble probs+results, entity_names, method, per-entity
    model_agreement, and rho/form metadata for the activity log.
    """
    kind, values, col = _dataset_distribution_inputs(df, columns_info, _DATASET_TOP_N)

    if kind == "none":
        return {
            "model_a_probs": {}, "model_a_results": [],
            "model_b_probs": {}, "model_b_results": [],
            "ensemble_probs": {}, "ensemble_results": [],
            "entity_names": [], "method": "none", "agreement": {},
            "rho": -0.107, "rho_fitted": False, "rho_n_matches": 0,
            "form_applied": False, "form_count": 0,
        }

    # Fit Dixon-Coles rho from the data (Improvement 3); default when no scorelines.
    rho, rho_n_matches, rho_fitted = fit_dixon_coles_rho(df, columns_info)

    # Detect entity/time columns up front (used by host detection + form).
    entity_col = None
    time_col = None
    if kind == "elo":
        from .data_analysis import _pick_entity_column, _pick_time_column
        cat_cols = [c["name"] for c in columns_info if c["type"] == "categorical"]
        entity_col = _pick_entity_column(df, cat_cols)
        time_col, _ = _pick_time_column(df, columns_info)

    # Home advantage (2.2) — boost the host nation's ELO before simulating.
    host_entity = None
    stability_note = None
    n_used = n_simulations
    if kind == "elo":
        host_entity = _detect_host_boost(df, columns_info, entity_col, values)
        model_a_probs = run_monte_carlo_tournament(values, n_simulations)
        model_b_probs = run_monte_carlo_poisson(values, n_simulations, rho=rho)
        method = f"elo_monte_carlo({col}) + elo_poisson_dc({col}, rho={rho:.4f})"

        # Prediction stability check (2.5): validate against a 1,000-sim run; if the
        # top entity's probability drifts > 3pp, escalate to 20,000 sims and re-run.
        if model_a_probs:
            top = max(model_a_probs, key=model_a_probs.get)
            valid = run_monte_carlo_tournament(values, 1000)
            drift = abs(model_a_probs.get(top, 0) - valid.get(top, 0)) * 100
            if drift > 3.0:
                n_used = 20000
                model_a_probs = run_monte_carlo_tournament(values, n_used)
                model_b_probs = run_monte_carlo_poisson(values, n_used, rho=rho)
                stability_note = f"Increased to {n_used:,} simulations for stability (drift {drift:.1f}%)"
            else:
                stability_note = f"Prediction validated — stable within {drift:.1f}% across validation run"
    else:
        # No ELO column → single softmax model; Poisson can't run without ratings.
        model_a_probs = _softmax_normalise(values)
        model_b_probs = {}
        method = f"softmax({col})"

    # Recent-form adjustment (Improvement 5) — only for ELO models with enough
    # coverage. Applied to both A and B (same per-entity multiplier), preserving
    # their divergence. entity_col/time_col were detected above.
    form_applied = False
    form_count = 0
    form: dict[str, float] = {}
    if kind == "elo":
        form_cols = _detect_form_columns(columns_info)
        if form_cols and entity_col and time_col:
            form = compute_form_index(df, entity_col, time_col, *form_cols)
            covered = sum(1 for e in values if e in form)
            if values and covered / len(values) >= 0.5:
                model_a_probs = _apply_form(model_a_probs, form)
                if model_b_probs:
                    model_b_probs = _apply_form(model_b_probs, form)
                form_applied = True
                form_count = covered

    if model_b_probs:
        ensemble_probs = {
            t: (model_a_probs.get(t, 0) + model_b_probs.get(t, 0)) / 2
            for t in set(model_a_probs) | set(model_b_probs)
        }
    else:
        ensemble_probs = dict(model_a_probs)

    agreement = _compute_agreement(model_a_probs, model_b_probs)

    if DEBUG:
        print(
            f"[PREDICTION] models built: A={len(model_a_probs)} B={len(model_b_probs)} "
            f"rho={rho:.4f} (fitted={rho_fitted}) form_applied={form_applied}",
            flush=True,
        )

    return {
        "model_a_probs": model_a_probs,
        # Interval widths now derive from model agreement (2.3) rather than a flat ±1.5%.
        "model_a_results": _results_with_interval(model_a_probs, agreement, top_n),
        "model_b_probs": model_b_probs,
        "model_b_results": _results_with_interval(model_b_probs, agreement, top_n),
        "ensemble_probs": ensemble_probs,
        "ensemble_results": _results_with_interval(ensemble_probs, agreement, top_n),
        "entity_names": list(values.keys()),
        "method": method,
        "agreement": agreement,
        "rho": rho,
        "rho_fitted": rho_fitted,
        "rho_n_matches": rho_n_matches,
        "form_applied": form_applied,
        "form_count": form_count,
        # Home advantage (2.2) + stability (2.5) metadata for the activity log / UI.
        "host_entity": host_entity,
        "host_boost": HOME_ADVANTAGE_ELO if host_entity else 0,
        "stability_note": stability_note,
        "n_simulations_used": n_used,
        # Surfaced for Model C (XGBoost) wiring in main.py.
        "elo_dict": dict(values) if kind == "elo" else {},
        "form_indices": form,
        "entity_col": entity_col,
        "time_col": time_col,
    }


# ---------------------------------------------------------------------------
# Model C — XGBoost trained on match history
# ---------------------------------------------------------------------------

# Canonical → accepted aliases for the required match-history columns.
_MATCH_COLS = {
    "date": ("date", "match_date", "datetime"),
    "home_team": ("home_team", "home", "hometeam"),
    "away_team": ("away_team", "away", "awayteam"),
    "home_goals": ("home_goals", "home_score", "hg", "fthg"),
    "away_goals": ("away_goals", "away_score", "ag", "ftag"),
}

_XGB_FEATURES = [
    "elo_diff", "home_form", "away_form", "h2h_home_wins",
    "home_avg_goals_for", "away_avg_goals_for",
    "home_avg_goals_against", "away_avg_goals_against",
]


def xgboost_available() -> bool:
    """True when xgboost imports AND its native library loads. On macOS without
    libomp the import raises XGBoostError (not ImportError), so we catch broadly."""
    try:
        import xgboost  # noqa: F401
        return True
    except Exception:
        return False


def _resolve_match_columns(matches_df: Any) -> Optional[dict]:
    """Map the required logical columns to actual dataframe column names (case-
    insensitive, with common aliases). Returns None if any are missing."""
    lower = {str(c).lower(): c for c in matches_df.columns}
    resolved = {}
    for logical, aliases in _MATCH_COLS.items():
        match = next((lower[a] for a in aliases if a in lower), None)
        if match is None:
            return None
        resolved[logical] = match
    return resolved


def build_match_features(matches_df: Any, elo_df: Any, entity_col: str, time_col: str):
    """Build feature matrix X and target y from match history.

    Returns (X, y) where X has the 8 feature columns in _XGB_FEATURES order and y is
    2=home win / 1=draw / 0=away win. Missing ELO lookups fall back to a team's
    average ELO (then the global mean). Returns empty frames when the required
    columns are absent."""
    import pandas as pd

    cols = _resolve_match_columns(matches_df)
    if cols is None:
        return pd.DataFrame(columns=_XGB_FEATURES), pd.Series(dtype=int)

    m = matches_df.copy()
    m[cols["date"]] = pd.to_datetime(m[cols["date"]], errors="coerce")
    for g in (cols["home_goals"], cols["away_goals"]):
        m[g] = pd.to_numeric(m[g], errors="coerce")
    m = m.dropna(subset=list(cols.values())).sort_values(cols["date"]).reset_index(drop=True)
    if m.empty:
        return pd.DataFrame(columns=_XGB_FEATURES), pd.Series(dtype=int)

    # --- ELO lookup nearest at-or-before a match date, per entity ----------
    elo_lookup, elo_avg, global_mean = _build_elo_lookup(elo_df, entity_col, time_col)

    def elo_at(team: str, when) -> float:
        records = elo_lookup.get(team)
        if records:
            best = None
            for d, val in records:  # records sorted ascending by date
                if d <= when:
                    best = val
                else:
                    break
            if best is not None:
                return best
        return elo_avg.get(team, global_mean)

    # --- rolling per-team history + head-to-head --------------------------
    from collections import defaultdict, deque
    hist = defaultdict(lambda: deque(maxlen=5))   # team -> last 5 {gf,ga,win,draw}
    h2h = defaultdict(lambda: deque(maxlen=5))     # frozenset(pair) -> last 5 (home_team, home_won)

    def form_rate(team):
        h = hist[team]
        if not h:
            return 0.5
        return sum(r["win"] + 0.5 * r["draw"] for r in h) / len(h)

    def avg(team, key):
        h = hist[team]
        return (sum(r[key] for r in h) / len(h)) if h else 1.3

    rows, targets = [], []
    for _, r in m.iterrows():
        home, away = str(r[cols["home_team"]]), str(r[cols["away_team"]])
        hg, ag = int(r[cols["home_goals"]]), int(r[cols["away_goals"]])
        when = r[cols["date"]]

        pair = frozenset((home, away))
        recent_h2h = h2h[pair]
        h2h_home = (sum(1 for ht, won in recent_h2h if ht == home and won) / len(recent_h2h)
                    if recent_h2h else 0.4)

        rows.append({
            "elo_diff": elo_at(home, when) - elo_at(away, when),
            "home_form": form_rate(home),
            "away_form": form_rate(away),
            "h2h_home_wins": h2h_home,
            "home_avg_goals_for": avg(home, "gf"),
            "away_avg_goals_for": avg(away, "gf"),
            "home_avg_goals_against": avg(home, "ga"),
            "away_avg_goals_against": avg(away, "ga"),
        })
        targets.append(2 if hg > ag else 1 if hg == ag else 0)

        # Record the outcome AFTER computing features (no leakage).
        hist[home].append({"gf": hg, "ga": ag, "win": int(hg > ag), "draw": int(hg == ag)})
        hist[away].append({"gf": ag, "ga": hg, "win": int(ag > hg), "draw": int(hg == ag)})
        h2h[pair].append((home, hg > ag))

    X = pd.DataFrame(rows, columns=_XGB_FEATURES)
    y = pd.Series(targets, dtype=int)
    return X, y


def _build_elo_lookup(elo_df: Any, entity_col: str, time_col: str):
    """Return (per-entity [(date, elo)] sorted asc, per-entity avg elo, global mean)."""
    import pandas as pd
    lookup: dict[str, list] = {}
    avg: dict[str, float] = {}
    all_vals: list[float] = []
    rating_col = detect_elo_column([c for c in elo_df.columns])
    if rating_col is None or entity_col not in elo_df.columns:
        return {}, {}, 1500.0

    work = elo_df[[entity_col, time_col, rating_col]].copy() if time_col in elo_df.columns else None
    if work is None:
        # No time column — use each entity's mean rating only.
        for ent, grp in elo_df.groupby(entity_col):
            vals = pd.to_numeric(grp[rating_col], errors="coerce").dropna()
            if len(vals):
                avg[str(ent)] = float(vals.mean())
                all_vals.extend(vals.tolist())
        return {}, avg, (sum(all_vals) / len(all_vals) if all_vals else 1500.0)

    # Convert time to datetime (year ints → Jan 1).
    dt = pd.to_datetime(work[time_col], errors="coerce")
    if dt.isna().all():
        dt = pd.to_datetime(work[time_col].astype(str), format="%Y", errors="coerce")
    work["_dt"] = dt
    work[rating_col] = pd.to_numeric(work[rating_col], errors="coerce")
    work = work.dropna(subset=["_dt", rating_col])

    for ent, grp in work.groupby(entity_col):
        g = grp.sort_values("_dt")
        recs = list(zip(g["_dt"].tolist(), g[rating_col].tolist()))
        lookup[str(ent)] = recs
        avg[str(ent)] = float(g[rating_col].mean())
        all_vals.extend(g[rating_col].tolist())

    global_mean = sum(all_vals) / len(all_vals) if all_vals else 1500.0
    return lookup, avg, global_mean


_MODEL_CACHE_DIR = "data/models"


def _training_hash(X: Any, y: Any) -> str:
    """Stable hash of the training data so identical match-history CSVs reuse a
    cached model (2.6)."""
    import hashlib
    try:
        import pandas as pd
        h = pd.util.hash_pandas_object(X, index=False).values.tobytes()
        h += pd.util.hash_pandas_object(y, index=False).values.tobytes()
        return hashlib.sha256(h).hexdigest()[:16]
    except Exception:
        return hashlib.sha256(repr((X, y)).encode()).hexdigest()[:16]


def train_xgboost_model(X: Any, y: Any):
    """Train an XGBoost classifier on match history (2.6): disk-cached by training
    hash, with early stopping on a 20% validation split. Returns None if xgboost is
    unavailable (e.g. missing OpenMP runtime) or the data is unusable."""
    try:
        from xgboost import XGBClassifier
    except Exception:
        return None
    if X is None or len(X) == 0 or y is None or len(y) == 0:
        return None

    import os
    import pickle
    os.makedirs(_MODEL_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(_MODEL_CACHE_DIR, f"{_training_hash(X, y)}.pkl")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass  # corrupt cache — retrain

    try:
        # 20% validation split for early stopping (stratified when feasible).
        eval_set = None
        Xt, yt = X, y
        try:
            from sklearn.model_selection import train_test_split
            strat = y if y.nunique() > 1 and y.value_counts().min() >= 2 else None
            Xt, Xv, yt, yv = train_test_split(X, y, test_size=0.2, random_state=42, stratify=strat)
            eval_set = [(Xv, yv)]
        except Exception:
            pass  # too little data to split — train on everything, no early stopping

        model = XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.1, subsample=0.8,
            random_state=42, eval_metric="mlogloss", verbosity=0,
            early_stopping_rounds=10 if eval_set else None,
        )
        if eval_set:
            model.fit(Xt, yt, eval_set=eval_set, verbose=False)
        else:
            model.fit(Xt, yt)

        try:
            with open(cache_path, "wb") as f:
                pickle.dump(model, f)
        except Exception:
            pass
        return model
    except Exception as e:
        print(f"[model_c] training failed: {e}", flush=True)
        return None


def xgboost_feature_importance(model, top: int = 5) -> list[dict]:
    """Top feature importances (gain) as [{feature, pct}], descending (2.6)."""
    try:
        importances = list(getattr(model, "feature_importances_", []))
    except Exception:
        return []
    if not importances:
        return []
    total = sum(importances) or 1.0
    paired = sorted(zip(_XGB_FEATURES, importances), key=lambda x: -x[1])
    return [{"feature": f, "pct": round(v / total * 100, 1)} for f, v in paired[:top] if v > 0]


def predict_match_xgboost(model, home_team: str, away_team: str,
                          elo_diff: float, home_form: float, away_form: float):
    """Return (p_home_win, p_draw, p_away_win) for a single match. Robust to a
    model trained on fewer than three outcome classes (maps via model.classes_)."""
    import pandas as pd
    features = pd.DataFrame([{
        "elo_diff": elo_diff,
        "home_form": home_form,
        "away_form": away_form,
        "h2h_home_wins": 0.4,           # neutral defaults for a simulated match
        "home_avg_goals_for": 1.5,
        "away_avg_goals_for": 1.3,
        "home_avg_goals_against": 1.1,
        "away_avg_goals_against": 1.2,
    }], columns=_XGB_FEATURES)
    proba = model.predict_proba(features)[0]
    classes = list(getattr(model, "classes_", [0, 1, 2]))

    def p(cls):
        return float(proba[classes.index(cls)]) if cls in classes else 0.0

    return p(2), p(1), p(0)


def run_monte_carlo_xgboost(teams: dict[str, float], model, form_indices: dict[str, float],
                            n_simulations: int = 10000) -> dict[str, float]:
    """Tournament simulation (same group-stage → knockout bracket as Models A/B)
    where knockout ties are resolved by the XGBoost match predictor. Per-pair
    predictions are cached since their features are deterministic."""
    if model is None or not teams:
        return {}
    cache: dict[tuple, tuple] = {}

    def knockout(a: str, b: str, elos: dict[str, float]) -> str:
        key = (a, b)
        if key not in cache:
            elo_diff = elos.get(a, 1500) - elos.get(b, 1500)
            pw, pd_, _pl = predict_match_xgboost(
                model, a, b, elo_diff, form_indices.get(a, 0.5), form_indices.get(b, 0.5)
            )
            cache[key] = (pw, pd_)
        pw, pd_ = cache[key]
        r = random.random()
        if r < pw:
            return a
        if r < pw + pd_:
            return random.choice([a, b])  # draw → penalties
        return b

    return _run_tournament(teams, n_simulations, knockout)


# ---------------------------------------------------------------------------
# Source extraction — internet
# ---------------------------------------------------------------------------

def _extract_percentages_window(text: str, entity_names: list[str], window: int = 500) -> dict[str, float]:
    """Wider-window fallback: scan for any percentage within `window` chars of an
    entity name (either side). Looser than extract_percentages — used only when the
    tighter pass finds nothing, so a noisy match beats no signal at all."""
    results: dict[str, float] = {}
    if not text:
        return results
    for name in entity_names:
        pat = (
            rf"(?:{re.escape(name)}.{{0,{window}}}?(\d+(?:\.\d+)?)\s*%)"
            rf"|(?:(\d+(?:\.\d+)?)\s*%.{{0,{window}}}?{re.escape(name)})"
        )
        vals = []
        for m in re.findall(pat, text, re.IGNORECASE | re.DOTALL):
            raw = m[0] or m[1]
            if raw and 0.5 < float(raw) < 99:
                vals.append(float(raw))
        if vals:
            results[name] = (sum(vals) / len(vals)) / 100
    return results


def extract_internet_probs(
    internet_findings: Optional[dict],
    entity_names: list[str],
) -> dict[str, float]:
    """Run extract_percentages over the combined text of all internet searches."""
    if not internet_findings or not entity_names:
        return {}
    parts = []
    for s in internet_findings.get("searches", []) or []:
        if s.get("content"):
            parts.append(s["content"])
    if not parts:
        # Backward-compatible single-content shape.
        combined = internet_findings.get("combined_summary") or internet_findings.get("content") or ""
        if combined:
            parts.append(combined)
    text = "\n\n".join(parts)
    probs = extract_percentages(text, entity_names)
    # Fix D — if the tight extraction found nothing, retry with a wider window so a
    # dataset whose research text spaces numbers further from names still yields
    # internet signal instead of an empty dict.
    if not probs:
        probs = _extract_percentages_window(text, entity_names, window=500)
    return probs


# ---------------------------------------------------------------------------
# Source extraction — council
# ---------------------------------------------------------------------------

def extract_council_probs(
    stage1_results: list[dict],
    entity_names: list[str],
    aggregate_rankings: Optional[list[dict]] = None,
) -> dict[str, float]:
    """Average per-model extracted probabilities, weighted by Stage 2 peer rank.

    aggregate_rankings is the sorted list of {model, average_rank, ...} produced by
    council.calculate_aggregate_rankings (lower average_rank = better). The weight
    for each model is 1/average_rank, so the best-reviewed model counts most. When
    rankings are unavailable, all models are weighted equally.
    """
    if not stage1_results or not entity_names:
        return {}

    rank_by_model: dict[str, float] = {}
    for r in (aggregate_rankings or []):
        model = r.get("model")
        avg = r.get("average_rank")
        if model and avg:
            rank_by_model[model] = avg

    weighted_sum: dict[str, float] = {}
    weight_total: dict[str, float] = {}

    for resp in stage1_results:
        model = resp.get("model", "")
        text = resp.get("response", "") or ""
        per_model = extract_percentages(text, entity_names)
        if not per_model:
            continue
        avg_rank = rank_by_model.get(model)
        weight = (1.0 / avg_rank) if avg_rank else 1.0
        for entity, prob in per_model.items():
            weighted_sum[entity] = weighted_sum.get(entity, 0.0) + prob * weight
            weight_total[entity] = weight_total.get(entity, 0.0) + weight

    return {
        e: weighted_sum[e] / weight_total[e]
        for e in weighted_sum
        if weight_total.get(e)
    }


# ---------------------------------------------------------------------------
# Orchestration + formatting helpers used by main.py
# ---------------------------------------------------------------------------

def predictions_to_table(results: list[PredictionResult]) -> list[dict]:
    """Serialise PredictionResult dataclasses to JSON-friendly dicts for the
    report and the frontend."""
    return [asdict(r) for r in results]


# ---------------------------------------------------------------------------
# Prediction explanation charts (Part 3)
# ---------------------------------------------------------------------------

# Per-source colours, kept consistent across every explanation chart.
_C_DATASET = "#4a90e2"   # blue
_C_INTERNET = "#9b59e0"  # purple
_C_COUNCIL = "#5cb85c"   # green
_CONF_COLOR = {"high": "#5ad08a", "medium": "#e3c34d", "low": "#e36a6a"}


def _fig_to_dict(fig) -> dict:
    """Serialise a Plotly figure to a plain {data, layout} dict for the frontend."""
    import json as _json
    import plotly.io as pio
    return _json.loads(pio.to_json(fig))


def generate_prediction_charts(
    prediction_results: list[PredictionResult],
    dataset_probs: dict[str, float],
    internet_probs: dict[str, float],
    council_probs: dict[str, float],
    df: Any = None,
    columns_info: Optional[list[dict]] = None,
    n_simulations: int = 1000,
    model_a_probs: Optional[dict[str, float]] = None,
    model_b_probs: Optional[dict[str, float]] = None,
    agreement: Optional[dict[str, float]] = None,
) -> list[dict]:
    """Build the five charts that explain HOW each probability was calculated.

    Returns a list of chart dicts ({id, title, type, plotly_json, note?, height?}).
    Each chart is built defensively — a failure in one never blocks the others or
    the pipeline. Plotly is imported lazily so the pure-math core stays importable
    without it.
    """
    if not prediction_results:
        return []

    try:
        import plotly.graph_objects as go
    except Exception as e:  # plotly missing — skip charts entirely
        print(f"[prediction_charts] plotly unavailable: {e}", flush=True)
        return []

    charts: list[dict] = []
    top = prediction_results[:10]
    top8 = prediction_results[:8]

    def pct(d: dict, e: str) -> float:
        return round(d.get(e, 0) * 100, 1)

    # Chart 1 — Algorithm weight breakdown (donut).
    try:
        fig = go.Figure(go.Pie(
            labels=["Dataset ELO simulation (40%)", "Internet research consensus (35%)", "AI council agreement (25%)"],
            values=[40, 35, 25],
            hole=0.55,
            marker=dict(colors=[_C_DATASET, _C_INTERNET, _C_COUNCIL]),
            textinfo="label+percent",
            sort=False,
        ))
        fig.update_layout(title="How the prediction was calculated", template="plotly_dark", showlegend=False)
        charts.append({"id": "weight_breakdown", "title": "How the prediction was calculated",
                       "type": "donut", "plotly_json": _fig_to_dict(fig), "height": 250})
    except Exception as e:
        print(f"[prediction_charts] chart1 failed: {e}", flush=True)

    # Chart 2 — What each source said (grouped bar, top 8).
    try:
        ents = [r.entity for r in top8]
        ds = [pct(dataset_probs, e) for e in ents]
        ip = [pct(internet_probs, e) for e in ents]
        cp = [pct(council_probs, e) for e in ents]
        note_text = lambda vals: ["no data from this source" if v == 0 else "" for v in vals]
        fig = go.Figure()
        fig.add_bar(name="Dataset", x=ents, y=ds, marker_color=_C_DATASET,
                    text=note_text(ds), textposition="outside")
        fig.add_bar(name="Internet", x=ents, y=ip, marker_color=_C_INTERNET,
                    text=note_text(ip), textposition="outside")
        fig.add_bar(name="Council", x=ents, y=cp, marker_color=_C_COUNCIL,
                    text=note_text(cp), textposition="outside")
        fig.update_layout(barmode="group", title="Source comparison — why we disagree",
                          xaxis_title="Entity", yaxis_title="Probability %", template="plotly_dark")
        charts.append({"id": "source_comparison", "title": "Source comparison — why we disagree",
                       "type": "bar", "plotly_json": _fig_to_dict(fig), "height": 300})
    except Exception as e:
        print(f"[prediction_charts] chart2 failed: {e}", flush=True)

    # Chart 3 — Final probability with confidence (horizontal range bars + point).
    try:
        rs = list(reversed(top))  # so the strongest entity sits at the top
        fig = go.Figure()
        for r in rs:
            color = _CONF_COLOR.get(r.confidence, _CONF_COLOR["medium"])
            fig.add_trace(go.Bar(
                y=[r.entity], x=[round(r.high_pct - r.low_pct, 2)], base=[r.low_pct],
                orientation="h", marker_color=color, showlegend=False,
                hovertemplate=f"{r.entity}: {r.low_pct}–{r.high_pct}%<extra></extra>",
            ))
        fig.add_trace(go.Scatter(
            y=[r.entity for r in rs], x=[r.point_estimate for r in rs],
            mode="markers", marker=dict(symbol="line-ns-open", size=14, color="white", line=dict(width=2)),
            showlegend=False, hovertemplate="point estimate: %{x}%<extra></extra>",
        ))
        fig.update_layout(title="Final computed probability ranges", xaxis_title="Probability %",
                          template="plotly_dark", bargap=0.35)
        charts.append({"id": "confidence_ranges", "title": "Final computed probability ranges",
                       "type": "bar", "plotly_json": _fig_to_dict(fig), "height": 300,
                       "note": "Ranges show ±1.5% uncertainty. Wider ranges indicate less data confidence."})
    except Exception as e:
        print(f"[prediction_charts] chart3 failed: {e}", flush=True)

    # Chart 4 — ELO rating history for top 5 (line) — only if a time + rating column exist.
    try:
        elo_chart = _build_elo_trajectory_chart(go, df, columns_info, [r.entity for r in top[:5]])
        if elo_chart:
            charts.append(elo_chart)
    except Exception as e:
        print(f"[prediction_charts] chart4 failed: {e}", flush=True)

    # Chart 5 — Full prediction breakdown (go.Table, top 8). Columns: Entity,
    # Model A, Model B, Ensemble, Internet, Council, Final range, Agreement.
    try:
        a_probs = model_a_probs or {}
        b_probs = model_b_probs or {}
        agree = agreement or {}
        ents = [r.entity for r in top8]

        def cell(d: dict, e: str) -> str:
            return f"{pct(d, e)}%" if d.get(e) else "–"

        cells = [
            ents,
            [cell(a_probs, e) for e in ents],
            [cell(b_probs, e) for e in ents],
            [cell(dataset_probs, e) for e in ents],  # ensemble drives dataset_probs
            [cell(internet_probs, e) for e in ents],
            [cell(council_probs, e) for e in ents],
            [f"{r.low_pct}–{r.high_pct}%" for r in top8],
            [f"{round(agree.get(r.entity, 1.0) * 100)}%" for r in top8],
        ]
        row_fill = [["#161616" if i % 2 else "#1f1f1f" for i in range(len(ents))]]
        fig = go.Figure(go.Table(
            header=dict(
                values=["Entity", "Model A", "Model B", "Ensemble", "Internet", "Council", "Final range", "Agreement"],
                fill_color="#1c2a44", font=dict(color="white", size=11), align="left", height=30,
            ),
            cells=dict(
                values=cells, fill_color=row_fill * 8, font=dict(color="#d6d6d6", size=11),
                align="left", height=26,
            ),
        ))
        fig.update_layout(title="Prediction confidence breakdown", template="plotly_dark",
                          margin=dict(l=10, r=10, t=40, b=10))
        charts.append({"id": "breakdown_table", "title": "Prediction confidence breakdown",
                       "type": "table", "plotly_json": _fig_to_dict(fig), "height": 60 + 28 * len(ents)})
    except Exception as e:
        print(f"[prediction_charts] chart5 failed: {e}", flush=True)

    return charts


def _build_elo_trajectory_chart(go, df: Any, columns_info: Optional[list[dict]], entities: list[str]) -> Optional[dict]:
    """Chart 4 — ELO trend over the last 10 years for the top predicted entities.

    Returns None when the dataset has no usable time + rating column (so the chart
    is simply omitted rather than faked)."""
    if df is None or not columns_info or not entities:
        return None
    import pandas as pd
    from .data_analysis import _pick_entity_column, _pick_time_column

    num_cols = [c["name"] for c in columns_info if c["type"] == "numeric"]
    cat_cols = [c["name"] for c in columns_info if c["type"] == "categorical"]
    rating_col = detect_elo_column(num_cols)
    entity_col = _pick_entity_column(df, cat_cols)
    time_col, time_kind = _pick_time_column(df, columns_info)
    if not (rating_col and entity_col and time_col) or rating_col not in df.columns:
        return None

    work = df[[entity_col, rating_col, time_col]].dropna().copy()
    if time_kind == "datetime":
        work["_period"] = pd.to_datetime(work[time_col]).dt.year
    else:
        work["_period"] = pd.to_numeric(work[time_col], errors="coerce")
    work = work.dropna(subset=["_period"])
    if work.empty:
        return None
    work["_period"] = work["_period"].astype(int)

    latest_year = int(work["_period"].max())
    cutoff = latest_year - 10
    work = work[work["_period"] >= cutoff]

    fig = go.Figure()
    palette = ["#4a90e2", "#5cb85c", "#e3c34d", "#9b59e0", "#e36a6a"]
    plotted = 0
    for i, ent in enumerate(entities):
        sub = work[work[entity_col].astype(str) == str(ent)]
        if sub.empty:
            continue
        series = sub.groupby("_period")[rating_col].mean().sort_index()
        color = palette[i % len(palette)]
        fig.add_trace(go.Scatter(
            x=list(series.index), y=list(series.values), mode="lines+markers",
            name=str(ent), line=dict(color=color, width=2), marker=dict(size=5),
        ))
        # Highlight the most recent value with a larger marker.
        fig.add_trace(go.Scatter(
            x=[series.index[-1]], y=[series.values[-1]], mode="markers",
            marker=dict(color=color, size=11, symbol="circle", line=dict(color="white", width=1.5)),
            showlegend=False, hovertemplate=f"{ent}: %{{y:.0f}} (%{{x}})<extra></extra>",
        ))
        plotted += 1
    if plotted == 0:
        return None

    # "Tournament start" annotation at 2026 when the axis spans it.
    if cutoff <= 2026 <= latest_year + 1:
        fig.add_vline(x=2026, line_dash="dash", line_color="rgba(255,255,255,0.4)",
                      annotation_text="Tournament start", annotation_position="top")

    fig.update_layout(title="Why these teams rank where they do", xaxis_title="Year",
                      yaxis_title=rating_col, template="plotly_dark")
    return {"id": "elo_trajectory", "title": "Why these teams rank where they do",
            "type": "line", "plotly_json": _fig_to_dict(fig), "height": 300}


_SOURCE_LABELS = {"dataset": "Data", "internet": "Web", "council": "Council"}


def _top5_lines(table: list[dict]) -> str:
    """Format the top 5 rows of a prediction table as 'Entity: low%-high%' lines."""
    if not table:
        return "  (none)"
    return "\n".join(f"  {p['entity']}: {p['low_pct']}%-{p['high_pct']}%" for p in table[:5])


def format_chairman_prediction_block(prediction_table: list[dict], suite: dict | None = None) -> str:
    """Build the system-instruction prefix injected into the chairman prompt.

    When `suite` is provided (model_a/model_b/ensemble/combined tables), the
    chairman is told it has THREE mathematical model outputs to explain — and is
    asked to explain where Model A and Model B diverge. Returns "" when there are
    no computed predictions so the chairman prompt is left untouched.
    """
    if not prediction_table and not (suite and suite.get("combined")):
        return ""

    lines = []
    for p in prediction_table:
        lines.append(f"  {p['entity']}: {p['low_pct']}%-{p['high_pct']}%")
    table_text = "\n".join(lines) if lines else _top5_lines((suite or {}).get("combined", []))

    # Change 5 — multi-model block. Only added when a suite with both math models
    # is available; otherwise the single-table wording below still applies.
    suite_block = ""
    if suite and suite.get("model_a"):
        suite_block = (
            "You have been provided with three mathematical model predictions:\n\n"
            f"Model A (ELO Monte Carlo):\n{_top5_lines(suite.get('model_a', []))}\n\n"
            f"Model B (ELO-Poisson/Dixon-Coles):\n{_top5_lines(suite.get('model_b', []))}\n\n"
            f"Ensemble average:\n{_top5_lines(suite.get('ensemble', []))}\n\n"
            f"Combined (with internet + council):\n{_top5_lines(suite.get('combined', []))}\n\n"
            "Where Model A and B DISAGREE significantly on an entity, explain WHY. "
            "Model A only considers win/loss. Model B simulates scorelines and "
            "low-scoring game patterns. A big divergence between them suggests that "
            "entity benefits from or is hurt by tournament variance (close games vs "
            "dominant wins).\n\n"
            "Do not change any of these numbers. Explain them.\n\n"
        )

    return (
        suite_block +
        "The deterministic prediction algorithm has computed the following "
        "probability estimates from the dataset (40%), internet research (35%), "
        "and council responses (25%). These numbers are mathematically derived — "
        "do not change them or suggest different values. Your role is to write a "
        "clear synthesis explaining WHY these probabilities make sense given the "
        "evidence, what the key factors are, and what could change them.\n\n"
        "COMPUTED PREDICTIONS:\n"
        f"{table_text}\n\n"
        "Write your synthesis around these numbers.\n\n"
        # Fix 5 — the chairman must always surface the dataset-derived numbers.
        "You have been provided with DATASET-BASED PREDICTIONS computed "
        "algorithmically from the uploaded data. These are real numbers, not "
        "estimates. You must include them in your response.\n\n"
        "Even if internet research is incomplete or unavailable, you must still "
        "provide these dataset-based predictions to the user. The user uploaded "
        "data specifically to get predictions from it. Refusing to report "
        "predictions when the data contains them is a failure to answer the "
        "question.\n\n"
        "Format your prediction table using the computed numbers provided. Do not "
        "invent different numbers. Do not say you cannot provide estimates.\n\n"
        # Fix 3d — mandatory closing table, fixed format.
        "FINAL INSTRUCTION: Your response MUST end with a section titled "
        "'PREDICTION TABLE' formatted exactly as:\n\n"
        "| Team | Probability | Confidence |\n"
        "|------|-------------|------------|\n"
        "| [name] | [X.X-Y.Y%] | [High/Medium/Low] |\n\n"
        "Use the algorithmic predictions provided above. If some teams are confirmed "
        "eliminated per the CONFIRMED FACTS section, note that next to their name but "
        "still show the pre-elimination baseline. This table is mandatory. End every "
        "response with it."
    )
