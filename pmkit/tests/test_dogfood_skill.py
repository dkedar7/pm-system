"""U1 tests — pm-dogfood skill + method reference are well-formed."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "pm-dogfood" / "SKILL.md"
METHOD = ROOT / "skills" / "pm-dogfood" / "references" / "dogfood-method.md"


def test_skill_frontmatter_and_flow():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---")
    head = text.split("---", 2)[1]
    assert "name: pm-dogfood" in head
    assert "argument-hint:" in head
    # the orchestration references the pmkit dogfood helpers
    for cmd in ("pmkit dogfood install", "pmkit dogfood ui", "pmkit dogfood mcp"):
        assert cmd in text
    assert "category-enforcement" not in text  # this is dogfood, not pm-spec
    assert "dogfood-method" in text


def test_method_reference_encodes_rules():
    text = METHOD.read_text(encoding="utf-8")
    # category -> interface mapping
    assert "agent-only" in text and "human-and-agent" in text
    # the confirmed-on-re-run rule and parity
    assert "reproduc" in text.lower() and "parity" in text.lower()
    # infer-from-docs
    assert "docs" in text.lower()
    # the streamlit-mcp worked example
    assert "streamlit-mcp" in text
