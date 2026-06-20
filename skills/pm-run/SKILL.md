---
name: pm-run
description: Run the PM opportunity funnel against an OSS target — discover opportunities, adversarially stress-test and rerank them, and persist a ranked backlog that stops at the human gate. Use when the user says "run pm", "find opportunities in <repo>", "pm-run <target>", or wants to refresh the opportunity backlog for a target.
argument-hint: "<owner/repo or ecosystem target>"
---

# pm-run — opportunity funnel orchestrator

> Scaffold stub. The full orchestration (discover → kill-test → rerank → persist, stopping
> at the human gate) is defined in implementation unit U8 and runs `workflows/pm-funnel.js`.

This skill opts into multi-agent orchestration: it fans out the adversarial kill-test panel
(`agents/pm-killtest-*`) and the RICE reranker (`agents/pm-reranker`) over discovered
candidates via the harness Workflow tool, then writes results to the SQLite backlog through
`pmkit`. It never advances an item past `survived` — promotion and approval are human actions
at the gate (`pmkit backlog approve`).

Until U8 lands, run the stages manually:

```bash
pmkit discover <target>        # ingest + dedup → candidates (status: new)
pmkit backlog list             # inspect what was found
```
