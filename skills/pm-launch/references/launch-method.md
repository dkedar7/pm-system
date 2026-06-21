# pm-launch method

Reference for the launch/amplify stage. The skill orchestrates; this explains the decisions.

## Config derivation

There is no required config file. pm-launch derives the launch from:
1. The product **repo** (README/docs — what it is, who it's for, the honest demo-worthy bits).
2. Its **pm-system backlog item** (category, problem, provenance).
3. An optional **`LAUNCH.md`** in the product repo as an override/escape hatch — pin channels,
   set the angle, add constraints. When present it wins over derived defaults; when absent the
   stage derives everything.

## Platforms

Reddit, Hacker News, X, LinkedIn. **Reddit gets full moderator-policy research** (it has
machine-readable rules and the highest cost-of-getting-it-wrong — a pulled post). The others
get best-effort norm notes (HN: Show HN guidelines; X/LinkedIn: self-promo norms), not a hard
verdict, because they have no machine-readable rules.

## Mod-policy verdicts (`pmkit launch policy`)

The `pm-launch-policy` agent extracts a community's rules; `pmkit.launch.policy.decide_policy`
scores them deterministically:

- **block** — a rule forbids the kind of self-promo/link post you're about to make. Do **not**
  post there. The verdict cites the exact rule.
- **warn** — a conditional rule applies (ratio, flair, account-age, designated day/thread).
  Post, but satisfy the cited rule first.
- **ok** — nothing relevant matched.
- **unavailable** — the rules couldn't be fetched (network/parse failure). Check manually; do
  not assume ok.

Verdicts are cached per (platform, community) with a 30-day TTL, so repeat launches don't
re-research. The verdict is **advisory** — it cites the rule so you make the final call; it is
not a substitute for reading the room.

## Collateral — two tiers

- **Tier A (agent-produced, authentic):** record the real product working — `pmkit launch
  capture` (Playwright screenshots/video by reusing the dogfood drivers, asciinema CLI casts,
  HTML→PNG diagrams). This is the least-slop collateral for a dev audience: it's your tool, in
  action. No AI-generated media (deferred v2: Remotion video, AI imagery).
- **Tier B (human-produced, polished):** Claude Design (claude.ai/design) for slides,
  one-pagers, launch graphics. It's a human-facing web app with **no public API yet**, so the
  skill does **not** drive it — it preps the inputs (point Design at the repo, hand it the
  Tier-A assets, draft the structure) and *you* compose the polished artifact. The Design →
  Claude Code handoff is a future integration hook.

## The guardrails (why they're structural, not advice)

- **Never post.** No code path in `pmkit launch` posts anything; posting is the operator's act.
- **Never final.** `launch_drafts` has no status/final/postable column and no setter — a draft
  cannot be represented as a finished post. The drafter persona produces starting-points only;
  the independent slop-critic flags AI-tells; the operator writes the final in their voice.
- **Emit-only schedule.** `launch plan` renders a checklist and creates no cron entries.

## The listen loop

`pmkit launch listen <target>` ingests post-launch reactions (via the existing connectors) as
`launch-feedback` candidates and folds them into the backlog using the same dedup/attach flow
discovery uses. A known opportunity accrues evidence; a genuinely new pain becomes a new `new`
candidate — closing the funnel into a loop. It is read-only: it reads public reactions and
never engages or posts.

## Out of scope

Auto-posting (ever); sustained build-in-public personal cadence (an operating rhythm, not a
per-product launch — lives with the career-constitution/weekly-nudge machinery); driving Claude
Design programmatically (no API yet).
