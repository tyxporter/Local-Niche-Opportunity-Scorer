"""Google Custom Search — marketing context, degrades gracefully (§4.3)."""

from lnos import customsearch


def test_no_key_is_unavailable_not_fabricated(monkeypatch):
    monkeypatch.delenv("GOOGLE_CSE_KEY", raising=False)
    r = customsearch.fetch_results("largest employers in Omaha", max_age_days=None)
    assert r.available is False and r.value is None
    assert "GOOGLE_CSE_KEY" in r.note


def test_empty_query_unavailable():
    r = customsearch.fetch_results("  ", max_age_days=None)
    assert r.available is False


def test_employer_snippets_empty_without_geography(monkeypatch):
    monkeypatch.delenv("GOOGLE_CSE_KEY", raising=False)
    assert customsearch.employer_context_snippets(county=None, cbsa=None) == []
    # With geography but no key, still empty (never fabricated).
    assert customsearch.employer_context_snippets(
        county="Douglas County", cbsa="Omaha-Council Bluffs, NE-IA") == []


def test_cx_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("GOOGLE_CSE_CX", raising=False)
    assert customsearch._cx() == customsearch.DEFAULT_CX
