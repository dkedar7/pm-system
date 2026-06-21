---
name: pm-launch
description: Prepare a shipped product's launch — find and vet the right channels/threads, research moderator policy (block/warn/ok + cited rule), build an emit-only launch plan, capture authentic Tier-A collateral, and draft per-platform STARTING-POINTS — then STOP at a hard human gate where the operator writes the final post in their voice and posts it. Afterward, listen to the response and fold it back into the backlog. Never auto-posts. Use when the user says "launch <product>", "pm-launch <product>", or "amplify <product>".
argument-hint: "<product> [--target owner/repo]"
---

# pm-launch — the funnel's launch/amplify stage

Do all the *logistics* of launching a shipped product, then hand a ready kit to the operator
and get out of the way. This is the funnel's closing loop: `discover → rerank → spec → gate →
delegate → ship → dogfood → LAUNCH → listen → discover`. It exists because a built thing
nobody hears about earns nothing — distribution is the goal the rest of the funnel serves.

Deterministic work is in `pmkit launch …`; this skill owns the research dispatch, the human
gate, and triggering the listen pass.

## The boundary (non-negotiable)
- **Automation/agents do the logistics:** targeting, mod-policy research, the plan, collateral,
  and *assistive* draft starting-points.
- **You (the human) do two things:** write the **final draft** of every post in your own voice,
  and **post it.** This is what keeps a launch from reading as slop.
- **Never auto-post.** Not to any channel, ever. No draft is ever presented as a finished post.

## Inputs
- A `product` and its `--target` (owner/repo or ecosystem). Launch config is derived on the fly
  from the repo + its pm-system backlog item; an optional `LAUNCH.md` in the product repo
  overrides (pinned channels, angle, constraints).

## Steps

1. **Target.** Dispatch `pm-launch-targeter` to find and vet the right communities/threads
   across Reddit, Hacker News, X, LinkedIn, with a cadence. Drop off-topic targets.

2. **Research mod policy (the killer feature).** For each target — Reddit foremost — dispatch
   `pm-launch-policy` to extract the community's rules, then score them:
   `pmkit launch policy --community <c> [--platform <p>]`. The verdict is **block / warn / ok**
   with the cited rule. A `block` means do not post there. This is what prevents a moderator
   pulling the post after the fact.

3. **Plan (emit-only).** Render the dated checklist from the targets + verdicts:
   `pmkit launch plan --product <p> --targets '<json>'`. It creates no cron entries and posts
   nothing — it's the routine you follow.

4. **Capture Tier-A collateral.** Record the *real product working* (the least-slop dev
   collateral): `pmkit launch capture --spec '<json>' --outdir <dir>` — reuses the dogfood
   drivers for screenshots/video, plus asciinema CLI casts and HTML→PNG diagrams. For polished
   Tier-B collateral (slides, one-pagers), prep the inputs and hand them to **Claude Design**
   (claude.ai/design) — that's your tool, not the agent's (no API yet); see the method ref.

5. **Draft starting-points.** Dispatch `pm-launch-drafter` per target (it refuses `block`
   targets), then the independent `pm-launch-slop-critic` on each draft. Store them:
   `pmkit launch draft …`. These are starting-points — raw material — never finished posts.

6. **Present the kit and STOP (the gate).** Show the operator: vetted targets + policy verdicts
   + the plan + the collateral + the labeled draft starting-points. Then stop. The operator
   writes the final post and posts it. Record what went out: `pmkit launch announce …`.

7. **Listen (a separate, later step).** After posting, fold the reactions back into the
   backlog: `pmkit launch listen <target>`. Read-only — it never engages or posts. New pain
   becomes new funnel input; echoes of known opportunities accrue as evidence.

## Hard rules
- Never post anywhere. Never present a draft as final/ready. A `block` policy verdict means do
  not post there — surface it loudly, don't paper over it.
- Listening is read-only.

## Output
The assembled launch kit (targets + policy verdicts + emit-only plan + collateral + labeled
draft starting-points), then a stop at the gate. Later, a listen summary of what folded back
into the backlog. See `references/launch-method.md` for config derivation, verdict meanings,
the Tier-A/Tier-B collateral split, and the Claude Design handoff.

> Live capture needs `pmkit[dogfood]` (Playwright) + a browser, and asciinema for CLI casts;
> on Windows the browser path also needs the MS VC++ 2015–2022 redistributable (see pm-dogfood).
