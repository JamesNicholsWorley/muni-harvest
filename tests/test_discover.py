"""Offline unit tests for the discovery model, storage, and HTML link extraction."""

from muni_harvest.discover.htmllinks import extract
from muni_harvest.discover.model import (
    classify_doc, is_file_url, is_storage_host, same_site, urlkey,
)
from muni_harvest.discover.storage import resolve_download


def test_urlkey_normalizes():
    assert urlkey("https://www.weston.gov/Foo/") == "weston.gov/Foo"
    assert urlkey("http://weston.gov/a#frag") == "weston.gov/a"
    assert urlkey("https://weston.gov/doc?id=5") == "weston.gov/doc?id=5"


def test_same_site_allows_subdomains_not_others():
    assert same_site("electionarchive.somervillema.gov", "somervillema.gov")
    assert same_site("www.weston.gov", "weston.gov")
    assert not same_site("facebook.com", "weston.gov")


def test_file_and_storage_detection():
    assert is_file_url("https://weston.gov/minutes.pdf")
    assert is_file_url("https://drive.google.com/file/d/ABC123/view")  # no ext, storage
    assert is_storage_host("bucket.s3.amazonaws.com")
    assert not is_file_url("https://weston.gov/boards/zba")


def test_drive_resolves_to_download_url():
    dl, host = resolve_download("https://drive.google.com/file/d/ABC123/view")
    assert dl == "https://drive.google.com/uc?export=download&id=ABC123"
    assert host == "drive.google.com"
    assert resolve_download("https://weston.gov/x.pdf")[1] == ""


def test_classify_uses_url_and_anchor():
    assert classify_doc("/x.pdf", "2023 Select Board Agenda") == "agenda"
    assert classify_doc("/minutes-2023.pdf") == "minutes"
    assert classify_doc("/atm-warrant.pdf") in ("warrant", "budget")
    assert classify_doc("/random.pdf") == "other"


def test_html_link_and_anchor_extraction():
    html = ('<title>ZBA</title><nav class="breadcrumbs">Home > Boards</nav>'
            '<a href="/minutes.pdf">April Minutes</a><a href="mailto:x@y.z">mail</a>')
    p = extract(html)
    hrefs = dict(p.links)
    assert hrefs["/minutes.pdf"] == "April Minutes"
    assert p.title == "ZBA"
    assert "Boards" in p.breadcrumb
