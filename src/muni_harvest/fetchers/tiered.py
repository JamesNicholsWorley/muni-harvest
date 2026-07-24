"""Tiered live fetcher (T0 -> T1 -> T2) + probe escalation.

Escalate only as far as needed, cheapest first:
  T0  plain stdlib HTTP (wide, politeness-bound)
  T1  cookie-lift: mint a browser session once per domain, replay via requests
  T2  in-browser fetch (full JS challenge pass) from a warm pooled driver

`escalate_blocked()` takes the hosts the free T0 probe flagged `blocked` and runs
them through T1/T2 to split them into:
  T1 / T2            -> a self-hosted browser tier handles it (justifies the VM)
  needs_unblocker    -> even a real browser can't pass -> the only paid residual

That split is what turns the browser-required *estimate* into the exact set that
decides self-host-VM vs rent-an-unblocker spend.
"""

from __future__ import annotations

import re

from ..core import fetch
from ..resolve.tier_cache import TierCache
from .waf_session import fetch_in_browser, mint_session

_CHALLENGE = re.compile(
    r"just a moment|cf-chl|checking your browser|attention required|"
    r"access denied|request unsuccessful|incapsula|imperva|"
    r"captcha|are you a robot|enable javascript to continue", re.I)


def _clean(status: int, text: str) -> bool:
    return status == 200 and not _CHALLENGE.search((text or "")[:8000])


def escalate_host(host: str, pool) -> dict:
    """Try T1 then T2 on the homepage. Returns {tier, signal}."""
    home = f"https://{host}/"

    # T1 — cookie-lift, then a plain request with the browser's cookies.
    try:
        sess = mint_session(home, wait=6)
        r = sess.get(home, timeout=30)
        if _clean(r.status_code, r.text):
            return {"tier": "T1", "signal": "cookie_lift"}
    except Exception as exc:  # noqa: BLE001
        t1_err = type(exc).__name__
    else:
        t1_err = "t1_challenged"

    # T2 — full in-browser fetch from a warm driver.
    try:
        with pool.lease() as d:
            d.get(home)
            status, text = fetch_in_browser(d, home)
        if _clean(status, text):
            return {"tier": "T2", "signal": "in_browser"}
        return {"tier": "needs_unblocker", "signal": f"t2_challenged:{status}"}
    except Exception as exc:  # noqa: BLE001
        return {"tier": "needs_unblocker", "signal": f"t2_err:{type(exc).__name__}"}


def escalate_blocked(*, limit: int | None = None, pool_size: int = 3) -> dict:
    """Reclassify TierCache 'blocked' hosts via the browser tier. Resumable
    (already-escalated hosts keep their non-'blocked' tier)."""
    from .browser_pool import BrowserPool

    cache = TierCache()
    blocked = [h for h, rec in cache._map.items() if rec.get("tier") == "blocked"]
    if limit:
        blocked = blocked[:limit]
    print(f"[*] escalating {len(blocked)} blocked host(s) through T1/T2 "
          f"({pool_size} warm drivers)")
    if not blocked:
        print("[OK] nothing blocked — no browser tier needed.")
        return {"escalated": 0}

    pool = BrowserPool(size=pool_size)
    counts: dict[str, int] = {}
    try:
        for host in blocked:
            res = escalate_host(host, pool)
            cache.set(host, res["tier"], signal=res["signal"], via="escalate")
            counts[res["tier"]] = counts.get(res["tier"], 0) + 1
            print(f"  [{res['tier']:<15}] {host:<36} {res['signal']}")
    finally:
        pool.close()

    print(f"\n[escalation result] {counts}")
    solvable = counts.get("T1", 0) + counts.get("T2", 0)
    print(f"[browser-solvable] {solvable}  |  [needs paid unblocker] "
          f"{counts.get('needs_unblocker', 0)}")
    return {"escalated": len(blocked), "counts": counts}
