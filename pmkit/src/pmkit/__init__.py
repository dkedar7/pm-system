"""pmkit — the human-first CLI for the pm-system opportunity funnel.

Deterministic stages (discovery, backlog, dedup, RICE math) live here. LLM-judgment
stages (kill-test, reranking, spec drafting) run as agents/skills in the plugin and
read/write the same backlog through this package.
"""

__version__ = "0.1.1"
