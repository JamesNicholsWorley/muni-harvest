"""Tier probe — the measurement that replaces the ~10% browser-required estimate.

For each host we attempt the cheapest transport (T0: plain stdlib HTTP) and detect
whether a WAF/challenge blocked us. The share of `blocked` hosts is the *upper
bound* on the browser-required fraction and is what gates real dollar spend
(self-host VM vs rent an unblocker). Escalation to T1 (cookie-lift) / T2 (full
browser) via waf_session lives behind the optional `live` extra and is layered on
after this free pass tells us how many domains actually need it.

Result -> resolve/TierCache (data/tier_cache.jsonl). Resumable: probed hosts skip.
"""

from __future__ import annotations

import re
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..archive.wayback import host_of, load_hosts
from ..config import load_settings, resolve_path
from ..core import RateLimiter, fetch
from ..resolve.tier_cache import TierCache

# Signatures that mean "a bot wall answered, not the real site."
_CHALLENGE = re.compile(
    r"just a moment|cf-chl|checking your browser|attention required|"
    r"access denied|request unsuccessful|incapsula|imperva|"
    r"captcha|are you a robot|enable javascript to continue", re.I)


def probe_host(host: str, *, limiter: RateLimiter | None = None,
               timeout: int = 20) -> dict:
    """T0 attempt. Returns {tier, status, signal}."""
    url = f"https://{host}/"
    if limiter:
        limiter.wait()
    try:
        body = fetch(url, tries=1, timeout=timeout).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429, 503):
            return {"tier": "blocked", "status": exc.code, "signal": "http_status"}
        # 4xx/5xx that isn't a classic WAF code — reachable but odd; T0 still "works".
        return {"tier": "T0", "status": exc.code, "signal": "http_error_ok"}
    except Exception as exc:  # noqa: BLE001 — DNS/TLS/timeout: unreachable via T0
        return {"tier": "blocked", "status": 0, "signal": f"neterr:{type(exc).__name__}"}
    if _CHALLENGE.search(body[:8000]):
        return {"tier": "blocked", "status": 200, "signal": "challenge_page"}
    return {"tier": "T0", "status": 200, "signal": "ok"}


def run(*, limit: int | None = None, workers: int | None = None) -> dict:
    cfg = load_settings()
    workers = workers or cfg["probe"]["workers"]
    inventory = resolve_path(cfg["paths"]["inventory_csv"])
    cache = TierCache()

    hosts = [h for h in load_hosts(inventory, limit=limit) if not cache.has(h)]
    print(f"[*] probing {len(hosts)} hosts ({len(cache._map)} cached); "
          f"{workers} workers")
    limiter = RateLimiter(cfg["wayback"]["per_host_rpm"])

    def work(host: str) -> None:
        res = probe_host(host, limiter=limiter)
        cache.set(host, res["tier"], status=res["status"], signal=res["signal"])
        marker = "OK " if res["tier"] == "T0" else "BLK"
        print(f"  [{marker}] {host:<38} {res['signal']}")

    if hosts:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for _ in as_completed([pool.submit(work, h) for h in hosts]):
                pass

    hist = cache.histogram()
    total = sum(hist.values()) or 1
    blocked = hist.get("blocked", 0)
    print(f"\n[tier histogram] {hist}")
    print(f"[browser-required upper bound] {blocked}/{total} "
          f"= {100 * blocked / total:.1f}%  (vs the ~10% estimate)")
    return {"histogram": hist, "blocked_pct": 100 * blocked / total}
