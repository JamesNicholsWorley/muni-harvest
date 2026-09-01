"""Board-level document coverage report + agenda<->minutes linkage.

Runs the wide-net classifier over every discovered file and answers: for each
governing body (Select Board, City/Town Council, Planning Board, ZBA, ...), how many
towns have agendas / minutes, and how many agenda+minutes we can LINK to the same
meeting. Linkage:
  - AgendaCenter: agenda & minutes share the meeting-id in the URL.
  - Freeform:     agenda & minutes share (board, date).
Deterministic, no downloads. A separate `verify` pass content-checks a sample.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from ..config import data_dir
from ..core import iter_jsonl, write_jsonl
from ..config import load_settings
from .docclass import BOARD_LABEL, classify_document

PRIORITY = ["select_board", "city_council", "planning_board", "zba", "conservation",
            "board_of_health", "school_committee", "finance", "elections",
            "town_meeting"]


def build(total_towns: int | None = None) -> dict:
    # The coverage denominator is the number of municipalities being harvested,
    # which is a property of the host list -- not a constant. It was 351 (the
    # Massachusetts town count) because that was the only host list this project
    # had. A sibling corpus covering the other five New England states harvests
    # 1,171, and a hardcoded 351 would report >100% coverage for it.
    if total_towns is None:
        total_towns = load_settings().get("discover", {}).get(
            "total_towns", 351)
    from .agendacenter_recover import load_recovered
    ac_map = load_recovered()  # (town, meeting_id) -> board, fills AgendaCenter gaps
    nodes = data_dir() / "discover" / "nodes.jsonl"
    cov: dict[tuple, set] = defaultdict(set)     # (board, doctype) -> {town}
    ac_ag: dict[str, set] = defaultdict(set)     # town -> {meeting_id} agendas
    ac_min: dict[str, set] = defaultdict(set)
    ff_ag: dict[str, set] = defaultdict(set)     # town -> {(board,date)} agendas
    ff_min: dict[str, set] = defaultdict(set)
    doctypes = Counter()
    boards = Counter()
    ac_board_unknown = 0
    files = 0

    for n in iter_jsonl(nodes):
        if n.get("kind") != "file":
            continue
        files += 1
        town = n.get("municipality") or ""
        c = classify_document(n["url"], n.get("anchor", ""))
        dt, bd = c["doctype"], c["board"]
        # Fill AgendaCenter's missing board from the recovered meeting_id->board map.
        if not bd and c["agendacenter"] and c["meeting_id"] and town:
            bd = ac_map.get((town, c["meeting_id"]), "")
        if dt:
            doctypes[dt] += 1
        if bd:
            boards[bd] += 1
        if dt in ("agenda", "minutes"):
            if not town:
                continue
            cov[(bd or "(unknown board)", dt)].add(town)
            if c["agendacenter"] and c["meeting_id"]:
                (ac_ag if dt == "agenda" else ac_min)[town].add(c["meeting_id"])
                if not bd:
                    ac_board_unknown += 1
            elif bd and c["date"]:
                (ff_ag if dt == "agenda" else ff_min)[town].add((bd, c["date"]))

    # agenda<->minutes linkage
    ac_linked = sum(len(ac_ag[t] & ac_min[t]) for t in ac_ag)
    ac_link_towns = sum(1 for t in ac_ag if ac_ag[t] & ac_min[t])
    ff_linked = sum(len(ff_ag[t] & ff_min[t]) for t in ff_ag)
    ff_link_towns = sum(1 for t in ff_ag if ff_ag[t] & ff_min[t])

    rows = []
    for b in PRIORITY:
        ag = cov.get((b, "agenda"), set())
        mn = cov.get((b, "minutes"), set())
        rows.append({"board": b, "label": BOARD_LABEL.get(b, b),
                     "towns_agenda": len(ag), "towns_minutes": len(mn),
                     "towns_both": len(ag & mn)})

    summary = {
        "files_classified": files,
        "doctype_counts": dict(doctypes.most_common()),
        "board_counts": dict(boards.most_common(15)),
        "priority": rows,
        "linkage": {"agendacenter_meetings": ac_linked, "agendacenter_towns": ac_link_towns,
                    "freeform_meetings": ff_linked, "freeform_towns": ff_link_towns,
                    "agendacenter_board_unknown_docs": ac_board_unknown},
        "total_towns": total_towns,
    }
    _print(summary)
    out = data_dir() / "discover"
    write_jsonl(out / "coverage.jsonl", rows)
    _render(out / "coverage.md", summary)
    return summary


def _print(s: dict) -> None:
    T = s["total_towns"]
    print(f"\n  Board coverage ({s['files_classified']:,} files classified; /{T} towns)\n")
    print(f"  {'body':<32}{'agendas':>9}{'minutes':>9}{'both':>7}")
    print(f"  {'-'*32}{'-'*9:>9}{'-'*9:>9}{'-'*7:>7}")
    for r in s["priority"]:
        print(f"  {r['label']:<32}{r['towns_agenda']:>9}{r['towns_minutes']:>9}{r['towns_both']:>7}")
    lk = s["linkage"]
    print(f"\n  agenda<->minutes linked meetings: "
          f"{lk['agendacenter_meetings']:,} (AgendaCenter) + "
          f"{lk['freeform_meetings']:,} (freeform)")
    print(f"  AgendaCenter agenda/minutes with UNKNOWN board: "
          f"{lk['agendacenter_board_unknown_docs']:,} (board lives in the empty anchor)")
    print(f"  top doctypes: {dict(list(s['doctype_counts'].items())[:6])}")


def _render(path, s: dict) -> None:
    import time
    T = s["total_towns"]
    lines = [f"# Board-level document coverage (generated {time.strftime('%Y-%m-%d')})",
             "", f"{s['files_classified']:,} files classified. Town counts are out of {T}.",
             "", "| Governing body | towns w/ agendas | towns w/ minutes | towns w/ both |",
             "|---|--:|--:|--:|"]
    for r in s["priority"]:
        lines.append(f"| {r['label']} | {r['towns_agenda']} | {r['towns_minutes']} "
                     f"| {r['towns_both']} |")
    lk = s["linkage"]
    lines += ["", "## Agenda ↔ minutes linkage", "",
              f"- AgendaCenter (linked by meeting-id): **{lk['agendacenter_meetings']:,}** "
              f"meetings across {lk['agendacenter_towns']} towns",
              f"- Freeform (linked by board+date): **{lk['freeform_meetings']:,}** "
              f"meetings across {lk['freeform_towns']} towns",
              f"- AgendaCenter agenda/minutes with **unknown board**: "
              f"{lk['agendacenter_board_unknown_docs']:,} (board is only in the link "
              f"text, which Wayback didn't capture — a board-recovery gap)",
              "", "## Doctype distribution", "",
              "| doctype | files |", "|---|--:|"]
    for k, v in s["doctype_counts"].items():
        lines.append(f"| {k} | {v:,} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
