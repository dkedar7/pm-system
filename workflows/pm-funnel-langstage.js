export const meta = {
  name: 'pm-funnel-langstage',
  description: 'Kill-test + RICE-rerank the six seeded LangStage opportunities (ids 31-36; skips discover).',
  phases: [
    { title: 'Stress-test', detail: 'four kill-test agents per candidate; prune on >=3 refutes (already-solved dispositive)' },
    { title: 'Rank', detail: 'RICE reranker scores each survivor' },
  ],
}

// Seeded candidates already in status 'new' — skip discover, validate/rank these.
const IDS = [31, 32, 33, 34, 35, 36]
const DB = '--db C:/kzest/pm-system/state/backlog.db'

// --- output schemas (force structured agent returns) ---
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

// Registry requires the plugin namespace prefix (pm-system:...) — bare names
// resolve to "agent type not found" and the whole panel silently degrades to
// zero verdicts. This was the bug that pruned all six on the prior run.
const AXES = [
  { axis: 'already-solved', agent: 'pm-system:pm-killtest-solved' },
  { axis: 'pain-is-rare', agent: 'pm-system:pm-killtest-rarity' },
  { axis: 'infeasible', agent: 'pm-system:pm-killtest-feasibility' },
  { axis: "won't-be-adopted", agent: 'pm-system:pm-killtest-adoption' },
]

const results = await pipeline(
  IDS,
  // Stage B: fan out the four kill-test axes, apply the majority rule via pmkit, persist.
  async (id) => {
    const verdicts = await parallel(
      AXES.map((a) => () =>
        agent(
          `Read opportunity ${id}: run \`pmkit backlog show ${id} ${DB} --json\`. ` +
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
    // mis-gates (the bug that pruned 31 and survived 34/36). Compact to the fields
    // the rule needs + a short reason, write verbatim, pass the clean path.
    const compact = got.map((x) => ({
      axis: x.axis,
      verdict: x.verdict,
      confidence: x.confidence,
      reason: (x.reason || '').slice(0, 200),
    }))
    const vfile = `C:/kzest/pm-system/state/.kt-verdicts-${id}.json`
    const payload = JSON.stringify(compact)
    const decided = await agent(
      `Use the Write tool to write this EXACT JSON verbatim (no edits) to ${vfile}:\n` +
        `${payload}\n\n` +
        `Then run: pmkit backlog killtest ${id} --decide --verdicts-file ${vfile} ${DB} --json\n` +
        `Return the resulting {status}.`,
      { label: `persist-killtest:${id}`, phase: 'Stress-test', schema: STATUS_SCHEMA }
    )
    return { id, verdicts: got, survived: !!decided && decided.status === 'survived' }
  },
  // Stage C: only survivors are scored.
  async (kt, id) => {
    if (!kt || !kt.survived) return { id, survived: false, verdicts: (kt && kt.verdicts) || [] }
    const s = await agent(
      `Read opportunity ${id}: run \`pmkit backlog show ${id} ${DB} --json\`. ` +
        `Score it with RICE sub-scores and return the JSON.`,
      { label: `rerank:${id}`, phase: 'Rank', agentType: 'pm-system:pm-reranker', schema: SCORES }
    )
    if (!s) return { id, survived: true, scored: false }
    await agent(
      `Run: pmkit backlog score ${id} --reach ${s.reach} --impact ${s.impact} ` +
        `--confidence ${s.confidence} --effort ${s.effort} ${DB}`,
      { label: `persist-score:${id}`, phase: 'Rank' }
    )
    return { id, survived: true, scored: true, scores: s }
  }
)

const survivors = results.filter((r) => r && r.survived).map((r) => r.id)
const pruned = results.filter((r) => r && !r.survived).map((r) => r.id)
log(`funnel complete: ${survivors.length} survived (${survivors.join(',')}), ${pruned.length} pruned (${pruned.join(',')})`)
return { survived: survivors, pruned, results }
