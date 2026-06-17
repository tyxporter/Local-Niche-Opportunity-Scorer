"""Census ACS -> Wealth raw signal (§4.0, §4.3).

ACS is the "market structure" layer: annual and LAGGED. We frame it that way
everywhere and NEVER as a real-time signal (§4.3). This module fetches raw ACS
observations (headline: median household income) with freshness metadata and
caching. It does NOT normalize into a Wealth sub-score — normalization and the
combination into Opp is §2.1 methodology and lives in scoring.py.

Census API works without a key at low volume; CENSUS_API_KEY lifts rate limits.
Geography is keyed by FIPS (state + county). Name->FIPS resolution is a
separate concern (firm geography, open item F2); pass FIPS in explicitly.
"""

from __future__ import annotations

import os
from typing import Optional

from .cache import FreshnessMeta, SignalResult, read_cache, write_cache

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

SOURCE = "census_acs"
# Most recent ACS 5-year vintage available as of this build. ACS lags ~1–2 yrs;
# the loader records the actual vintage it pulled and flags `lagged=True`.
DEFAULT_ACS_YEAR = 2023
ACS_TTL_DAYS = 180  # annual data; a long TTL is fine

# Headline wealth variable: median household income (past 12 months).
VAR_MEDIAN_HOUSEHOLD_INCOME = "B19013_001E"


def fetch_median_household_income(
    state_fips: str,
    county_fips: str,
    *,
    year: int = DEFAULT_ACS_YEAR,
    max_age_days: Optional[int] = ACS_TTL_DAYS,
    timeout: float = 8.0,
) -> SignalResult:
    """Fetch county median household income (raw USD) from ACS 5-year.

    Returns a SignalResult; on any failure/thinness returns an explicit
    `unavailable` result with a plain-language note (never a fabricated value).
    """
    params = {"var": VAR_MEDIAN_HOUSEHOLD_INCOME, "state": state_fips,
              "county": county_fips, "year": year}

    cached = read_cache(SOURCE, params, max_age_days)
    if cached is not None:
        return _result_from_payload(cached, year)

    if requests is None:
        return SignalResult.unavailable(
            SOURCE, "requests not installed — cannot fetch ACS; install requests.",
            lagged=True)

    url = f"https://api.census.gov/data/{year}/acs/acs5"
    q = {"get": f"NAME,{VAR_MEDIAN_HOUSEHOLD_INCOME}",
         "for": f"county:{county_fips}", "in": f"state:{state_fips}"}
    key = os.environ.get("CENSUS_API_KEY")
    if key:
        q["key"] = key

    try:
        resp = requests.get(url, params=q, timeout=timeout)
        resp.raise_for_status()
        # Census returns an HTML page (HTTP 200) when the key is missing/invalid.
        if "json" not in resp.headers.get("content-type", "").lower():
            reason = ("CENSUS_API_KEY required (the ACS API no longer serves "
                      "keyless requests)" if "Missing Key" in resp.text
                      else "non-JSON response")
            return SignalResult.unavailable(
                SOURCE, f"ACS {reason} for state {state_fips}/county {county_fips} "
                        f"(year {year}).", as_of=str(year), lagged=True)
        rows = resp.json()
    except Exception as exc:  # noqa: BLE001 - degrade gracefully (§4.3)
        return SignalResult.unavailable(
            SOURCE,
            f"ACS unavailable for state {state_fips}/county {county_fips} "
            f"(year {year}): {type(exc).__name__}. Snapshot will narrow this claim.",
            as_of=str(year), lagged=True)

    # rows = [["NAME","B19013_001E","state","county"], [<name>, <value>, ...]]
    if not rows or len(rows) < 2:
        return SignalResult.unavailable(
            SOURCE, f"ACS returned no rows for {state_fips}/{county_fips}.",
            as_of=str(year), lagged=True)

    header, data = rows[0], rows[1]
    record = dict(zip(header, data))
    raw = record.get(VAR_MEDIAN_HOUSEHOLD_INCOME)
    name = record.get("NAME", "")
    # ACS uses negative sentinels (e.g. -666666666) for unavailable estimates.
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = None
    if value is None or value < 0:
        payload = {"value": None, "name": name, "year": year, "thin": True}
        write_cache(SOURCE, params, payload)
        return SignalResult.unavailable(
            SOURCE, f"ACS median household income estimate not available for "
                    f"{name or 'this county'} (year {year}).",
            as_of=str(year), lagged=True)

    payload = {"value": value, "name": name, "year": year, "thin": False}
    write_cache(SOURCE, params, payload)
    return _result_from_payload(payload, year)


def _result_from_payload(payload: dict, year: int) -> SignalResult:
    if payload.get("value") is None:
        return SignalResult.unavailable(
            SOURCE, f"ACS estimate not available ({payload.get('name','')}, {year}).",
            as_of=str(payload.get("year", year)), lagged=True)
    meta = FreshnessMeta(
        source=SOURCE,
        as_of=str(payload.get("year", year)),
        ttl_days=ACS_TTL_DAYS,
        lagged=True,
        note=("ACS 5-year estimate — market-structure framing only; lagged, "
              "not a real-time signal (§4.3)."),
    ).stamp_now()
    return SignalResult(
        source=SOURCE, available=True, value=payload["value"], unit="USD",
        meta=meta,
        note=f"Median household income, {payload.get('name','county')} (ACS {year}).",
    )
