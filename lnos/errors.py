"""Shared fail-loud exceptions.

The methodology guardrail (§2.1 / D6) is enforced as a raised exception, not a
silent default: any attempt to compute Read/Opp/buckets/quadrants before Ty has
supplied the methodology raises `MethodologyNotProvided` rather than returning
an invented number.
"""

from __future__ import annotations


class LnosError(Exception):
    """Base class for all Local Niche Opportunity Scorer errors."""


class InputContractError(LnosError):
    """Raised when a required firm-record field is missing/invalid at a point
    that must hard-stop (§4.1). The brief generator's normal path does NOT
    raise — it returns the 'cannot generate — missing [field], owner [owner]'
    message and produces no document — but this exists for callers that prefer
    to fail loudly in code.
    """


class NicheTaxonomyNotProvided(LnosError):
    """Raised when the Blue Ocean niche taxonomy (the eight profiles) is needed
    to validate a firm record but has not been supplied yet (open item #4).
    The taxonomy is Ty's to provide; we do not invent profile names.
    """

    def __init__(self):
        super().__init__(
            "Blue Ocean niche taxonomy not provided — cannot validate the niche "
            "profile against the defined eight. Supply data/blue_ocean_niches.json "
            "(profiles + Salesforce schema). Owner: Ty."
        )


class MethodologyNotProvided(LnosError):
    """Raised when scoring math is invoked before §2.1 has been supplied.

    Per §2.1 and D6, the Opp formula, normalization, Read computation, bucket
    thresholds, and quadrant cut points come from Ty directly and are NOT
    derived/inferred/fitted from any data. Until they are wired in, the
    combination logic is intentionally absent and this is raised loudly.
    """

    def __init__(self, what: str):
        super().__init__(
            f"{what} requires the §2.1 methodology, which has not been provided "
            f"(marked TO-BE-PROVIDED). Per §2.1/D6 the scorer will not infer, "
            f"propose, or fit a formula. Supply the spec to unblock."
        )
