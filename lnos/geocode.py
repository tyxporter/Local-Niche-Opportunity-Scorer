"""City/State -> County + CBSA + FIPS resolution (keyless, cloud-friendly).

Resolves the geography keys the data layer needs (FRED LAUS / ACS key off
state+county FIPS) from a firm's city/state, in two keyless steps:

  1. city/state -> lat/lon  (Open-Meteo geocoding; Nominatim fallback)
  2. lat/lon    -> county FIPS + CBSA  (US Census Geocoder, coordinates layer)

Open-Meteo is the primary because it is built for programmatic use and works
from cloud hosts (Streamlit Cloud) where Nominatim often rate-limits/blocks.

This is RESOLUTION from supplied city/state (Ty's data), not inference from a
firm name (§1/v2.3 forbids the latter). Cached aggressively (geography is
stable) and fully graceful: any failure returns an unavailable result, never a
guessed county.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .cache import read_cache, write_cache

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

SOURCE = "geocode"
GEO_TTL_DAYS = 365
_OPENMETEO = "https://geocoding-api.open-meteo.com/v1/search"
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_CENSUS_COORDS = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
_UA = "LocalNicheOpportunityScorer/0.8 (Carson Wealth internal tool)"

_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


@dataclass
class GeoResolution:
    available: bool
    state_fips: Optional[str] = None
    county_fips: Optional[str] = None
    county_name: Optional[str] = None
    cbsa: Optional[str] = None
    cbsa_code: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    note: str = ""

    @property
    def has_fips(self) -> bool:
        return bool(self.state_fips and self.county_fips)


def _state_full(state: str) -> Optional[str]:
    s = (state or "").strip()
    if not s:
        return None
    if len(s) == 2 and s.upper() in _STATES:
        return _STATES[s.upper()]
    return s  # already a full name


def resolve(city: str, state: str, *, max_age_days: Optional[int] = GEO_TTL_DAYS,
            timeout: float = 12.0) -> GeoResolution:
    """Resolve city/state -> county + CBSA + FIPS. Unavailable on any failure."""
    if not city or not state:
        return GeoResolution(False, note="city/state missing — cannot resolve geography.")

    params = {"city": city.strip(), "state": state.strip()}
    cached = read_cache(SOURCE, params, max_age_days)
    if cached is not None:
        return _from_payload(cached)
    if requests is None:
        return GeoResolution(False, note="requests not installed.")

    latlon = _latlon(city, state, timeout)
    if latlon is None:
        return GeoResolution(False, note=f"could not geocode {city}, {state}.")
    lat, lon = latlon

    payload = _county_from_coords(lon, lat, timeout)
    if payload is None:
        return GeoResolution(False, lat=lat, lon=lon,
                             note=f"no county for {city}, {state} coordinates.")
    payload.update({"lat": lat, "lon": lon})
    write_cache(SOURCE, params, payload)
    return _from_payload(payload)


def _latlon(city: str, state: str, timeout: float):
    return (_latlon_openmeteo(city, state, timeout)
            or _latlon_nominatim(city, state, timeout))


def _latlon_openmeteo(city: str, state: str, timeout: float):
    full = _state_full(state)
    try:
        r = requests.get(_OPENMETEO, timeout=timeout, params={
            "name": city.strip(), "count": 10, "country": "US",
            "language": "en", "format": "json"})
        r.raise_for_status()
        results = r.json().get("results") or []
    except Exception:  # noqa: BLE001
        return None
    # Require a state match so we don't grab a same-named city in another state.
    for x in results:
        if full and (x.get("admin1") or "").strip().lower() == full.lower():
            try:
                return float(x["latitude"]), float(x["longitude"])
            except (KeyError, ValueError, TypeError):
                return None
    return None


def _latlon_nominatim(city: str, state: str, timeout: float):
    try:
        r = requests.get(_NOMINATIM, headers={"User-Agent": _UA}, timeout=timeout,
                         params={"city": city.strip(), "state": state.strip(),
                                 "country": "USA", "format": "json", "limit": 1})
        r.raise_for_status()
        hits = r.json()
    except Exception:  # noqa: BLE001
        return None
    if not hits:
        return None
    try:
        return float(hits[0]["lat"]), float(hits[0]["lon"])
    except (KeyError, ValueError, TypeError):
        return None


def _county_from_coords(lon: float, lat: float, timeout: float) -> Optional[dict]:
    try:
        r = requests.get(_CENSUS_COORDS, timeout=timeout, params={
            "x": lon, "y": lat, "benchmark": "Public_AR_Current",
            "vintage": "Current_Current", "layers": "all", "format": "json"})
        r.raise_for_status()
        data = r.json()
    except Exception:  # noqa: BLE001
        return None
    return _parse_geographies(data.get("result", {}).get("geographies", {}))


def _parse_geographies(geos: dict) -> Optional[dict]:
    """Pull county + CBSA from a Census coordinates 'geographies' block."""
    if not geos:
        return None
    counties = geos.get("Counties")
    if not counties:
        return None
    county = counties[0]
    msa = (geos.get("Metropolitan Statistical Areas")
           or geos.get("Combined Statistical Areas") or [None])[0]
    return {
        "state_fips": county.get("STATE"),
        "county_fips": county.get("COUNTY"),
        "county_name": county.get("NAME") or county.get("BASENAME"),
        "cbsa": (msa.get("NAME") or msa.get("BASENAME")) if msa else None,
        "cbsa_code": msa.get("CBSA") if msa else None,
    }


def _from_payload(p: dict) -> GeoResolution:
    return GeoResolution(
        available=bool(p.get("state_fips") and p.get("county_fips")),
        state_fips=p.get("state_fips"), county_fips=p.get("county_fips"),
        county_name=p.get("county_name"), cbsa=p.get("cbsa"),
        cbsa_code=p.get("cbsa_code"), lat=p.get("lat"), lon=p.get("lon"),
        note="resolved via Open-Meteo + Census Geocoder.")
