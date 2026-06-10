"""FRED -> current-data layer for the brief snapshot (§4 D4, §4.2 §4.3).

FRED is the reliable spine of the Local Market Snapshot. This module fetches
the latest observation for a FRED series (county unemployment via LAUS, house
price index, building permits, etc.) with caching + freshness, degrading
gracefully when the key/network/series is unavailable.

Raw observations only — no interpretation here. Section 1 of the brief
presents 3–5 of these cleanly with NO interpretation (§4.2).
"""

from __future__ import annotations

import os
from typing import Optional

from .cache import FreshnessMeta, SignalResult, read_cache, write_cache

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

SOURCE = "fred"
FRED_TTL_DAYS = 7  # "current" layer — refresh weekly
_BASE = "https://api.stlouisfed.org/fred/series/observations"


def county_unemployment_series(state_fips: str, county_fips: str) -> str:
    """LAUS county unemployment RATE series id.

    Format: LAUCN{state2}{county3}0000000003  (measure 03 = unemployment rate).
    """
    return f"LAUCN{state_fips:0>2}{county_fips:0>3}0000000003"


def fetch_series_latest(
    series_id: str,
    *,
    units: Optional[str] = None,
    max_age_days: Optional[int] = FRED_TTL_DAYS,
    timeout: float = 8.0,
) -> SignalResult:
    """Fetch the most recent non-missing observation for a FRED series."""
    params = {"series_id": series_id}
    cached = read_cache(SOURCE, params, max_age_days)
    if cached is not None:
        return _result_from_payload(cached, units)

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        return SignalResult.unavailable(
            SOURCE, f"FRED_API_KEY not set — cannot fetch series {series_id}. "
                    f"Snapshot will narrow or omit this metric.")
    if requests is None:
        return SignalResult.unavailable(
            SOURCE, "requests not installed — cannot fetch FRED.")

    q = {"series_id": series_id, "api_key": api_key, "file_type": "json",
         "sort_order": "desc", "limit": 1}
    try:
        resp = requests.get(_BASE, params=q, timeout=timeout)
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
    except Exception as exc:  # noqa: BLE001 - degrade gracefully (§4.3)
        return SignalResult.unavailable(
            SOURCE, f"FRED series {series_id} unavailable: {type(exc).__name__}.")

    obs = [o for o in obs if o.get("value") not in (None, ".", "")]
    if not obs:
        return SignalResult.unavailable(
            SOURCE, f"FRED series {series_id} returned no usable observations.")

    latest = obs[0]
    try:
        value = float(latest["value"])
    except (KeyError, ValueError):
        return SignalResult.unavailable(
            SOURCE, f"FRED series {series_id} latest value not numeric.")

    payload = {"value": value, "date": latest.get("date"), "series_id": series_id}
    write_cache(SOURCE, params, payload)
    return _result_from_payload(payload, units)


def _result_from_payload(payload: dict, units: Optional[str]) -> SignalResult:
    meta = FreshnessMeta(
        source=SOURCE, as_of=payload.get("date"), ttl_days=FRED_TTL_DAYS,
        note=f"FRED series {payload.get('series_id','')} latest observation.",
    ).stamp_now()
    return SignalResult(
        source=SOURCE, available=True, value=payload["value"], unit=units,
        meta=meta,
        note=f"{payload.get('series_id','FRED series')} = {payload['value']} "
             f"({payload.get('date','')}).",
    )
