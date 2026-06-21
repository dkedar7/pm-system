"""Moderator-policy research — the killer feature of the launch stage.

For a community, produce a ``block`` / ``warn`` / ``ok`` verdict with the *cited rule(s)* so
the operator never gets a post pulled by a moderator again. The verdict logic is a **pure
function** (``decide_policy``) over structured rules, so it is reproducible and unit-testable.
Reading a community's prose rules into that structure is judgment that belongs to the
``pm-launch-policy`` agent; the live Reddit fetch here is a convenience for the deterministic
path and is gated — a fetch failure degrades to a clean ``unavailable`` verdict, never a crash.

Caching (``resolve_policy``) reuses ``LaunchStore``'s ``mod_policy_cache`` with a 30-day TTL.
Non-Reddit platforms have no machine-readable rules; they return ``ok`` plus a norm note.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from ..connectors.base import http_get_json

# Keyword heuristics over rule text. BLOCK takes precedence over WARN; conservative by design
# (advisory — the verdict cites the rule so the human makes the final call).
_BLOCK_SIGNALS = (
    "no self-promotion", "no self promotion", "no selfpromo", "no advertising",
    "no promotion", "no marketing", "no blogspam", "no blog spam", "not allowed",
    "prohibited", "banned", "zero tolerance", "no spam", "no soliciting",
    "do not post your own", "no links to your own",
)
_WARN_SIGNALS = (
    "ratio", "1:10", "9:1", "10%", "10 percent", "once per", "once a week",
    "limit", "flair", "approval required", "must be approved", "account age",
    "karma", "weekly thread", "megathread", "self-promotion saturday", "only on",
    "must include", "no more than",
)

# Best-effort norm notes for platforms without machine-readable rules (R1 / Scope: others).
NORM_NOTES = {
    "hackernews": "No machine-readable rules. Use 'Show HN:' for your own work; one post; "
                  "no reposting; engage genuinely in comments.",
    "x": "No hard self-promo gate; norms favor a narrative thread over a bare link, and "
         "replying in relevant conversations over broadcasting.",
    "linkedin": "No hard self-promo gate; norms favor a story/lesson framing over a raw "
                "announcement; external links can suppress reach.",
}

DEFAULT_TTL_DAYS = 30


def decide_policy(rules: list[dict]) -> tuple[str, list[dict]]:
    """Pure verdict over structured rules. Each rule is ``{"text": str, "url": str}``.

    Returns ``(verdict, cited_rules)`` where verdict is ``block`` | ``warn`` | ``ok`` and
    cited_rules is the subset that triggered a non-ok verdict (empty for ``ok``).
    """
    blockers = [r for r in rules if _matches(r, _BLOCK_SIGNALS)]
    if blockers:
        return "block", blockers
    warners = [r for r in rules if _matches(r, _WARN_SIGNALS)]
    if warners:
        return "warn", warners
    return "ok", []


def _matches(rule: dict, signals: tuple[str, ...]) -> bool:
    text = (rule.get("text") or "").lower()
    return any(sig in text for sig in signals)


def is_stale(fetched_at: str, ttl_days: int, now: Optional[datetime] = None) -> bool:
    """Pure: is a cache row older than its TTL? Unparseable timestamps count as stale."""
    now = now or datetime.now(timezone.utc)
    try:
        ts = datetime.fromisoformat(fetched_at)
    except (ValueError, TypeError):
        return True
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return now - ts > timedelta(days=int(ttl_days))


def parse_subreddit_rules(data: dict) -> list[dict]:
    """Pure: turn Reddit's ``about/rules.json`` payload into structured rules."""
    out: list[dict] = []
    for r in (data or {}).get("rules", []):
        name = (r.get("short_name") or "").strip()
        desc = (r.get("description") or "").strip()
        text = f"{name}: {desc}".strip(": ").strip()
        if text:
            out.append({"text": text, "url": ""})
    return out


def fetch_subreddit_rules(community: str, timeout: float = 15.0) -> list[dict]:
    """Live fetch of a subreddit's rules (keyless public JSON). Raises on network failure;
    the resolver catches that and degrades to an ``unavailable`` verdict."""
    sub = community.strip().lstrip("/")
    if sub.lower().startswith("r/"):
        sub = sub[2:]
    url = f"https://www.reddit.com/r/{sub}/about/rules.json"
    data = http_get_json(url, {}, timeout)
    return parse_subreddit_rules(data)


def _default_fetcher(platform: str) -> Optional[Callable[[str], list[dict]]]:
    if platform == "reddit":
        return fetch_subreddit_rules
    return None  # non-reddit: no machine-readable rules


def resolve_policy(
    store,
    community: str,
    *,
    platform: str = "reddit",
    fetcher: Optional[Callable[[str], list[dict]]] = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
    now: Optional[datetime] = None,
    use_cache: bool = True,
) -> dict:
    """Resolve a policy verdict, reading/refreshing the cache. Never raises on fetch failure.

    Returns a dict: ``{platform, community, verdict, cited_rules, cached, [note], [error]}``.
    """
    if use_cache:
        cached = store.get_policy(platform, community)
        if cached and not is_stale(cached["fetched_at"], cached["ttl_days"], now):
            return {
                "platform": platform, "community": community,
                "verdict": cached["verdict"], "cited_rules": cached["cited_rules"],
                "cached": True,
            }

    fetcher = fetcher if fetcher is not None else _default_fetcher(platform)
    if fetcher is None:
        # Non-reddit platform with no machine-readable rules: ok + a norm note.
        return {
            "platform": platform, "community": community, "verdict": "ok",
            "cited_rules": [], "cached": False,
            "note": NORM_NOTES.get(platform, "No machine-readable rules; follow community norms."),
        }
    try:
        rules = fetcher(community)
    except Exception as e:  # network / parse failure -> clean unavailable, not a crash
        return {
            "platform": platform, "community": community, "verdict": "unavailable",
            "cited_rules": [], "cached": False, "error": f"{type(e).__name__}: {e}",
        }
    verdict, cited = decide_policy(rules)
    store.put_policy(platform, community, verdict, cited, ttl_days=ttl_days)
    return {
        "platform": platform, "community": community, "verdict": verdict,
        "cited_rules": cited, "cached": False,
    }
