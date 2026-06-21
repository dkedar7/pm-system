"""File confirmed dogfood gaps back to the opportunity backlog (deduped).

Closes the funnel loop: a reproducible doc-vs-reality gap becomes a new opportunity.
Only *confirmed* gaps are filed (the skill marks the ones that reproduced on re-run);
flaky/unconfirmed gaps stay report-only. Filing reuses the backlog's exact-key dedup, so
re-running pm-dogfood doesn't pile up duplicates. Each filed item carries a
``source=dogfood`` provenance entry.
"""

from __future__ import annotations

from typing import Iterable

from ..backlog import Backlog
from .report import Finding


def file_gaps(
    backlog: Backlog,
    target: str,
    gaps: Iterable[Finding],
    confirmed: set[str],
    *,
    source: str = "dogfood",
) -> dict:
    """File confirmed gaps as backlog opportunities; skip unconfirmed; dedup the rest.

    ``confirmed`` is the set of gap titles that reproduced. Returns counts of
    filed / deduped / skipped (report-only) gap titles.
    """
    filed: list[int] = []
    deduped: list[int] = []
    skipped: list[str] = []
    for g in gaps:
        if g.title not in confirmed:
            skipped.append(g.title)
            continue
        before = len(backlog.list())
        opp_id = backlog.add_candidate(
            target=target,
            title=f"[dogfood] {g.title}",
            problem=f"{g.claim} -> observed: {g.observed}".strip(),
            sources=[{"type": source, "url": "", "excerpt": (g.observed or "")[:200]}],
        )
        if len(backlog.list()) > before:
            filed.append(opp_id)
        else:
            deduped.append(opp_id)
    return {"filed": filed, "deduped": deduped, "skipped": skipped}
