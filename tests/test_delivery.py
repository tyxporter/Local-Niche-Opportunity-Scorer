"""Phase 7 — delivery wrapper content (app-only); separate from the document."""

from lnos import compliance
from lnos.delivery import build_delivery_wrapper, CETERA_REMINDER
from lnos.firm_record import FirmRecord, NicheTaxonomy

FAKE_TAXONOMY = NicheTaxonomy(available=True, profiles=("Pre-Retirees",))


def _record(**overrides) -> FirmRecord:
    base = dict(
        firm_id="cwmg-omaha-cia", legal_name="CWMG Omaha LLC",
        county="Douglas County", cbsa="Omaha-Council Bluffs, NE-IA",
        niche_profile="Pre-Retirees", local_employers=["Mutual of Omaha"],
        compliance_structure="Carson-only",
        disclosure_block="Approved disclosure.", channel_inventory=["email"],
    )
    base.update(overrides)
    return FirmRecord.from_dict(base)


def test_dual_firm_gets_cetera_reminder():
    w = build_delivery_wrapper(_record(compliance_structure="dual Carson/Cetera"),
                               taxonomy=FAKE_TAXONOMY)
    assert w.cetera_reminder == CETERA_REMINDER


def test_carson_only_firm_has_no_cetera_reminder():
    w = build_delivery_wrapper(_record(), taxonomy=FAKE_TAXONOMY)
    assert w.cetera_reminder is None


def test_missing_inputs_become_flags_with_owner():
    w = build_delivery_wrapper(_record(channel_inventory=[]), taxonomy=FAKE_TAXONOMY)
    assert any("channel_inventory" in f and "owner Firm" in f
               for f in w.missing_input_flags)


def test_prioritization_read_placeholder_then_tys_input():
    assert "[Add your" in build_delivery_wrapper(_record(), taxonomy=FAKE_TAXONOMY).prioritization_read
    w = build_delivery_wrapper(_record(), prioritization_read="Lead with the seminar play.",
                               taxonomy=FAKE_TAXONOMY)
    assert w.prioritization_read == "Lead with the seminar play."


def test_suggested_intro_is_compliance_clean():
    w = build_delivery_wrapper(_record(), taxonomy=FAKE_TAXONOMY)
    assert w.suggested_intro
    assert compliance.lint(w.suggested_intro).ok
