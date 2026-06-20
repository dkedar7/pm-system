"""U3 tests — discovery orchestration with injected fake connectors (no network)."""

from __future__ import annotations

import pytest

from pmkit.backlog import Backlog
from pmkit.connectors.base import Config, ConnectorError, candidate
from pmkit.discover import run_discovery


class FakeConnector:
    def __init__(self, name, cands=None, avail=(True, "ok"), error=None):
        self.name = name
        self._cands = cands or []
        self._avail = avail
        self._error = error

    def available(self, cfg):
        return self._avail

    def fetch(self, target, cfg, limit):
        if self._error:
            raise self._error
        return self._cands


@pytest.fixture()
def bl(tmp_path):
    store = Backlog(str(tmp_path / "b.db"))
    yield store
    store.close()


def test_adds_new_and_flags_low_confidence(bl):
    cands = [
        candidate("Add websocket transport", "support realtime streaming connections",
                  "github", "https://gh/1", engagement=20),
        candidate("Fix rare typo somewhere", "minor docs spelling issue noticed once",
                  "github", "https://gh/2", engagement=0),  # below min_engagement -> low conf
    ]
    conn = FakeConnector("github", cands)
    summary = run_discovery(bl, "o/r", connectors=[conn], cfg=Config())
    assert summary["new"] == 2
    assert summary["low_confidence"] == 1
    items = bl.list()
    low = [i for i in items if i["low_confidence"]]
    assert len(low) == 1 and low[0]["title"].startswith("Fix rare typo")


def test_rerun_merges_not_duplicates(bl):
    cands = [candidate("No retry logic in client", "the http client has no retry logic",
                       "github", "https://gh/1", engagement=10)]
    conn = FakeConnector("github", cands)
    first = run_discovery(bl, "o/r", connectors=[conn], cfg=Config())
    assert first["new"] == 1
    # second run with the same signal -> merged, zero new rows (R10)
    second = run_discovery(bl, "o/r", connectors=[conn], cfg=Config())
    assert second["new"] == 0
    assert second["merged"] == 1
    assert len(bl.list()) == 1


def test_unavailable_connector_skipped(bl):
    conn = FakeConnector("web", avail=(False, "no BRAVE_API_KEY"))
    summary = run_discovery(bl, "o/r", connectors=[conn], cfg=Config())
    assert summary["skipped"] == [{"source": "web", "reason": "no BRAVE_API_KEY"}]
    assert summary["new"] == 0


def test_connector_error_does_not_abort_run(bl):
    bad = FakeConnector("reddit", error=ConnectorError("HTTP 429"))
    good = FakeConnector("github", [candidate("Real thing", "a genuine unmet need here",
                                              "github", "https://gh/9", engagement=15)])
    summary = run_discovery(bl, "o/r", connectors=[bad, good], cfg=Config())
    assert any(s["source"] == "reddit" for s in summary["skipped"])
    assert summary["new"] == 1  # the good connector still ran


def test_near_duplicate_within_run_merges(bl):
    cands = [
        candidate("HTTP client lacks retry", "the http client has no retry logic at all",
                  "github", "https://gh/1", engagement=10),
        candidate("Client needs retry support", "http client missing retry logic entirely",
                  "hn", "https://hn/2", engagement=8),
    ]
    conn = FakeConnector("multi", cands)
    summary = run_discovery(bl, "o/r", connectors=[conn], cfg=Config(), near_threshold=0.4)
    assert summary["new"] == 1
    assert summary["merged"] == 1
    item = bl.list()[0]
    assert len(item["sources"]) == 2  # both signals attached as evidence
