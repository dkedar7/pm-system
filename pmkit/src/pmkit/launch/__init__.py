"""pm-launch — the funnel's launch/amplify stage (deterministic core).

This package holds the *logistics* layer of launching a shipped product: the launch-state
ledger and mod-policy cache (``store``), moderator-policy verdicts (``policy``), the
listen/feedback loop (``listen``), the emit-only launch plan (``plan``), Tier-A collateral
capture (``collateral``), and draft-starting-point storage (``drafts``).

Hard boundaries, enforced here rather than left to convention:
- Nothing in this package posts to any channel — ever (the human gate lives in the skill).
- Drafts are *starting-points*; there is no "final"/"postable" state in the data model.
- The launch plan is emit-only: it renders an artifact and creates no cron side-effects.

Judgment (which channels, reading prose rules, writing copy, slop critique) lives in the
``agents/pm-launch-*`` personas; this package is the rule/ledger half.
"""
