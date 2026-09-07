# pages/

What it takes to rebuild the published pages from the corpus, kept where a cloud
session can reach it.

The generators lived only on the owner's machine, in `CivicAtlasMA`, which has no
remote. So nothing in CI could rebuild them, and `audit.html` sat showing a
snapshot from before a day of QA — records that had been resolved still listed as
defects, and defects found since not listed at all. A page that tells an agent
where to find work is worse than useless when it is a day stale, because it reads
exactly like a current one.

    audit_defects.py        builds defects.js, the data behind audit.html
    inventory/              the two ledgers it reads besides the corpus

`audit.html` itself is a static shell and is not generated; only `defects.js` is.
That is why the page could look alive while its contents aged.

## The layout it expects

The script computes its own root two directories up from itself and reads:

    <root>/data/inventory/municipalities.csv
    <root>/data/inventory/master_urls.csv
    <root>/publish/json/*.json
    <root>/research/interface/enrollment/denominators.csv   (optional)

and writes `defects.js` beside itself. Rather than edit the script to suit CI,
`.github/workflows/rebuild-pages.yml` in `civicatlasma` assembles that shape from
the two repositories and runs it unchanged. A script that runs identically on the
owner's machine and in CI is one that can be trusted in both.

`denominators.csv` is already here as `config/denominators.csv` and is the same
file, byte for byte, as the copy the local tree keeps.

## What is NOT here

`build_mvp.py`, which builds `mvp-data.js`. It reads the raw OCR, the extracted
text, the source PDFs, a turnout table and several inventory columns that live
only in the local corpus, and it is five and a half thousand lines. Rebuilding
the map in CI is a bigger job than rebuilding the defect register, and pretending
otherwise by vendoring half its inputs would produce a map built from a corpus
that is partly missing — which is worse than a map somebody has to rebuild by
hand and knows they have to.

So the map is still rebuilt on the owner's machine, and that is a known gap
rather than a hidden one.
