"""Census geocoder parsing + graceful degrade (no inference, no fabrication)."""

from lnos import geocode


def test_resolve_requires_city_and_state():
    r = geocode.resolve("", "NE")
    assert r.available is False and not r.has_fips


def test_parse_extracts_county_and_cbsa():
    geos = {
        "Counties": [{"STATE": "31", "COUNTY": "055", "NAME": "Douglas County"}],
        "Metropolitan Statistical Areas": [
            {"NAME": "Omaha, NE-IA Metro Area", "CBSA": "36540"}],
    }
    p = geocode._parse_geographies(geos)
    assert p["state_fips"] == "31" and p["county_fips"] == "055"
    assert p["county_name"] == "Douglas County"
    assert p["cbsa"] == "Omaha, NE-IA Metro Area" and p["cbsa_code"] == "36540"


def test_parse_no_match_returns_none():
    assert geocode._parse_geographies({}) is None
    assert geocode._parse_geographies({"Urban Areas": [{"NAME": "x"}]}) is None


def test_parse_county_without_cbsa():
    geos = {"Counties": [{"STATE": "18", "COUNTY": "083", "NAME": "Knox County"}]}
    p = geocode._parse_geographies(geos)
    assert p["county_fips"] == "083" and p["cbsa"] is None
