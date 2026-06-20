"""Hacker News connector via the Algolia search API. Zero-config."""

from __future__ import annotations

import urllib.parse

from .base import Config, candidate, http_get_json


class HNConnector:
    name = "hn"

    def available(self, cfg: Config) -> tuple[bool, str]:
        return True, "Algolia HN search (no key)"

    def fetch(self, target: str, cfg: Config, limit: int = 25) -> list[dict]:
        query = target.split("/")[-1]  # repo/project name
        q = urllib.parse.quote(query)
        url = f"https://hn.algolia.com/api/v1/search?query={q}&tags=story&hitsPerPage={limit}"
        data = http_get_json(url, {}, cfg.timeout)
        return parse_hn(data, query)


def parse_hn(data: dict, query: str) -> list[dict]:
    out: list[dict] = []
    for hit in (data or {}).get("hits", []):
        title = hit.get("title") or hit.get("story_title") or ""
        if not title:
            continue
        object_id = hit.get("objectID")
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
        out.append(
            candidate(
                title=title,
                problem=f"Discussed on Hacker News re: {query}",
                source_type="hn",
                url=url,
                engagement=int(hit.get("points", 0)) + int(hit.get("num_comments", 0)),
                created_at=hit.get("created_at"),
            )
        )
    return out
