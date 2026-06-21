"""U4 tests — the emit-only launch plan renderer (pure)."""

from __future__ import annotations

import json

import pytest

from pmkit.cli import main
from pmkit.launch.plan import build_plan, render_markdown


def test_render_attaches_policy_verdict_inline():
    plan = build_plan("streamlit-mcp", [
        {"platform": "reddit", "community": "r/gis",
         "policy": {"verdict": "warn", "cited_rules": [{"text": "1:10 ratio rule"}]}},
    ])
    md = render_markdown(plan)
    assert "WARN" in md
    assert "1:10 ratio rule" in md


def test_block_renders_do_not_post():
    plan = build_plan("p", [
        {"platform": "reddit", "community": "r/python",
         "policy": {"verdict": "block", "cited_rules": [{"text": "No self-promotion"}]}},
    ])
    md = render_markdown(plan)
    assert "DO NOT POST" in md


def test_days_render_in_order():
    plan = build_plan("p", [
        {"platform": "hackernews", "community": "Show HN", "day": 2},
        {"platform": "reddit", "community": "r/gis", "day": 0},
    ])
    md = render_markdown(plan)
    assert md.index("Day 0") < md.index("Day 2")
    assert md.index("r/gis") < md.index("Show HN")  # day 0 group first


def test_empty_targets_is_valid_plan():
    plan = build_plan("p", [])
    md = render_markdown(plan)
    assert "(no targets)" in md  # no error


def test_build_plan_requires_platform_and_community():
    with pytest.raises(ValueError):
        build_plan("p", [{"community": "r/gis"}])       # missing platform
    with pytest.raises(ValueError):
        build_plan("p", [{"platform": "reddit"}])       # missing community


def test_channel_alias_accepted():
    plan = build_plan("p", [{"platform": "x", "channel": "@handle"}])
    assert plan["targets"][0]["community"] == "@handle"


def test_emit_only_note_present():
    md = render_markdown(build_plan("p", [{"platform": "reddit", "community": "r/x"}]))
    assert "never posts" in md.lower()


def test_cli_launch_plan_json(capsys):
    targets = json.dumps([{"platform": "reddit", "community": "r/gis",
                           "policy": {"verdict": "ok"}}])
    rc = main(["launch", "plan", "--product", "streamlit-mcp", "--targets", targets, "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["product"] == "streamlit-mcp"
    assert out["targets"][0]["verdict"] == "ok"
