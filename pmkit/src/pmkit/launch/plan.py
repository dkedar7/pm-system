"""The emit-only launch plan renderer.

Turns structured targets (produced by the ``pm-launch-targeter`` agent, each carrying its
mod-policy verdict from ``policy.py``) into a dated checklist the operator follows. Pure and
deterministic. **Emit-only**: this renders an artifact and creates no cron entries and posts
nothing — the human owns timing and the act of posting.
"""

from __future__ import annotations

# Human-readable verdict markers (ASCII — renders safely on any terminal).
_MARK = {
    "block": "BLOCK — DO NOT POST HERE",
    "warn": "WARN — check the cited rule",
    "ok": "OK",
    "unavailable": "RULES UNAVAILABLE — check manually",
    "unknown": "UNKNOWN — research policy first",
}


def build_plan(product: str, targets: list[dict]) -> dict:
    """Validate + normalize targets into an ordered plan. Pure.

    Each target: ``{platform, community|channel, [thread], [angle], [day], [policy]}`` where
    ``policy`` is the dict from ``policy.resolve_policy`` (``{verdict, cited_rules, [note]}``).
    """
    norm: list[dict] = []
    for i, t in enumerate(targets):
        platform = t.get("platform")
        community = t.get("community") or t.get("channel")
        if not platform:
            raise ValueError(f"target {i}: missing 'platform'")
        if not community:
            raise ValueError(f"target {i}: missing 'community'/'channel'")
        policy = t.get("policy") or {}
        norm.append({
            "platform": platform,
            "community": community,
            "thread": t.get("thread"),
            "angle": t.get("angle"),
            "day": int(t.get("day", 0)),
            "verdict": policy.get("verdict") or "unknown",
            "cited_rules": policy.get("cited_rules") or [],
            "note": policy.get("note"),
        })
    norm.sort(key=lambda x: (x["day"], x["platform"], x["community"]))
    return {"product": product, "targets": norm}


def render_markdown(plan: dict) -> str:
    """Render the plan as a dated, emit-only checklist."""
    lines = [
        f"# Launch plan: {plan['product']}",
        "",
        "> Emit-only. pm-launch prepared this; **you** write the final post in your voice "
        "and post it — the system never posts.",
        "",
    ]
    targets = plan.get("targets", [])
    if not targets:
        lines.append("_(no targets)_")
        return "\n".join(lines) + "\n"

    by_day: dict[int, list[dict]] = {}
    for t in targets:
        by_day.setdefault(t["day"], []).append(t)

    for day in sorted(by_day):
        lines.append(f"## Day {day}")
        for t in by_day[day]:
            mark = _MARK.get(t["verdict"], t["verdict"])
            lines.append(f"- [ ] **{t['platform']} · {t['community']}** — {mark}")
            for r in t["cited_rules"]:
                lines.append(f"    - rule: {r.get('text', '')}")
            if t.get("note"):
                lines.append(f"    - note: {t['note']}")
            if t.get("thread"):
                lines.append(f"    - thread: {t['thread']}")
            if t.get("angle"):
                lines.append(f"    - angle: {t['angle']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
