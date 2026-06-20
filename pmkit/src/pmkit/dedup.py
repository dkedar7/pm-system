"""Near-duplicate detection for discovered candidates.

The backlog handles *exact* dedup via the normalized (target, dedup_key). This module adds
*near*-duplicate matching so two differently-worded reports of the same problem on the same
target collapse into one item (evidence accrues rather than duplicating). Pure functions,
no I/O — fully unit-testable.
"""

from __future__ import annotations

import re
from typing import Optional

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# A small stopword set keeps generic words from inflating similarity.
_STOP = {
    "the", "a", "an", "to", "of", "and", "or", "in", "on", "for", "is", "are",
    "be", "with", "no", "not", "it", "this", "that", "when", "how", "i", "we",
    "you", "my", "should", "would", "could", "can", "have", "has", "add", "support",
}

DEFAULT_THRESHOLD = 0.6


def token_set(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP and len(t) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def similarity(text_a: str, text_b: str) -> float:
    """Token-set Jaccard over the combined title+problem text of two candidates."""
    return jaccard(token_set(text_a), token_set(text_b))


def _candidate_text(item: dict) -> str:
    return f"{item.get('title', '')} {item.get('problem', '')}"


def find_near_duplicate(
    cand: dict,
    existing: list[dict],
    threshold: float = DEFAULT_THRESHOLD,
) -> Optional[dict]:
    """Return the most similar existing item above ``threshold``, or None.

    ``cand`` and each ``existing`` item are dicts with 'title' and 'problem'.
    """
    cand_text = _candidate_text(cand)
    best: Optional[dict] = None
    best_score = threshold
    for item in existing:
        score = similarity(cand_text, _candidate_text(item))
        if score >= best_score:
            best = item
            best_score = score
    return best
