"""CivicPlus DocumentCenter enumerator (227 towns) — the big JS-CMS backdoor.

Modern DocumentCenter is a React SPA whose files are served as
/ImageRepository/Document?documentID={id} (NOT /DocumentCenter/View), so a link-graph
crawl and Wayback both miss them. Reverse-engineered backdoor (plain requests, no
browser):
  1. GET /DocumentCenter          -> session cookies
  2. GET /antiforgery             -> CSRF token
  3. POST /admin/DocumentCenter/Home/_AjaxLoadingReact?type=1
        body {"value":fid,"selectedFolder":fid,...} + RequestVerificationToken header
        -> JSON tree children: {Text, Value, LoadOnDemand}
     LoadOnDemand=true  -> folder (recurse)
     LoadOnDemand=false -> document (Value=documentID -> ImageRepository URL)

The folder path (e.g. "Agendas / Board of Appeals / 2015") is carried as the anchor
so the existing classifier derives board+doctype+date.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import urllib.request

from ..archive.wayback import load_hosts, load_hosts_file
from ..config import data_dir, load_settings, resolve_path
from ..core import RateLimiter, append_jsonl
from .pipeline import host_to_municipality

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _session(host: str, timeout: int = 30):
    """Return (opener, token) or (None, None) if not a CivicPlus DocumentCenter."""
    import http.cookiejar
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [("User-Agent", _UA)]
    try:
        opener.open(f"https://{host}/DocumentCenter", timeout=timeout).read()
        af = opener.open(f"https://{host}/antiforgery", timeout=timeout).read()
        token = json.loads(af.decode("utf-8", "replace")).get("token")
    except Exception:  # noqa: BLE001
        return None, None
    return (opener, token) if token else (None, None)


def _children(opener, host: str, token: str, fid, timeout: int = 30) -> list[dict]:
    body = json.dumps({"value": str(fid), "expandTree": False, "loadSource": 7,
                       "selectedFolder": int(fid)}).encode()
    req = urllib.request.Request(
        f"https://{host}/admin/DocumentCenter/Home/_AjaxLoadingReact?type=1",
        data=body, method="POST",
        headers={"User-Agent": _UA, "Content-Type": "application/json",
                 "RequestVerificationToken": token,
                 "X-Requested-With": "XMLHttpRequest"})
    try:
        raw = opener.open(req, timeout=timeout).read().decode("utf-8", "replace")
        return json.loads(raw).get("Data", []) or []
    except Exception:  # noqa: BLE001
        return []


def harvest_town(host: str, *, limiter=None, max_nodes: int = 8000,
                 max_depth: int = 8) -> list[dict]:
    """Recursive tree walk -> document records with folder-path breadcrumbs."""
    opener, token = _session(host)
    if not opener:
        return []
    docs: list[dict] = []
    seen_folders: set[str] = set()
    # stack of (folder_id, path_list)
    stack = [("1", [])]
    visited = 0
    while stack and visited < max_nodes:
        fid, path = stack.pop()
        if fid in seen_folders or len(path) > max_depth:
            continue
        seen_folders.add(fid)
        if limiter:
            limiter.wait()
        for node in _children(opener, host, token, fid):
            visited += 1
            text = (node.get("Text") or "").strip()
            val = str(node.get("Value") or "")
            if node.get("LoadOnDemand"):                      # folder
                stack.append((val, path + [text]))
            elif val.isdigit():                                # document
                docs.append({"documentID": val, "title": text,
                             "breadcrumb": " / ".join(path)})
    return docs


def _target_hosts(hosts_file):
    cfg = load_settings()
    inv = resolve_path(cfg["paths"]["inventory_csv"])
    if hosts_file:
        hosts = load_hosts_file(resolve_path(hosts_file))
    else:
        hosts = load_hosts(inv)
    muni = host_to_municipality(inv) if inv.exists() else {}
    return hosts, muni


def run(*, workers: int = 8, hosts_file: str | None = None,
        shard: str | None = None) -> dict:
    hosts, muni = _target_hosts(hosts_file)
    if shard:
        from ..archive.wayback import shard_hosts
        hosts = shard_hosts(hosts, shard)
    out_dir = data_dir() / "discover"
    nodes_path = out_dir / "nodes.jsonl"
    done_path = out_dir / "documentcenter_done.txt"
    out_dir.mkdir(parents=True, exist_ok=True)
    done = set(done_path.read_text(encoding="utf-8").split()) if done_path.exists() else set()
    todo = [h for h in hosts if h not in done]
    print(f"[*] DocumentCenter enumerate: {len(todo)} hosts ({len(done)} done); {workers} workers")

    limiter = RateLimiter(load_settings()["wayback"]["per_host_rpm"])
    lock = threading.Lock()
    totals = {"towns_with_dc": 0, "docs": 0}

    def work(host: str):
        docs = harvest_town(host, limiter=limiter)
        rows = []
        for d in docs:
            url = f"https://{host}/ImageRepository/Document?documentID={d['documentID']}"
            rows.append({"seed_host": host, "municipality": muni.get(host, ""),
                         "url": url, "urlkey": url.split("//", 1)[-1], "kind": "file",
                         "mimetype": "application/pdf", "doctype": "",
                         # folder path + title -> classifier derives board/doctype/date
                         "anchor": f"{d['breadcrumb']} {d['title']}"[:200],
                         "depth": 2, "parent_url": f"https://{host}/DocumentCenter",
                         "breadcrumb": d["breadcrumb"][:300],
                         "discovered_via": "documentcenter", "storage_host": ""})
        with lock:
            if rows:
                append_jsonl(nodes_path, rows)
            with done_path.open("a", encoding="utf-8") as fh:
                fh.write(host + "\n")
            if rows:
                totals["towns_with_dc"] += 1
                totals["docs"] += len(rows)
        if rows:
            print(f"  [OK] {host:<32} {len(rows):>5} documents")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for _ in as_completed([ex.submit(work, h) for h in todo]):
            pass
    print(f"\n[done] DocumentCenter: {totals['towns_with_dc']} towns, "
          f"{totals['docs']} documents -> {nodes_path}")
    return totals
