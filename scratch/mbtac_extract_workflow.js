export const meta = {
  name: 'mbtac-vote-extract',
  description: 'Extract MBTA Communities Act (40A 3A) zoning-vote records from screened minutes/warrant docs',
  phases: [{ title: 'Extract', detail: 'one agent per confirmed doc -> structured vote events' }],
}

// args = array of manifest rows, each:
//   { town, community_type, governing_body, board, doctype, year, url, topic_pages, textfile }
// Each row's `textfile` is a local page-labeled text dump (Stage 3a prep). An extractor agent
// Reads it and returns every 3A vote event found. We flatten + return; the caller writes jsonl.

const DOCS = Array.isArray(args) ? args : []
log(`extracting from ${DOCS.length} screened docs`)

const EVENT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    has_3a_vote: { type: 'boolean', description: 'true if the doc records at least one vote/motion on MBTA Communities / 40A Section 3A / multifamily-district zoning' },
    records: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          meeting_body: { type: 'string', description: 'planning_board | select_board | city_council | town_meeting | representative_town_meeting | zoning_board | other' },
          meeting_date: { type: 'string', description: 'ISO YYYY-MM-DD if determinable, else ""' },
          doc_page: { type: 'integer', description: 'PAGE number (from the ===== PAGE n ===== labels) where the vote appears; 0 if unknown' },
          article_number: { type: 'string', description: 'town-meeting/warrant article or council order/ordinance number, else ""' },
          motion_snippet: { type: 'string', description: 'short paraphrase of what was voted on' },
          vote_yes: { type: 'integer', description: 'yes/favor count; -1 if not a numeric tally (e.g. voice vote)' },
          vote_no: { type: 'integer', description: 'no/opposed count; -1 if unknown' },
          vote_abstain: { type: 'integer', description: 'abstentions; -1 if unknown' },
          threshold_required: { type: 'string', description: 'e.g. "2/3", "majority", or "" if unstated' },
          threshold_met: { type: 'boolean' },
          outcome: { type: 'string', description: 'adopted | rejected | tabled | continued | recommended | not_recommended | referred | withdrawn | unknown' },
          is_terminal: { type: 'boolean', description: 'true if this is the final/binding disposition (not a continued/procedural step)' },
          evidence_quote: { type: 'string', description: 'verbatim sentence(s) from the text proving the vote + tally' },
        },
        required: ['meeting_body', 'meeting_date', 'doc_page', 'article_number', 'motion_snippet',
                   'vote_yes', 'vote_no', 'vote_abstain', 'threshold_required', 'threshold_met',
                   'outcome', 'is_terminal', 'evidence_quote'],
      },
    },
  },
  required: ['has_3a_vote', 'records'],
}

function prompt(d) {
  return `You are extracting municipal ZONING-VOTE records from a Massachusetts town/city document.
Municipality: ${d.town}  (MBTA community type: ${d.community_type}; governing body: ${d.governing_body || 'unknown'})
Screened doctype/board: ${d.doctype} / ${d.board}   Source URL: ${d.url}
TOPIC pages flagged by the screener: ${d.topic_pages || '(all)'}

TASK: Read the local text file below and find EVERY vote, motion, or recorded disposition on the
town's **MBTA Communities Act** compliance zoning — i.e. G.L. c.40A Section 3A, the "3A district",
a multifamily overlay/zoning district adopted to comply with the MBTA Communities Law, or an
explicitly-named MBTA-Communities warrant article / council ordinance.

Read the file with the Read tool: ${d.textfile}

Rules:
- Return one record PER vote event. A single doc can hold several (e.g. Planning Board recommendation
  AND Town Meeting adoption; or a continued vote across sessions).
- A REJECTION or a FAILED motion is a valid, wanted record (outcome=rejected) - not a miss.
- Voice/standing votes with no numbers: set the counts to -1 and capture the wording (e.g.
  "declared adopted by the requisite two-thirds") in evidence_quote; set threshold_met accordingly.
- Zoning normally needs a 2/3 vote at Town Meeting - record threshold_required and whether it was met.
- If the doc only DISCUSSES 3A with no vote/motion/disposition, set has_3a_vote=false and records=[].
- Only extract what the text supports; never invent tallies. Quote verbatim in evidence_quote.`
}

const results = await pipeline(
  DOCS,
  (d) => agent(prompt(d), {
    label: `extract:${d.town_norm || d.town}`,
    phase: 'Extract',
    schema: EVENT_SCHEMA,
    agentType: 'general-purpose',
  }).then((r) => ({ doc: d, out: r })),
)

const out = []
for (const r of results.filter(Boolean)) {
  if (!r.out || !r.out.has_3a_vote) continue
  for (const rec of (r.out.records || [])) {
    out.push({
      municipality: r.doc.town,
      community_type: r.doc.community_type,
      governing_body: r.doc.governing_body || '',
      screened_board: r.doc.board,
      screened_doctype: r.doc.doctype,
      doc_url: r.doc.url,
      ...rec,
    })
  }
}
log(`extracted ${out.length} vote events from ${out.length ? new Set(out.map(o => o.municipality)).size : 0} towns`)
return { events: out }
