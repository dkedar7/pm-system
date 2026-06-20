"""Reddit connector via the public search JSON. Keyless but rate-limited; degrades."""

from __future__ import annotations

import urllib.parse

from .base import Config, candidate, http_get_json


class RedditConnector:
    name = "reddit"

    def available(self, cfg: Config) -> tuple[bool, str]:
        return True, "public search JSON (best-effort; may rate-limit)"

    def fetch(self, target: str, cfg: Config, limit: int = 25) -> list[dict]:
        query = target.split("/")[-1]
        q = urllib.parse.quote(query)
        url = f"https://www.reddit.com/search.json?q={q}&sort=top&t=year&limit={limit}"
        data = http_get_json(url, {}, cfg.timeout)
        return parse_reddit(data, query)


def parse_reddit(data: dict, query: str) -> list[dict]:
    out: list[dict] = []
    for child in (data or {}).get("data", {}).get("children", []):
        d = child.get("data", {})
        title = d.get("title", "")
        if not title:
            continue
        permalink = d.get("permalink", "")
        out.append(
            candidate(
                title=title,
                problem=(d.get("selftext") or f"Reddit discussion re: {query}")[:1000],
                source_type="reddit",
                url=f"https://www.reddit.com{permalink}" if permalink else d.get("url", ""),
                engagement=int(d.get("score", 0)) + int(d.get("num_comments", 0)),
                created_at=str(d.get("created_utc", "")),
            )
        )
    return out
