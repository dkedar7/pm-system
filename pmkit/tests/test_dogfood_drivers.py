"""U3/U4 tests — UI + MCP driver pure cores, availability gating, CLI install."""

from __future__ import annotations

import sys

import pytest

from pmkit.cli import main
from pmkit.dogfood.mcp import drive_mcp, mcp_client_available, plan_calls
from pmkit.dogfood.ui import drive_ui, playwright_available, translate_steps

PY = sys.executable or "python"


# --- UI translate (pure) ---
def test_translate_valid_steps():
    plan = translate_steps([
        {"action": "set", "target": "Name", "value": "agent"},
        {"action": "click", "target": "Save"},
        {"action": "read", "target": None},
    ])
    assert [p["action"] for p in plan] == ["set", "click", "read"]


def test_translate_rejects_unknown_action():
    with pytest.raises(ValueError):
        translate_steps([{"action": "scroll", "target": "x"}])


def test_translate_set_requires_value():
    with pytest.raises(ValueError):
        translate_steps([{"action": "set", "target": "Name"}])


def test_translate_click_requires_target():
    with pytest.raises(ValueError):
        translate_steps([{"action": "click"}])


def test_playwright_available_is_bool_and_gates_drive():
    assert isinstance(playwright_available(), bool)
    if not playwright_available():
        with pytest.raises(RuntimeError):
            drive_ui("http://localhost:1", [{"action": "read", "target": None}])


# --- MCP plan (pure) ---
def test_plan_calls_valid():
    plan = plan_calls([{"tool": "set_widget", "args": {"identifier": "Name", "value": "x"}}])
    assert plan[0]["tool"] == "set_widget" and plan[0]["args"]["value"] == "x"


def test_plan_calls_requires_tool():
    with pytest.raises(ValueError):
        plan_calls([{"args": {}}])


def test_plan_calls_args_must_be_dict():
    with pytest.raises(ValueError):
        plan_calls([{"tool": "x", "args": ["nope"]}])


def test_mcp_available_is_bool_and_gates_drive():
    assert isinstance(mcp_client_available(), bool)
    if not mcp_client_available():
        with pytest.raises(RuntimeError):
            drive_mcp(["streamlit-mcp", "serve", "app.py"], [{"tool": "list_widgets", "args": {}}])


# --- CLI ---
def test_cli_dogfood_install_passes(capsys):
    rc = main(["dogfood", "install", "--cmd", f'{PY} -c "print(1)"'])
    assert rc == 0


def test_cli_dogfood_install_reports_gap(capsys):
    rc = main(["dogfood", "install", "--cmd", f'{PY} -c "import sys; sys.exit(2)"'])
    assert rc == 1  # gap -> nonzero exit
