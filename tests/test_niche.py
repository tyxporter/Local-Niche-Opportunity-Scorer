"""Blue Ocean niche auto-selection (classification into the defined eight)."""

from lnos import niche
from lnos.firm_record import NicheTaxonomy

TAX = NicheTaxonomy(available=True,
                    profiles=("Pre-Retirees", "Business Owners", "Medical Professionals"),
                    descriptions={"Business Owners": "owners of local companies"})


class FakeLLM:
    def __init__(self, text):
        self.text = text

    def complete(self, *, system, prompt, temperature):
        return self.text


def test_selects_valid_profile_from_json():
    llm = FakeLLM('{"profile": "Business Owners", "rationale": "manufacturing base"}')
    sel = niche.select_niche(taxonomy=TAX, firm_context={"cbsa": "Omaha"}, llm=llm)
    assert sel.available and sel.profile == "Business Owners"
    assert "manufacturing" in sel.rationale


def test_tolerates_extra_words_around_name():
    sel = niche.select_niche(taxonomy=TAX, firm_context={},
                             llm=FakeLLM('The best fit is Pre-Retirees here.'))
    assert sel.available and sel.profile == "Pre-Retirees"


def test_off_list_profile_is_rejected_not_invented():
    sel = niche.select_niche(taxonomy=TAX, firm_context={},
                             llm=FakeLLM('{"profile": "Crypto Bros"}'))
    assert not sel.available and sel.profile is None


def test_unavailable_taxonomy_blocks():
    sel = niche.select_niche(taxonomy=NicheTaxonomy(False), firm_context={},
                             llm=FakeLLM("x"))
    assert not sel.available


def test_llm_error_degrades():
    class Boom:
        def complete(self, **k):
            raise RuntimeError("nope")
    sel = niche.select_niche(taxonomy=TAX, firm_context={}, llm=Boom())
    assert not sel.available
