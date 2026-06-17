"""Phase 2 — data layer degrades gracefully (§4.3): no fabrication, ever."""

import os

from lnos import fred, trends, competition
from lnos.cache import SignalResult


def test_unavailable_result_is_explicit_and_empty():
    r = SignalResult.unavailable("x", "nope")
    assert r.available is False and r.value is None and r.note == "nope"


def test_fred_without_key_is_unavailable_not_fabricated(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    r = fred.fetch_series_latest("LAUCN310550000000003", max_age_days=None)
    assert r.available is False and r.value is None
    assert "FRED_API_KEY" in r.note


def test_fred_county_series_id_format():
    assert fred.county_unemployment_series("31", "055") == "LAUCN310550000000003A"


def test_trends_empty_keywords_unavailable():
    r = trends.fetch_interest([], max_age_days=None)
    assert r.available is False and r.value is None


def test_competition_empty_query_unavailable():
    r = competition.fetch_competitor_count("", max_age_days=None)
    assert r.available is False and r.value is None
