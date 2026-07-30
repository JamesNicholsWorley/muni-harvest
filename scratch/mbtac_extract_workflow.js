export const meta = {
  name: 'mbtac-vote-extract',
  description: 'Extract MBTA Communities Act (40A 3A) zoning-vote records from batched minutes/warrant snippets',
  phases: [{ title: 'Extract', detail: 'one agent per batch of ~12 docs -> structured vote events' }],
}

// args = { dir: "<abs path to mbtac_batches>", n: <number of batch_NNN.txt files> }
// Each batch file holds up to ~12 doc blocks, each headed by:
//   ### DOC <id> | town=... | community_type=... | governing_body=... | screened_board=... |
//       screened_doctype=... | url=...
// followed by tight page-labeled snippets. One agent reads a whole batch and returns a result
// per DOC block. doc_id ties results back to scratch/mbtac_extract_index.csv metadata.

let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch (e) { A = {} } }
const DIR = A && A.dir
const N = A && A.n
if (!DIR || !N) throw new Error('args must be { dir, n }; got: ' + JSON.stringify(args))
log(`extracting from ${N} batch files in ${DIR}`)

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    results: {
      type: 'array',
      description: 'one entry per ### DOC block in the batch file',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          doc_id: { type: 'string', description: 'the <id> from the ### DOC header' },
          town: { type: 'string' },
          screened_board: { type: 'string' },
          screened_doctype: { type: 'string' },
          url: { type: 'string' },
          has_3a_vote: { type: 'boolean', description: 'true if this doc records >=1 vote/motion/disposition on MBTA Communities / 40A Section 3A / multifamily-district zoning' },
          records: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                meeting_body: { type: 'string', description: 'planning_board | select_board | city_council | town_meeting | representative_town_meeting | zoning_board | other' },
                meeting_date: { type: 'string', description: 'ISO YYYY-MM-DD if determinable, else ""' },
                doc_page: { type: 'integer', description: 'PAGE n from the [PAGE n] labels where the vote appears; 0 if unknown' },
                article_number: { type: 'string' },
                motion_snippet: { type: 'string', description: 'short paraphrase of what was voted on' },
                vote_yes: { type: 'integer', description: 'yes/favor count; -1 if not a numeric tally (voice vote)' },
                vote_no: { type: 'integer' },
                vote_abstain: { type: 'integer' },
                threshold_required: { type: 'string', description: 'e.g. "2/3", "majority", or ""' },
                threshold_met: { type: 'boolean' },
                outcome: { type: 'string', description: 'adopted | rejected | tabled | continued | recommended | not_recommended | referred | withdrawn | unknown' },
                is_terminal: { type: 'boolean', description: 'true if the final/binding disposition' },
                evidence_quote: { type: 'string', description: 'verbatim sentence(s) proving the vote + tally' },
              },
              required: ['meeting_body', 'meeting_date', 'doc_page', 'article_number', 'motion_snippet',
                         'vote_yes', 'vote_no', 'vote_abstain', 'threshold_required', 'threshold_met',
                         'outcome', 'is_terminal', 'evidence_quote'],
            },
          },
        },
        required: ['doc_id', 'town', 'screened_board', 'screened_doctype', 'url', 'has_3a_vote', 'records'],
      },
    },
  },
  required: ['results'],
}

function prompt(i) {
  const path = `${DIR}/batch_${String(i).padStart(3, '0')}.txt`
  return `You extract municipal ZONING-VOTE records from Massachusetts meeting documents.

Read this batch file: ${path}
It contains several document blocks. Each starts with a header line:
  ### DOC <id> | town=... | community_type=... | governing_body=... | screened_board=... | screened_doctype=... | url=...
followed by tight, page-labeled text snippets (lines like [PAGE 7]).

For EACH ### DOC block, find EVERY vote, motion, or recorded disposition on that town's MBTA
Communities Act compliance zoning -- G.L. c.40A Section 3A, the "3A district", a multifamily
overlay/zoning district adopted to comply with the MBTA Communities Law, or an explicitly-named
MBTA-Communities warrant article / council ordinance. Return one entry in "results" per DOC block
(copy its doc_id, town, screened_board, screened_doctype, url from the header).

Rules:
- One record PER vote event; a doc may hold several (Planning Board recommendation AND Town
  Meeting adoption; or a vote continued across sessions).
- A REJECTION or FAILED motion IS a wanted record (outcome=rejected) -- not a miss.
- Voice/standing votes with no numbers: counts = -1, capture wording in evidence_quote
  (e.g. "declared adopted by the requisite two-thirds"), set threshold_met accordingly.
- Zoning normally needs 2/3 at Town Meeting -- record threshold_required + whether met.
- A warrant's "Recommended/Not Recommended" by Select Board/Planning Board/FinCom is a
  recommendation record (is_terminal=false), NOT the Town Meeting vote.
- If a DOC only DISCUSSES 3A with no vote/motion/disposition, set has_3a_vote=false, records=[].
- Never invent tallies; quote verbatim in evidence_quote.`
}

const idx = Array.from({ length: N }, (_, i) => i)
const batchOut = await pipeline(
  idx,
  (i) => agent(prompt(i), { label: `extract:batch${i}`, phase: 'Extract', schema: SCHEMA, model: 'sonnet' }),
)

const out = []
for (const b of batchOut.filter(Boolean)) {
  for (const d of (b.results || [])) {
    if (!d.has_3a_vote) continue
    for (const rec of (d.records || [])) {
      out.push({ doc_id: d.doc_id, municipality: d.town, screened_board: d.screened_board,
                 screened_doctype: d.screened_doctype, doc_url: d.url, ...rec })
    }
  }
}
const towns = new Set(out.map((o) => o.municipality))
log(`extracted ${out.length} vote events across ${towns.size} towns`)
return { events: out, n_batches: N, n_events: out.length, n_towns: towns.size }
