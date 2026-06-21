"""Launch-stage persistence: the state ledger + the mod-policy cache.

Shares the backlog SQLite DB (one file for the whole funnel) but owns two tables it creates
idempotently on open, mirroring ``backlog.py``'s bootstrap. Deterministic and unit-testable;
no network, no posting.

- ``launch_state`` — per (product, channel) ledger row: planned vs announced, where, when.
- ``mod_policy_cache`` — per (platform, community) cached verdict + cited rules + freshness.
  This module only stores/reads the cache; the *staleness* decision (re-fetch past TTL) lives
  in ``policy.py`` so the verdict logic stays in one place.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..backlog import default_db_path

# The four launch channels (Reddit gets full mod-policy research; others get norm notes).
CHANNELS = ("reddit", "hackernews", "x", "linkedin")
LAUNCH_STATUSES = ("planned", "announced")
POLICY_VERDICTS = ("block", "warn", "ok", "unavailable")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LaunchStore:
    """Connection wrapper over the launch tables in the shared backlog DB."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else default_db_path()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    # ------------------------------------------------------------------ schema
    def _ensure_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS launch_state (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product         TEXT NOT NULL,
                channel         TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'planned',
                url             TEXT,
                artifact_version TEXT,
                opportunity_id  INTEGER,
                announced_at    TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_launch_state_pc
                ON launch_state(product, channel);

            CREATE TABLE IF NOT EXISTS mod_policy_cache (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                platform    TEXT NOT NULL,
                community   TEXT NOT NULL,
                verdict     TEXT NOT NULL,
                cited_rules TEXT NOT NULL DEFAULT '[]',
                fetched_at  TEXT NOT NULL,
                ttl_days    INTEGER NOT NULL DEFAULT 30
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mod_policy_pc
                ON mod_policy_cache(platform, community);

            -- Draft STARTING-POINTS only. There is deliberately no 'status'/'final'/
            -- 'postable' column: the data model itself cannot represent a finished post,
            -- so nothing here can ever be mistaken for one. The human writes the final.
            CREATE TABLE IF NOT EXISTS launch_drafts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                product        TEXT NOT NULL,
                platform       TEXT NOT NULL,
                community      TEXT,
                kind           TEXT NOT NULL DEFAULT 'starting_point',
                text           TEXT NOT NULL,
                critic_flagged INTEGER,
                critic_score   REAL,
                critic         TEXT,
                created_at     TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "LaunchStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------ state ledger
    def record_state(
        self,
        product: str,
        channel: str,
        *,
        status: str = "planned",
        url: Optional[str] = None,
        artifact_version: Optional[str] = None,
        opportunity_id: Optional[int] = None,
    ) -> int:
        """Upsert a (product, channel) ledger row. Returns its id."""
        if status not in LAUNCH_STATUSES:
            raise ValueError(f"status must be one of {LAUNCH_STATUSES}, got {status!r}")
        now = _now()
        existing = self.conn.execute(
            "SELECT id FROM launch_state WHERE product = ? AND channel = ?",
            (product, channel),
        ).fetchone()
        announced_at = now if status == "announced" else None
        if existing is not None:
            self.conn.execute(
                """
                UPDATE launch_state
                   SET status = ?, url = COALESCE(?, url),
                       artifact_version = COALESCE(?, artifact_version),
                       opportunity_id = COALESCE(?, opportunity_id),
                       announced_at = COALESCE(?, announced_at),
                       updated_at = ?
                 WHERE id = ?
                """,
                (status, url, artifact_version, opportunity_id, announced_at, now,
                 int(existing["id"])),
            )
            self.conn.commit()
            return int(existing["id"])
        cur = self.conn.execute(
            """
            INSERT INTO launch_state
                (product, channel, status, url, artifact_version, opportunity_id,
                 announced_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (product, channel, status, url, artifact_version, opportunity_id,
             announced_at, now, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def announce(self, product: str, channel: str, url: Optional[str] = None) -> int:
        """Mark a (product, channel) as announced (status='announced', stamps time)."""
        return self.record_state(product, channel, status="announced", url=url)

    def list_state(self, product: Optional[str] = None) -> list[dict]:
        if product:
            rows = self.conn.execute(
                "SELECT * FROM launch_state WHERE product = ? ORDER BY channel",
                (product,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM launch_state ORDER BY product, channel"
            ).fetchall()
        return [dict(r) for r in rows]

    def status_counts(self, product: Optional[str] = None) -> dict[str, int]:
        out = {s: 0 for s in LAUNCH_STATUSES}
        for row in self.list_state(product):
            out[row["status"]] = out.get(row["status"], 0) + 1
        return out

    # ------------------------------------------------------------ policy cache
    def put_policy(
        self,
        platform: str,
        community: str,
        verdict: str,
        cited_rules: list[dict],
        ttl_days: int = 30,
    ) -> None:
        """Upsert a cached policy verdict for (platform, community)."""
        if verdict not in POLICY_VERDICTS:
            raise ValueError(f"verdict must be one of {POLICY_VERDICTS}, got {verdict!r}")
        now = _now()
        self.conn.execute(
            """
            INSERT INTO mod_policy_cache (platform, community, verdict, cited_rules,
                                          fetched_at, ttl_days)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, community) DO UPDATE SET
                verdict = excluded.verdict,
                cited_rules = excluded.cited_rules,
                fetched_at = excluded.fetched_at,
                ttl_days = excluded.ttl_days
            """,
            (platform, community, verdict, json.dumps(cited_rules), now, int(ttl_days)),
        )
        self.conn.commit()

    def get_policy(self, platform: str, community: str) -> Optional[dict]:
        """Return the cached verdict row (cited_rules decoded), or None. Freshness is the
        caller's call — the row carries ``fetched_at`` and ``ttl_days``."""
        row = self.conn.execute(
            "SELECT * FROM mod_policy_cache WHERE platform = ? AND community = ?",
            (platform, community),
        ).fetchone()
        if row is None:
            return None
        d: dict[str, Any] = dict(row)
        d["cited_rules"] = json.loads(d.get("cited_rules") or "[]")
        return d

    # ----------------------------------------------------------- draft storage
    # NOTE: ``kind`` is hardcoded to 'starting_point' on insert and there is no setter to
    # change it — the never-final guardrail is structural, not a convention.
    def add_draft(
        self,
        product: str,
        platform: str,
        text: str,
        *,
        community: Optional[str] = None,
        critic: Optional[dict] = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO launch_drafts
                (product, platform, community, kind, text,
                 critic_flagged, critic_score, critic, created_at)
            VALUES (?, ?, ?, 'starting_point', ?, ?, ?, ?, ?)
            """,
            (
                product, platform, community, text,
                (1 if critic and critic.get("flagged") else 0) if critic else None,
                (critic.get("score") if critic else None),
                (json.dumps(critic) if critic else None),
                _now(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_drafts(self, product: Optional[str] = None) -> list[dict]:
        if product:
            rows = self.conn.execute(
                "SELECT * FROM launch_drafts WHERE product = ? ORDER BY id", (product,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM launch_drafts ORDER BY id"
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["critic"] = json.loads(d["critic"]) if d.get("critic") else None
            d["critic_flagged"] = bool(d["critic_flagged"]) if d["critic_flagged"] is not None else None
            out.append(d)
        return out
