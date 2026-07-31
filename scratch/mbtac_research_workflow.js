export const meta = {
  name: 'mbtac-vote-research',
  description: 'Research the Planning Board + legislative-body vote on MBTA 3A zoning for every MBTA-C town',
  phases: [{ title: 'Research', detail: 'agents research batches of towns via web/news + seed data' }],
}

// args = { seed: "<abs path to mbtac_seed.csv>", total: <#towns>, batch: <towns per agent> }
// Each agent handles a contiguous slice of seed rows, researches each town on the web (news +
// official + town sites), and returns per-town records: form of government, Planning Board
// recommendation, and the legislative-body (Town Meeting / City Council) vote on 3A zoning.

let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch (e) { A = {} } }
const SEED = A && A.seed
const TOTAL = (A && A.total) || 0
const BATCH = (A && A.batch) || 3
if (!SEED || !TOTAL) throw new Error('args must be { seed, total, batch }; got: ' + JSON.stringify(args))
const nAgents = Math.ceil(TOTAL / BATCH)
log(`researching ${TOTAL} towns in ${nAgents} agents (${BATCH}/agent)`)

const TOWN = {
  type: 'object',
  additionalProperties: false,
  properties: {
    town: { type: 'string' },
    legislative_form: { type: 'string', description: 'Open Town Meeting | Representative Town Meeting | City Council' },
    planning_board_recommendation: { type: 'string', description: 'favorable | unfavorable | no_action | split | unknown' },
    planning_board_date: { type: 'string', description: 'ISO date of the PB vote/hearing, else ""' },
    planning_board_vote: { type: 'string', description: 'tally like "5-0" if reported, else ""' },
    legislative_outcome: { type: 'string', description: 'adopted | rejected | tabled | pending | unknown' },
    legislative_date: { type: 'string', description: 'ISO date of the decisive legislative vote, else ""' },
    legislative_tally: { type: 'string', description: 'e.g. "250-29" or "voice/unanimous" or ""' },
    legislative_article: { type: 'string', description: 'warrant article / council order number, else ""' },
    threshold: { type: 'string', description: '2/3 | majority | "" ' },
    eohlc_status: { type: 'string', description: 'echo/refine the seed status: Compliant | Conditional | Interim | Non-Compliant | Unknown' },
    adoption_date: { type: 'string', description: 'district adoption date (confirm/ correct the seed), else ""' },
    confidence: { type: 'string', description: 'high | medium | low' },
    sources: { type: 'array', items: { type: 'string' }, description: 'URLs used (news + official)' },
    notes: { type: 'string', description: 'brief: multiple attempts, litigation (e.g. Milton SJC), rejection then re-vote, etc.' },
  },
  required: ['town', 'legislative_form', 'planning_board_recommendation', 'planning_board_date',
             'planning_board_vote', 'legislative_outcome', 'legislative_date', 'legislative_tally',
             'legislative_article', 'threshold', 'eohlc_status', 'adoption_date', 'confidence',
             'sources', 'notes'],
}
const SCHEMA = { type: 'object', additionalProperties: false, required: ['towns'],
  properties: { towns: { type: 'array', items: TOWN } } }

function prompt(start, count) {
  return `You research Massachusetts municipal votes on MBTA Communities Act (G.L. c.40A Section 3A)
compliant multifamily zoning. Read the seed CSV: ${SEED}
Process DATA ROWS ${start} to ${start + count - 1} (0-based, header excluded). Each row has:
  town, town_norm, community_type, governing_body (Select Board|City Council), eohlc_status,
  adoption_date (EOHLC-certified district adoption date if compliant), extracted_legislative,
  extracted_planning_board, extracted_source_url  (the last three = what we already found in town
  documents -- TRUST these as a strong starting point; verify/complete them).

For EACH assigned town, determine and return:
1. legislative_form: Open Town Meeting, Representative Town Meeting, or City Council. (governing_body
   "City Council" -> City Council. Select Board towns are Town Meeting -- decide Open vs
   Representative: the larger/older towns like Arlington, Brookline, Belmont, Milton, Natick, Needham,
   Reading, Wakefield, Winchester, Framingham-area use Representative Town Meeting; most are Open.)
2. Planning Board recommendation on the 3A zoning article (favorable/unfavorable/no_action/split),
   with date + vote tally if reported.
3. The DECISIVE legislative-body vote: outcome (adopted/rejected/tabled/pending), date, tally
   (e.g. "250-29" or "voice/unanimous"), article number, and threshold (zoning needs 2/3 at Town
   Meeting). For compliant towns the adoption_date seed tells you WHEN -- find that meeting's vote.
   For non-compliant/rejected towns, capture the failed vote(s) and any re-votes.

Method: use WebSearch + WebFetch. Good queries: '"<town>" MBTA Communities 3A zoning town meeting
vote 2024', '"<town>" multifamily overlay adopted OR rejected', local news (Patch, Wicked Local,
Boston Globe/.com, town news), and the town's own MBTA Communities page. Cross-check the EOHLC
adoption_date. Keep it tight: ~1-3 searches per town; lean on the seed. Record source URLs.
If a fact is genuinely unavailable, use "" / "unknown" and set confidence=low -- never invent tallies.`
}

const slices = []
for (let s = 0; s < TOTAL; s += BATCH) slices.push([s, Math.min(BATCH, TOTAL - s)])

const batchOut = await pipeline(
  slices,
  ([start, count]) => agent(prompt(start, count),
    { label: `research:${start}-${start + count - 1}`, phase: 'Research', schema: SCHEMA,
      agentType: 'general-purpose', model: 'sonnet' }),
)

const towns = []
for (const b of batchOut.filter(Boolean)) for (const t of (b.towns || [])) towns.push(t)
log(`researched ${towns.length} towns`)
return { towns, n_towns: towns.length }
