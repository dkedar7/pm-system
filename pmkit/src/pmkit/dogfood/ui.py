"""Human/UI driver — drives a rendered app in a real browser via Playwright.

The step-translation (scenario -> action plan) is pure and unit-tested. The live browser
pass lazily imports Playwright and is gated on availability, so pmkit stays stdlib-only and
the test suite runs without a browser. Live selectors are best-effort for Streamlit (label
+ role) and are validated by the integration run (U6), not unit tests.
"""

from __future__ import annotations

from typing import Any, Optional

SUPPORTED_ACTIONS = ("set", "click", "read")


def translate_steps(steps: list[dict]) -> list[dict]:
    """Validate + normalize inferred scenario steps into a UI action plan. Pure."""
    plan: list[dict] = []
    for i, s in enumerate(steps):
        action = s.get("action")
        if action not in SUPPORTED_ACTIONS:
            raise ValueError(f"step {i}: unknown action {action!r} (expected {SUPPORTED_ACTIONS})")
        target = s.get("target")
        if action in ("set", "click") and not target:
            raise ValueError(f"step {i}: '{action}' needs a target")
        if action == "set" and "value" not in s:
            raise ValueError(f"step {i}: 'set' needs a value")
        plan.append({"action": action, "target": target, "value": s.get("value")})
    return plan


def playwright_available() -> bool:
    # Import the sync API, not just the top-level package: the sync API pulls in
    # greenlet's compiled extension, so a shallow `import playwright` can pass while
    # the browser runtime cannot actually start (e.g. a missing VC++ runtime DLL on
    # Windows). Importing sync_playwright makes the gate reflect launchability.
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception:
        return False
    return True


def drive_ui(url: str, steps: list[dict], *, timeout_ms: int = 10000) -> list[dict]:
    """Drive the app's rendered UI in a real browser. Raises if Playwright is absent."""
    plan = translate_steps(steps)
    if not playwright_available():
        raise RuntimeError("Playwright not installed — run `pip install 'pmkit[dogfood]'` "
                           "then `playwright install chromium`")
    from playwright.sync_api import sync_playwright

    obs: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            try:
                page.goto(url, timeout=timeout_ms)
            except Exception as e:
                # a failed connect is a gap, not a crash (and must not skip browser.close)
                obs.append({"step": f"goto {url}", "ok": False,
                            "observed": f"{type(e).__name__}: {e}"})
                return obs
            for step in plan:
                obs.append(_run_step(page, step))
        finally:
            browser.close()
    return obs


def _settle(page: Any) -> None:
    """Let a reactive frontend (e.g. Streamlit) finish its rerun before we read.

    Streamlit reruns asynchronously over a websocket: an interaction returns
    immediately but the new DOM paints a beat later. Reading too soon captures the
    pre-rerun page. We wait for network to quiesce (best-effort — the websocket may
    never fully idle) plus a short paint budget. Cheap and generic across frameworks.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    page.wait_for_timeout(400)


def _run_step(page: Any, step: dict) -> dict:
    action, target, value = step["action"], step["target"], step["value"]
    try:
        if action == "set":
            loc = page.get_by_label(target)
            loc.fill(str(value))
            # Streamlit (and many reactive inputs) only commit a typed value on
            # Enter/blur, not on a programmatic fill — without this the rerun never
            # fires and the new value is silently dropped.
            loc.press("Enter")
            _settle(page)
            return {"step": f"set {target}={value}", "ok": True, "observed": "set"}
        if action == "click":
            page.get_by_role("button", name=target).click()
            _settle(page)
            return {"step": f"click {target}", "ok": True, "observed": "clicked"}
        # read
        text = page.get_by_text(target).inner_text() if target else page.inner_text("body")
        return {"step": f"read {target or 'page'}", "ok": True, "observed": text[:500]}
    except Exception as e:
        return {"step": f"{action} {target}", "ok": False, "observed": f"{type(e).__name__}: {e}"}
