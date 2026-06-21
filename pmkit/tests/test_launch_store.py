"""U1 tests — launch storage (state ledger + mod-policy cache) and the CLI skeleton."""

from __future__ import annotations

import pytest

from pmkit.cli import main
from pmkit.launch.store import LaunchStore


def _store(tmp_path):
    return LaunchStore(tmp_path / "backlog.db")


# --- schema / idempotency ---
def test_open_creates_tables_idempotently(tmp_path):
    with _store(tmp_path):
        pass
    # opening the same DB again must not error (CREATE TABLE IF NOT EXISTS)
    with _store(tmp_path) as st:
        tables = {r[0] for r in st.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"launch_state", "mod_policy_cache"} <= tables


# --- state ledger ---
def test_record_state_then_announce_upserts_one_row(tmp_path):
    with _store(tmp_path) as st:
        st.record_state("streamlit-mcp", "reddit", status="planned")
        st.announce("streamlit-mcp", "reddit", url="https://reddit.com/r/x/abc")
        rows = st.list_state("streamlit-mcp")
    assert len(rows) == 1  # upsert by (product, channel), not a second row
    assert rows[0]["status"] == "announced"
    assert rows[0]["url"].endswith("abc")
    assert rows[0]["announced_at"]  # stamped on announce


def test_status_counts(tmp_path):
    with _store(tmp_path) as st:
        st.record_state("p", "reddit", status="planned")
        st.record_state("p", "hackernews", status="planned")
        st.announce("p", "x")
        counts = st.status_counts("p")
    assert counts == {"planned": 2, "announced": 1}


def test_record_state_rejects_bad_status(tmp_path):
    with _store(tmp_path) as st:
        with pytest.raises(ValueError):
            st.record_state("p", "reddit", status="posted")


# --- policy cache ---
def test_put_then_get_policy_roundtrips(tmp_path):
    rules = [{"text": "No self-promotion", "url": "https://reddit.com/r/gis/about/rules"}]
    with _store(tmp_path) as st:
        st.put_policy("reddit", "r/gis", "block", rules, ttl_days=30)
        got = st.get_policy("reddit", "r/gis")
    assert got["verdict"] == "block"
    assert got["cited_rules"] == rules
    assert got["ttl_days"] == 30
    assert got["fetched_at"]


def test_put_policy_upserts(tmp_path):
    with _store(tmp_path) as st:
        st.put_policy("reddit", "r/gis", "warn", [])
        st.put_policy("reddit", "r/gis", "ok", [])  # same key -> update, not duplicate
        got = st.get_policy("reddit", "r/gis")
        n = st.conn.execute(
            "SELECT COUNT(*) FROM mod_policy_cache WHERE platform='reddit' AND community='r/gis'"
        ).fetchone()[0]
    assert got["verdict"] == "ok"
    assert n == 1


def test_get_policy_missing_returns_none(tmp_path):
    with _store(tmp_path) as st:
        assert st.get_policy("reddit", "r/nope") is None


def test_put_policy_rejects_bad_verdict(tmp_path):
    with _store(tmp_path) as st:
        with pytest.raises(ValueError):
            st.put_policy("reddit", "r/gis", "maybe", [])


# --- CLI skeleton ---
def test_cli_launch_announce_and_status(tmp_path, capsys):
    db = str(tmp_path / "backlog.db")
    assert main(["launch", "announce", "--product", "streamlit-mcp",
                 "--channel", "reddit", "--url", "https://x", "--db", db]) == 0
    assert main(["launch", "status", "--product", "streamlit-mcp",
                 "--json", "--db", db]) == 0
    out = capsys.readouterr().out
    assert '"announced": 1' in out


def test_cli_launch_state_list(tmp_path, capsys):
    db = str(tmp_path / "backlog.db")
    main(["launch", "announce", "--product", "p", "--channel", "x", "--db", db])
    assert main(["launch", "state", "--db", db]) == 0
    out = capsys.readouterr().out
    assert "x" in out and "announced" in out
