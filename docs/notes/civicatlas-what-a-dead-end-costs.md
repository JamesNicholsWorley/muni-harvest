---
name: civicatlas-what-a-dead-end-costs
description: "28 records cited a document nobody held. 3 were fetchable from the recorded URL, 5 more from the Wayback Machine, 1 URL was a lead rather than a document, and 13 news articles are gone -- the difference between 'no source' and 'no source we tried for'."
metadata:
  type: reference
---

Twenty-eight records cited a document and nothing in either repository held one.
That number is worth distrusting on sight: it is a statement about what has been
attempted, not about what exists.

Working through them from a residential connection with `curl_cffi`:

    3   fetched from the URL the inventory already recorded, verified against
        the record, published: Ashby 2024 (9/9 names), Dighton 2022 (13/15),
        Colrain 2026 (every contest closes exactly on its 79 ballots)
    5   recovered from the Wayback Machine and held privately: the 2026 news
        articles, 47 of 47 names found across the five
    1   a lead, not a document: Chilmark 2022's URL resolves to the 2024 town
        report, whose elections are April 2024 and April 2025. Seven of eleven
        names matched -- all incumbents appearing in both years, which is how a
        wrong document passes a name check
   13   gone. recorder.com answers 403 and the Wayback Machine never crawled
        them. Headline, URL and date survive in each record; the text does not
    6   no URL was ever recorded

So a third of the "missing" documents were a fetch away, and the ones that are
genuinely gone are gone for a stated reason rather than an unexamined one.

Two things this cost, both worth remembering:

**A name check cannot tell you a document is the right one.** Chilmark's wrong
report matched seven names because towns re-elect people. Only the ELECTION
HEADING settles it -- April 2024 and April 2025 on a page that was supposed to
report 2022.

**Removing a reproduction removes the reading.** The eighteen news articles were
taken out of the public repository for good reason, and doing so left eighteen
records with no text anything could check them against. Recovering the five that
could be recovered is the repair; the other thirteen are a documented gap, which
is the second-best outcome and much better than a silent one.
