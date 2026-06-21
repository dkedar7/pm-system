"""The kill-test survival rule — the single, tested source of truth.

A blunt "prune on >= N refutes" majority let a vendor-already-shipped idea survive on a
2-of-4 split (the Dash->MCP case). The fix: the **already-solved** axis is *dispositive* —
a confident already-solved refutation prunes a candidate regardless of how the other axes
voted (if the thing already exists, nothing else matters). Otherwise the strict majority
applies. The pm-run orchestrator calls this via `pmkit backlog killtest --decide` rather
than re-implementing the rule, so there's no JS/Python drift.
"""

from __future__ import annotations

SOLVED_AXIS = "already-solved"
SOLVED_CONFIDENCE = 0.7  # an already-solved refute at/above this is a hard kill


def decide_survival(verdicts: list[dict], prune_at: int = 3) -> tuple[bool, str]:
    """Return (survived, reason) for a candidate given its per-axis kill-test verdicts.

    Each verdict is a dict with at least ``verdict`` ('refute'|'survive') and ``axis``;
    ``confidence`` (0..1) is optional and defaults to 1.0.
    """
    refutes = [v for v in verdicts if v.get("verdict") == "refute"]
    for v in refutes:
        if v.get("axis") == SOLVED_AXIS and float(v.get("confidence", 1.0)) >= SOLVED_CONFIDENCE:
            reason = (v.get("reason") or "").strip()
            return False, f"pruned: already-solved is dispositive ({reason})"[:200]
    n = len(refutes)
    if n >= prune_at:
        return False, f"pruned: majority refute ({n}/{len(verdicts)})"
    return True, f"survived ({n} refute(s); need {prune_at}, no dispositive already-solved)"
