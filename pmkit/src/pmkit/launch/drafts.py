"""Draft starting-points + slop-critic verdicts — with a structural never-final guardrail.

The drafting agent produces *starting-points* and the independent slop-critic judges them.
This module stores and emits them. The guardrail is structural, not cosmetic: there is no
"final"/"postable" state anywhere in the data model or this API, so nothing here can be
mistaken for a ready post. Every emitted draft is labeled a starting-point the operator must
rewrite in their own voice. The operator writes the final post and posts it.
"""

from __future__ import annotations

DRAFT_KIND = "starting_point"  # the only kind — there is deliberately no 'final'/'postable'

_PREAMBLE = (
    "STARTING-POINTS — raw material, NOT posts. Rewrite each in your own voice; "
    "never paste as-is. You write the final post and you post it."
)


def record_draft(
    store,
    product: str,
    platform: str,
    text: str,
    *,
    community: str | None = None,
    critic: dict | None = None,
) -> int:
    """Store one draft starting-point (optionally with its slop-critic verdict)."""
    return store.add_draft(product, platform, text, community=community, critic=critic)


def emit(drafts: list[dict]) -> str:
    """Render stored drafts, ALWAYS labeled starting-points; flag any the critic flagged."""
    lines = [_PREAMBLE, ""]
    if not drafts:
        lines.append("_(no drafts)_")
        return "\n".join(lines) + "\n"
    for d in drafts:
        loc = f"{d['platform']}" + (f" · {d['community']}" if d.get("community") else "")
        lines.append(f"## [{d['id']}] {loc} — STARTING-POINT (rewrite before posting)")
        if d.get("critic_flagged"):
            critic = d.get("critic") or {}
            tells = ", ".join(critic.get("tells", [])) or "reads as AI slop"
            lines.append(f"> ⚠ slop-critic FLAGGED (score {critic.get('score', '?')}): {tells}")
            if critic.get("suggestion"):
                lines.append(f"> fix: {critic['suggestion']}")
        elif d.get("critic_flagged") is False:
            lines.append("> slop-critic: clear")
        lines.append("")
        lines.append(d["text"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
