"""U6 tests — sample-app synth + the streamlit-mcp end-to-end glue.

The deterministic end-to-end (install report -> findings -> file gaps) runs everywhere.
The live drive (real browser + real MCP client + network install) is gated on the
optional deps being present, so it skips in a plain test env.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pmkit.backlog import Backlog
from pmkit.dogfood.install import InstallReport, StepResult
from pmkit.dogfood.file_gaps import file_gaps
from pmkit.dogfood.mcp import mcp_client_available
from pmkit.dogfood.report import build_report
from pmkit.dogfood.sample import sample_streamlit_source, synth_streamlit_app
from pmkit.dogfood.ui import playwright_available


def test_sample_source_is_valid_python_with_widgets():
    src = sample_streamlit_source()
    compile(src, "<sample_app>", "exec")  # must be valid Python
    assert "st.text_input(" in src and "st.button(" in src and "st.session_state" in src


def test_synth_writes_app(tmp_path):
    p = synth_streamlit_app(str(tmp_path / "app.py"))
    assert Path(p).exists() and "st.text_input(" in Path(p).read_text(encoding="utf-8")


def test_end_to_end_deterministic_glue(tmp_path):
    """The pipeline minus live drivers: a documented install gap flows to a filed,
    confirmed backlog opportunity; matching surfaces report parity pass."""
    synth_streamlit_app(str(tmp_path / "app.py"))
    install = InstallReport(steps=[
        StepResult("uvx streamlit-mcp", True, 0, "ok", gap=False),
        StepResult("uv tool install .", False, 1, "no pyproject here", gap=True, reason="exit 1"),
    ])
    report = build_report(
        "streamlit/streamlit",
        install=install,
        ui=[{"step": "set Name=agent", "ok": True, "observed": "set"}],
        mcp=[{"step": "set_widget", "ok": True, "observed": "ok"}],
        ui_state={"name": "agent"},
        mcp_state={"name": "agent"},
    )
    assert report.passed() is False  # the install gap
    assert any(f.interface == "parity" and not f.gap for f in report.findings)  # parity holds

    bl = Backlog(str(tmp_path / "b.db"))
    gap_title = report.gaps[0].title
    out = file_gaps(bl, "streamlit/streamlit", report.gaps, confirmed={gap_title})
    assert len(out["filed"]) == 1
    assert bl.list()[0]["title"].startswith("[dogfood]")
    bl.close()


@pytest.mark.skipif(
    not (playwright_available() and mcp_client_available()),
    reason="live streamlit-mcp dogfood needs pmkit[dogfood] (Playwright + FastMCP) + network",
)
def test_live_streamlit_mcp_scenario(tmp_path):  # pragma: no cover - integration
    # Placeholder for the full live run (synth app -> install uvx streamlit-mcp ->
    # drive UI + MCP -> parity -> report). Exercised manually / in an integration env.
    app = synth_streamlit_app(str(tmp_path / "app.py"))
    assert Path(app).exists()
