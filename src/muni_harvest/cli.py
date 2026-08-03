"""muni-harvest command-line entrypoint.

  muni-harvest budget  <seed|summary|spend|alloc> ...
  muni-harvest wayback [--limit N] [--workers N]     # free deep doc enumeration
  muni-harvest probe   [--limit N] [--workers N]     # measure browser-required %
  muni-harvest resolve                               # cheapest-source-wins routing
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="muni-harvest", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("budget", add_help=False,
                   help="budget ledger (seed|summary|spend|alloc)")

    p_wb = sub.add_parser("wayback", help="parallel Wayback CDX doc enumeration")
    p_wb.add_argument("--limit", type=int, default=None)
    p_wb.add_argument("--workers", type=int, default=None)
    p_wb.add_argument("--hosts-file", default=None,
                      help="read hosts from this file instead of the inventory CSV")
    p_wb.add_argument("--shard", default=None,
                      help="run only shard I/N (for distributed runners), e.g. 3/20")

    p_pr = sub.add_parser("probe", help="tier-probe the domains (browser-required fraction)")
    p_pr.add_argument("--limit", type=int, default=None)
    p_pr.add_argument("--workers", type=int, default=None)

    sub.add_parser("resolve", help="print cheapest-source-wins routing summary")

    p_dis = sub.add_parser("discover",
                           help="union Wayback+sitemaps+crawl+CMS into a nav-tree")
    p_dis.add_argument("--limit", type=int, default=None)
    p_dis.add_argument("--workers", type=int, default=None)
    p_dis.add_argument("--hosts-file", default=None)
    p_dis.add_argument("--max-pages", type=int, default=None)
    p_dis.add_argument("--max-depth", type=int, default=None)
    p_dis.add_argument("--shard", default=None, help="run only shard I/N (distributed)")

    sub.add_parser("scorecard",
                   help="coverage stats vs the core civic-doc checklist")

    sub.add_parser("groundtruth",
                   help="election-result recall vs the 942 known-collected PDFs")

    sub.add_parser("coverage",
                   help="board-level agenda/minutes coverage + linkage (wide-net classifier)")

    p_acr = sub.add_parser("recover-boards",
                           help="recover AgendaCenter meeting->board (fills unknown-board gap)")
    p_acr.add_argument("--workers", type=int, default=8)

    p_dc = sub.add_parser("documentcenter",
                          help="enumerate CivicPlus DocumentCenter (React API backdoor)")
    p_dc.add_argument("--workers", type=int, default=8)
    p_dc.add_argument("--hosts-file", default=None)
    p_dc.add_argument("--shard", default=None)

    p_sw = sub.add_parser("docsweep",
                          help="sitemap-seeded whole-site document sweep (all linked docs)")
    p_sw.add_argument("--workers", type=int, default=8)
    p_sw.add_argument("--hosts-file", default=None)
    p_sw.add_argument("--shard", default=None)
    p_sw.add_argument("--max-pages", type=int, default=6000)
    p_sw.add_argument("--limit", type=int, default=None)

    sub.add_parser("export-manifests",
                   help="extract committable dc/agenda manifests from the corpus (for Actions)")

    p_ids = sub.add_parser("dc-idsweep",
                           help="probe DocumentCenter /View/{id} gaps to recover de-linked archives")
    p_ids.add_argument("--workers", type=int, default=8)
    p_ids.add_argument("--shard", default=None)
    p_ids.add_argument("--limit", type=int, default=None)
    p_ids.add_argument("--per-host-cap", type=int, default=15000,
                       help="max gap probes per host (newest first); logged if hit")
    p_ids.add_argument("--min-density", type=float, default=0.12,
                       help="known-id density gate for the ceiling (ignore sparse outliers)")
    p_ids.add_argument("--rpm", type=int, default=240,
                       help="shard-global probe rate (spread across ~6 hosts/shard)")
    p_ids.add_argument("--headroom", type=int, default=0,
                       help="also probe this many ids ABOVE the known ceiling, to reach "
                            "documents posted since the manifest was built (current-year "
                            "results); stops after 150 consecutive misses")

    p_mr = sub.add_parser("minutes-recover",
                          help="deterministic AgendaCenter minutes recovery (agenda-only meetings)")
    p_mr.add_argument("--workers", type=int, default=8)
    p_mr.add_argument("--shard", default=None)
    p_mr.add_argument("--limit", type=int, default=None)

    p_ver = sub.add_parser("verify",
                           help="content-verify election docs (open PDFs, check results)")
    p_ver.add_argument("--limit", type=int, default=None)
    p_ver.add_argument("--per-town", type=int, default=3)
    p_ver.add_argument("--workers", type=int, default=8)
    p_ver.add_argument("--emit", action="store_true",
                       help="write config/verify_candidates.jsonl and exit")
    p_ver.add_argument("--candidates", default=None,
                       help="verify from a committed candidates file (for runners)")
    p_ver.add_argument("--shard", default=None, help="run only shard I/N")

    sub.add_parser("store", add_help=False,
                   help="object storage (R2/B2): ping | ensure")

    p_esc = sub.add_parser("escalate",
                           help="run T0-blocked hosts through the T1/T2 browser tier")
    p_esc.add_argument("--limit", type=int, default=None)
    p_esc.add_argument("--pool-size", type=int, default=3)
    p_esc.add_argument("--redo", action="store_true",
                       help="also re-check hosts previously marked needs_unblocker")

    # budget/store own their own subparser trees, so split argv at the top level.
    if argv and argv[0] == "budget":
        from .budget import ledger
        ledger.main(argv[1:])
        return 0
    if argv and argv[0] == "store":
        from . import store
        store.main(argv[1:])
        return 0

    args = ap.parse_args(argv)
    if args.cmd == "wayback":
        from .archive import wayback
        wayback.harvest(limit=args.limit, workers=args.workers,
                        hosts_file=args.hosts_file, shard=args.shard)
    elif args.cmd == "probe":
        from .probe import tier_probe
        tier_probe.run(limit=args.limit, workers=args.workers)
    elif args.cmd == "resolve":
        from .resolve import resolver
        resolver.summary()
    elif args.cmd == "discover":
        from .discover import pipeline
        pipeline.run(limit=args.limit, workers=args.workers,
                     hosts_file=args.hosts_file, max_pages=args.max_pages,
                     max_depth=args.max_depth, shard=args.shard)
    elif args.cmd == "scorecard":
        from .discover import scorecard
        scorecard.build()
    elif args.cmd == "groundtruth":
        from .discover import groundtruth
        groundtruth.build()
    elif args.cmd == "coverage":
        from .discover import coverage
        coverage.build()
    elif args.cmd == "recover-boards":
        from .discover import agendacenter_recover
        agendacenter_recover.run(workers=args.workers)
    elif args.cmd == "documentcenter":
        from .discover import documentcenter
        documentcenter.run(workers=args.workers, hosts_file=args.hosts_file,
                           shard=args.shard)
    elif args.cmd == "export-manifests":
        from .discover import recover_manifest
        recover_manifest.build()
    elif args.cmd == "dc-idsweep":
        from .discover import dc_idsweep
        dc_idsweep.run(workers=args.workers, shard=args.shard, limit=args.limit,
                       per_host_cap=args.per_host_cap, min_density=args.min_density,
                       rpm=args.rpm, headroom=args.headroom)
    elif args.cmd == "minutes-recover":
        from .discover import minutes_recover
        minutes_recover.run(workers=args.workers, shard=args.shard, limit=args.limit)
    elif args.cmd == "docsweep":
        from .discover import docsweep
        docsweep.run(workers=args.workers, hosts_file=args.hosts_file,
                     shard=args.shard, max_pages=args.max_pages, limit=args.limit)
    elif args.cmd == "verify":
        from .discover import verify
        if args.emit:
            verify.emit_candidates(per_town=args.per_town)
        else:
            verify.verify(limit=args.limit, per_town=args.per_town,
                          workers=args.workers, candidates_file=args.candidates,
                          shard=args.shard)
    elif args.cmd == "escalate":
        from .fetchers import tiered
        tiered.escalate_blocked(limit=args.limit, pool_size=args.pool_size,
                                redo=args.redo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
