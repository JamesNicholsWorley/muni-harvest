"""Arithmetic that a printed return performs on itself.

A return is a redundant document. It prints figures that must add up in more
than one direction, and it prints them for several races that must agree with
each other. That redundancy is free evidence, it needs no model, and it is
available BEFORE anything is parsed -- which is the point. A check that runs
after a parse tells you a record is wrong. A check that runs on the text tells
you which figures to read again.

Three kinds, in increasing strength:

    across a row      precinct figures sum to the row's printed total
    down a column     candidates + blanks + write-ins sum to the printed TOTALS
    across races      every race's TOTALS divided by its seats is the same
                      number, because that number is the ballot count

The third is the strongest and the least used. A voter marks a three-seat race
up to three times, so a three-seat race prints roughly three times the ballots.
Divide each race's total by its seats and the quotients agree -- so a race whose
quotient disagrees has either the wrong seat count or a misread total, and a
race with NO printed seat count can have one derived.
"""
import collections
import re

NUM = re.compile(r"^[0-9]{1,7}$")


def numbers(line):
    return [int(t) for t in line.split() if NUM.match(t)]


# --------------------------------------------------------------- row and column

def closes(parts, total):
    return sum(parts) == total


def derive_ballots(race_totals_and_seats, tolerance=0):
    """The ballot count, or None when the races do not agree on one.

    Two races that disagree are a disagreement, not a derivation. Returning
    None is the honest answer and the caller must be able to act on it; a
    silently-picked winner here would poison every check downstream.
    """
    quotients = collections.Counter()
    for total, seats in race_totals_and_seats:
        if not seats or total is None or total % seats:
            continue
        quotients[total // seats] += 1
    if not quotients:
        return None
    best, n = quotients.most_common(1)[0]
    if n < 2:
        return None
    # A single dissenter is a misread race; a split vote is not a derivation.
    if sum(v for k, v in quotients.items() if abs(k - best) > tolerance) >= n:
        return None
    return best


def implied_seats(total, ballots):
    """What the seat count must be if this total is right.

    Cross-checks `num_winners`, which is the most error-prone field in the
    corpus and invisible to any diff that looks at size. A printed seat count
    still outranks this -- the arithmetic is a lower bound, because blanks and
    uncounted write-ins pull the total down, never up.
    """
    if not ballots or total is None:
        return None
    n = round(total / ballots)
    return n if n >= 1 and abs(total - n * ballots) <= 0.02 * n * ballots else None


# ------------------------------------------------------------------ digit bleed

def _splits(tok):
    """Every way one printed token could be two numbers set close together."""
    s = str(tok)
    for i in range(1, len(s)):
        a, b = s[:i], s[i:]
        # A vote total does not begin with a zero, and neither half may vanish.
        if b[0] == "0" and len(b) > 1:
            continue
        yield int(a), int(b)


def repair_row(parts, total):
    """Repair a row that does not close, but only where the repair is unique.

    Two adjacent columns set tight enough that a reader runs them together --
    `50 47` read as `5047`, or a total column touching the last precinct -- are
    the commonest way a scanned return produces a plausible wrong number. It is
    also, unusually, a recoverable error: the row states its own total, so a
    proposed split either makes the row close or it does not.

    Uniqueness is the whole safeguard. If two different splits both close the
    row, the arithmetic does not know which is right and neither do we, so
    nothing is returned. A repair that had to choose would be a guess wearing
    the costume of a proof.

    Returns (repaired_parts, description) or (None, reason).
    """
    if sum(parts) == total:
        return list(parts), "already closes"
    found = []
    # One token is really two numbers run together.
    for i, tok in enumerate(parts):
        for a, b in _splits(tok):
            cand = parts[:i] + [a, b] + parts[i + 1:]
            if sum(cand) == total:
                found.append((cand, f"split {tok} into {a} and {b}"))
    # Two tokens are really one number broken by a stray space.
    for i in range(len(parts) - 1):
        joined = int(f"{parts[i]}{parts[i+1]}")
        cand = parts[:i] + [joined] + parts[i + 2:]
        if sum(cand) == total:
            found.append((cand, f"joined {parts[i]} and {parts[i+1]} into {joined}"))
    if not found:
        return None, "no split closes the row"
    uniq = {tuple(c) for c, _ in found}
    if len(uniq) > 1:
        return None, f"{len(uniq)} different splits close it; ambiguous"
    return found[0][0], found[0][1]
