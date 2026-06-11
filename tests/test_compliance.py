"""Phase 6 — compliance guardrails (§4.4, LOAD-BEARING)."""

import pytest

from lnos import compliance
from lnos.compliance import (
    lint, generate_compliant, ComplianceBlocked, assert_no_scorer_labels,
    STANDING_DISCLOSURE_LINE,
)
from lnos.errors import LnosError


def test_clean_prose_passes_lint():
    text = ("Local healthcare and manufacturing employers anchor this market. "
            "Outreach to pre-retirees aligns with the firm's seminar channel.")
    assert lint(text).ok


@pytest.mark.parametrize("phrase", [
    "We expect the sector to grow.",
    "This market is poised for growth.",
    "Rates are set to rise.",
    "Tech will outperform next year.",
    "We predict strong demand.",
    "Our forecast is bullish.",
    "We recommend buying now.",
    "Clients should buy this fund.",
    "Strong returns ahead.",
    "Past performance is notable.",
    "The market outlook is positive.",
])
def test_forward_looking_and_advice_phrases_are_caught(phrase):
    result = lint(phrase)
    assert not result.ok and result.hits


def test_generate_blocks_after_retries_and_never_ships_draft():
    # Always emits a banned phrase -> must block, not return the draft.
    with pytest.raises(ComplianceBlocked):
        generate_compliant(lambda attempt: "The outlook is strong.",
                           max_attempts=3, section="section 2")


def test_generate_returns_first_clean_draft():
    drafts = ["The outlook is strong.", "Healthcare employers anchor the market."]
    out = generate_compliant(lambda attempt: drafts[attempt], max_attempts=3)
    assert out.attempts == 2 and "anchor" in out.text


def test_d2_label_boundary_blocks_scorer_internals():
    with pytest.raises(LnosError):
        assert_no_scorer_labels({"legal_name": "X", "bucket": "Lead"})
    with pytest.raises(LnosError):
        assert_no_scorer_labels({"quadrant": "Lean-In"})

    class Payload:
        opp = 88.0
    with pytest.raises(LnosError):
        assert_no_scorer_labels(Payload())

    assert_no_scorer_labels({"legal_name": "X", "county": "Douglas"})  # clean -> ok


def test_standing_disclosure_line_is_marketing_not_advice():
    assert "not investment advice" in STANDING_DISCLOSURE_LINE
    assert "marketing-opportunity brief" in STANDING_DISCLOSURE_LINE
