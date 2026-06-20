"""Connector framework: config, HTTP helper, and the candidate shape.

A connector fetches signals from one OSS source and returns *candidate* dicts. The HTTP
fetch is always separated from a pure ``parse_*`` function so parsing is unit-testable
without the network. Connectors never raise out of discovery: a missing key or a source
error is reported as a skip, not a crash (graceful degradation, R3/U3).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

DEFAULT_UA = "pmkit/0.1 (+https://github.com/dkedar7/pm-system)"


class ConnectorError(Exception):
    """A source-level failure (auth, network, bad target). Caught by discovery."""


@dataclass
class Config:
    """Runtime config, sourced from the environment. All keys optional."""

    github_token: Optional[str] = None
    brave_key: Optional[str] = None
    x_bearer: Optional[str] = None
    user_agent: str = DEFAULT_UA
    timeout: float = 15.0
    min_engagement: int = 2  # below this, a candidate is flagged low-confidence

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            github_token=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
            brave_key=os.environ.get("BRAVE_API_KEY"),
            x_bearer=os.environ.get("X_BEARER_TOKEN") or os.environ.get("TWITTER_BEARER_TOKEN"),
        )


def candidate(title: str, problem: str, source_type: str, url: str,
              engagement: int = 0, created_at: Optional[str] = None) -> dict:
    """Build a normalized candidate dict with one source of provenance."""
    return {
        "title": (title or "").strip()[:200],
        "problem": (problem or "").strip()[:1000],
        "engagement": int(engagement or 0),
        "source": {"type": source_type, "url": url, "created_at": created_at},
    }


def http_get_json(url: str, headers: Optional[dict] = None, timeout: float = 15.0):
    """GET a URL and parse JSON. Raises ConnectorError on any failure."""
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ConnectorError(f"HTTP {e.code} for {url}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ConnectorError(f"network error for {url}: {e}") from e
    except json.JSONDecodeError as e:
        raise ConnectorError(f"bad JSON from {url}: {e}") from e
