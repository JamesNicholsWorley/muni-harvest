"""Meeting-level agenda vs minutes completion, using AgendaCenter meeting-ids
(the one clean join: agenda & minutes of the same meeting share the id).

For each AgendaCenter town: how many meeting-ids have agenda-only, minutes-only, both.
This is the real "agendas missing minutes" question."""
from __future__ import annotations
import json, re, sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.docclass import classify_document

NODES = Path(__file__).resolve().parents[1] / "data" / "discover" / "nodes.jsonl"

# per (town) -> meeting_id -> set of doctypes
ag = defaultdict(set)   # town -> {mid}
mn = defaultdict(set)
host_of = {}
for line in NODES.open(encoding="utf-8"):
    try: rec = json.loads(line)
    except Exception: continue
    if rec.get("kind") != "file": continue
    url = rec["url"]
    if "/AgendaCenter/ViewFile/" not in url: continue
    town = rec.get("municipality") or ""
    if not town: continue
    c = classify_document(url)
    if not c["agendacenter"] or not c["meeting_id"]: continue
    mid = c["meeting_id"]
    if c["doctype"] == "agenda": ag[town].add(mid)
    elif c["doctype"] == "minutes": mn[town].add(mid)

# aggregate
tot_ag_only = tot_min_only = tot_both = 0
per_town = []
for town in sorted(set(ag) | set(mn)):
    a, m = ag[town], mn[town]
    both = a & m
    a_only = a - m
    m_only = m - a
    tot_ag_only += len(a_only); tot_min_only += len(m_only); tot_both += len(both)
    per_town.append((town, len(a), len(m), len(both), len(a_only), len(m_only)))

allmids = tot_ag_only + tot_min_only + tot_both
print(f"AgendaCenter meeting-ids across {len(per_town)} towns: {allmids:,}")
print(f"  both agenda+minutes: {tot_both:,} ({tot_both/allmids:.1%})")
print(f"  agenda ONLY:         {tot_ag_only:,} ({tot_ag_only/allmids:.1%})")
print(f"  minutes ONLY:        {tot_min_only:,} ({tot_min_only/allmids:.1%})")
tot_ag = tot_both + tot_ag_only
print(f"\n  of all meetings WITH an agenda ({tot_ag:,}), {tot_both/tot_ag:.1%} also have minutes")

# towns with the biggest agenda-only gaps (candidates for manual check)
per_town.sort(key=lambda r: r[4], reverse=True)
print("\nTop 15 towns by agenda-only count (agenda w/o matching minutes):")
print(f"  {'town':<20}{'agendas':>8}{'minutes':>8}{'both':>6}{'ag_only':>8}{'min_only':>9}")
for t,a,m,b,ao,mo in per_town[:15]:
    print(f"  {t:<20}{a:>8}{m:>8}{b:>6}{ao:>8}{mo:>9}")

# a few well-covered towns for manual verification (both agendas and minutes present)
print("\nTowns with BALANCED agenda+minutes (good manual-check candidates):")
bal = [r for r in per_town if r[1]>30 and r[2]>30]
bal.sort(key=lambda r: r[3], reverse=True)
for t,a,m,b,ao,mo in bal[:10]:
    print(f"  {t:<20}{a:>8}{m:>8}{b:>6}{ao:>8}{mo:>9}")
