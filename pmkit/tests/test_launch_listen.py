"""U3 tests — the listen loop folds reactions into the backlog (reuses discover flow)."""

from __future__ import annotations

from pmkit.backlog import Backlog
from pmkit.connectors.base import Config, ConnectorError, candidate
from pmkit.launch.listen import run_listen


class FakeConnector:
    def __init__(self, name, cands, *, available=True, raises=None):
        self.name = name
        self._cands = cands
        self._available = available
        self._raises = raises

    def available(self, cfg):
        return (self._available, "" if self._available else "no key")

    def fetch(self, target, cfg, limit):
        if self._raises:
            raise self._raises
        return self._cands


def _bl(tmp_path):
    return Backlog(tmp_path / "backlog.db")


def test_new_feedback_added_with_launch_feedback_source(tmp_path):
    conn = FakeConnector("reddit", [
        candidate("Love it but wish it did X", "users want feature X after launch",
                  "reddit", "https://r/abc", engagement=12),
    ])
    with _bl(tmp_path) as bl:
        summary = run_listen(bl, "streamlit-mcp", connectors=[conn], cfg=Config())
        assert summary["new"] == 1
        item = bl.list()[0]
    assert item["sources"][0]["type"] == "launch-feedback"
    assert item["sources"][0]["origin"] == "reddit"
    assert item["title"].startswith("[launch-feedback]")


def test_feedback_matching_existing_attaches_evidence(tmp_path):
    with _bl(tmp_path) as bl:
        existing = bl.add_candidate(
            "streamlit-mcp", "selectbox unsupported",
            problem="set_widget fails on selectbox widgets in streamlit apps",
            sources=[{"type": "github", "url": "https://gh/1"}])
        conn = FakeConnector("reddit", [
            # same problem resurfacing post-launch -> exact dedup key match -> attach evidence
            candidate("selectbox still broken",
                      "set_widget fails on selectbox widgets in streamlit apps",
                      "reddit", "https://r/xyz", engagement=20)])
        summary = run_listen(bl, "streamlit-mcp", connectors=[conn], cfg=Config())
        items = bl.list()
        merged = bl.get(existing)
    assert summary["merged"] == 1 and summary["new"] == 0
    assert len(items) == 1  # folded in, no duplicate row
    assert any(s["type"] == "launch-feedback" for s in merged["sources"])


def test_low_engagement_flagged_not_dropped(tmp_path):
    conn = FakeConnector("reddit", [
        candidate("meh", "a weakly-engaged reaction", "reddit", "https://r/q", engagement=0)])
    with _bl(tmp_path) as bl:
        summary = run_listen(bl, "p", connectors=[conn], cfg=Config(min_engagement=2))
        item = bl.list()[0]
    assert summary["new"] == 1 and summary["low_confidence"] == 1
    assert item["low_confidence"] is True


def test_connector_error_skipped_not_fatal(tmp_path):
    bad = FakeConnector("x", [], raises=ConnectorError("rate limited"))
    good = FakeConnector("reddit", [
        candidate("works", "a real reaction", "reddit", "https://r/ok", engagement=5)])
    with _bl(tmp_path) as bl:
        summary = run_listen(bl, "p", connectors=[bad, good], cfg=Config())
    assert summary["new"] == 1
    assert any(s["source"] == "x" for s in summary["skipped"])


def test_cli_launch_listen_runs(tmp_path, capsys, monkeypatch):
    # Stub the connector registry so the CLI path is exercised without a network call.
    import pmkit.connectors as conns
    fake = FakeConnector("reddit", [
        candidate("hi", "a launch reaction", "reddit", "https://r/ok", engagement=9)])
    monkeypatch.setattr(conns, "get_connectors", lambda names=None: [fake])
    from pmkit.cli import main
    db = str(tmp_path / "backlog.db")
    rc = main(["launch", "listen", "streamlit-mcp", "--json", "--db", db])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"new": 1' in out and '"target": "streamlit-mcp"' in out
