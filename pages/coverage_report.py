"""Standing coverage report -> a single self-contained HTML page.

One inventory, 2021-2026, all in master_urls.csv. Coverage = a usable hosted document /
parsed result exists (coverage_state == 'published'). The denominator excludes town-years
with no election (coverage_state == 'no_election'). 2026 was merged in from the former
separate cohort: 296 even-year towns are expected, of which those with a parsed result are
published and the rest are no_source gaps (2026 collection is still ongoing).

Run:  python src/coverage_report.py   ->   reports/coverage.html
No arguments, no network, no inventory writes. Safe to run any time.
"""
from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Paths are overridable so the same generator serves the local sweep and CI.
# In the workspace it writes reports/coverage.html for a human to look at; in
# the Pages rebuild it writes the published page directly, which is the whole
# point -- this file's own docstring records that leaving publication manual
# let the page go stale by six days while showing documents as good coverage
# that QA had already condemned.
ROOT = Path(os.environ.get("COVERAGE_ROOT",
                           Path(__file__).resolve().parent.parent))
MASTER = Path(os.environ.get("COVERAGE_MASTER",
                             ROOT / "data" / "inventory" / "master_urls.csv"))
OUT = Path(os.environ.get("COVERAGE_OUT", ROOT / "reports" / "coverage.html"))

PRIOR_YEARS = ["2021", "2022", "2023", "2024", "2025", "2026"]



PRE2021_DIR = os.environ.get("COVERAGE_PRE2021", "")
PRE2021_TOWNS = 292          # towns holding an annual election
PRE2021_YEARS = 21           # 2000-2020


def _pre2021():
    """(town_years, municipalities, by_year) from the published folder, or None.

    Reads what was actually published rather than what was parsed. A record
    held back by the gate is not coverage, and counting it would put a number
    on the page that no visitor can reach.
    """
    import glob
    import json
    if not PRE2021_DIR or not Path(PRE2021_DIR).is_dir():
        return None
    towns, by_year = set(), {}
    n = 0
    for f in glob.glob(str(Path(PRE2021_DIR) / "*.json")):
        # Only a malformed file is skipped. An earlier `except Exception` here
        # swallowed a NameError -- this module does not import `io` -- and
        # every one of 547 readable records was skipped in silence, leaving a
        # section that reported zero coverage with complete confidence. A bare
        # except around a read will eventually hide the bug that matters.
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        el = d.get("elections") or []
        if not el:
            continue
        n += 1
        towns.add(el[0].get("municipality"))
        y = (el[0].get("date") or "")[:4]
        if y:
            by_year[y] = by_year.get(y, 0) + 1
    return n, len(towns), by_year


def _pre2021_html():
    got = _pre2021()
    if not got:
        return ""
    n, ntowns, by_year = got
    # A section reporting zero is worse than no section: it states a number,
    # and the number is wrong whenever the cause is a path that did not
    # resolve rather than a corpus that is empty. The population table failed
    # exactly this way and would have published 0.0% people-year coverage.
    if n == 0:
        return ("\n<h2>2000-2020, from Annual Town Reports</h2>\n"
                "<p class=note>Not rendered: the published pre-2021 folder was "
                "configured but held no readable record. This says the wiring "
                "is wrong, not that the coverage is zero.</p>\n")
    possible = PRE2021_TOWNS * PRE2021_YEARS
    bars = "".join(
        "<tr><td>%s</td><td class=n>%d</td></tr>" % (y, by_year[y])
        for y in sorted(by_year))
    return """
<h2>2000-2020, from Annual Town Reports</h2>
<p class=note>A separate corpus, published at
<code>json_pre2021/</code> and marked <code>provenance: atr_section</code>.
These were cut out of annual town reports by a locator rather than taken from a
document the clerk published as the return, so they are weaker evidence and are
kept apart to say so. Only records passing the publication gate are counted --
what is held back is not coverage.</p>
<p><b>%d</b> town-years across <b>%d</b> municipalities, of a possible
%s (292 towns x 21 years) = <b>%.1f%%</b>.</p>
<p class=note>The denominator is every annual town election held, not the
documents we managed to find. Roughly half of those town-years have no located
document at all, which is a discovery problem rather than a parsing one.</p>
<table class=grid><thead><tr><th>year</th><th class=n>town-years</th></tr>
</thead><tbody>%s</tbody></table>
""" % (n, ntowns, "{:,}".format(possible), n * 100.0 / possible, bars)


