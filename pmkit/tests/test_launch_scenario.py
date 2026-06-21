"""U9 — streamlit-mcp launch scenario end-to-end over the deterministic cores.

Fixtures/fakes stand in for the network (policy fetch, listen connectors) and the browser
(collateral capture is validated, not run). Asserts the full pipeline ties together and the
gate posture holds: a block verdict surfaces, the plan is emit-only, drafts stay
starting-points, and reactions fold back into the backlog deduped.
"""

from __future__ import annotations

from pmkit.backlog import Backlog
from pmkit.connectors.base import Config, candidate
from pmkit.launch.collateral import plan_capture
from pmkit.launch.drafts import emit, record_draft
from pmkit.launch.listen import run_listen
from pmkit.launch.plan import build_plan, render_markdown
from pmkit.launch.policy import resolve_policy
from pmkit.launch.store import LaunchStore

PRODUCT = "streamlit-mcp"
TARGET = "dkedar7/streamlit-mcp"


class FakeConnector:
    def __init__(self, name, cands):
        self.name = name
        self._cands = cands

    def available(self, cfg):
        return True, ""

    def fetch(self, target, cfg, limit):
        return self._cands


def test_full_launch_scenario(tmp_path):
    db = tmp_path / "backlog.db"

    # 1. Ledger: record an announcement.
    # 2. Policy: a no-self-promo subreddit blocks; a permissive one is ok (cached in the DB).
    with LaunchStore(db) as st:
        st.announce(PRODUCT, "reddit", url="https://reddit.com/r/datascience/x")
        block = resolve_policy(
            st, "r/datascience",
            fetcher=lambda c: [{"text": "No self-promotion of your own tools", "url": "u"}])
        okv = resolve_policy(
            st, "r/streamlit", fetcher=lambda c: [{"text": "Be excellent to each other", "url": ""}])
        assert st.status_counts(PRODUCT) == {"planned": 0, "announced": 1}
    assert block["verdict"] == "block"
    assert okv["verdict"] == "ok"

    # 3. Plan: verdicts attach; the block surfaces; the emit-only gate language is present.
    plan = build_plan(PRODUCT, [
        {"platform": "reddit", "community": "r/datascience", "day": 0, "policy": block},
        {"platform": "reddit", "community": "r/streamlit", "day": 0, "policy": okv},
        {"platform": "hackernews", "community": "Show HN", "day": 1, "policy": {"verdict": "ok"}},
    ])
    md = render_markdown(plan)
    assert "DO NOT POST" in md            # block verdict surfaced
    assert "never posts" in md.lower()    # emit-only / gate language

    # 4. Collateral: a capture plan validates (live capture is not run here).
    cap = plan_capture([
        {"kind": "screenshot", "url": "http://localhost:8765", "name": "demo"},
        {"kind": "cli_cast", "command": "uvx streamlit-mcp --help"},
    ])
    assert [c["kind"] for c in cap] == ["screenshot", "cli_cast"]

    # 5. Draft: a starting-point with a (clean) critic verdict; never a finished post.
    with LaunchStore(db) as st:
        record_draft(st, PRODUCT, "hackernews",
                     "Show HN: streamlit-mcp — drive a Streamlit app over MCP, no browser",
                     community="Show HN",
                     critic={"flagged": False, "score": 0.1, "tells": [], "suggestion": ""})
        drafts = st.list_drafts(PRODUCT)
    assert drafts[0]["kind"] == "starting_point"
    assert "STARTING-POINT" in emit(drafts)

    # 6. Listen: reactions fold into the backlog as launch-feedback; a repeat dedups.
    reactions = FakeConnector("reddit", [
        candidate("love this", "users want selectbox widgets supported by set_widget",
                  "reddit", "https://r/ok", engagement=15),
        candidate("same here", "users want selectbox widgets supported by set_widget",
                  "reddit", "https://r/ok2", engagement=9),  # same problem -> dedup
    ])
    with Backlog(db) as bl:
        summary = run_listen(bl, TARGET, connectors=[reactions], cfg=Config())
        items = [it for it in bl.list() if it["target"] == TARGET]
    assert summary["new"] == 1 and summary["merged"] == 1   # second folded into first
    assert len(items) == 1
    assert items[0]["sources"][0]["type"] == "launch-feedback"
    assert items[0]["status"] == "new"  # discoverable by the funnel -> loop closed

    # 7. Gate posture: the launch store exposes no posting surface at all.
    assert not any(hasattr(LaunchStore, m) for m in ("post", "publish", "send", "submit"))
