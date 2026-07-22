"""The research status bar must never drop to 0% mid-run. The pipeline persists
`current_stage` under two naming schemes — underscore keys
(update_conversation_status: 'council_stage1'…) and the human `_advance` labels
('stage 1'…) — and BOTH end up read by the status poller. Every active stage
must therefore resolve to a non-zero progress in `_PROGRESS_PCT`.
"""
from backend.main import _PROGRESS_PCT

# Human labels emitted by _advance() in the pipeline (backend/main.py).
_ADVANCE_LABELS = [
    "initialising", "data analysis", "internet research", "prediction engine",
    "stage 1", "stage 2", "stage 3", "report",
]
# Underscore keys persisted by update_conversation_status().
_STATUS_KEYS = [
    "data_analysis", "research", "council_stage1", "council_stage2",
    "council_stage3", "synthesis",
]


def test_every_active_stage_has_nonzero_progress():
    missing = [s for s in _ADVANCE_LABELS + _STATUS_KEYS if _PROGRESS_PCT.get(s, 0) <= 0]
    assert not missing, f"stages that render the bar at 0% mid-run: {missing}"


def test_progress_is_monotonic_along_the_pipeline():
    # The order a run actually moves through; percentages must not go backwards.
    order = ["initialising", "data analysis", "internet research", "prediction engine",
             "stage 1", "stage 2", "stage 3", "report", "done"]
    pcts = [_PROGRESS_PCT[s] for s in order]
    assert pcts == sorted(pcts), f"progress goes backwards: {list(zip(order, pcts))}"
