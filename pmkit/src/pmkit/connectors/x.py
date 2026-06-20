"""X (Twitter) connector via API v2 recent search. Requires X_BEARER_TOKEN; skipped otherwise."""

from __future__ import annotations

import urllib.parse

from .base import Config, ConnectorError, candidate, http_get_json


class XConnector:
    name = "x"

    def available(self, cfg: Config) -> tuple[bool, str]:
        if cfg.x_bearer:
            return True, "X API v2 recent search"
        return False, "no X_BEARER_TOKEN"

    def fetch(self, target: str, cfg: Config, limit: int = 25) -> list[dict]:
        if not cfg.x_bearer:
            raise ConnectorError("no X_BEARER_TOKEN")
        query = urllib.parse.quote(f"{target.split('/')[-1]} (bug OR feature OR wish) -is:retweet lang:en")
        url = (
            "https://api.twitter.com/2/tweets/search/recent"
            f"?query={query}&max_results={min(max(limit, 10), 100)}"
            "&tweet.fields=public_metrics,created_at"
        )
        headers = {"Authorization": f"Bearer {cfg.x_bearer}"}
        data = http_get_json(url, headers, cfg.timeout)
        return parse_x(data, target)


def parse_x(data: dict, target: str) -> list[dict]:
    out: list[dict] = []
    for t in (data or {}).get("data", []):
        text = t.get("text", "")
        if not text:
            continue
        metrics = t.get("public_metrics", {})
        engagement = int(metrics.get("like_count", 0)) + int(metrics.get("retweet_count", 0))
        out.append(
            candidate(
                title=text[:120],
                problem=text,
                source_type="x",
                url=f"https://twitter.com/i/web/status/{t.get('id')}",
                engagement=engagement,
                created_at=t.get("created_at"),
            )
        )
    return out
