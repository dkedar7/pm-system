"""U5 tests — confirmed + deduped backlog filing."""

from __future__ import annotations

import pytest

from pmkit.backlog import Backlog
from pmkit.dogfood.file_gaps import file_gaps
from pmkit.dogfood.report import Finding


@pytest.fixture()
def bl(tmp_path):
    store = Backlog(str(tmp_path / "b.db"))
    yield store
    store.close()


def _gap(title, observed="bad"):
    return Finding("install", title, "fail", gap=True, claim="docs say X works", observed=observed)


def test_only_confirmed_gaps_are_filed(bl):
    gaps = [_gap("install command wrong"), _gap("bearer not enforced")]
    out = file_gaps(bl, "o/r", gaps, confirmed={"install command wrong"})
    assert len(out["filed"]) == 1
    assert out["skipped"] == ["bearer not enforced"]
    items = bl.list()
    assert len(items) == 1 and items[0]["title"].startswith("[dogfood]")
    assert items[0]["sources"][0]["type"] == "dogfood"


def test_refiling_same_gap_dedups(bl):
    """AE5: a gap already in the backlog is deduped, not duplicated."""
    g = _gap("install command wrong")
    first = file_gaps(bl, "o/r", [g], confirmed={"install command wrong"})
    assert len(first["filed"]) == 1
    second = file_gaps(bl, "o/r", [g], confirmed={"install command wrong"})
    assert second["filed"] == [] and len(second["deduped"]) == 1
    assert len(bl.list()) == 1  # no duplicate row


def test_flaky_gap_is_report_only(bl):
    out = file_gaps(bl, "o/r", [_gap("flaky thing")], confirmed=set())
    assert out["filed"] == [] and out["skipped"] == ["flaky thing"]
    assert bl.list() == []


def test_distinct_titles_same_output_both_filed(bl):
    """Distinct gaps with identical observed text must NOT collapse (title is in the key)."""
    gaps = [_gap("gap A", observed="exit 1"), _gap("gap B", observed="exit 1")]
    out = file_gaps(bl, "o/r", gaps, confirmed={"gap A", "gap B"})
    assert len(out["filed"]) == 2 and len(bl.list()) == 2
