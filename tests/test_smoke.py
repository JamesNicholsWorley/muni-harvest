"""Fast, offline smoke tests — no network. Validate the core plumbing."""

from muni_harvest.archive.wayback import classify, host_of, valid_host
from muni_harvest.core import RateLimiter, slugify
from muni_harvest.probe.tier_probe import _CHALLENGE


def test_host_of_strips_scheme_and_www():
    assert host_of("https://www.boston.gov/elections") == "boston.gov"
    assert host_of("westonma.gov") == "westonma.gov"


def test_classify_doctypes():
    assert classify("/2023-election-results.pdf") == "election"
    assert classify("/zba/variance-minutes.pdf") in ("minutes", "planning")
    assert classify("/random-file.pdf") == "other"


def test_rate_limiter_disabled_when_zero():
    rl = RateLimiter(0)
    rl.wait()  # must not raise / must not sleep
    assert rl.interval == 0.0


def test_challenge_signature_matches_cloudflare():
    assert _CHALLENGE.search("Just a moment... checking your browser")
    assert not _CHALLENGE.search("Welcome to the Town of Weston")


def test_slugify():
    assert slugify("Town of Weston, MA!") == "town-of-weston-ma"


def test_policy_applies_overrides_and_excludes():
    from muni_harvest.archive.wayback import _apply_policy
    ov = {"seekonkma.gov": "seekonk-ma.gov"}
    ex = {"wpri.com"}
    assert _apply_policy("seekonkma.gov", ov, ex) == "seekonk-ma.gov"  # corrected
    assert _apply_policy("wpri.com", ov, ex) is None                    # news excluded
    assert _apply_policy("weston.gov", ov, ex) == "weston.gov"          # untouched
    assert _apply_policy("results.xlsx", ov, ex) is None                # invalid


def test_valid_host_rejects_junk():
    assert valid_host("weston.gov")
    assert valid_host("town.barnstable.ma.us")
    assert not valid_host(r"c:\users\owner\downloads\results.xlsx")  # local path
    assert not valid_host("results.xlsx")   # bare filename, no domain
    assert not valid_host("localhost")      # no dot
