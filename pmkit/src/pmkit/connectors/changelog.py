"""Changelog / releases utility.

Recent releases are not opportunities, so this is not a candidate-producing connector.
It supplies "recently shipped" context that the already-solved kill-test (U4) uses to
refute candidates a maintainer has just addressed. Zero-config (GitHub releases API).
"""

from __future__ import annotations

from .base import Config, ConnectorError, http_get_json


def recent_releases(target: str, cfg: Config, limit: int = 10) -> list[dict]:
    if "/" not in target:
        raise ConnectorError(f"changelog needs an owner/repo target, got {target!r}")
    owner, repo = target.split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page={limit}"
    headers = {"Accept": "application/vnd.github+json"}
    if cfg.github_token:
        headers["Authorization"] = f"Bearer {cfg.github_token}"
    data = http_get_json(url, headers, cfg.timeout)
    return parse_releases(data)


def parse_releases(data: list) -> list[dict]:
    out: list[dict] = []
    for r in data or []:
        out.append(
            {
                "name": r.get("name") or r.get("tag_name", ""),
                "tag": r.get("tag_name", ""),
                "published_at": r.get("published_at"),
                "body": (r.get("body") or "")[:2000],
                "url": r.get("html_url", ""),
            }
        )
    return out
