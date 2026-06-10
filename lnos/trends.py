"""Google Trends -> Demand raw signal (§4.0, §4.3).

Fetches search-interest for advisory-relevant query terms in a geography and
returns a raw interest reading (0–100 index, Google's own scale) with freshness
metadata + caching. Normalization into a Demand sub-score and the combination
into Opp is §2.1 methodology — done in scoring.py, never here.

pytrends is an OPTIONAL dependency. If it is absent or the unofficial endpoint
fails, this module degrades gracefully to an explicit unavailable result
(§4.3) rather than crashing the package.
"""

from __future__ import annotations

from statistics import mean
from typing import Optional, Sequence

from .cache import FreshnessMeta, SignalResult, read_cache, write_cache

try:
    from pytrends.request import TrendReq
except Exception:  # noqa: BLE001 - optional dep; any import issue -> degrade
    TrendReq = None

SOURCE = "google_trends"
TRENDS_TTL_DAYS = 3  # demand is the most time-sensitive signal


def fetch_interest(
    keywords: Sequence[str],
    *,
    geo: str = "US",
    timeframe: str = "today 12-m",
    max_age_days: Optional[int] = TRENDS_TTL_DAYS,
) -> SignalResult:
    """Average recent search interest for `keywords` in `geo`.

    `geo` is a Google Trends geo code (e.g. "US", "US-NE", or a metro DMA id).
    Returns a raw 0–100 index (Google's scale). Thin/flat series are reported
    honestly rather than smoothed.
    """
    kws = [k for k in keywords if k and k.strip()]
    if not kws:
        return SignalResult.unavailable(
            SOURCE, "No keywords supplied for Demand signal.")

    params = {"keywords": sorted(kws), "geo": geo, "timeframe": timeframe}
    cached = read_cache(SOURCE, params, max_age_days)
    if cached is not None:
        return _result_from_payload(cached, geo)

    if TrendReq is None:
        return SignalResult.unavailable(
            SOURCE, "pytrends not installed — cannot fetch Google Trends; "
                    "Demand will be narrowed/omitted for this market.")

    try:
        pt = TrendReq(hl="en-US", tz=360)
        pt.build_payload(kws, timeframe=timeframe, geo=geo)
        df = pt.interest_over_time()
    except Exception as exc:  # noqa: BLE001 - degrade gracefully (§4.3)
        return SignalResult.unavailable(
            SOURCE, f"Google Trends unavailable for geo {geo}: "
                    f"{type(exc).__name__}.")

    if df is None or df.empty:
        return SignalResult.unavailable(
            SOURCE, f"Google Trends returned no data for {kws} in {geo} "
                    f"(thin/low-volume market).")

    cols = [c for c in df.columns if c != "isPartial"]
    # Average of each keyword's mean interest over the window.
    per_kw = {c: float(df[c].mean()) for c in cols}
    value = round(mean(per_kw.values()), 1) if per_kw else None
    if value is None:
        return SignalResult.unavailable(
            SOURCE, f"Google Trends produced no interest values for {kws}.")

    last_date = str(df.index[-1].date()) if hasattr(df.index[-1], "date") else None
    payload = {"value": value, "per_keyword": per_kw, "geo": geo,
               "keywords": kws, "as_of": last_date, "timeframe": timeframe}
    write_cache(SOURCE, params, payload)
    return _result_from_payload(payload, geo)


def _result_from_payload(payload: dict, geo: str) -> SignalResult:
    meta = FreshnessMeta(
        source=SOURCE, as_of=payload.get("as_of"), ttl_days=TRENDS_TTL_DAYS,
        note=("Google Trends relative search interest (0–100 index). "
              "Marketing/outreach context only — not a market event (§4.3)."),
    ).stamp_now()
    return SignalResult(
        source=SOURCE, available=True, value=payload["value"],
        unit="index_0_100", meta=meta,
        note=f"Avg search interest for {payload.get('keywords')} in {geo} "
             f"({payload.get('timeframe')}).",
    )
