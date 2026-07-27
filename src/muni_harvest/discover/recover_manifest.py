"""Extract compact, committable manifests from the (multi-GB, gitignored) corpus so the
dc-idsweep and minutes-recover workflows can run on GitHub Actions without the whole
corpus. Each is a tiny gzipped slice:

  config/dc_known_ids.jsonl.gz   host -> {url_host, ids:[int]}       (DocumentCenter ids
                                          already captured -> gap computation)
  config/agenda_only.jsonl.gz    host -> {url_host, muni, need:[[date,id]]}  (agenda-only
                                          AgendaCenter meetings to probe for minutes)

Regenerate after each corpus merge:  muni-harvest export-manifests
"""

from __future__ import annotations

import gzip
import json
import re
from collections import defaultdict

from ..config import REPO_ROOT, data_dir
from ..core import iter_jsonl

_VIEW = re.compile(r"/DocumentCenter/View/(\d+)", re.I)
_IMG = re.compile(r"documentID=(\d+)", re.I)
_AC = re.compile(r"/AgendaCenter/ViewFile/(Agenda|Minutes)/_(\d{8})-(\d+)", re.I)

_CORPUS_FILES = ("nodes.jsonl", "nodes_docsweep.jsonl", "nodes_idsweep.jsonl",
                 "nodes_minutes.jsonl")


def _config_dir():
    # committed manifests live next to muni_hosts.txt in the repo's config/ dir
    return REPO_ROOT / "config"


def dc_manifest_path():
    return _config_dir() / "dc_known_ids.jsonl.gz"


def agenda_manifest_path():
    return _config_dir() / "agenda_only.jsonl.gz"


def _corpus_iter():
    disc = data_dir() / "discover"
    for name in _CORPUS_FILES:
        p = disc / name
        if p.exists():
            yield from iter_jsonl(p)


def build() -> dict:
    dc: dict[str, dict] = defaultdict(lambda: {"url_host": "", "ids": set()})
    ag: dict[str, dict[str, tuple]] = defaultdict(dict)     # host -> {mid:(date,url_host)}
    mn: dict[str, set] = defaultdict(set)
    muni: dict[str, str] = {}

    for n in _corpus_iter():
        u = n.get("url", "")
        host = n.get("seed_host") or re.sub(r"^https?://", "", u).split("/")[0]
        url_host = re.sub(r"^https?://", "", u).split("/")[0].split(":")[0]
        m = _VIEW.search(u) or _IMG.search(u)
        if m:
            rec = dc[host]
            rec["ids"].add(int(m.group(1)))
            if not rec["url_host"]:
                rec["url_host"] = url_host
        a = _AC.search(u)
        if a:
            muni.setdefault(host, n.get("municipality", ""))
            typ, date, mid = a.group(1).lower(), a.group(2), a.group(3)
            if typ == "agenda":
                ag[host].setdefault(mid, (date, url_host))
            else:
                mn[host].add(mid)

    _config_dir().mkdir(parents=True, exist_ok=True)
    with gzip.open(dc_manifest_path(), "wt", encoding="utf-8") as f:
        for host, rec in dc.items():
            f.write(json.dumps({"host": host, "url_host": rec["url_host"],
                                "ids": sorted(rec["ids"])}) + "\n")
    n_ag = 0
    with gzip.open(agenda_manifest_path(), "wt", encoding="utf-8") as f:
        for host, meetings in ag.items():
            need = [[d, mid] for mid, (d, uh) in meetings.items() if mid not in mn[host]]
            if not need:
                continue
            n_ag += len(need)
            uh = next(iter(meetings.values()))[1]
            f.write(json.dumps({"host": host, "url_host": uh, "muni": muni.get(host, ""),
                                "need": need}) + "\n")
    totals = {"dc_hosts": len(dc), "dc_ids": sum(len(r["ids"]) for r in dc.values()),
              "agenda_hosts": sum(1 for h in ag), "agenda_only_meetings": n_ag}
    print(f"[export-manifests] DocumentCenter: {totals['dc_hosts']} hosts, "
          f"{totals['dc_ids']:,} known ids -> {dc_manifest_path().name}")
    print(f"[export-manifests] AgendaCenter agenda-only: {totals['agenda_only_meetings']:,} "
          f"meetings across {totals['agenda_hosts']} hosts -> {agenda_manifest_path().name}")
    return totals


def load_dc() -> dict[str, dict] | None:
    p = dc_manifest_path()
    if not p.exists():
        return None
    out: dict[str, dict] = {}
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            out[r["host"]] = {"url_host": r["url_host"], "ids": set(r["ids"])}
    return out


def load_agenda() -> dict[str, dict] | None:
    p = agenda_manifest_path()
    if not p.exists():
        return None
    out: dict[str, dict] = {}
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            out[r["host"]] = {"muni": r.get("muni", ""),
                              "need": {mid: (d, r["url_host"]) for d, mid in r["need"]}}
    return out