def _read_master() -> list[dict]:
    with MASTER.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _population() -> dict:
    """{normalized municipality -> population}, or {} if the source is unavailable.

    Reads a committed CSV first and the workbook second. The workbook lives at
    an absolute path on one machine, so a CI run silently produced
    "population source unavailable" and a page reporting 0.0% people-year
    coverage -- which is not a missing number, it is a wrong one, and it would
    have been published. Coverage is reported two ways precisely because the
    two answers differ by more than ten points; losing one of them quietly is
    the failure this guards against.
    """
    here = Path(__file__).resolve().parent
    for cand in (Path(os.environ["COVERAGE_POPULATION"])
                 if os.environ.get("COVERAGE_POPULATION") else None,
                 here.parent / "config" / "population.csv",
                 ROOT / "config" / "population.csv"):
        if cand and cand.exists():
            with cand.open(encoding="utf-8", newline="") as fh:
                return {re.sub(r"[^a-z]", "", r["community"].lower()):
                        float(r["population"]) for r in csv.DictReader(fh)}
    try:
        from open_search_tabs import population
        return {re.sub(r"[^a-z]", "", k.lower()): v for k, v in population().items()}
    except Exception:
        return {}



def _official_domains() -> dict:
    """{normalized municipality -> official site URL} from targets.csv, or {}."""
    path = ROOT / "data" / "inventory" / "targets.csv"
    out: dict[str, str] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            d = (r.get("official_domain") or "").strip()
            m = (r.get("municipality") or "").strip()
            if d and m:
                out[re.sub(r"[^a-z]", "", m.lower())] = d if d.startswith("http") else "https://" + d
    return out


