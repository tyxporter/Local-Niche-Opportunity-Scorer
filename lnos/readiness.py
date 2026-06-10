"""Readiness overlay -> Read (§4.0, Phase 3).

Read is the internal overlay (not an external signal). It overlaps with
firm-record fields (channel inventory, marketing maturity), so the brief
explicitly warns against two independent sources of readiness truth drifting.

SINGLE-SOURCE DESIGN (proposed for Ty's confirmation — open item #10):
  * Read is derived ONLY from the firm record. There is no separate readiness
    store. `readiness.py` is the sole place that turns firm-record fields into
    Read. The firm record is the single source of truth; this module is the
    single computation point. No drift is possible because there is exactly one
    input store and one transform.

What is BUILDABLE now (and is built here):
  * The Read input contract (`ReadinessInputs`) and the extraction of those
    inputs from a firm record (`extract_readiness_inputs`).

What is BLOCKED on §2.1 (and intentionally raises):
  * `compute_read` — the actual math turning inputs into the numeric Read.
    The brief states "how Read is computed/ingested — I will provide." Until
    then this raises MethodologyNotProvided rather than inventing a score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from .errors import MethodologyNotProvided

# Documents the single-source decision in one machine-readable place.
READ_SOURCE = "firm_record"  # the ONLY source of readiness truth (no drift)

# Firm-record fields that feed Read. Keeping this list in one place is what
# prevents a second, drifting definition of readiness from appearing elsewhere.
READINESS_FIELDS = (
    "channel_inventory",      # what the firm can actually execute (required field)
    "marketing_maturity_stage",  # optional enriching field
    "plays_run",              # plays already run (optional)
    "advisor_count",          # optional enriching field
    "prior_brief_date",       # optional enriching field
)


@dataclass
class ReadinessInputs:
    """The firm-record-derived inputs to Read. Raw inputs only — no scoring."""

    channel_inventory: list[str] = field(default_factory=list)
    marketing_maturity_stage: Optional[str] = None
    plays_run: list[str] = field(default_factory=list)
    advisor_count: Optional[int] = None
    prior_brief_date: Optional[str] = None

    @property
    def has_channel_inventory(self) -> bool:
        return bool(self.channel_inventory)


def extract_readiness_inputs(firm_record: Mapping) -> ReadinessInputs:
    """Pull readiness inputs from a firm record (the single source of truth).

    Tolerant of missing optional fields. Does NOT validate required-field
    presence — that fail-loud check is the §4.1 input contract's job (Phase 5).
    """
    def _as_list(v):
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return list(v)

    return ReadinessInputs(
        channel_inventory=_as_list(firm_record.get("channel_inventory")),
        marketing_maturity_stage=firm_record.get("marketing_maturity_stage"),
        plays_run=_as_list(firm_record.get("plays_run")),
        advisor_count=firm_record.get("advisor_count"),
        prior_brief_date=firm_record.get("prior_brief_date"),
    )


def compute_read(inputs: ReadinessInputs) -> float:
    """Compute the numeric Read from firm-record inputs.

    BLOCKED: the computation/ingestion method for Read is §2.1 (Ty-provided).
    This intentionally raises rather than returning an invented value.
    """
    raise MethodologyNotProvided("Read computation")
