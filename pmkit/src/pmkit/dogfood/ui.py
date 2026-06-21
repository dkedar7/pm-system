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
    try:
        import playwright  # noqa: F401
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


def _run_step(page: Any, step: dict) -> dict:
    action, target, value = step["action"], step["target"], step["value"]
    try:
        if action == "set":
            page.get_by_label(target).fill(str(value))
            return {"step": f"set {target}={value}", "ok": True, "observed": "set"}
        if action == "click":
            page.get_by_role("button", name=target).click()
            return {"step": f"click {target}", "ok": True, "observed": "clicked"}
        # read
        text = page.get_by_text(target).inner_text() if target else page.inner_text("body")
        return {"step": f"read {target or 'page'}", "ok": True, "observed": text[:500]}
    except Exception as e:
        return {"step": f"{action} {target}", "ok": False, "observed": f"{type(e).__name__}: {e}"}