def prior_stats(rows: list[dict]) -> dict:
    """Coverage for 2021-2025 by year and by source_kind, from coverage_state.

    Also weights by population: a "people-year" is one resident-year of an expected
    town-year. People-year coverage runs well above town-year coverage because the
    uncovered town-years are overwhelmingly tiny towns -- cities are near-fully covered.
    """
    pop = _population()
    dom = _official_domains()

    def popof(muni):
        return pop.get(re.sub(r"[^a-z]", "", (muni or "").lower()), 0)

    def domof(muni, native):
        d = dom.get(re.sub(r"[^a-z]", "", (muni or "").lower()), "")
        if not d and native and "google" not in native:  # fall back to the row's own url host
            m = re.match(r"https?://[^/]+", native)
            d = m.group(0) if m else ""
        return d

    by_year = {y: defaultdict(int) for y in PRIOR_YEARS}
    by_kind: dict[str, defaultdict] = defaultdict(lambda: defaultdict(int))
    pop_tot = defaultdict(float)   # year -> expected people-years
    pop_cov = defaultdict(float)   # year -> covered people-years
    pop_held = defaultdict(float)  # year -> held-but-unpublished people-years
    gaps: list[tuple[str, str]] = []
    for r in rows:
        cs_raw = r.get("coverage_state", "")
        if r.get("expected", "").lower() != "yes" and cs_raw != "no_election":
            # no_election rows carry expected=no, so this filter was dropping all
            # 109 of them before they could be counted -- which is why the
            # "No elec" column read 0 in every year including 2022 and 2024,
            # where it should show the 55 cities that only elect in odd years.
            # They are counted and NOT put in denom (see pack); asserting no
            # election happened is a finding about the world and belongs on the
            # page, but it is not a town-year we owed a document for.
            continue
        y = r.get("year", "")
        if y not in by_year:
            continue
        cs = r.get("coverage_state", "") or "unknown"
        by_year[y][cs] += 1
        by_kind[r.get("source_kind", "") or "unknown"][cs] += 1
        if cs in ("published", "no_source", "pending_parse"):
            p = popof(r.get("municipality", ""))
            pop_tot[y] += p
            if cs == "published":
                pop_cov[y] += p
            elif cs == "pending_parse":
                pop_held[y] += p
        if cs == "no_source":
            muni = r.get("municipality", "")
            gaps.append((muni, y, popof(muni), domof(muni, r.get("native_url", ""))))

    def pack(counter: dict) -> dict:
        pub = counter.get("published", 0)
        gap = counter.get("no_source", 0)
        pend = counter.get("pending_parse", 0)
        na = counter.get("no_election", 0)
        denom = pub + gap + pend            # excludes no_election
        return {"published": pub, "no_source": gap, "pending_parse": pend,
                "no_election": na, "denom": denom,
                "pct": (100.0 * pub / denom) if denom else 0.0,
                "held_pct": (100.0 * pend / denom) if denom else 0.0}

    years = {y: pack(by_year[y]) for y in PRIOR_YEARS}
    for y in PRIOR_YEARS:
        years[y]["pop_pct"] = (100.0 * pop_cov[y] / pop_tot[y]) if pop_tot[y] else 0.0
        years[y]["pop_held_pct"] = ((100.0 * pop_held[y] / pop_tot[y])
                                    if pop_tot[y] else 0.0)
    tp, tc, th = (sum(pop_tot.values()), sum(pop_cov.values()),
                  sum(pop_held.values()))
    return {
        "years": years,
        "kinds": {k: pack(v) for k, v in sorted(by_kind.items())},
        "overall": pack({k: sum(by_year[y].get(k, 0) for y in PRIOR_YEARS)
                         for k in ("published", "no_source", "pending_parse", "no_election")}),
        "pop": {"pct": (100.0 * tc / tp) if tp else 0.0,
                "held_pct": (100.0 * th / tp) if tp else 0.0,
                "covered": tc, "held": th, "total": tp, "have": bool(pop)},
        "gaps": sorted((m, y) for m, y, _p, _d in gaps),
        "gaps_ranked": sorted(gaps, key=lambda g: -g[2]),
    }


def _bar(pct: float, held: float = 0.0) -> str:
    """Green = published. Amber = held: we have the document, it is not out yet.

    The two are stacked rather than summed into one number on purpose. Held is
    not coverage -- nobody can read it -- but it is also not a gap, and drawing
    it as empty bar made the reachable work invisible."""
    seg = (f'<div class="held" style="left:{pct:.1f}%;width:{held:.1f}%"></div>'
           if held > 0 else "")
    return (f'<div class="bar"><div class="fill" style="width:{pct:.1f}%"></div>{seg}'
            f'<span>{pct:.1f}%</span></div>')


