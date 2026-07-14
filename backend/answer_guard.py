"""Numeric grounding for assistant answers (Night 3, Phase 0a/0d).

The engine executes literally; the model then narrates freely. This closes the
narration gap with a hard, code-level check (not a prompt):

  - Every number in the answer must appear in the executed result, OR be the
    output of an arithmetic derivation the answer explicitly shows.
  - The answer must not restate a figure under a NEW time unit (weekly/daily/…)
    that the data doesn't provide, without showing the conversion.

"Your weekly earnings are 480506" fails both readings: 480506 is a monthly
figure relabelled weekly with no arithmetic. `check_answer` catches it.
"""
import re

# question/answer period units → canonical
_UNIT_WORDS = {
    "weekly": "week", "per week": "week", "a week": "week", "/week": "week",
    "daily": "day", "per day": "day", "a day": "day", "/day": "day",
    "hourly": "hour", "per hour": "hour",
    "annually": "year", "annual": "year", "yearly": "year", "per year": "year",
    "a year": "year", "per annum": "year",
    "monthly": "month", "per month": "month", "a month": "month",
    "quarterly": "quarter", "per quarter": "quarter",
}
# an explicit conversion is shown → derived numbers are allowed
_ARITH = re.compile(r"[÷/*×]|\bdivided by\b|\bmultiplied by\b|\btimes\b|\bx\s*\d")
# a minus only counts as a sign when NOT glued to a preceding word char / dot /
# hyphen, so an ISO date like 2026-06-01 isn't read as the numbers -6 and -1.
_NUM = re.compile(r"(?<![\w.\-])-?\d[\d,]*(?:\.\d+)?")
_DATEISH = re.compile(r"\b\d{4}-\d{1,2}(?:-\d{1,2})?\b|\b\d{1,2}:\d{2}\b")
_DECLINE = ("can't", "cannot", "can not", "not able", "unable", "no way to",
            "doesn't have", "does not have", "isn't in", "is not in", "not in this data",
            "not available", "would need", "assume", "assuming")


def _numbers(text: str) -> list[float]:
    text = _DATEISH.sub(" ", text or "")  # dates/times aren't metrics
    out = []
    for m in _NUM.findall(text):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def _result_values(result: dict) -> set[float]:
    vals = set()
    for row in (result or {}).get("rows", []) or []:
        for v in (row.values() if isinstance(row, dict) else []):
            try:
                vals.add(round(float(v), 2))
            except (TypeError, ValueError):
                pass
    # Guard-supplied values (the corrected latest-period figure and the raw sum
    # named in the warning) are legitimately computed numbers the answer may cite.
    for k in ("corrected", "raw_sum"):
        if isinstance((result or {}).get(k), (int, float)):
            vals.add(round(float(result[k]), 2))
    return vals


def _grounded(n: float, values: set[float]) -> bool:
    # allow a small relative tolerance for rounding/formatting
    return any(abs(n - v) <= max(1.0, abs(v) * 0.01) for v in values)


def check_answer(question: str, reply: str, result: dict,
                 data_period: str = None) -> tuple[bool, str]:
    """Return (ok, reason). ok=False means the answer states something it cannot
    defend from the executed result and must be refused/re-asked.

    `data_period` (day|week|month|quarter|year) is the granularity the data
    actually carries; when the user asks for a *different* period, the answer
    must convert explicitly or decline — not deflect to a number."""
    reply = reply or ""
    q = (question or "").lower()
    r = reply.lower()
    has_arith = bool(_ARITH.search(reply))
    declines = any(p in r for p in _DECLINE)

    # --- invented unit (Phase 0d) ----------------------------------------------
    asked_unit = next((u for kw, u in _UNIT_WORDS.items() if kw in q), None)
    stated_unit = next((u for kw, u in _UNIT_WORDS.items() if kw in r), None)
    # (a) restating a number under the SAME asked unit with no conversion shown.
    if asked_unit and stated_unit == asked_unit and not has_arith:
        return False, (f"the answer states a '{asked_unit}ly' figure but the data isn't in "
                       f"{asked_unit}s and no unit conversion was shown")
    # (b) asked for a period the data doesn't carry → must convert or decline,
    #     never deflect to some other number/unit.
    if asked_unit and data_period and asked_unit != data_period and not has_arith and not declines:
        return False, (f"the question asks for a {asked_unit}ly figure but the data is "
                       f"{data_period}ly; convert it explicitly or say it can't be answered")

    # --- numeric grounding: every stated number must be in the result or derived
    values = _result_values(result)
    for n in _numbers(reply):
        if 1900 <= n <= 2100 and float(n).is_integer():
            continue  # a year/period label, not a metric
        if _grounded(n, values):
            continue
        if has_arith:
            continue  # a shown derivation may introduce intermediate/result numbers
        return False, f"the number {n:g} is not in the computed result and no derivation was shown"

    return True, "ok"
