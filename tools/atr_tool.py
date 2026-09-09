"""The tool schema the ATR parse emits into.

The schema is the enforcement, not the prose. CivicAtlasMA's corpus came out
verbatim across 1,900 records because its tool has exactly one office field and
one name field, so a canonical form had nowhere to go -- a stronger guarantee
than instructing a model not to normalise, and the reason the stale prose specs
never mattered.

So every rule that CAN be expressed as a field, or the absence of one, is
expressed that way here. `num_winners_source` is required, because a number
that never has to say where it came from is a number nobody has checked.
`ballots_cast` does not exist, because it is derivable and every derivable
field asked for is a hallucination site. There is no confidence score on a
figure, because a figure is either read or it is not.
"""

CANDIDATE = {
    "type": "object",
    "properties": {
        "name_original": {
            "type": "string",
            "description": "Exactly as printed. Not Title Case, initials not "
                           "expanded, suffixes kept. A parenthetical printed "
                           "inside the name stays in the name."},
        "votes": {
            "type": ["integer", "null"],
            "description": "The printed figure. null when the cell is blank, "
                           "illegible or absent -- NEVER 0, which is an "
                           "assertion the document did not make."},
        "votes_by_precinct": {
            "type": ["array", "null"],
            "items": {"type": ["integer", "null"]},
            "description": "Per-precinct figures in printed order, or null "
                           "where the return prints no precinct columns."},
        # Present ONLY on rows that carry a mark. Emitting false and null on
        # every other row cost 21% of the output on a multi-precinct return
        # and said nothing on any of them; `winner_marks_used` at the document
        # level already distinguishes "not marked" from "nothing is marked".
        "elected_marked": {
            "type": "boolean",
            "description": "true, and present ONLY on rows carrying a winner "
                           "mark. Omit entirely on every other row."},
        "annotation_original": {
            "type": "string",
            "description": "A mark printed BESIDE the name, verbatim: 'CFR'. "
                           "Omit entirely when there is none."},
    },
    "required": ["name_original", "votes"],
}

CONTEST = {
    "type": "object",
    "properties": {
        "office_original": {
            "type": "string",
            "description": "The heading exactly as printed. A heading spanning "
                           "two printed rows is joined with a single space."},
        "district_original": {
            "type": "string",
            "description": "Precinct or ward for a sub_town contest, even when "
                           "it appears only in the heading. Empty for a "
                           "regional contest named only in the heading."},
        "scope": {"type": "string",
                  "enum": ["at_large", "sub_town", "regional_district"]},
        "num_winners": {
            "type": ["integer", "null"],
            "description": "SEATS UP, not people who won. A race where nobody "
                           "was elected still had a seat up, so this is never "
                           "0. null when it genuinely cannot be determined."},
        "num_winners_source": {"type": "string",
                               "enum": ["printed", "marked", "derived", "null"]},
        "seats_quote": {"type": ["string", "null"],
                        "description": "The printed line carrying the seat "
                                       "count, when source is 'printed'."},
        "num_winners_basis": {"type": ["string", "null"]},
        "printed_total": {"type": ["integer", "null"],
                          "description": "The TOTALS figure the document "
                                         "prints, never a sum you performed."},
        "printed_total_by_precinct": {"type": ["array", "null"],
                                      "items": {"type": ["integer", "null"]}},
        "precinct_labels": {"type": ["array", "null"],
                            "items": {"type": "string"}},
        "is_recount": {"type": "boolean"},
        "recount_date": {"type": ["string", "null"]},
        "regional_note": {"type": ["string", "null"]},
        "candidates": {"type": "array", "items": CANDIDATE},
        "problems": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["office_original", "scope", "num_winners",
                 "num_winners_source", "candidates", "problems"],
}

TOOL = {
    "name": "emit_return",
    "description": "Return the transcribed annual municipal election.",
    "input_schema": {
        "type": "object",
        "properties": {
            "municipality_original": {
                "type": ["string", "null"],
                "description": "As the page prints it -- 'TOWN OF STERLING' "
                               "stays whole. null when never named."},
            "municipality_printed": {"type": "boolean"},
            "date_original": {
                "type": ["string", "null"],
                "description": "The election date the PAGE prints, verbatim. "
                               "It outranks the year in the filename; never "
                               "adjust it towards the filename."},
            "winner_marks_used": {
                "type": ["boolean", "null"],
                "description": "Whether this document marks winners at all."},
            "saw_special": {"type": "boolean",
                            "description": "A MUNICIPAL special election was "
                                           "present and skipped."},
            "other_dates_seen": {"type": "array", "items": {"type": "string"}},
            "elections": {"type": "array", "items": CONTEST},
            "questions": {"type": "array", "items": {"type": "string"}},
            "document_problems": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["municipality_original", "municipality_printed",
                     "date_original", "elections", "document_problems"],
    },
}