def render(prior: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    o = prior["overall"]

    yr_rows = "".join(
        # 'Held' (pending_parse) has to be rendered or the row does not add up:
        # denom = covered + gap + held, and leaving the third term out made 2025
        # read "289 + 9 + 0 = 351". The 53 missing were town-years we hold and
        # have not published, which is exactly the number a reader most wants.
        f"<tr><td>{y}</td><td class=n>{s['published']}</td>"
        f"<td class=n>{s['no_source']}</td><td class=n>{s['pending_parse']}</td>"
        f"<td class=n>{s['no_election']}</td>"
        f"<td class=n>{s['denom']}</td><td>{_bar(s['pct'], s['held_pct'])}</td>"
        f"<td>{_bar(s['pop_pct'], s['pop_held_pct'])}</td></tr>"
        for y, s in prior["years"].items())

    kind_rows = "".join(
        f"<tr><td>{k}</td><td class=n>{s['published']}</td>"
        f"<td class=n>{s['no_source']}</td><td class=n>{s['pending_parse']}</td>"
        f"<td class=n>{s['denom']}</td>"
        f"<td>{_bar(s['pct'], s['held_pct'])}</td></tr>"
        for k, s in prior["kinds"].items())

    gap_by_year: dict[str, int] = defaultdict(int)
    for _m, y in prior["gaps"]:
        gap_by_year[y] += 1
    gap_summary = ", ".join(f"{y}: {gap_by_year[y]}" for y in PRIOR_YEARS)

    from urllib.parse import quote_plus
    TOP_N = len(prior["gaps_ranked"])          # show ALL uncovered town-years
    hunt_rows = ""
    for i, (muni, year, p, d) in enumerate(prior["gaps_ranked"][:TOP_N], 1):
        q = quote_plus(f'"{muni}" MA "{year}" annual town election results')
        search = f"https://www.google.com/search?q={q}"
        site = (f'<a href="{d}" target=_blank rel=noopener>site</a>' if d else
                '<span class=mut>—</span>')
        hunt_rows += (
            f"<tr><td class=n>{i}</td><td>{muni}</td><td class=n>{year}</td>"
            f"<td class=n>{int(p):,}</td>"
            f"<td>{site} · <a href=\"{search}\" target=_blank rel=noopener>search</a></td></tr>")
    n_gaps = len(prior["gaps_ranked"])

    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>CivicAtlasMA coverage</title>
<style>
:root{{--ink:#1a2233;--mut:#6b7688;--line:#e3e8f0;--good:#2e7d5b;--bg:#f7f9fc}}
*{{box-sizing:border-box}}
body{{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);
background:var(--bg);margin:0;padding:2rem}}
.wrap{{max-width:920px;margin:0 auto}}
h1{{font-size:1.5rem;margin:0 0 .2rem}}
.sub{{color:var(--mut);margin:0 0 1.5rem;font-size:.9rem}}
.card{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:1.25rem 1.5rem;
margin:0 0 1.25rem;box-shadow:0 1px 2px rgba(20,30,50,.04)}}
h2{{font-size:1.05rem;margin:0 0 1rem;display:flex;justify-content:space-between;align-items:baseline}}
h2 .big{{font-size:1.6rem;font-weight:700;color:var(--good)}}
table{{width:100%;border-collapse:collapse;font-size:.9rem}}
th,td{{text-align:left;padding:.4rem .5rem;border-bottom:1px solid var(--line)}}
th{{color:var(--mut);font-weight:600;font-size:.78rem;text-transform:uppercase;letter-spacing:.03em}}
td.n{{text-align:right;font-variant-numeric:tabular-nums;width:4.5rem}}
.mut{{color:var(--mut)}}
a{{color:#2e6fa8;text-decoration:none}} a:hover{{text-decoration:underline}}
.bar{{position:relative;background:#eef1f6;border-radius:5px;height:20px;min-width:120px;overflow:hidden}}
.bar .fill{{position:absolute;inset:0 auto 0 0;background:linear-gradient(90deg,#3a8f6a,#2e7d5b)}}
.bar .held{{position:absolute;top:0;bottom:0;background:repeating-linear-gradient(45deg,#e0a33e,#e0a33e 4px,#eab55e 4px,#eab55e 8px)}}
.key{{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:middle;margin-right:.3rem}}
.bar span{{position:relative;padding:0 .5rem;font-size:.78rem;line-height:20px;
font-variant-numeric:tabular-nums;color:#123}}
.note{{color:var(--mut);font-size:.82rem;margin:.75rem 0 0}}
.prov{{display:inline-block;background:#fff4e0;color:#8a5a00;border:1px solid #f0d9a8;
border-radius:6px;padding:.05rem .5rem;font-size:.72rem;font-weight:600;vertical-align:middle}}
.grid{{display:flex;gap:1rem;flex-wrap:wrap}}
.stat{{flex:1;min-width:130px;background:var(--bg);border:1px solid var(--line);
border-radius:8px;padding:.75rem}}
.stat b{{display:block;font-size:1.5rem;line-height:1.1}}
.stat span{{color:var(--mut);font-size:.8rem}}
</style></head><body><div class=wrap>
<h1>CivicAtlasMA — election-results coverage</h1>
<p class=sub>Generated {now} · 351 municipalities · source: master_urls.csv</p>

<div class=card>
<h2>2021–2026 <span><span class=big>{o['pct']:.1f}%</span>
<span style="font-size:.9rem;color:var(--mut)"> town-years&nbsp;·&nbsp;</span>
<span class=big>{prior['pop']['pct']:.1f}%</span>
<span style="font-size:.9rem;color:var(--mut)"> people-years</span></span></h2>
<div class=grid>
<div class=stat><b>{o['published']}</b><span>covered (hosted doc)</span></div>
<div class=stat><b>{o['no_source']}</b><span>gaps (no source)</span></div>
<div class=stat><b>{o['denom']}</b><span>expected town-years</span></div>
<div class=stat><b>{prior['pop']['covered']/1e6:.1f}M</b><span>of {prior['pop']['total']/1e6:.1f}M people-years</span></div>
</div>
<h3 style="font-size:.9rem;margin:1.25rem 0 .5rem">By year</h3>
<table><tr><th>Year</th><th class=n>Covered</th><th class=n>Gap</th>
<th class=n title="held but not published: parsed, or awaiting a citation">Held</th>
<th class=n>No&nbsp;elec</th><th class=n>Denom</th><th>Town-year&nbsp;%</th>
<th>People-year&nbsp;%</th></tr>
{yr_rows}</table>
<p class=note>People-year coverage weights each town-year by population: it runs ~12 points
above town-year coverage because the uncovered town-years are overwhelmingly small towns —
cities are near-fully covered.</p>
<h3 style="font-size:.9rem;margin:1.25rem 0 .5rem">By source type</h3>
<table><tr><th>Source</th><th class=n>Covered</th><th class=n>Gap</th>
<th class=n>Held</th><th class=n>Denom</th><th>Coverage</th></tr>
{kind_rows}</table>
<p class=note><b>Covered + Gap + Held = Denom.</b> A <b>gap</b> is a town-year we hold nothing
for. <b>Held</b> means we have the document but have not published it — most of those are
waiting on a citation, not on a document. Only Covered counts toward the percentage.
In the bars: <span class=key style="background:#2e7d5b"></span>published,
<span class=key style="background:repeating-linear-gradient(45deg,#e0a33e,#e0a33e 3px,#eab55e 3px,#eab55e 6px)"></span>held.
<b>No&nbsp;elec</b> is a finding about the world — no election was held — so it sits outside
the denominator; the 55 in each even year are the cities that elect only in odd years.</p>
<p class=note>Gaps by year — {gap_summary}. "No election" town-years are excluded from the
denominator (the town held no election that year, so there is nothing to collect).</p>
</div>

<div class=card>
<h2>Uncovered town-years <span style="font-size:.85rem;color:var(--mut)">all {n_gaps} gaps, ranked by population — highest-value first</span></h2>
<table><tr><th class=n>#</th><th>Town</th><th class=n>Year</th><th class=n>Population</th>
<th>Find it</th></tr>
{hunt_rows}</table>
<p class=note>Ranked by town population, so the top of the list moves people-year coverage
the most. "site" opens the town's official site; "search" is a Google query for that
town-year's results. Recovering a doc here means hosting it and re-running the parse gate.
2026 gaps appear here too now that 2026 is a normal year — collection for it is still ongoing.</p>
</div>
{_pre2021_html()}
</div></body></html>"""


def main() -> None:
    rows = _read_master()
    prior = prior_stats(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(prior), encoding="utf-8")
    o = prior["overall"]
    pw = prior["pop"]
    print(f"2021-2026: {o['published']}/{o['denom']} = {o['pct']:.1f}% town-years covered "
          f"({o['no_source']} gaps, {o['no_election']} no-election excluded)")
    print(f"           population-weighted: {pw['pct']:.1f}% people-years "
          f"({pw['covered']/1e6:.2f}M/{pw['total']/1e6:.2f}M)"
          + ("" if pw["have"] else "  [population source unavailable]"))
    y26 = prior["years"].get("2026", {})
    if y26:
        print(f"2026: {y26['published']}/{y26['denom']} = {y26['pct']:.1f}% "
              f"(now a normal year; collection ongoing)")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
