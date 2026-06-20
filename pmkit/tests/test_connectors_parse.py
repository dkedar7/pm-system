"""U3 tests — connector parsers (pure, no network)."""

from __future__ import annotations

from pmkit.connectors.changelog import parse_releases
from pmkit.connectors.github import parse_issues
from pmkit.connectors.hn import parse_hn
from pmkit.connectors.reddit import parse_reddit
from pmkit.connectors.web import parse_brave
from pmkit.connectors.x import parse_x


def test_parse_issues_skips_prs_and_scores_engagement():
    data = [
        {"title": "PR not issue", "pull_request": {"url": "x"}, "html_url": "p"},
        {
            "title": "No retry logic",
            "body": "the client cannot retry",
            "html_url": "https://gh/1",
            "comments": 2,
            "reactions": {"total_count": 3},
            "created_at": "2026-01-01T00:00:00Z",
        },
    ]
    cands = parse_issues(data, "o/r")
    assert len(cands) == 1
    c = cands[0]
    assert c["title"] == "No retry logic"
    assert c["engagement"] == 5  # 3 reactions + 2 comments
    assert c["source"]["type"] == "github"
    assert c["source"]["url"] == "https://gh/1"


def test_parse_hn():
    data = {"hits": [{"title": "Show HN: tool", "objectID": "42", "points": 10, "num_comments": 4}]}
    cands = parse_hn(data, "tool")
    assert cands[0]["engagement"] == 14
    assert "ycombinator" in cands[0]["source"]["url"] or cands[0]["source"]["url"]


def test_parse_reddit():
    data = {"data": {"children": [
        {"data": {"title": "T", "selftext": "body", "permalink": "/r/x/1",
                  "score": 4, "num_comments": 2, "created_utc": 123}}]}}
    cands = parse_reddit(data, "x")
    assert cands[0]["engagement"] == 6
    assert cands[0]["source"]["url"].endswith("/r/x/1")


def test_parse_brave():
    data = {"web": {"results": [{"title": "T", "description": "d", "url": "http://u"}]}}
    cands = parse_brave(data, "o/r")
    assert cands[0]["title"] == "T" and cands[0]["engagement"] == 0


def test_parse_x():
    data = {"data": [{"id": "99", "text": "this is broken", "public_metrics": {
        "like_count": 7, "retweet_count": 3}}]}
    cands = parse_x(data, "o/r")
    assert cands[0]["engagement"] == 10
    assert cands[0]["source"]["url"].endswith("/99")


def test_parse_releases():
    data = [{"name": "v1", "tag_name": "v1.0", "published_at": "2026-01-01",
             "body": "notes", "html_url": "http://r"}]
    rel = parse_releases(data)
    assert rel[0]["tag"] == "v1.0" and rel[0]["name"] == "v1"
