"""SQLite-backed opportunity backlog with an explicit lifecycle.

The backlog is the persistent spine of the funnel and the operator's source of truth.
Both humans (via the CLI) and agents (via this module) read and write through it.

Lifecycle (enforced by ``TRANSITIONS``)::

    new ──► survived ──► specced ──► approved ──► delegated ──► shipped
      └──► pruned

The hard human gate lives in :meth:`Backlog.record_delegation`: an item cannot be
delegated unless it carries an approval record (written only by :meth:`Backlog.approve`).
Making the gate optional per-target later (the deferred autonomy goal) is a config concern
layered on top of this contract — the contract itself never lets unapproved work through.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

STATUSES = (
    "new",
    "survived",
    "pruned",
    "specced",
    "approved",
    "delegated",
    "shipped",
)

# Allowed status transitions. Anything not listed is rejected.
TRANSITIONS: dict[str, set[str]] = {
    "new": {"survived", "pruned"},
    "survived": {"specced"},
    "specced": {"approved"},
    "approved": {"delegated"},
    "delegated": {"shipped"},
    "pruned": set(),
    "shipped": set(),
}

CATEGORIES = ("agent-only", "human-and-agent")


class BacklogError(Exception):
    """Base error for illegal backlog operations."""


class TransitionError(BacklogError):
    """Raised on an illegal lifecycle transition."""


class GateError(BacklogError):
    """Raised when delegation is attempted without a recorded approval."""


def default_db_path() -> Path:
    """Resolve the backlog DB path: ``$PMKIT_DB_PATH`` or ``~/.pmkit/backlog.db``."""
    env = os.environ.get("PMKIT_DB_PATH")
    if env:
        return Path(env)
    return Path.home() / ".pmkit" / "backlog.db"


def make_dedup_key(target: str, problem: str, max_words: int = 12) -> str:
    """Build a stable, normalized key from the target and problem statement.

    Lowercases, strips punctuation, collapses whitespace, and keeps the first
    ``max_words`` tokens. Two candidates describing the same problem on the same
    target produce the same key. Near-duplicate (non-identical) detection is the
    job of ``pmkit.dedup``; this is the exact-match backbone.
    """
    norm = re.sub(r"[^a-z0-9\s]", " ", (problem or "").lower())
    words = norm.split()[:max_words]
    slug = "-".join(words)
    return f"{(target or '').strip().lower()}::{slug}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Backlog:
    """Connection wrapper over the opportunity backlog DB."""

    def __init__(self, db_path: Optional[os.PathLike[str] | str] = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else default_db_path()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._ensure_schema()

    # ------------------------------------------------------------------ schema
    def _ensure_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                target        TEXT NOT NULL,
                title         TEXT NOT NULL,
                problem       TEXT NOT NULL DEFAULT '',
                dedup_key     TEXT NOT NULL,
                category      TEXT,
                status        TEXT NOT NULL DEFAULT 'new',
                low_confidence INTEGER NOT NULL DEFAULT 0,
                sources       TEXT NOT NULL DEFAULT '[]',
                reach         REAL,
                impact        REAL,
                confidence    REAL,
                effort        REAL,
                rice          REAL,
                killtest      TEXT,
                spec_path     TEXT,
                approval      TEXT,
                delegation    TEXT,
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_opp_status ON opportunities(status);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_opp_dedup
                ON opportunities(target, dedup_key);
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Backlog":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------- create/read
    def add_candidate(
        self,
        target: str,
        title: str,
        problem: str = "",
        sources: Optional[Iterable[dict]] = None,
        dedup_key: Optional[str] = None,
        low_confidence: bool = False,
    ) -> int:
        """Insert a new candidate (status ``new``). If an item with the same
        (target, dedup_key) already exists, attach the new sources to it instead
        and return its id — this is the exact-match arm of dedup (R10)."""
        key = dedup_key or make_dedup_key(target, problem)
        existing = self.find_existing(target, key)
        if existing is not None:
            self.attach_evidence(existing["id"], sources or [])
            return int(existing["id"])
        now = _now()
        cur = self.conn.execute(
            """
            INSERT INTO opportunities
                (target, title, problem, dedup_key, status, low_confidence,
                 sources, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'new', ?, ?, ?, ?)
            """,
            (
                target,
                title,
                problem,
                key,
                1 if low_confidence else 0,
                json.dumps(list(sources or [])),
                now,
                now,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def find_existing(self, target: str, dedup_key: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM opportunities WHERE target = ? AND dedup_key = ?",
            (target, dedup_key),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get(self, opp_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM opportunities WHERE id = ?", (opp_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list(
        self,
        status: Optional[str] = None,
        sort: str = "created",
        limit: Optional[int] = None,
    ) -> list[dict]:
        sql = "SELECT * FROM opportunities"
        params: list[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        if sort == "score":
            sql += " ORDER BY rice IS NULL, rice DESC, id ASC"
        else:
            sql += " ORDER BY created_at ASC, id ASC"
        if limit:
            sql += " LIMIT ?"
            params.append(int(limit))
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def counts(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM opportunities GROUP BY status"
        ).fetchall()
        out = {s: 0 for s in STATUSES}
        for r in rows:
            out[r["status"]] = r["n"]
        return out

    # ----------------------------------------------------------------- mutate
    def attach_evidence(self, opp_id: int, sources: Iterable[dict]) -> None:
        """Merge new sources into an existing item (dedup by url). Used when a
        re-run rediscovers a known problem — evidence accrues, no duplicate row."""
        item = self._require(opp_id)
        existing = item["sources"]
        seen = {s.get("url") for s in existing if s.get("url")}
        for s in sources:
            if s.get("url") and s["url"] in seen:
                continue
            existing.append(s)
            if s.get("url"):
                seen.add(s["url"])
        self.conn.execute(
            "UPDATE opportunities SET sources = ?, updated_at = ? WHERE id = ?",
            (json.dumps(existing), _now(), opp_id),
        )
        self.conn.commit()

    def _set_status(self, opp_id: int, new_status: str) -> None:
        item = self._require(opp_id)
        current = item["status"]
        if new_status not in TRANSITIONS.get(current, set()):
            raise TransitionError(
                f"illegal transition {current!r} -> {new_status!r} for opp {opp_id}"
            )
        self.conn.execute(
            "UPDATE opportunities SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, _now(), opp_id),
        )
        self.conn.commit()

    def record_killtest(self, opp_id: int, verdicts: list[dict], survived: bool) -> None:
        """Store per-axis kill-test verdicts and move new -> survived | pruned."""
        self._require(opp_id)
        self.conn.execute(
            "UPDATE opportunities SET killtest = ?, updated_at = ? WHERE id = ?",
            (json.dumps(verdicts), _now(), opp_id),
        )
        self.conn.commit()
        self._set_status(opp_id, "survived" if survived else "pruned")

    def set_scores(
        self,
        opp_id: int,
        reach: float,
        impact: float,
        confidence: float,
        effort: float,
    ) -> float:
        """Store RICE sub-scores and the computed composite. Returns the composite.
        Re-running updates the same row in place (R5)."""
        from .rice import compute_rice

        self._require(opp_id)
        rice = compute_rice(reach, impact, confidence, effort)
        self.conn.execute(
            """
            UPDATE opportunities
               SET reach = ?, impact = ?, confidence = ?, effort = ?, rice = ?,
                   updated_at = ?
             WHERE id = ?
            """,
            (reach, impact, confidence, effort, rice, _now(), opp_id),
        )
        self.conn.commit()
        return rice

    def set_category(self, opp_id: int, category: str) -> None:
        if category not in CATEGORIES:
            raise BacklogError(
                f"category must be one of {CATEGORIES}, got {category!r}"
            )
        self._require(opp_id)
        self.conn.execute(
            "UPDATE opportunities SET category = ?, updated_at = ? WHERE id = ?",
            (category, _now(), opp_id),
        )
        self.conn.commit()

    def promote(self, opp_id: int) -> None:
        """Operator selects a survived item for spec drafting: survived -> specced."""
        self._set_status(opp_id, "specced")

    def set_spec(self, opp_id: int, spec_path: str) -> None:
        """Record the drafted requirements doc path on a specced item."""
        item = self._require(opp_id)
        if item["status"] not in ("specced", "approved"):
            raise BacklogError(
                f"cannot attach spec to opp {opp_id} in status {item['status']!r}"
            )
        self.conn.execute(
            "UPDATE opportunities SET spec_path = ?, updated_at = ? WHERE id = ?",
            (spec_path, _now(), opp_id),
        )
        self.conn.commit()

    def approve(self, opp_id: int, note: Optional[str] = None) -> None:
        """The hard human gate: specced -> approved, writing an approval record."""
        item = self._require(opp_id)
        if item["status"] != "specced":
            raise TransitionError(
                f"can only approve a 'specced' item; opp {opp_id} is {item['status']!r}"
            )
        record = {"approved_at": _now(), "note": note}
        self.conn.execute(
            "UPDATE opportunities SET approval = ? WHERE id = ?",
            (json.dumps(record), opp_id),
        )
        self.conn.commit()
        self._set_status(opp_id, "approved")

    def record_delegation(
        self, opp_id: int, spec_path: Optional[str], target: Optional[str] = None
    ) -> None:
        """Delegate an approved item to implementation. Refuses without an approval
        record — this is the gate enforced in code, not just by status (R7)."""
        item = self._require(opp_id)
        if not item.get("approval"):
            raise GateError(
                f"opp {opp_id} has no approval record; cannot delegate (gate)"
            )
        if item["status"] != "approved":
            raise TransitionError(
                f"can only delegate an 'approved' item; opp {opp_id} is {item['status']!r}"
            )
        record = {
            "delegated_at": _now(),
            "spec_path": spec_path or item.get("spec_path"),
            "target": target or item.get("target"),
            "category": item.get("category"),
        }
        self.conn.execute(
            "UPDATE opportunities SET delegation = ? WHERE id = ?",
            (json.dumps(record), opp_id),
        )
        self.conn.commit()
        self._set_status(opp_id, "delegated")

    def mark_shipped(self, opp_id: int) -> None:
        self._set_status(opp_id, "shipped")

    # ----------------------------------------------------------------- export
    def export_markdown(self) -> str:
        """Render a stable, human-readable snapshot of the backlog."""
        items = self.list(sort="score")
        lines = ["# Opportunity backlog", ""]
        counts = self.counts()
        summary = ", ".join(f"{k}: {v}" for k, v in counts.items() if v)
        lines.append(f"_{summary or 'empty'}_")
        lines.append("")
        for it in items:
            score = "-" if it["rice"] is None else f"{it['rice']:.2f}"
            cat = it["category"] or "-"
            flag = " (low-confidence)" if it["low_confidence"] else ""
            lines.append(f"## [{it['id']}] {it['title']}")
            lines.append(
                f"- target: `{it['target']}` | status: **{it['status']}** | "
                f"RICE: {score} | category: {cat}{flag}"
            )
            if it["problem"]:
                lines.append(f"- problem: {it['problem']}")
            if it["sources"]:
                urls = ", ".join(s.get("url", "?") for s in it["sources"][:5])
                lines.append(f"- sources: {urls}")
            lines.append("")
        return "\n".join(lines)

    # ----------------------------------------------------------------- helpers
    def _require(self, opp_id: int) -> dict:
        item = self.get(opp_id)
        if item is None:
            raise BacklogError(f"opportunity {opp_id} not found")
        return item

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["sources"] = json.loads(d.get("sources") or "[]")
        d["killtest"] = json.loads(d["killtest"]) if d.get("killtest") else None
        d["approval"] = json.loads(d["approval"]) if d.get("approval") else None
        d["delegation"] = json.loads(d["delegation"]) if d.get("delegation") else None
        d["low_confidence"] = bool(d.get("low_confidence"))
        return d
