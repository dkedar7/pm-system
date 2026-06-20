"""Discovery orchestration: run connectors, dedup, and write candidates to the backlog.

Connectors are injectable so the orchestration is testable without the network. Each
candidate is matched against the existing backlog (near-duplicate by similarity, exact by
the backlog's own key) — a match attaches evidence, a miss creates a new item. Candidates
with weak engagement or no source are flagged low-confidence rather than dropped (R3).
"""

from __future__ import annotations

from typing import Optional

from .backlog import Backlog
from .connectors import get_connectors
from .connectors.base import Config, ConnectorError
from .dedup import DEFAULT_THRESHOLD, find_near_duplicate


def run_discovery(
    backlog: Backlog,
    target: str,
    connectors: Optional[list] = None,
    cfg: Optional[Config] = None,
    limit: int = 25,
    near_threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    cfg = cfg or Config.from_env()
    connectors = connectors if connectors is not None else get_connectors()

    summary = {
        "target": target,
        "fetched": 0,
        "new": 0,
        "merged": 0,
        "low_confidence": 0,
        "by_source": {},
        "skipped": [],
    }

    # Seed with existing items for this target so re-runs dedup across runs (R10).
    current = [it for it in backlog.list() if it["target"] == target]

    for conn in connectors:
        ok, reason = conn.available(cfg)
        if not ok:
            summary["skipped"].append({"source": conn.name, "reason": reason})
            continue
        try:
            cands = conn.fetch(target, cfg, limit)
        except ConnectorError as e:
            summary["skipped"].append({"source": conn.name, "reason": str(e)})
            continue
        except Exception as e:  # defensive: a connector bug must not abort the run
            summary["skipped"].append({"source": conn.name, "reason": f"unexpected: {e}"})
            continue

        summary["by_source"][conn.name] = len(cands)
        for cand in cands:
            summary["fetched"] += 1
            low_conf = cand["engagement"] < cfg.min_engagement or not cand["source"].get("url")
            dup = find_near_duplicate(cand, current, near_threshold)
            if dup is not None:
                backlog.attach_evidence(dup["id"], [cand["source"]])
                summary["merged"] += 1
                continue
            opp_id = backlog.add_candidate(
                target=target,
                title=cand["title"],
                problem=cand["problem"],
                sources=[cand["source"]],
                low_confidence=low_conf,
            )
            summary["new"] += 1
            if low_conf:
                summary["low_confidence"] += 1
            # Make this candidate visible to later ones in the same run.
            current.append({"id": opp_id, "title": cand["title"], "problem": cand["problem"]})

    return summary
