"""Google Programmable Search (Custom Search JSON API) -> employer/news context.

This is a MARKETING-CONTEXT source for brief section 2 (Local Signal Read) — it
surfaces local employer/sector signal to inform outreach prose. Per §4.3 it is
NEVER a market event with investment meaning, and it is NOT one of the locked
scorer signals (Wealth/Demand/Saturation = Census/Trends/FINRA). It does not
feed scoring.

Reads GOOGLE_CSE_KEY (secret) and GOOGLE_CSE_CX (the search engine id; not
secret — defaults to the project's cx). Cached + freshness-stamped, and it
degrades gracefully (§4.3): no key / network / quota error -> an explicit
unavailable result, never fabricated snippets.
"""

from __future__ import annotations

import os
from typing import Optional

from .cache import FreshnessMeta, SignalResult, read_cache, write_cache

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

SOURCE = "google_cse"
CSE_TTL_DAYS = 14
DEFAULT_CX = "13d04e872f34645c6"  # Carson Local Market Scorer engine (cx is not secret)
_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


def _cx() -> str:
    return os.environ.get("GOOGLE_CSE_CX") or DEFAULT_CX


def fetch_results(
    query: str,
    *,
    num: int = 5,
    max_age_days: Optional[int] = CSE_TTL_DAYS,
    timeout: float = 8.0,
) -> SignalResult:
    """Return up to `num` web results (title/snippet/link) for `query`.

    SignalResult.value is a list of dicts; on any failure returns an explicit
    unavailable result with a plain-language note.
    """
    if not query or not query.strip():
        return SignalResult.unavailable(SOURCE, "No query supplied for web context.")

    params = {"q": query.strip(), "cx": _cx(), "num": max(1, min(num, 10))}
    cached = read_cache(SOURCE, params, max_age_days)
    if cached is not None:
        return _result_from_payload(cached)

    key = os.environ.get("GOOGLE_CSE_KEY")
    if not key:
        return SignalResult.unavailable(
            SOURCE, "GOOGLE_CSE_KEY not set — web employer/news context skipped.")
    if requests is None:
        return SignalResult.unavailable(SOURCE, "requests not installed.")

    try:
        resp = requests.get(_ENDPOINT, params={**params, "key": key}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 - degrade gracefully (§4.3)
        return SignalResult.unavailable(
            SOURCE, f"Custom Search unavailable for {query!r}: {type(exc).__name__}.")

    items = [
        {"title": it.get("title"), "snippet": it.get("snippet"),
         "link": it.get("link"), "source": it.get("displayLink")}
        for it in data.get("items", [])
    ]
    if not items:
        return SignalResult.unavailable(
            SOURCE, f"No web results for {query!r} (thin/over-narrow query).")

    payload = {"items": items, "query": query.strip()}
    write_cache(SOURCE, params, payload)
    return _result_from_payload(payload)


def employer_context_snippets(
    *, county: Optional[str] = None, cbsa: Optional[str] = None,
    place: Optional[str] = None, num: int = 5
) -> list[str]:
    """Convenience: plain snippet strings about local employers/sectors.

    `place` (e.g. "Omaha, NE") overrides; otherwise uses cbsa or county.
    Returns [] when geography is missing or the source is unavailable — callers
    treat empty as "no web context" and narrow accordingly (§4.3).
    """
    where = place or cbsa or county
    if not where:
        return []
    res = fetch_results(f"largest employers and major industries in {where}", num=num)
    if not res.available:
        return []
    return [f"{i['snippet']} ({i['source']})" for i in res.value if i.get("snippet")]


def _result_from_payload(payload: dict) -> SignalResult:
    meta = FreshnessMeta(
        source=SOURCE, ttl_days=CSE_TTL_DAYS,
        note=("Google Programmable Search results — marketing/outreach context "
              "only, not a market event (§4.3)."),
    ).stamp_now()
    return SignalResult(
        source=SOURCE, available=True, value=payload["items"], unit="results",
        meta=meta, note=f"{len(payload['items'])} web results for "
                        f"{payload.get('query','query')!r}.")
