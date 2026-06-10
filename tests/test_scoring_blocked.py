"""Phase 3–4 — methodology surface is BLOCKED on §2.1, schema is present."""

import pytest

from lnos import scoring, readiness
from lnos.errors import MethodologyNotProvided


def test_output_label_vocabularies_match_brief_section1():
    assert [b.value for b in scoring.Bucket] == [
        "Lead", "Build", "Challenge", "Hold"]
    assert [q.value for q in scoring.Quadrant] == [
        "Lean-In", "Develop", "Optimize", "Reposition-Sustain"]


@pytest.mark.parametrize("call", [
    lambda: scoring.combine_opp(1, 2, 3),
    lambda: scoring.assign_bucket(50),
    lambda: scoring.assign_quadrant(50, 50),
    lambda: scoring.normalize_signal(None, signal="wealth"),
])
def test_scoring_math_is_blocked(call):
    with pytest.raises(MethodologyNotProvided):
        call()


def test_read_computation_is_blocked():
    inputs = readiness.ReadinessInputs(channel_inventory=["email"])
    with pytest.raises(MethodologyNotProvided):
        readiness.compute_read(inputs)


def test_readiness_single_source_constant():
    assert readiness.READ_SOURCE == "firm_record"


def test_readiness_inputs_extracted_from_firm_record():
    rec = {"channel_inventory": "email, seminars",
           "marketing_maturity_stage": "developing",
           "plays_run": ["webinar"]}
    inp = readiness.extract_readiness_inputs(rec)
    assert inp.channel_inventory == ["email", "seminars"]
    assert inp.marketing_maturity_stage == "developing"
    assert inp.plays_run == ["webinar"]
    assert inp.has_channel_inventory
