"""Discovery connectors registry.

Each connector fetches signals from one OSS source and returns normalized candidate
dicts with provenance. Connectors degrade gracefully: a missing key or a source error
skips that source rather than aborting the run.
"""

from __future__ import annotations

from .github import GitHubConnector
from .hn import HNConnector
from .reddit import RedditConnector
from .web import WebConnector
from .x import XConnector

# Order matters only for display; discovery runs all available connectors.
REGISTRY = [
    GitHubConnector(),
    HNConnector(),
    RedditConnector(),
    WebConnector(),
    XConnector(),
]


def get_connectors(names=None):
    """Return connector instances, optionally filtered by name."""
    if not names:
        return list(REGISTRY)
    wanted = set(names)
    selected = [c for c in REGISTRY if c.name in wanted]
    unknown = wanted - {c.name for c in REGISTRY}
    if unknown:
        raise ValueError(f"unknown source(s): {sorted(unknown)}")
    return selected
