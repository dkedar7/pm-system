---
name: pm-spec
description: Draft a survived opportunity into a requirements document, classifying it as agent-only or human-and-agent and enforcing a human-first interface with human↔agent parity for human-and-agent products. Use when the user says "spec opportunity <id>", "draft requirements for <id>", or "pm-spec <id>" against the pm-system backlog.
argument-hint: "<backlog opportunity id>"
---

# pm-spec — category-aware requirements drafting

Turn one survived/promoted backlog opportunity into a requirements document a planner can
implement, with the product category and its interface obligations baked in. This is a
human-and-agent skill: a person can run the same steps; the agent just automates them.

## Inputs
- A backlog opportunity id. Read it: `pmkit backlog show <id> --json`.
  Use `--db <path>` if the operator points at a non-default backlog.

## Steps

1. **Read the opportunity.** Pull its title, problem, sources, engagement, and kill-test
   verdicts via `pmkit backlog show <id> --json`. If its status is `survived`, promote it
   first: `pmkit backlog promote <id>` (→ `specced`).

2. **Classify the category.** Apply `references/category-enforcement.md`. Decide
   `agent-only` vs `human-and-agent`, then record it:
   `pmkit backlog categorize <id> --category <category>`.

3. **Draft the requirements doc.** Reuse the compound-engineering requirements shape
   (Summary, Problem Frame, Requirements with R-IDs, Scope Boundaries, Success Criteria) —
   prefer running `/ce-brainstorm` for the drafting when available, seeding it with the
   opportunity's problem and sources. Whatever the drafting path:
   - Put the resolved **category** in the doc's summary/frontmatter.
   - If **human-and-agent**, the FIRST requirements are the human-first interface and the
     human↔agent parity clause (see the enforcement reference). These are mandatory.
   - If **agent-only**, state the agent-only scope and omit the interface requirements.
   Write the doc to `docs/brainstorms/YYYY-MM-DD-<slug>-requirements.md`.

4. **Record the spec path.** `pmkit backlog spec <id> --path <doc-path>` so the backlog and
   the eventual delegation handoff point at the drafted requirements.

5. **Stop at the gate.** Leave the item at `specced`. Approval (`pmkit backlog approve <id>`)
   is a human action — do not approve or delegate from this skill.

## Output
Report the opportunity id, the chosen category, and the requirements doc path. Note that the
item is awaiting human approval at the gate.
