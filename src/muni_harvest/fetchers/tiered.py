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

import time

from ..core import fetch
from ..resolve.tier_cache import TierCache

# NOTE: selenium-backed helpers (waf_session, browser_pool) are imported lazily
# inside the functions that need them, so the pure classifiers below (_clean,
# _dom_clean) stay importable without the `live` extra.

_CHALLENGE = re.compile(
    r"just a moment|cf-chl|checking your browser|attention required|"
    r"access denied|request unsuccessful|incapsula|imperva|"
    r"captcha|are you a robot|enable javascript to continue", re.I)


def _clean(status: int, text: str) -> bool:
    return status == 200 and not _CHALLENGE.search((text or "")[:8000])


def _dom_clean(src: str) -> bool:
    """A loaded page is 'clean' if it rendered real content.

    Size-first: WAF interstitials ("Just a moment", Incapsula, Access Denied) are
    tiny (<~10KB); real municipal homepages are large. So a big DOM is the real site
    even if it happens to contain the word 'captcha' in a contact-form widget. Only
    for small/ambiguous pages do we fall back to challenge-marker matching.
    """
    if not src or len(src) < 1500:
        return False
    if len(src) > 12000:
        return True
    return not _CHALLENGE.search(src[:8000])


def escalate_host(host: str, pool) -> dict:
    """Try T1 then T2 on the homepage. Returns {tier, signal}.

    T2 inspects the *loaded DOM* (page_source) after redirects/JS — NOT a re-fetch
    of the original URL, which would be cross-origin (bare-domain -> www) and
    spuriously fail with status 0.
    """
    home = f"https://{host}/"

    from .waf_session import mint_session

    # T1 — cookie-lift, then a plain request with the browser's cookies (requests
    # follows the www redirect on its own).
    try:
        sess = mint_session(home, wait=6)
        r = sess.get(home, timeout=30)
        if _clean(r.status_code, r.text):
            return {"tier": "T1", "signal": "cookie_lift"}
    except Exception:  # noqa: BLE001 — fall through to the full browser tier
        pass

    # T2 — load in a real browser and read the rendered DOM after it settles.
    try:
        with pool.lease() as d:
            d.get(home)
            time.sleep(4)
            src = d.page_source
        if _dom_clean(src):
            return {"tier": "T2", "signal": "in_browser_dom"}
        return {"tier": "needs_unblocker", "signal": f"t2_dom_len:{len(src or '')}"}
    except Exception as exc:  # noqa: BLE001
        return {"tier": "needs_unblocker", "signal": f"t2_err:{type(exc).__name__}"}


def escalate_blocked(*, limit: int | None = None, pool_size: int = 3,
                     redo: bool = False) -> dict:
    """Reclassify TierCache 'blocked' hosts via the browser tier. Resumable
    (already-escalated hosts keep their tier). With redo=True, also re-checks hosts
    previously marked needs_unblocker (use after fixing escalation logic)."""
    from .browser_pool import BrowserPool

    targets = {"blocked", "needs_unblocker"} if redo else {"blocked"}
    cache = TierCache()
    blocked = [h for h, rec in cache._map.items() if rec.get("tier") in targets]
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
