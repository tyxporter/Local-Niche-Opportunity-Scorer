"""Phase 1 — firm spine loads correctly from the canonical workbook."""

from lnos import firms


def test_scoreable_set_is_47_house_excluded():
    fs = firms.load_firms(include_pending=True, include_house=False)
    assert len(fs) == 47  # 45 matched + 2 pending; house accounts excluded
    assert all(not f.is_house_account for f in fs)


def test_matched_count_and_total_match_verified_baseline():
    fs = firms.load_firms(include_pending=False, include_house=False)
    assert len(fs) == 45
    total = sum(f.aum_usd for f in fs)
    assert abs(total - firms.EXPECTED_MATCHED_TOTAL_USD) < 1.0


def test_pending_firms_have_null_aum_not_inferred():
    fs = firms.load_firms(include_pending=True, include_house=False)
    pending = [f for f in fs if f.aum_pending]
    assert {f.roster_name for f in pending} == {
        "CWMG-Johnson City-CIA", "CWMG-Las Vegas-CIA"}
    assert all(f.aum_usd is None for f in pending)


def test_house_accounts_excluded_by_default_present_when_requested():
    default = firms.load_firms()
    assert all(not f.is_house_account for f in default)
    with_house = firms.load_firms(include_house=True)
    house = [f for f in with_house if f.is_house_account]
    assert {f.roster_name for f in house} == {
        "Carson Group-CIA", "Corporate Accounts-CIA"}


def test_geography_keys_unresolved_until_template_completed():
    fs = firms.load_firms()
    # County/CBSA come from the template (still blank) -> no firm has
    # FRED-keyable geography yet. City/state may be populated from the city/state
    # file; county+CBSA (the FRED keys) are what gate has_geography.
    assert firms.firms_missing_geography(fs) == fs
    assert all(f.county is None and f.cbsa is None for f in fs)


def test_city_state_merged_with_confidence():
    fs = {f.roster_name: f for f in firms.load_firms()}
    omaha = fs["CWMG-Omaha-CIA"]
    assert omaha.city == "Omaha" and omaha.state == "NE"
    assert "Confirmed" in (omaha.geo_confidence or "")
    assert not omaha.has_geography  # county/CBSA still pending the template
    # Brand-name firm with no city/state in the list is flagged, not invented.
    applied = fs["Applied Financial Planning Inc-CIA"]
    assert applied.city is None and applied.geo_confidence == "NEEDS SALESFORCE"


def test_summary_shape():
    s = firms.spine_summary()
    assert s["scoreable_firms"] == 47
    assert s["matched_with_aum"] == 45
    assert len(s["aum_pending"]) == 2
    assert len(s["house_accounts_excluded"]) == 2
