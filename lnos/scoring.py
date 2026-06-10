"""Scoring (§4.0 Phase 4) — the §2.1 boundary.

This module defines ONLY what Ty has already specified: the §1 output schema —
the five numeric fields (Opp, Read, Wealth, Demand, Saturation), the four
buckets, and the four quadrants — as concrete types.

It does NOT contain the methodology. Per §2.1 / D6, the normalization of raw
signals, the weighting that combines Wealth/Demand/Saturation into Opp, the
Read computation, the bucket thresholds, and the quadrant cut points are
supplied by Ty directly and are NOT inferred, proposed, or fitted here. Every
function that would need those numbers raises `MethodologyNotProvided` until
the spec is wired in. There are deliberately NO placeholder weights anywhere.

D2 boundary: ScorerOutput (incl. bucket/quadrant labels) is INTERNAL only. It
must never be passed to docx/section builders or any firm-facing artifact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .cache import SignalResult
from .errors import MethodologyNotProvided


# --- Output label vocabularies (from §1 — provided by Ty) --------------------
class Bucket(Enum):
    """Opp tiers. Order is high→low opportunity. INTERNAL label (D2)."""

    LEAD = "Lead"
    BUILD = "Build"
    CHALLENGE = "Challenge"
    HOLD = "Hold"


class Quadrant(Enum):
    """Opp × Read crossing. INTERNAL label (D2)."""

    LEAN_IN = "Lean-In"
    DEVELOP = "Develop"
    OPTIMIZE = "Optimize"
    REPOSITION_SUSTAIN = "Reposition-Sustain"


# --- Inputs -----------------------------------------------------------------
@dataclass
class RawSignals:
    """Raw observations from the data layer for one firm's market.

    These are the *unnormalized* readings (census -> wealth, trends -> demand,
    competition -> saturation). Turning them into sub-scores is §2.1.
    """

    wealth: SignalResult       # census_acs (median household income, etc.)
    demand: SignalResult       # google_trends interest
    saturation: SignalResult   # finra_brokercheck competitor count

    @property
    def any_unavailable(self) -> bool:
        return not (self.wealth.available and self.demand.available
                    and self.saturation.available)


# --- Output (INTERNAL ONLY — D2) --------------------------------------------
@dataclass
class ScorerOutput:
    """The §1 scorer output for one firm. Internal delivery wrapper only.

    NEVER hand this (or any field of it, especially bucket/quadrant) to a
    firm-facing builder. The brief shows ranked reasoning, not metrics (D1/D2).
    """

    firm_id: str
    roster_name: str
    aum_usd: Optional[float]   # descriptive metadata; nullable; never blocks

    # Five numeric fields (§1)
    opp: float
    read: float
    wealth: float
    demand: float
    saturation: float

    # Label fields (§1)
    bucket: Bucket
    quadrant: Quadrant

    # Provenance / honesty flags (§4.3)
    narrowed_claims: tuple[str, ...] = ()  # sources that were thin/unavailable


# --- Methodology surface (ALL BLOCKED on §2.1) ------------------------------
def normalize_signal(raw: SignalResult, *, signal: str) -> float:
    """Normalize a raw signal into a 0–? sub-score (Wealth/Demand/Saturation).

    BLOCKED: the normalization method is §2.1 (Ty-provided).
    """
    raise MethodologyNotProvided(f"{signal} normalization")


def combine_opp(wealth: float, demand: float, saturation: float) -> float:
    """Combine sub-scores into Opp.

    BLOCKED: the weighting/formula is §2.1 (Ty-provided). No placeholder weights.
    """
    raise MethodologyNotProvided("Opp combination")


def assign_bucket(opp: float) -> Bucket:
    """Map Opp -> Lead/Build/Challenge/Hold.

    BLOCKED: the tier thresholds are §2.1 (Ty-provided).
    """
    raise MethodologyNotProvided("Bucket tiering")


def assign_quadrant(opp: float, read: float) -> Quadrant:
    """Map (Opp, Read) -> Lean-In/Develop/Optimize/Reposition-Sustain.

    BLOCKED: the quadrant cut points are §2.1 (Ty-provided).
    """
    raise MethodologyNotProvided("Quadrant cut points")


def score_firm(
    *,
    firm_id: str,
    roster_name: str,
    aum_usd: Optional[float],
    signals: RawSignals,
    readiness_inputs,  # lnos.readiness.ReadinessInputs
) -> ScorerOutput:
    """Produce the full §1 ScorerOutput for one firm.

    Orchestration is in place; the math is not. This raises
    MethodologyNotProvided until §2.1 is supplied. When unblocked, this is the
    single entry point that normalizes signals, computes Read, combines Opp, and
    assigns bucket/quadrant — all using Ty's spec verbatim.
    """
    raise MethodologyNotProvided("score_firm (full §1 scoring)")
