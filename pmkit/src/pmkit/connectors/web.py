"""Web search connector via Brave Search. Requires BRAVE_API_KEY; skipped otherwise."""

from __future__ import annotations

import urllib.parse

from .base import Config, ConnectorError, candidate, http_get_json


class WebConnector:
    name = "web"

    def available(self, cfg: Config) -> tuple[bool, str]:
        if cfg.brave_key:
            return True, "Brave Search"
        return False, "no BRAVE_API_KEY"

    def fetch(self, target: str, cfg: Config, limit: int = 20) -> list[dict]:
        if not cfg.brave_key:
            raise ConnectorError("no BRAVE_API_KEY")
        query = f"{target.split('/')[-1]} issues OR limitations OR feature request"
        q = urllib.parse.quote(query)
        url = f"https://api.search.brave.com/res/v1/web/search?q={q}&count={min(limit, 20)}"
        headers = {"Accept": "application/json", "X-Subscription-Token": cfg.brave_key}
        data = http_get_json(url, headers, cfg.timeout)
        return parse_brave(data, target)


def parse_brave(data: dict, target: str) -> list[dict]:
    out: list[dict] = []
    for r in (data or {}).get("web", {}).get("results", []):
        title = r.get("title", "")
        if not title:
            continue
        out.append(
            candidate(
                title=title,
                problem=(r.get("description") or "")[:1000],
                source_type="web",
                url=r.get("url", ""),
                engagement=0,  # web results carry no engagement signal
            )
        )
    return out
