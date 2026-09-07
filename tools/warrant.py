"""Find the election warrant, so "uncontested" can be confirmed rather than assumed.

A return that prints names and no figures is either an uncontested election or a
document we cut wrong, and from the return alone the two look identical. The
warrant settles it. It is the legal instrument that calls the election and it
enumerates the offices to be filled and the seats and terms for each, so a
return whose offices match the warrant's, one name against each, is uncontested
as a matter of record rather than as an inference from missing numbers.

It also supplies the seat count for `num_winners` on exactly the documents that
never print one -- small-town returns -- which is the field the corpus gets
wrong most often.

The warrant is easy to recognise and easy to confuse with the return, since both
head themselves with the election and both list the same offices. Two things
separate them: the warrant addresses the constables in fixed statutory language,
and it carries no figures at all.
"""
import re

# Massachusetts warrants have said this, nearly verbatim, since the 19th century.
SUMMONS = re.compile(
    r"(GREETING|you\s+are\s+hereby\s+(?:directed|required)|"
    r"in\s+the\s+name\s+of\s+the\s+Commonwealth|"
    r"to\s+(?:any|either)\s+of\s+the\s+Constables|"
    r"qualified\s+to\s+vote\s+in\s+(?:town\s+)?elections)", re.I)
WARRANT_WORD = re.compile(r"\bWARRANT\b", re.I)
# "to bring in their votes for" / "to choose the following officers"
CALLS_OFFICERS = re.compile(
    r"(bring\s+in\s+their\s+(?:votes|ballots)|choose\s+the\s+following|"
    r"following\s+officers|elect\s+the\s+following)", re.I)
SEATS = re.compile(
    r"(?:\b(one|two|three|four|five|six|seven|eight|nine|ten|1|2|3|4|5|6|7|8|9|10)\b"
    r"\s*(?:\(\d+\)\s*)?)(?:for\s+)?(?:a\s+term\s+of\s+)?(?:th(?:ree|ee)|one|two|four|five|\d)\s*(?:\(\d\)\s*)?year",
    re.I)
NUM = re.compile(r"^[0-9]{1,6}$")


def figure_density(text):
    toks = text.split()
    if not toks:
        return 0.0
    return sum(1 for t in toks if NUM.match(t)) / len(toks)


def score_page(text):
    """How much this page looks like a warrant rather than a return.

    Figures are the discriminator that matters. A warrant names offices and
    terms and prints no vote totals; a return prints little else. A page heavy
    in both is the return reprinting its own ballot instructions, which is
    common and is not a warrant.
    """
    s = 0
    if WARRANT_WORD.search(text):
        s += 2
    if SUMMONS.search(text):
        s += 3
    if CALLS_OFFICERS.search(text):
        s += 3
    s += min(len(SEATS.findall(text)), 6)
    if figure_density(text) > 0.12:
        s -= 4          # too many numbers to be a warrant
    return s


def find(page_texts, threshold=6):
    """Indices of pages that read as an election warrant, best first."""
    scored = [(score_page(t), i) for i, t in enumerate(page_texts)]
    return [(i, s) for s, i in sorted(scored, reverse=True) if s >= threshold]


# A return does not have to be a table. Aquinnah 2016 prints its whole election
# in running prose inside the town meeting section, on page 149 of the report:
#
#     One Selectman for Three Years  Gary Haley 128, Macey Dunbar 29,
#     One Moderator for Three Years Michael Hebert 132, Blanks 24, Others 7
#
# Offices, candidates, figures and a contested race -- everything a tabular
# return has, and invisible to a locator that requires a table. It is invisible
# to the warrant score too, which subtracts for figure density precisely to
# avoid matching returns.
#
# These sit outside the section cut around the results page, because there is no
# results page, which is why they can only be found by reading the whole report.
PROSE_OFFICE = re.compile(
    r"\b(One|Two|Three|Four|Five|Six|\d)\s+"
    r"[A-Z][A-Za-z'/ ]{3,40}?\s+for\s+"
    r"(One|Two|Three|Four|Five|Seven|\d)\s+Years?\b", re.I)
NAME_VOTE = re.compile(r"[A-Z][a-z]+\s+[A-Z][A-Za-z'\-]+,?\s+\d{1,5}\b")


def prose_return_score(text):
    """How much this page reads as an election return written as sentences.

    The opposite balance to `score_page`: a warrant names offices and prints no
    figures, while this names offices AND attaches a figure to a person. The
    two are scored separately rather than merged, because a page can be both --
    Aquinnah's is a town meeting warrant whose Article One carries the results.
    """
    offices = len(PROSE_OFFICE.findall(text))
    pairs = len(NAME_VOTE.findall(text))
    if offices < 2 or pairs < 4:
        return 0
    return min(offices, 8) + min(pairs // 2, 8)
