"""U2 tests — mod-policy verdict (pure), staleness, parse, and cached resolver."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pmkit.cli import main
from pmkit.launch.policy import (
    decide_policy,
    fetch_subreddit_rules,
    is_stale,
    parse_subreddit_rules,
    resolve_policy,
)
from pmkit.launch.store import LaunchStore


# --- decide_policy (pure) ---
def test_self_promo_ban_blocks_with_citation():
    rules = [{"text": "No self-promotion of your own projects", "url": "u"}]
    verdict, cited = decide_policy(rules)
    assert verdict == "block"
    assert cited and cited[0]["url"] == "u"


def test_ratio_rule_warns():
    rules = [{"text": "Keep a 1:10 ratio of self-posts to other contributions", "url": ""}]
    verdict, cited = decide_policy(rules)
    assert verdict == "warn"
    assert len(cited) == 1


def test_irrelevant_rules_are_ok():
    rules = [{"text": "Be civil and on topic", "url": ""}]
    verdict, cited = decide_policy(rules)
    assert verdict == "ok"
    assert cited == []


def test_block_takes_precedence_over_warn():
    rules = [
        {"text": "Maintain a 1:10 ratio", "url": ""},          # warn
        {"text": "No advertising or self promotion", "url": ""},  # block
    ]
    verdict, _ = decide_policy(rules)
    assert verdict == "block"


# --- is_stale (pure) ---
def test_is_stale_fresh_vs_expired():
    now = datetime(2026, 6, 21, tzinfo=timezone.utc)
    fresh = (now - timedelta(days=5)).isoformat()
    old = (now - timedelta(days=40)).isoformat()
    assert is_stale(fresh, 30, now) is False
    assert is_stale(old, 30, now) is True


def test_is_stale_unparseable_is_stale():
    assert is_stale("not-a-date", 30) is True


# --- parse_subreddit_rules (pure) ---
def test_parse_subreddit_rules_fixture():
    data = {"rules": [
        {"short_name": "No self-promo", "description": "Don't post your own blog"},
        {"short_name": "Be civil", "description": ""},
    ]}
    rules = parse_subreddit_rules(data)
    assert len(rules) == 2
    assert "No self-promo" in rules[0]["text"]


# --- resolver (cache + injected fetcher; no network) ---
def test_resolve_fetches_then_caches(tmp_path):
    calls = {"n": 0}

    def fake_fetcher(community):
        calls["n"] += 1
        return [{"text": "No self-promotion allowed", "url": ""}]

    with LaunchStore(tmp_path / "b.db") as st:
        r1 = resolve_policy(st, "r/gis", fetcher=fake_fetcher)
        assert r1["verdict"] == "block" and r1["cached"] is False
        r2 = resolve_policy(st, "r/gis", fetcher=fake_fetcher)  # served from cache
        assert r2["verdict"] == "block" and r2["cached"] is True
    assert calls["n"] == 1  # second call hit the cache, did not re-fetch


def test_resolve_refetches_when_stale(tmp_path):
    def fetcher(community):
        return [{"text": "be nice", "url": ""}]

    now = datetime.now(timezone.utc)
    later = now + timedelta(days=40)
    with LaunchStore(tmp_path / "b.db") as st:
        resolve_policy(st, "r/gis", fetcher=fetcher, now=now)
        r = resolve_policy(st, "r/gis", fetcher=fetcher, now=later)  # past TTL
    assert r["cached"] is False  # stale -> re-fetched


def test_resolve_fetch_failure_is_unavailable_not_crash(tmp_path):
    def boom(community):
        raise RuntimeError("network down")

    with LaunchStore(tmp_path / "b.db") as st:
        r = resolve_policy(st, "r/gis", fetcher=boom)
    assert r["verdict"] == "unavailable"
    assert "network down" in r["error"]


def test_resolve_non_reddit_returns_norm_note(tmp_path):
    with LaunchStore(tmp_path / "b.db") as st:
        r = resolve_policy(st, "Show HN", platform="hackernews")
    assert r["verdict"] == "ok"
    assert "Show HN" in r["note"]


# --- CLI ---
def test_cli_launch_policy_block_exits_nonzero(tmp_path, capsys, monkeypatch):
    import pmkit.launch.policy as pol
    monkeypatch.setattr(pol, "fetch_subreddit_rules",
                        lambda community, timeout=15.0: [{"text": "No self-promotion", "url": ""}])
    db = str(tmp_path / "b.db")
    rc = main(["launch", "policy", "--community", "r/gis", "--json", "--db", db])
    assert rc == 1  # block -> nonzero (a hard "do not post here")
    assert '"verdict": "block"' in capsys.readouterr().out
