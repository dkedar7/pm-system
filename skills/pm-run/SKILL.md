---
name: pm-run
description: Run the PM opportunity funnel against an OSS target — discover opportunities, adversarially stress-test and rerank them, persist a ranked backlog that stops at the human gate, and (separately) delegate approved items to implementation. Use when the user says "run pm", "find opportunities in <repo>", "pm-run <target>", or "delegate approved opportunities".
argument-hint: "<owner/repo or ecosystem target>"
---

# pm-run — opportunity funnel orchestrator

This skill opts into multi-agent orchestration. It fans out the adversarial kill-test panel
and the RICE reranker over discovered candidates, writes results to the SQLite backlog via
`pmkit`, and **stops at the human gate** — it never approves or auto-delegates. Delegation of
already-approved items is a separate, explicit step (Stage 3).

Use `--db <path>` on `pmkit` calls if the operator points at a non-default backlog.

## Stage 1 — Run the funnel (discover → stress-test → rank)

Run the deterministic orchestration in `workflows/pm-funnel.js` via the harness Workflow
tool, passing the target. It performs:

1. **Discover** — `pmkit discover <target>` ingests + dedups signals into `new` candidates.
2. **Kill-test** — for each `new` candidate, fan out the four `pm-killtest-*` agents
   (already-solved, pain-is-rare, infeasible, won't-be-adopted) in parallel. Apply the
   **majority rule: prune when ≥ 3 of 4 axes refute**; otherwise the candidate survives.
   Record verdicts: `pmkit backlog ...` (the workflow writes `survived`/`pruned`).
3. **Rerank** — for each survivor, run `pm-reranker` to get RICE sub-scores, then persist
   with `pmkit` (the composite is computed by `pmkit`'s RICE function).
4. **Halt** — the run ends with a ranked backlog of `survived` items. It does **not** advance
   anything to `specced`/`approved`/`delegated`.

Edge cases the workflow handles: **zero candidates** → report "nothing new" and stop; a
**single kill-test agent failure** → decide on the remaining verdicts rather than aborting
the candidate.

If the Workflow tool is unavailable, run the stages manually: `pmkit discover <target>`, then
dispatch the kill-test and reranker agents yourself per candidate, writing results with `pmkit`.

After the run, show the operator the top of the backlog: `pmkit backlog list --status survived --sort score`.

## Stage 2 — Review and gate (human)

The operator drives this:
- Inspect: `pmkit backlog list` / `pmkit backlog show <id>`.
- Select for drafting: `pmkit backlog promote <id>` (→ `specced`), then `/pm-spec <id>` to draft
  category-aware requirements.
- Approve at the gate: `pmkit backlog approve <id>` (→ `approved`). Only a human approves.

## Stage 3 — Delegate approved items

For each `approved` item the operator asks to ship:
1. Read it: `pmkit backlog show <id> --json` (use its `spec_path` and `category`).
2. Hand the spec to implementation — invoke `/ce-plan` with the spec doc (or `/lfg` for the
   full autonomous build), carrying the category so the planner honors the interface contract.
3. Record the handoff: `pmkit backlog delegate <id>` (→ `delegated`). This **refuses** any item
   without an approval record — the gate is enforced in code, not just convention.

`auto_gate` (a future per-target option to make Stage 2's approval optional) defaults **off**;
v1 always requires a human approval before Stage 3. The approval/delegation records are the
contract that makes per-target autonomy a later config change, not a rewrite.
