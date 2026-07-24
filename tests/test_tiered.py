"""Offline tests for the tier classifiers (no selenium needed — imports are lazy)."""

from muni_harvest.fetchers.tiered import _clean, _dom_clean


def test_clean_requires_200_and_no_challenge():
    assert _clean(200, "<html>Welcome to the Town of Weston</html>")
    assert not _clean(403, "forbidden")
    assert not _clean(200, "Just a moment... checking your browser")


def test_dom_clean_is_size_aware():
    # A big rendered page is the real site even if it mentions 'captcha' somewhere.
    big = "x" * 20000 + "recaptcha contact form"
    assert _dom_clean(big)
    # A tiny challenge interstitial is not clean.
    assert not _dom_clean("Just a moment...")
    # A small-but-ambiguous page with a challenge marker fails.
    assert not _dom_clean("<html>" + "a" * 2000 + " enable javascript to continue</html>")
    assert not _dom_clean("")
