"""Tier-A collateral capture — record the real product working.

The most credible, least-slop dev collateral is the tool itself in action. This module
captures that authentically by reusing the pm-dogfood drivers: Playwright screenshots/video
of a running app, asciinema CLI casts, and SVG/HTML rendered to PNG via the same browser. No
AI-generated media (that's deferred v2).

``plan_capture`` (pure) validates a capture spec; ``run_capture`` (live, gated) performs it.
Each capture kind is gated on its tool's availability — a missing tool degrades that step to a
clean skip, never a crash. Pure validation is unit-tested; the live pass is exercised by the
scenario/integration run and on a real machine.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Optional

CAPTURE_KINDS = ("screenshot", "video", "cli_cast", "diagram")


def plan_capture(requests: list[dict]) -> list[dict]:
    """Validate + normalize capture requests into a plan. Pure (no browser, no shell)."""
    plan: list[dict] = []
    for i, r in enumerate(requests):
        kind = r.get("kind")
        if kind not in CAPTURE_KINDS:
            raise ValueError(f"request {i}: unknown kind {kind!r} (expected {CAPTURE_KINDS})")
        name = r.get("name") or f"{kind}-{i}"
        if kind in ("screenshot", "video"):
            if not r.get("url"):
                raise ValueError(f"request {i} ({kind}): missing 'url'")
            plan.append({"kind": kind, "name": name, "url": r["url"],
                         "steps": r.get("steps") or []})
        elif kind == "cli_cast":
            if not r.get("command"):
                raise ValueError(f"request {i} (cli_cast): missing 'command'")
            plan.append({"kind": kind, "name": name, "command": r["command"]})
        else:  # diagram
            if not r.get("html") and not r.get("html_path"):
                raise ValueError(f"request {i} (diagram): needs 'html' or 'html_path'")
            plan.append({"kind": kind, "name": name,
                         "html": r.get("html"), "html_path": r.get("html_path")})
    return plan


def _tool_for(kind: str) -> str:
    return "asciinema" if kind == "cli_cast" else "playwright/chromium"


def capture_available(kind: str) -> bool:
    """Is the tool needed for this capture kind installed and launchable?"""
    if kind == "cli_cast":
        return shutil.which("asciinema") is not None
    # screenshot / video / diagram all need a launchable browser (reuse the dogfood gate).
    from ..dogfood.ui import playwright_available
    return playwright_available()


def run_capture(plan: list[dict], outdir: str, *, url_timeout_ms: int = 15000) -> list[dict]:
    """Perform the capture plan. Each step's tool is gated; unavailable -> clean skip.

    Returns per-step results: ``{kind, name, ok, [path], [skipped], [reason]}``. Never raises
    for a single step's failure — the run continues so independent captures still land.
    """
    os.makedirs(outdir, exist_ok=True)
    results: list[dict] = []
    for step in plan:
        kind = step["kind"]
        if not capture_available(kind):
            results.append({"kind": kind, "name": step["name"], "ok": False,
                            "skipped": True, "reason": f"{_tool_for(kind)} unavailable"})
            continue
        try:
            path = _capture_one(step, outdir, url_timeout_ms)
            results.append({"kind": kind, "name": step["name"], "ok": True, "path": path})
        except Exception as e:
            results.append({"kind": kind, "name": step["name"], "ok": False,
                            "skipped": False, "reason": f"{type(e).__name__}: {e}"})
    return results


def _capture_one(step: dict, outdir: str, url_timeout_ms: int) -> Optional[str]:
    kind = step["kind"]
    if kind == "cli_cast":
        return _capture_cli_cast(step, outdir)
    if kind == "diagram":
        return _capture_diagram(step, outdir)
    return _capture_browser(step, outdir, url_timeout_ms)


def _apply_steps(page, steps: list[dict]) -> None:
    # Reuse the pm-dogfood Streamlit-aware UI stepping (fill+Enter+settle).
    from ..dogfood.ui import _run_step, translate_steps
    for s in translate_steps(steps):
        _run_step(page, s)


def _capture_browser(step: dict, outdir: str, url_timeout_ms: int) -> Optional[str]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            if step["kind"] == "video":
                ctx = browser.new_context(record_video_dir=outdir)
                page = ctx.new_page()
                page.goto(step["url"], timeout=url_timeout_ms)
                _apply_steps(page, step["steps"])
                vid = page.video.path() if page.video else None
                ctx.close()
                return vid
            page = browser.new_page()
            page.goto(step["url"], timeout=url_timeout_ms)
            _apply_steps(page, step["steps"])
            out = os.path.join(outdir, f"{step['name']}.png")
            page.screenshot(path=out, full_page=True)
            return out
        finally:
            browser.close()


def _capture_diagram(step: dict, outdir: str) -> Optional[str]:
    from playwright.sync_api import sync_playwright

    html_path = step.get("html_path")
    tmp = None
    if not html_path:
        fd, tmp = tempfile.mkstemp(suffix=".html", prefix="pmkit-diagram-")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(step["html"])
        html_path = tmp
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(f"file://{os.path.abspath(html_path)}")
                out = os.path.join(outdir, f"{step['name']}.png")
                page.screenshot(path=out, full_page=True)
                return out
            finally:
                browser.close()
    finally:
        if tmp:
            os.unlink(tmp)


def _capture_cli_cast(step: dict, outdir: str) -> Optional[str]:
    import subprocess

    out = os.path.join(outdir, f"{step['name']}.cast")
    subprocess.run(
        ["asciinema", "rec", "--overwrite", "--command", step["command"], out],
        check=True, capture_output=True, text=True, timeout=120,
    )
    return out
