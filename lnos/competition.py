"""FINRA BrokerCheck -> Saturation raw signal (§4.0, §4.3).

Returns a raw count of advisory firms / registered representatives near a
location as the Saturation observation, with freshness metadata + caching.
The mapping of this raw count into a Saturation sub-score (and whether more
competitors raises or lowers Opp) is §2.1 methodology — done in scoring.py.

NOTE ON SOURCE: FINRA BrokerCheck exposes a public search endpoint that is not
a formally documented/stable API. We treat it as best-effort: on any failure
we degrade gracefully to an explicit unavailable result (§4.3) and the snapshot
narrows the claim rather than fabricating a count. Respect FINRA terms of use;
keep request volume low (results are cached).
"""

from __future__ import annotations

from typing import Optional

from .cache import FreshnessMeta, SignalResult, read_cache, write_cache

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

SOURCE = "finra_brokercheck"
SATURATION_TTL_DAYS = 30
_FIRM_SEARCH = "https://api.brokercheck.finra.org/search/firm"
_INDIVIDUAL_SEARCH = "https://api.brokercheck.finra.org/search/individual"


def fetch_competitor_count(
    query: str,
    *,
    kind: str = "firm",
    max_age_days: Optional[int] = SATURATION_TTL_DAYS,
    timeout: float = 8.0,
) -> SignalResult:
    """Raw count of BrokerCheck matches for `query` (e.g. a city/ZIP/region).

    kind: "firm" or "individual". Returns a SignalResult whose value is the
    total match count (raw Saturation observation).
    """
    if kind not in ("firm", "individual"):
        raise ValueError("kind must be 'firm' or 'individual'")
    if not query or not query.strip():
        return SignalResult.unavailable(
            SOURCE, "No location query supplied for Saturation signal.")

    params = {"query": query.strip(), "kind": kind}
    cached = read_cache(SOURCE, params, max_age_days)
    if cached is not None:
        return _result_from_payload(cached)

    if requests is None:
        return SignalResult.unavailable(
            SOURCE, "requests not installed — cannot query BrokerCheck.")

    url = _FIRM_SEARCH if kind == "firm" else _INDIVIDUAL_SEARCH
    q = {"query": query.strip(), "filter": "active=true", "includePrevious": "false",
         "hl": "true", "nrows": "12", "start": "0", "r": "25", "wt": "json"}
    try:
        resp = requests.get(url, params=q, timeout=timeout,
                            headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 - degrade gracefully (§4.3)
        return SignalResult.unavailable(
            SOURCE, f"BrokerCheck unavailable for '{query}' ({kind}): "
                    f"{type(exc).__name__}. Saturation will be narrowed.")

    total = _extract_total(data)
    if total is None:
        return SignalResult.unavailable(
            SOURCE, f"BrokerCheck returned an unexpected shape for '{query}'.")

    payload = {"value": total, "query": query.strip(), "kind": kind}
    write_cache(SOURCE, params, payload)
    return _result_from_payload(payload)


def _extract_total(data: dict) -> Optional[int]:
    """Pull the total hit count from BrokerCheck's (Solr-style) response."""
    if not isinstance(data, dict):
        return None
    hits = data.get("hits")
    if isinstance(hits, dict) and "total" in hits:
        try:
            return int(hits["total"])
        except (TypeError, ValueError):
            return None
    # Fallback for alternate response shapes.
    resp = data.get("response")
    if isinstance(resp, dict) and "numFound" in resp:
        try:
            return int(resp["numFound"])
        except (TypeError, ValueError):
            return None
    return None


def _result_from_payload(payload: dict) -> SignalResult:
    meta = FreshnessMeta(
        source=SOURCE, ttl_days=SATURATION_TTL_DAYS,
        note=("FINRA BrokerCheck active-match count (best-effort public search). "
              "Raw competitor density — sub-score mapping is §2.1."),
    ).stamp_now()
    return SignalResult(
        source=SOURCE, available=True, value=payload["value"], unit="count",
        meta=meta,
        note=f"{payload['value']} active {payload['kind']} matches for "
             f"'{payload['query']}' (BrokerCheck).",
    )
