"""The listen loop — fold post-launch reactions back into the discovery backlog.

This is what closes the funnel into a loop: after a launch, the reactions (comments,
mentions, threads) are ingested as ``launch-feedback`` candidates through the *same*
dedup/attach path discovery already uses (``backlog.find_existing`` → ``attach_evidence``
or ``add_candidate``), reusing ``Config.min_engagement`` and ``dedup.find_near_duplicate``.
Feedback that echoes a known opportunity accrues as evidence; a genuinely new pain becomes a
new ``new`` candidate the funnel can pick up. Read-only — listening never engages or posts.
"""

from __future__ import annotations

from typing import Optional

from ..backlog import Backlog, make_dedup_key
from ..connectors import get_connectors
from ..connectors.base import Config, ConnectorError
from ..dedup import DEFAULT_THRESHOLD, find_near_duplicate

SOURCE_TAG = "launch-feedback"


def run_listen(
    backlog: Backlog,
    target: str,
    connectors: Optional[list] = None,
    cfg: Optional[Config] = None,
    limit: int = 25,
    near_threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """Ingest reactions for ``target`` as launch-feedback. Mirrors discovery's ingestion
    flow but tags provenance ``launch-feedback`` (origin connector preserved)."""
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
        except Exception as e:  # a connector bug must not abort the listen pass
            summary["skipped"].append({"source": conn.name, "reason": f"unexpected: {e}"})
            continue

        summary["by_source"][conn.name] = len(cands)
        for cand in cands:
            summary["fetched"] += 1
            low_conf = cand["engagement"] < cfg.min_engagement or not cand["source"].get("url")
            # Retag provenance as launch-feedback, preserving the origin connector.
            source = {**cand["source"], "type": SOURCE_TAG,
                      "origin": cand["source"].get("type")}
            key = make_dedup_key(target, cand["problem"])
            dup = (backlog.find_existing(target, key)
                   or find_near_duplicate(cand, current, near_threshold))
            if dup is not None:
                backlog.attach_evidence(dup["id"], [source])
                summary["merged"] += 1
                continue
            opp_id = backlog.add_candidate(
                target=target,
                title=f"[launch-feedback] {cand['title']}",
                problem=cand["problem"],
                sources=[source],
                low_confidence=low_conf,
            )
            summary["new"] += 1
            if low_conf:
                summary["low_confidence"] += 1
            current.append({"id": opp_id, "title": cand["title"], "problem": cand["problem"]})

    return summary
