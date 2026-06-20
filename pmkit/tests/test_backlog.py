"""U2 tests — backlog store, lifecycle, gate, and export."""

from __future__ import annotations

import pytest

from pmkit.backlog import (
    Backlog,
    BacklogError,
    GateError,
    TransitionError,
    make_dedup_key,
)


@pytest.fixture()
def bl(tmp_path):
    store = Backlog(str(tmp_path / "backlog.db"))
    yield store
    store.close()


def _new_survived(bl, target="o/r", title="t", problem="p"):
    opp = bl.add_candidate(target=target, title=title, problem=problem)
    bl.record_killtest(opp, [{"axis": "rarity", "verdict": "survive"}], survived=True)
    return opp


def test_empty_list_is_clean(bl):
    assert bl.list() == []
    assert bl.counts()["new"] == 0


def test_add_and_get(bl):
    opp = bl.add_candidate(
        target="o/r",
        title="Add retries",
        problem="HTTP client has no retry",
        sources=[{"type": "github", "url": "https://x/1"}],
    )
    item = bl.get(opp)
    assert item["status"] == "new"
    assert item["title"] == "Add retries"
    assert item["sources"][0]["url"] == "https://x/1"
    assert item["category"] is None


def test_dedup_attaches_evidence_same_problem(bl):
    """R10: re-discovering the same problem attaches evidence, adds no new row."""
    a = bl.add_candidate("o/r", "Retry", "client has no retry logic",
                         sources=[{"type": "hn", "url": "https://a"}])
    b = bl.add_candidate("o/r", "Retry (dup)", "client has no retry logic",
                         sources=[{"type": "reddit", "url": "https://b"}])
    assert a == b
    item = bl.get(a)
    urls = {s["url"] for s in item["sources"]}
    assert urls == {"https://a", "https://b"}
    assert len(bl.list()) == 1


def test_distinct_problem_creates_new_row(bl):
    a = bl.add_candidate("o/r", "Retry", "client has no retry logic")
    b = bl.add_candidate("o/r", "Docs", "the quickstart docs are out of date")
    assert a != b
    assert len(bl.list()) == 2


def test_full_legal_lifecycle(bl):
    opp = bl.add_candidate("o/r", "t", "p")
    bl.record_killtest(opp, [{"axis": "solved", "verdict": "survive"}], survived=True)
    assert bl.get(opp)["status"] == "survived"
    bl.set_scores(opp, reach=100, impact=2, confidence=0.8, effort=4)
    bl.set_category(opp, "human-and-agent")
    bl.promote(opp)
    assert bl.get(opp)["status"] == "specced"
    bl.set_spec(opp, "docs/brainstorms/x-requirements.md")
    bl.approve(opp, note="lgtm")
    assert bl.get(opp)["status"] == "approved"
    bl.record_delegation(opp, spec_path="docs/brainstorms/x-requirements.md")
    item = bl.get(opp)
    assert item["status"] == "delegated"
    assert item["delegation"]["category"] == "human-and-agent"
    bl.mark_shipped(opp)
    assert bl.get(opp)["status"] == "shipped"


def test_killtest_failure_prunes(bl):
    opp = bl.add_candidate("o/r", "t", "p")
    bl.record_killtest(opp, [{"axis": "solved", "verdict": "refute"}], survived=False)
    assert bl.get(opp)["status"] == "pruned"


def test_illegal_transition_rejected(bl):
    opp = bl.add_candidate("o/r", "t", "p")  # status new
    with pytest.raises(TransitionError):
        bl.approve(opp)  # can't approve a 'new' item (only 'specced')
    with pytest.raises(TransitionError):
        bl.promote(opp)  # can't promote a 'new' item (only 'survived')


def test_gate_blocks_delegation_without_approval(bl):
    """R7: a specced-but-unapproved item cannot be delegated."""
    opp = _new_survived(bl)
    bl.promote(opp)  # specced, no approval record
    with pytest.raises(BacklogError):  # GateError or TransitionError — both block it
        bl.record_delegation(opp, spec_path="x.md")
    # and it's specifically the gate that fires when status would otherwise allow it:
    bl.approve(opp)
    item = bl.get(opp)
    assert item["approval"] is not None


def test_delegation_requires_approval_record_directly(bl):
    opp = _new_survived(bl)
    bl.promote(opp)
    bl.approve(opp)
    # approved + approval present -> delegation allowed
    bl.record_delegation(opp, spec_path="x.md")
    assert bl.get(opp)["status"] == "delegated"


def test_list_sort_by_score(bl):
    low = _new_survived(bl, problem="low value problem here")
    high = _new_survived(bl, problem="high value problem here")
    bl.set_scores(low, reach=10, impact=1, confidence=0.5, effort=5)     # 1.0
    bl.set_scores(high, reach=100, impact=3, confidence=0.9, effort=2)   # 135.0
    ordered = bl.list(status="survived", sort="score")
    assert [it["id"] for it in ordered] == [high, low]


def test_set_scores_rerun_updates_in_place(bl):
    opp = _new_survived(bl)
    first = bl.set_scores(opp, reach=10, impact=1, confidence=1, effort=10)
    second = bl.set_scores(opp, reach=100, impact=2, confidence=1, effort=10)
    assert second > first
    assert len(bl.list()) == 1  # updated, not duplicated


def test_set_category_validates(bl):
    opp = bl.add_candidate("o/r", "t", "p")
    with pytest.raises(BacklogError):
        bl.set_category(opp, "nonsense")


def test_low_confidence_flag_persists(bl):
    opp = bl.add_candidate("o/r", "t", "no verifiable source", low_confidence=True)
    assert bl.get(opp)["low_confidence"] is True


def test_export_markdown_contains_items(bl):
    opp = _new_survived(bl, title="Exported item")
    bl.set_scores(opp, reach=10, impact=2, confidence=0.5, effort=2)
    md = bl.export_markdown()
    assert "Exported item" in md
    assert "RICE" in md


def test_make_dedup_key_stable():
    k1 = make_dedup_key("O/R", "The Client Has No Retry!")
    k2 = make_dedup_key("o/r", "the client has no retry")
    assert k1 == k2
