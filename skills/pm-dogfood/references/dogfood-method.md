# Dogfood method

The detail behind the pm-dogfood flow.

## Infer the scenario from the docs

There is no declared per-product scenario in v1. Read the product's README/docs and reproduce
the documented usage as a fresh user would — the install commands, the example invocations,
the advertised features. The discipline: **only do what the docs tell you**. If the docs are
incomplete or wrong, that *is* the finding. Synthesize the smallest sample input the documented
usage needs (e.g. a minimal Streamlit app to serve), rather than asking the operator for one.

## Category → interfaces

The set of surfaces to exercise comes from the product's category (the same taxonomy the
funnel assigns at spec time):

| Category | Surfaces to exercise |
|---|---|
| `agent-only` | the agent surface only (no UI pass) |
| `human-and-agent` | **both** the human surface (real browser) and the agent surface (real MCP client) |

For `human-and-agent` products, also assert **parity**: the two surfaces must produce
consistent results for the same actions; divergence is a gap.

## The confirmed-on-re-run rule

Inferring from docs is non-deterministic, so a single failure isn't enough to file. A gap is
**confirmed** only if it reproduces on a re-run of the failing step. Confirmed gaps are
auto-filed to the backlog (deduped, `source=dogfood`); unconfirmed/flaky ones stay in the
report only. This keeps the backlog clean across repeated runs.

## Example: streamlit-mcp (human-and-agent)

1. Install per the README: `uvx streamlit-mcp` (a gap if the documented command fails).
2. Synthesize a minimal Streamlit app (a text input, a button, an output line).
3. Human/UI: run the app; drive it in a real browser — set the input, click the button, read
   the output (`pmkit dogfood ui`).
4. Agent/MCP: `streamlit-mcp serve <app>`; connect as an MCP client and call
   `set_widget` / `click` / `read_output` on the same app (`pmkit dogfood mcp`).
5. Parity: the value read via the UI and via `read_output` must agree.
6. Report + file confirmed gaps. (This run would have flagged this session's two real bugs:
   a wrong documented install command, and a claimed HTTP bearer auth that wasn't enforced.)
