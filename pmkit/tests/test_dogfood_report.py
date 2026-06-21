"""U5 tests — report, parity, render."""

from __future__ import annotations

from pmkit.dogfood.install import InstallReport, StepResult
from pmkit.dogfood.report import build_report, parity_check, render_markdown


def _install(ok_cmd="good", bad=False):
    steps = [StepResult("good cmd", True, 0, "ok", gap=False)]
    if bad:
        steps.append(StepResult("uv tool install .", False, 1, "no pyproject", gap=True, reason="exit 1"))
    return InstallReport(steps=steps)


def test_from_install_maps_pass_and_gap():
    rep = build_report("o/r", install=_install(bad=True))
    statuses = {(f.interface, f.status, f.gap) for f in rep.findings}
    assert ("install", "pass", False) in statuses
    assert ("install", "fail", True) in statuses
    assert rep.passed() is False


def test_failed_ui_observation_is_gap():
    rep = build_report("o/r", ui=[{"step": "click Save", "ok": False, "observed": "button not found"}])
    g = rep.gaps[0]
    assert g.interface == "ui" and g.title == "click Save" and "not found" in g.observed


def test_parity_divergence_is_gap():
    findings = parity_check({"name": "agent"}, {"name": "world"})
    assert len(findings) == 1 and findings[0].gap and "disagree" in findings[0].title


def test_parity_match_is_pass():
    findings = parity_check({"name": "agent", "count": 1}, {"name": "agent", "count": 1})
    assert len(findings) == 1 and findings[0].gap is False and findings[0].status == "pass"


def test_parity_disjoint_nonempty_is_not_checkable():
    f = parity_check({"a": 1}, {"b": 2})
    assert len(f) == 1 and f[0].gap and "not checkable" in f[0].title


def test_parity_both_empty_is_silent():
    assert parity_check({}, {}) == []


def test_build_report_with_parity_states():
    rep = build_report(
        "o/r",
        ui=[{"step": "read", "ok": True, "observed": "ok"}],
        mcp=[{"step": "read", "ok": True, "observed": "ok"}],
        ui_state={"name": "agent"},
        mcp_state={"name": "world"},
    )
    assert any(f.interface == "parity" and f.gap for f in rep.findings)
    assert rep.per_interface()["ui"]["pass"] == 1


def test_render_markdown_contains_target_and_gaps():
    rep = build_report("plotly/streamlit", install=_install(bad=True))
    md = render_markdown(rep)
    assert "plotly/streamlit" in md and "GAPS FOUND" in md and "uv tool install ." in md


def test_clean_report_passes():
    rep = build_report("o/r", install=_install(bad=False))
    assert rep.passed() is True and "PASS" in render_markdown(rep)
