"""U4 tests — kill-test persona files are well-formed and declare the verdict contract.

We cannot unit-test LLM judgment, but we can guarantee each persona has valid frontmatter,
the right tools, and an explicit refute/survive JSON contract — so the orchestrator (U8) can
rely on a uniform shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"

KILLTEST = [
    ("pm-killtest-solved", "already-solved"),
    ("pm-killtest-rarity", "pain-is-rare"),
    ("pm-killtest-feasibility", "infeasible"),
    ("pm-killtest-adoption", "won't-be-adopted"),
]


def _read(name: str) -> str:
    return (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def test_all_four_killtest_personas_exist():
    found = sorted(p.stem for p in AGENTS_DIR.glob("pm-killtest-*.md"))
    assert found == sorted(name for name, _ in KILLTEST)


@pytest.mark.parametrize("name,axis", KILLTEST)
def test_persona_frontmatter_and_contract(name, axis):
    text = _read(name)
    assert text.startswith("---"), f"{name} missing frontmatter"
    head = text.split("---", 2)[1]
    assert f"name: {name}" in head
    assert "description:" in head and "model:" in head and "tools:" in head
    assert "WebSearch" in head, "kill-test agents need web research tools"
    # the body must declare the axis and the refute/survive JSON contract
    assert axis in text
    assert '"verdict"' in text
    assert "refute" in text and "survive" in text
