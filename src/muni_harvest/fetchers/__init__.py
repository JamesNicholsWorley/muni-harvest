"""Tiered live fetcher + BrowserPool (T0/T1/T2).

DEFERRED until the tier-probe sizes the browser-required fraction (spend gate).
Will wrap Exploratory/WaterCosts/sources/_common/waf_session.py:
  T0  threaded stdlib requests (wide, politeness-bound)
  T1  mint_session() cookie-lift (one browser boot per domain)
  T2  fetch_in_browser()/full render, leased from a persistent BrowserPool
      of 2-6 warm drivers (replaces the fatal boot-a-browser-per-site pattern).
"""
