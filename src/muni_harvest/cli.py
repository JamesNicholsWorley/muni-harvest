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

    sub.add_parser("scorecard",
                   help="coverage stats vs the core civic-doc checklist")

    # budget owns its own subparser tree, so split argv at the top level.
    if argv and argv[0] == "budget":
        from .budget import ledger
        ledger.main(argv[1:])
        return 0

    args = ap.parse_args(argv)
    if args.cmd == "wayback":
        from .archive import wayback
        wayback.harvest(limit=args.limit, workers=args.workers,
                        hosts_file=args.hosts_file)
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
                     max_depth=args.max_depth)
    elif args.cmd == "scorecard":
        from .discover import scorecard
        scorecard.build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
