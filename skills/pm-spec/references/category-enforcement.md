# Category enforcement

Every product the funnel pursues is exactly one of two categories. The category is recorded
on the backlog item and must propagate into the drafted requirements and the delegation
handoff, so downstream planning builds the right interface.

## Classify the opportunity

Ask: **does a human use the deliverable directly?**

- **human-and-agent** — a person is an intended direct user (a CLI, an app, a dashboard, a
  command, a library a developer calls). Most user-facing opportunities are this.
- **agent-only** — the deliverable is internal machinery consumed solely by other agents or
  automation, with no direct human entry point (an internal scorer, a background classifier,
  an orchestration step). When unsure, default to **human-and-agent** — under-serving humans
  is the costlier error for this funnel.

Record it: `pmkit backlog categorize <id> --category <agent-only|human-and-agent>`.

## Requirements the spec MUST carry

### If `human-and-agent`
The drafted requirements document must include, as explicit, non-optional requirements:

1. **Human-first interface.** The product's primary entry point is built for humans —
   a CLI, a UI, or a slash command (CLI is the default when nothing else is indicated).
   The human surface is primary; the agent path is secondary.
2. **Human↔agent parity.** Any action the agent can take, a human can take through that
   human-first surface, and vice versa. Neither surface has privileged capabilities the
   other lacks.

Write these as real requirements (e.g. `R1. The product ships a CLI as its primary
interface...`, `R2. Every agent-invocable action is reachable by a human via the CLI...`),
not as asides. The human-first interface requirement is the FIRST requirement in the spec.

### If `agent-only`
Do **not** impose a human-first interface or parity requirement — that would be wrong for
internal machinery. State plainly in scope that the deliverable is agent-only with no human
entry point, and focus the spec on the agent contract (inputs, outputs, invocation).

## Propagation
- The category lives on the backlog item (above).
- The spec records it in its frontmatter/summary so a planner reads it cold.
- Delegation carries the category in its handoff record (the backlog does this automatically
  in `record_delegation`), so `ce-plan`/`lfg` inherit the interface constraint.
