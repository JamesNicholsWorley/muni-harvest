#!/usr/bin/env python3
"""WAF-bypass helper — VENDORED from Exploratory/WaterCosts/sources/_common/waf_session.py.

Kept self-contained so muni-harvest deploys to the VM without the WaterCosts tree.
Three strategies, cheapest first:
  1. mint_session(url)     -> requests.Session with the browser's cookies (fast path).
  2. fetch_in_browser(d,u) -> (status, text) via in-browser fetch (same origin).
  3. fetch_bytes(d,u)      -> (status, bytes) via in-browser fetch + base64 (WAF'd PDFs).

Requires the `live` extra (selenium + requests). Chrome must be installed; Selenium
Manager auto-provisions the matching driver.
"""
from __future__ import annotations

import base64
import time

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
SEP = "~~||~~"


def build_driver(headful=False, perf=False, stealth=False):
    opts = Options()
    if not headful:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1500,1100")
    opts.add_argument(f"--user-agent={UA}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    if stealth:
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument("--disable-infobars")
        opts.add_argument("--start-maximized")
    if perf:
        opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    d = webdriver.Chrome(options=opts)
    d.set_page_load_timeout(90)
    if stealth:
        try:
            d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source":
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                "window.chrome={runtime:{}};"
                "Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});"
                "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});"})
        except Exception:
            pass
    return d


def mint_session(url, wait=6, headful=False):
    d = build_driver(headful)
    try:
        d.get(url)
        time.sleep(wait)
        cookies = d.get_cookies()
    finally:
        d.quit()
    s = requests.Session()
    s.headers["User-Agent"] = UA
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain"),
                          path=c.get("path", "/"))
        except Exception:
            pass
    return s


def fetch_in_browser(driver, url):
    """(status, text) via in-browser fetch (same origin)."""
    js = ("var cb=arguments[arguments.length-1];"
          "fetch(arguments[0]).then(r=>r.text().then(t=>cb(r.status+'%s'+t)))"
          ".catch(e=>cb('0%s'+e));" % (SEP, SEP))
    driver.set_script_timeout(90)
    res = driver.execute_async_script(js, url)
    status, _, text = res.partition(SEP)
    return (int(status) if status.isdigit() else 0), text


def fetch_bytes(driver, url):
    """(status, bytes) via in-browser fetch + base64 (for WAF-protected PDFs)."""
    js = ("var cb=arguments[arguments.length-1];"
          "fetch(arguments[0]).then(r=>r.blob().then(b=>{var fr=new FileReader();"
          "fr.onloadend=function(){cb(r.status+'%s'+fr.result)};"
          "fr.readAsDataURL(b)})).catch(e=>cb('0%s'+e));" % (SEP, SEP))
    driver.set_script_timeout(120)
    res = driver.execute_async_script(js, url)
    status, _, dataurl = res.partition(SEP)
    if dataurl.startswith("data:") and "," in dataurl:
        return (int(status) if status.isdigit() else 200), \
            base64.b64decode(dataurl.split(",", 1)[1])
    return (int(status) if status.isdigit() else 0), b""
