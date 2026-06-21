---
name: pm-dogfood
description: Acceptance-test a shipped product by using it exactly as the docs advertise — install from the published artifact in a clean room, infer usage from the docs, exercise every interface the product's category demands (human-and-agent → real-browser UI + real MCP-client handshake), then report doc-vs-reality gaps and auto-file confirmed ones to the backlog. Use when the user says "dogfood <product>", "acceptance-test <product>", or "pm-dogfood <product>".
argument-hint: "<product> [--category agent-only|human-and-agent]"
---

# pm-dogfood — the funnel's acceptance stage

Use a shipped product the way a fresh user/agent would, following only what the docs say,
and report where reality diverges. This is the funnel's closing stage: `discover → rerank →
spec → gate → delegate → ship → dogfood`. Its point is to catch what tests miss — doc drift
and broken claims — because it follows the **published docs against the published artifact**,
not the source tree.

Deterministic work is in `pmkit dogfood …`; this skill owns inference and judgment.

## Inputs
- A product: its repo (for docs) and published artifact. Optionally `--category`; if omitted,
  read it from the product's pm-system backlog item.

## Steps

1. **Read the docs.** Read the product's README and linked docs — they are the source of
   truth for how it's *supposed* to be installed and used.

2. **Clean-room install, verbatim.** Run the documented install commands as written:
   `pmkit dogfood install --cmd "<documented command>" [--cmd "…"]`. It runs them in a
   throwaway env. A failed documented step is a **gap** (e.g. a README that says
   `uv tool install .` for a PyPI package), not a stop — keep going.

3. **Infer the scenario from the docs.** From the documented usage, derive the concrete
   interactions to perform. Synthesize a minimal sample input when the product needs one
   (e.g. a small Streamlit app for streamlit-mcp). No declared scenario file is required.

4. **Derive the interfaces from the category** (see `references/dogfood-method.md`):
   - `agent-only` → exercise the agent surface only.
   - `human-and-agent` → exercise **both** the human surface and the agent surface.

5. **Exercise each surface (real, not headless shortcuts):**
   - Human/UI: run the app and drive its rendered UI in a real browser —
     `pmkit dogfood ui --url <url> --steps '<json steps>'`.
   - Agent/MCP: connect as a real client —
     `pmkit dogfood mcp --server "<documented serve command>" --calls '<json tool calls>'`.

6. **Judge gaps and confirm.** A documented claim that doesn't hold (a tool that errors, a
   feature that isn't wired, surfaces that disagree) is a gap. **Re-run a failing step to
   confirm** before filing — flaky/non-reproducible observations stay report-only.

7. **Report + auto-file.** Assemble a report (per-interface pass/fail + each gap's
   claim/observed + UI↔MCP parity) and file the **confirmed** gaps to the backlog, deduped,
   tagged `source=dogfood`. (The report/parity/file logic lives in `pmkit`'s dogfood module.)

## Output
The dogfood report (PASS or the gap list), plus a note of which confirmed gaps were filed to
the backlog (and which were report-only). Stops there — it does not fix the gaps.

> Live UI/MCP drivers need `pmkit[dogfood]` (Playwright + FastMCP client) and a browser
> (`playwright install chromium`). The install/report/file stages are stdlib-only.
>
> **Windows:** the UI path also needs the **Microsoft Visual C++ 2015–2022 Redistributable
> (x64)** — Playwright's sync API rides on greenlet, whose compiled extension links
> `vcruntime140_1.dll` / `msvcp140.dll`. Without it the browser fails to launch with
> `DLL load failed while importing _greenlet` (uv's standalone Python ships only
> `vcruntime140.dll`, so plain-C extensions load but greenlet does not). Install once with
> `winget install Microsoft.VCRedist.2015+.x64`. `playwright_available()` reflects this —
> it returns False when the runtime can't launch, so the UI path degrades to a clean
> finding rather than a crash.
