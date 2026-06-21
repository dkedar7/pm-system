"""U5 tests — collateral capture: pure plan validation + availability gating.

The live capture itself (browser/asciinema) is exercised by the scenario run and on a real
machine; here we test the pure plan and that an absent tool degrades to a clean skip.
"""

from __future__ import annotations

import json

import pytest

from pmkit.cli import main
from pmkit.launch.collateral import capture_available, plan_capture, run_capture


# --- plan_capture (pure) ---
def test_plan_capture_normalizes_mixed_spec():
    plan = plan_capture([
        {"kind": "screenshot", "url": "http://localhost:8765", "name": "home"},
        {"kind": "cli_cast", "command": "uvx streamlit-mcp --help"},
        {"kind": "diagram", "html": "<h1>hi</h1>"},
    ])
    assert [p["kind"] for p in plan] == ["screenshot", "cli_cast", "diagram"]
    assert plan[0]["name"] == "home"
    assert plan[1]["name"] == "cli_cast-1"  # auto-named


def test_plan_capture_unknown_kind_raises():
    with pytest.raises(ValueError):
        plan_capture([{"kind": "hologram"}])


def test_plan_capture_screenshot_requires_url():
    with pytest.raises(ValueError):
        plan_capture([{"kind": "screenshot"}])


def test_plan_capture_cli_cast_requires_command():
    with pytest.raises(ValueError):
        plan_capture([{"kind": "cli_cast"}])


def test_plan_capture_diagram_requires_html():
    with pytest.raises(ValueError):
        plan_capture([{"kind": "diagram"}])


# --- availability gating ---
def test_capture_available_is_bool():
    for kind in ("screenshot", "video", "cli_cast", "diagram"):
        assert isinstance(capture_available(kind), bool)


def test_run_capture_skips_when_tool_unavailable(monkeypatch, tmp_path):
    # Force both tools unavailable -> every step is a clean skip, no crash.
    import pmkit.launch.collateral as col
    monkeypatch.setattr(col, "capture_available", lambda kind: False)
    plan = plan_capture([
        {"kind": "screenshot", "url": "http://x"},
        {"kind": "cli_cast", "command": "echo hi"},
    ])
    results = run_capture(plan, str(tmp_path))
    assert all(r["skipped"] and not r["ok"] for r in results)
    assert "unavailable" in results[0]["reason"]


# --- CLI ---
def test_cli_launch_capture_all_skipped_is_rc0(monkeypatch, tmp_path, capsys):
    import pmkit.launch.collateral as col
    monkeypatch.setattr(col, "capture_available", lambda kind: False)
    spec = json.dumps([{"kind": "screenshot", "url": "http://x", "name": "home"}])
    rc = main(["launch", "capture", "--spec", spec, "--outdir", str(tmp_path), "--json"])
    assert rc == 0  # environmental skips are not failures
    out = json.loads(capsys.readouterr().out)
    assert out[0]["skipped"] is True


def test_cli_launch_capture_bad_spec_rc1(capsys, tmp_path):
    rc = main(["launch", "capture", "--spec", '[{"kind":"nope"}]',
               "--outdir", str(tmp_path)])
    assert rc == 1
