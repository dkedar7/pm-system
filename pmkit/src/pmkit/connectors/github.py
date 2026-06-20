"""GitHub issues connector. Zero-config (better with GITHUB_TOKEN for rate limits)."""

from __future__ import annotations

from .base import Config, ConnectorError, candidate, http_get_json


class GitHubConnector:
    name = "github"

    def available(self, cfg: Config) -> tuple[bool, str]:
        return True, "public API (set GITHUB_TOKEN to raise rate limits)"

    def fetch(self, target: str, cfg: Config, limit: int = 25) -> list[dict]:
        if "/" not in target:
            raise ConnectorError(f"github needs an owner/repo target, got {target!r}")
        owner, repo = target.split("/", 1)
        # sort=comments (desc) biases toward discussed issues; avoids the URL-encoding
        # pitfalls of the reactions-+1 token while still surfacing high-signal pain.
        url = (
            f"https://api.github.com/repos/{owner}/{repo}/issues"
            f"?state=open&sort=comments&direction=desc&per_page={min(limit, 100)}"
        )
        headers = {"Accept": "application/vnd.github+json"}
        if cfg.github_token:
            headers["Authorization"] = f"Bearer {cfg.github_token}"
        data = http_get_json(url, headers, cfg.timeout)
        return parse_issues(data, target)


def parse_issues(data: list, target: str) -> list[dict]:
    """Pure parser: GitHub issues JSON -> candidates. Skips pull requests."""
    out: list[dict] = []
    for it in data or []:
        if "pull_request" in it:  # the issues endpoint also returns PRs
            continue
        reactions = (it.get("reactions") or {}).get("total_count", 0)
        engagement = int(reactions) + int(it.get("comments", 0))
        out.append(
            candidate(
                title=it.get("title", ""),
                problem=(it.get("body") or "")[:1000],
                source_type="github",
                url=it.get("html_url", ""),
                engagement=engagement,
                created_at=it.get("created_at"),
            )
        )
    return out
