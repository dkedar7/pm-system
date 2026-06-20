"""U3 tests — near-duplicate detection (pure functions)."""

from __future__ import annotations

from pmkit.dedup import find_near_duplicate, jaccard, similarity, token_set


def test_token_set_drops_stopwords_and_short():
    toks = token_set("The client has no retry logic")
    assert "client" in toks and "retry" in toks and "logic" in toks
    assert "the" not in toks and "no" not in toks


def test_jaccard_bounds():
    assert jaccard(set(), set()) == 0.0
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert jaccard({"a"}, {"b"}) == 0.0


def test_similarity_identical_and_disjoint():
    assert similarity("retry logic missing", "retry logic missing") == 1.0
    assert similarity("retry logic", "documentation typo") == 0.0


def test_find_near_duplicate_matches_above_threshold():
    existing = [
        {"id": 1, "title": "HTTP client lacks retry", "problem": "the http client has no retry logic at all"},
        {"id": 2, "title": "Docs typo on homepage", "problem": "the quickstart has a spelling mistake"},
    ]
    cand = {"title": "Client needs retry", "problem": "http client missing retry logic entirely"}
    match = find_near_duplicate(cand, existing, threshold=0.4)
    assert match is not None and match["id"] == 1


def test_find_near_duplicate_returns_none_below_threshold():
    existing = [{"id": 1, "title": "Docs typo", "problem": "spelling mistake in readme"}]
    cand = {"title": "Add websocket transport", "problem": "support realtime streaming connections"}
    assert find_near_duplicate(cand, existing, threshold=0.6) is None
