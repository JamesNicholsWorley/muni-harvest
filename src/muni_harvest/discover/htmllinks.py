"""Stdlib HTML link extraction (keeps the discovery tier dependency-free).

Pulls <a href> links with their anchor text, the page <title>, and a best-effort
breadcrumb trail (elements whose class/id contains 'breadcrumb'), so the crawler
can record where each link sits in the site's navigation.
"""

from __future__ import annotations

from html.parser import HTMLParser


class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []   # (href, anchor_text)
        self.title: str = ""
        self.breadcrumb: str = ""
        self._href: str | None = None
        self._text: list[str] = []
        self._in_title = False
        self._crumb_depth = 0          # >0 while inside a breadcrumb container
        self._crumb_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "title":
            self._in_title = True
        marker = f"{d.get('class', '')} {d.get('id', '')}".lower()
        if "breadcrumb" in marker:
            self._crumb_depth += 1
        if tag == "a" and d.get("href"):
            self._href = d["href"]
            self._text = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []
        if self._crumb_depth > 0 and tag in ("nav", "ol", "ul", "div", "p"):
            # Close the breadcrumb region on the first structural close.
            self._crumb_depth -= 1
            if self._crumb_depth == 0 and not self.breadcrumb:
                self.breadcrumb = " > ".join(
                    t for t in (s.strip() for s in self._crumb_text) if t)

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._href is not None:
            self._text.append(data)
        if self._crumb_depth > 0:
            self._crumb_text.append(data)


def extract(html: str) -> LinkExtractor:
    p = LinkExtractor()
    try:
        p.feed(html)
    except Exception:  # noqa: BLE001 — malformed HTML shouldn't kill a crawl
        pass
    p.title = " ".join(p.title.split())
    return p
