"""Approved disclosure selection (verbatim, by compliance structure)."""

from lnos import disclosures
from lnos.firm_record import ComplianceStructure


def test_dual_gets_cetera_block():
    d = disclosures.for_structure("dual Carson/Cetera")
    assert d == disclosures.CETERA
    assert "Cetera Wealth Services LLC" in d
    assert "Member FINRA/SIPC" in d


def test_carson_only_gets_ria_block():
    d = disclosures.for_structure("Carson-only")
    assert d == disclosures.RIA_ONLY
    assert "Cetera" not in d
    assert "SEC Registered Investment Advisor" in d


def test_unknown_defaults_to_ria_only():
    assert disclosures.for_structure(None) == disclosures.RIA_ONLY


def test_both_blocks_share_confidentiality_paragraph():
    tail = "permanently delete the email and its attachments."
    assert disclosures.CETERA.endswith(tail)
    assert disclosures.RIA_ONLY.endswith(tail)


def test_enum_parse_roundtrip():
    assert ComplianceStructure.parse("dual Carson/Cetera") is \
        ComplianceStructure.DUAL_CARSON_CETERA
