"""RICE value-per-effort scoring.

The composite is the classic RICE form: (reach * impact * confidence) / effort.

- reach:       how many users/instances feel this (>= 0)
- impact:      per-instance value when addressed (>= 0)
- confidence:  0..1 multiplier on how trustworthy the estimate is
- effort:      cost to build, in arbitrary effort units (> 0)

Sub-scores are stored separately on the backlog item so the weighting can become
tunable later (a deferred goal); this module is the single source of truth for the
composite so the CLI and the reranker agree.
"""

from __future__ import annotations


class RiceError(ValueError):
    """Raised when RICE inputs are invalid (e.g., non-positive effort)."""


def compute_rice(reach: float, impact: float, confidence: float, effort: float) -> float:
    """Return the RICE composite. Effort must be > 0; confidence is clamped to 0..1.

    Raises RiceError on non-positive effort (division would be undefined) or
    negative reach/impact.
    """
    if effort is None or effort <= 0:
        raise RiceError(f"effort must be > 0, got {effort!r}")
    if reach is None or reach < 0:
        raise RiceError(f"reach must be >= 0, got {reach!r}")
    if impact is None or impact < 0:
        raise RiceError(f"impact must be >= 0, got {impact!r}")
    conf = _clamp01(confidence)
    return (float(reach) * float(impact) * conf) / float(effort)


def _clamp01(value: float) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def rank(items: list[dict]) -> list[dict]:
    """Return items ordered by their ``rice`` value, highest first, None last.

    Pure mirror of the backlog's ``list(sort="score")`` ordering — handy for the
    reranker and for tests, and stable on ties by id.
    """
    def key(it: dict):
        rice = it.get("rice")
        return (rice is None, -(rice or 0.0), it.get("id", 0))

    return sorted(items, key=key)
