export const meta = {
  name: 'pm-funnel',
  description: 'Discover OSS opportunities, adversarially stress-test and rerank them, and persist a ranked backlog that halts at the human gate.',
  phases: [
    { title: 'Discover', detail: 'pmkit discover ingests + dedups signals into candidates' },
    { title: 'Stress-test', detail: 'four kill-test agents per candidate; prune on >=3 refutes' },
    { title: 'Rank', detail: 'RICE reranker scores each survivor' },
  ],
}

// --- output schemas (force structured agent returns) ---
const DISCOVERED = {
  type: 'object',
  properties: {
    new_ids: { type: 'array', items: { type: 'integer' } },
    fetched: { type: 'integer' },
    new: { type: 'integer' },
    merged: { type: 'integer' },
  },
  required: ['new_ids'],
}

const VERDICT = {
  type: 'object',
  properties: {
    axis: { type: 'string' },
    verdict: { type: 'string', enum: ['refute', 'survive'] },
    confidence: { type: 'number' },
    reason: { type: 'string' },
    evidence: { type: 'array', items: { type: 'string' } },
  },
  required: ['axis', 'verdict'],
}

const SCORES = {
  type: 'object',
  properties: {
    reach: { type: 'number' },
    impact: { type: 'number' },
    confidence: { type: 'number' },
    effort: { type: 'number' },
    rationale: { type: 'string' },
  },
  required: ['reach', 'impact', 'confidence', 'effort'],
}

const STATUS_SCHEMA = {
  type: 'object',
  properties: { status: { type: 'string' } },
  required: ['status'],
}

// agentType resolves through the same registry as the Agent tool, which requires
// the plugin namespace prefix. Bare names ("pm-killtest-solved") fail with
// "agent type not found" — every verdict degrades to null and the panel silently
// prunes everything. Keep these fully qualified.
const AXES = [
  { axis: 'already-solved', agent: 'pm-system:pm-killtest-solved' },
  { axis: 'pain-is-rare', agent: 'pm-system:pm-killtest-rarity' },
  { axis: 'infeasible', agent: 'pm-system:pm-killtest-feasibility' },
  { axis: "won't-be-adopted", agent: 'pm-system:pm-killtest-adoption' },
]
// The survival rule lives in pmkit (`killtest.decide_survival`, applied via
// `pmkit backlog killtest --decide`): already-solved is dispositive, else majority (>=3/4).

const target = typeof args === 'string' ? args : (args && args.target) || ''
if (!target) {
  log('pm-funnel: no target provided')
  return { error: 'no target' }
}

// --- Stage A: discover (one agent runs the deterministic CLI) ---
phase('Discover')
const disc = await agent(
  `Run the shell command \`pmkit discover ${target} --json\`, then ` +
    `\`pmkit backlog list --status new --json\`. Return the discover summary ` +
    `(fetched, new, merged) and new_ids = the ids of every candidate now in status 'new'.`,
  { label: `discover:${target}`, phase: 'Discover', schema: DISCOVERED }
)

const newIds = (disc && disc.new_ids) || []
log(`discovered ${newIds.length} new candidate(s) for ${target}`)
if (newIds.length === 0) {
  return { target, candidates: 0, message: 'nothing new' }
}

// --- Stages B + C: per-candidate kill-test, then rerank survivors (pipelined) ---
const results = await pipeline(
  newIds,
  // Stage B: fan out the four kill-test axes, apply the majority rule, persist.
  async (id) => {
    const verdicts = await parallel(
      AXES.map((a) => () =>
        agent(
          `Read opportunity ${id}: run \`pmkit backlog show ${id} --json\`. ` +
            `Apply your ${a.axis} kill-test and return your verdict JSON.`,
          {
            label: `killtest:${a.axis}:${id}`,
            phase: 'Stress-test',
            agentType: a.agent,
            schema: VERDICT,
          }
        )
      )
    )
    const got = verdicts.filter(Boolean) // a dead agent degrades to remaining verdicts
    // Persist via a FILE, never an inline shell arg. A bulky verdicts blob (long
    // reasons with quotes/parens/em-dashes) gets mangled when an LLM agent rebuilds
    // it into a shell command, which silently empties the array so decide_survival
    // mis-gates. Compact to the fields the rule needs + a short reason, write
    // verbatim, pass the clean path. pmkit still applies the survival rule
    // (already-solved dispositive, else majority) — single source of truth, no drift.
    const compact = got.map((x) => ({
      axis: x.axis,
      verdict: x.verdict,
      confidence: x.confidence,
      reason: (x.reason || '').slice(0, 200),
    }))
    const vfile = `.pmkit-kt-verdicts-${id}.json`
    const payload = JSON.stringify(compact)
    const decided = await agent(
      `Use the Write tool to write this EXACT JSON verbatim (no edits) to a file ${vfile} ` +
        `in the current directory:\n${payload}\n\n` +
        `Then run: pmkit backlog killtest ${id} --decide --verdicts-file ${vfile} --json\n` +
        `Return the resulting {status}.`,
      { label: `persist-killtest:${id}`, phase: 'Stress-test', schema: STATUS_SCHEMA }
    )
    return { id, survived: !!decided && decided.status === 'survived' }
  },
  // Stage C: only survivors are scored.
  async (kt, id) => {
    if (!kt || !kt.survived) return { id, pruned: true }
    const s = await agent(
      `Read opportunity ${id}: run \`pmkit backlog show ${id} --json\`. ` +
        `Score it with RICE sub-scores and return the JSON.`,
      { label: `rerank:${id}`, phase: 'Rank', agentType: 'pm-system:pm-reranker', schema: SCORES }
    )
    if (!s) return { id, scored: false }
    await agent(
      `Run: pmkit backlog score ${id} --reach ${s.reach} --impact ${s.impact} ` +
        `--confidence ${s.confidence} --effort ${s.effort}`,
      { label: `persist-score:${id}`, phase: 'Rank' }
    )
    return { id, scored: true }
  }
)

const survivors = results.filter((r) => r && r.scored).length
log(`funnel complete: ${survivors} scored survivor(s); halting at the human gate`)
return { target, candidates: newIds.length, survivors, results }
