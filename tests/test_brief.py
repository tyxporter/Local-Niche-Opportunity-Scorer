"""Phase 6 — brief assembly: 6 sections, fail-loud gate, blocked ranking, D2."""

import pytest

from lnos import brief, snapshot as snap_mod
from lnos.brief import (
    Brief, BlockedBrief, RankedPlay, generate_brief,
    build_section5_where_to_start, build_section6_compliance_footer,
    rank_plays_from_scorer, LLMUnavailable, SECTION_TITLES,
)
from lnos.firm_record import FirmRecord, NicheTaxonomy
from lnos.errors import MethodologyNotProvided, LnosError


FAKE_TAXONOMY = NicheTaxonomy(available=True, profiles=("Pre-Retirees",))
CLEAN_PROSE = ("Local healthcare and manufacturing employers anchor this market; "
               "outreach to pre-retirees fits the firm's seminar and email channels.")


class FakeLLM:
    def __init__(self, text=CLEAN_PROSE):
        self.text = text
        self.calls = 0

    def complete(self, *, system, prompt, temperature):
        self.calls += 1
        return self.text


def _complete_record(**overrides) -> FirmRecord:
    base = dict(
        firm_id="cwmg-omaha-cia", legal_name="CWMG Omaha LLC",
        county="Douglas County", cbsa="Omaha-Council Bluffs, NE-IA",
        niche_profile="Pre-Retirees", local_employers=["Mutual of Omaha"],
        compliance_structure="Carson-only",
        disclosure_block="Approved disclosure text, verbatim.",
        channel_inventory=["email", "seminars"],
    )
    base.update(overrides)
    return FirmRecord.from_dict(base)


def _snapshot():
    return snap_mod.build_snapshot("cwmg-omaha-cia")  # narrowed (no FIPS) but valid


def test_incomplete_record_blocks_with_no_document():
    rec = _complete_record(disclosure_block=None)
    result = generate_brief(rec, _snapshot(), llm=FakeLLM(),
                            ranked_plays=[RankedPlay("Play", "reason")],
                            taxonomy=FAKE_TAXONOMY)
    assert isinstance(result, BlockedBrief)
    assert "cannot generate" in result.message


def test_complete_record_produces_six_sections_in_order():
    plays = [RankedPlay("Seminar series", "fits the firm's strongest channel"),
             RankedPlay("Email nurture", "low lift, broad reach")]
    result = generate_brief(_complete_record(), _snapshot(), llm=FakeLLM(),
                            ranked_plays=plays, taxonomy=FAKE_TAXONOMY)
    assert isinstance(result, Brief)
    assert [s.title for s in result.sections] == list(SECTION_TITLES)
    assert [s.number for s in result.sections] == [1, 2, 3, 4, 5, 6]


def test_section6_templates_disclosure_verbatim_plus_standing_line():
    sec = build_section6_compliance_footer(_complete_record())
    assert "Approved disclosure text, verbatim." in sec.body
    assert "not investment advice" in sec.body


def test_no_scorer_label_appears_in_any_section():
    plays = [RankedPlay("Seminar", "fits channel")]
    result = generate_brief(_complete_record(), _snapshot(), llm=FakeLLM(),
                            ranked_plays=plays, taxonomy=FAKE_TAXONOMY)
    blob = "\n".join(s.body for s in result.sections).lower()
    for label in ("lean-in", "challenge", "quadrant", "bucket", "opp ", "reposition"):
        assert label not in blob


def test_filename_base_format():
    plays = [RankedPlay("Seminar", "fits channel")]
    result = generate_brief(_complete_record(), _snapshot(), llm=FakeLLM(),
                            ranked_plays=plays, taxonomy=FAKE_TAXONOMY)
    base = result.filename_base()
    assert base.startswith("CWMG-Omaha-LLC-Local-Opportunity-Brief-")


def test_missing_llm_fails_loud():
    with pytest.raises(LLMUnavailable):
        generate_brief(_complete_record(), _snapshot(), llm=None,
                       ranked_plays=[RankedPlay("p", "r")], taxonomy=FAKE_TAXONOMY)


def test_where_to_start_ranking_from_scorer_is_blocked():
    with pytest.raises(MethodologyNotProvided):
        rank_plays_from_scorer(object(), [RankedPlay("p", "r")])
    with pytest.raises(MethodologyNotProvided):
        generate_brief(_complete_record(), _snapshot(), llm=FakeLLM(),
                       ranked_plays=None, taxonomy=FAKE_TAXONOMY)


def test_where_to_start_render_has_no_numbers_only_ranking():
    sec = build_section5_where_to_start(
        [RankedPlay("Seminar", "fits channel"), RankedPlay("Email", "low lift")])
    assert "1. Seminar" in sec.body and "2. Email" in sec.body
    assert "Start with #1." in sec.body


def test_prose_section_blocks_on_banned_llm_output():
    from lnos.compliance import ComplianceBlocked
    bad_llm = FakeLLM(text="The market outlook is strong and returns will rise.")
    with pytest.raises(ComplianceBlocked):
        generate_brief(_complete_record(), _snapshot(), llm=bad_llm,
                       ranked_plays=[RankedPlay("p", "r")], taxonomy=FAKE_TAXONOMY)
