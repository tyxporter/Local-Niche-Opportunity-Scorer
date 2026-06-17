"""Phase 5 — firm input contract fails loud; optional fields never block."""

import json

import pytest

from lnos import firm_record as fr
from lnos.firm_record import (
    FirmRecord, NicheTaxonomy, ComplianceStructure,
    validate_firm_record, assert_valid,
)
from lnos.errors import InputContractError


# A stand-in taxonomy so we can test the machinery without inventing the real
# eight profiles (those are Ty's to provide).
FAKE_TAXONOMY = NicheTaxonomy(available=True, profiles=("Pre-Retirees", "Business Owners"))


def _complete_record(**overrides) -> FirmRecord:
    base = dict(
        firm_id="cwmg-omaha-cia",
        legal_name="CWMG Omaha LLC",
        county="Douglas County",
        cbsa="Omaha-Council Bluffs, NE-IA",
        niche_profile="Pre-Retirees",
        local_employers=["Mutual of Omaha", "Union Pacific"],
        compliance_structure="Carson-only",
        disclosure_block="Approved disclosure text, verbatim.",
        channel_inventory=["email", "seminars"],
    )
    base.update(overrides)
    return FirmRecord.from_dict(base)


def test_complete_record_passes():
    result = validate_firm_record(_complete_record(), taxonomy=FAKE_TAXONOMY)
    assert result.ok
    assert result.message() == ""


def test_missing_required_field_blocks_with_owner_message():
    rec = _complete_record(channel_inventory=[])
    result = validate_firm_record(rec, taxonomy=FAKE_TAXONOMY)
    assert not result.ok
    assert "cannot generate — missing channel_inventory, owner Firm" in result.message()


def test_optional_fields_never_block():
    rec = _complete_record()  # no aum/advisor/maturity supplied
    assert rec.aum_usd is None and rec.advisor_count is None
    assert validate_firm_record(rec, taxonomy=FAKE_TAXONOMY).ok


def test_niche_taxonomy_not_provided_blocks_niche():
    unavailable = NicheTaxonomy(available=False, note="NOT PROVIDED")
    result = validate_firm_record(_complete_record(), taxonomy=unavailable)
    assert not result.ok
    assert any(f == "niche_profile" for f, _, _ in result.problems)


def test_invalid_niche_value_blocks():
    rec = _complete_record(niche_profile="Not A Real Profile")
    result = validate_firm_record(rec, taxonomy=FAKE_TAXONOMY)
    assert not result.ok
    assert any(f == "niche_profile" and "invalid" in r for f, r, _ in result.problems)


def test_invalid_compliance_structure_blocks():
    rec = _complete_record(compliance_structure="something else")
    result = validate_firm_record(rec, taxonomy=FAKE_TAXONOMY)
    assert not result.ok
    assert any(f == "compliance_structure" for f, _, _ in result.problems)


def test_compliance_structure_parsing():
    assert ComplianceStructure.parse("Carson-only") is ComplianceStructure.CARSON_ONLY
    assert ComplianceStructure.parse("dual Carson/Cetera") is ComplianceStructure.DUAL_CARSON_CETERA
    assert ComplianceStructure.parse("bogus") is None


def test_dual_firm_requires_cetera_review():
    rec = _complete_record(compliance_structure="dual Carson/Cetera")
    assert rec.requires_cetera_review is True
    assert _complete_record().requires_cetera_review is False


def test_assert_valid_raises_on_incomplete():
    with pytest.raises(InputContractError):
        assert_valid(_complete_record(legal_name=None), taxonomy=FAKE_TAXONOMY)


def test_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "FIRM_RECORDS_DIR", tmp_path)
    rec = _complete_record()
    path = fr.save_firm_record(rec)
    assert path.exists()
    loaded = fr.load_firm_record("cwmg-omaha-cia")
    assert loaded.legal_name == "CWMG Omaha LLC"
    assert loaded.channel_inventory == ["email", "seminars"]


def test_shipped_taxonomy_has_eight_profiles():
    # The real taxonomy is now provided (8 Blue Ocean profiles, allow_other).
    tax = fr.load_niche_taxonomy()
    assert tax.available is True
    assert len(tax.profiles) == 8
    assert "Equity Concentrator" in tax.profiles
    assert tax.allow_other is True
    assert tax.descriptions.get("Compressed Earner")
