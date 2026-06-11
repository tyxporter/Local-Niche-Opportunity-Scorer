"""Local Market Snapshot — brief section 1 (§4.2, §4.3).

Assembles 3–5 current-data facts (FRED spine: county unemployment, housing
trend; ACS for median household income as market structure) into clean,
UN-interpreted metrics. This is the only section with no LLM prose — it
presents numbers and their provenance, nothing more (§4.2 "no interpretation").

Reliability rules (§4.3) are enforced here: a stale/unavailable/thin source is
reported as a narrowed claim in plain language; we NEVER fabricate a value.

FIPS note: FRED LAUS and ACS key off numeric FIPS (state + county). The firm
geography template carries county NAME + CBSA, not FIPS; resolving name->FIPS
is a separate step (geography is still being completed, open item F2). Until
FIPS are supplied, the snapshot narrows every metric rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import census, fred
from .cache import SignalResult


@dataclass
class SnapshotMetric:
    label: str
    result: SignalResult

    @property
    def available(self) -> bool:
        return self.result.available

    def display(self) -> str:
        """Plain one-liner for the section; narrows honestly when unavailable."""
        if not self.result.available:
            return f"{self.label}: not available — {self.result.note}"
        unit = self.result.unit or ""
        as_of = self.result.meta.as_of
        stamp = f" (as of {as_of})" if as_of else ""
        return f"{self.label}: {self.result.value} {unit}{stamp}".rstrip()


@dataclass
class Snapshot:
    firm_id: str
    metrics: list[SnapshotMetric] = field(default_factory=list)

    @property
    def available_metrics(self) -> list[SnapshotMetric]:
        return [m for m in self.metrics if m.available]

    @property
    def narrowed(self) -> list[str]:
        """Plain-language notes for every metric we could not present (§4.3)."""
        return [f"{m.label}: {m.result.note}" for m in self.metrics if not m.available]

    @property
    def is_thin(self) -> bool:
        """True when too few metrics resolved to stand as a snapshot (3–5 target)."""
        return len(self.available_metrics) < 3


def build_snapshot(
    firm_id: str,
    *,
    state_fips: Optional[str] = None,
    county_fips: Optional[str] = None,
    acs_year: int = census.DEFAULT_ACS_YEAR,
) -> Snapshot:
    """Build the section-1 snapshot for a firm's market.

    Without resolved FIPS, every metric narrows (we do not guess geography).
    """
    metrics: list[SnapshotMetric] = []

    if not (state_fips and county_fips):
        note = ("market geography not resolved to FIPS yet (county/CBSA pending "
                "— open item F2); snapshot narrowed.")
        for label in ("County unemployment rate", "Median household income",
                      "Home price index"):
            metrics.append(SnapshotMetric(label, SignalResult.unavailable("snapshot", note)))
        return Snapshot(firm_id=firm_id, metrics=metrics)

    # FRED spine: county unemployment (LAUS).
    unemp = fred.fetch_series_latest(
        fred.county_unemployment_series(state_fips, county_fips), units="%")
    metrics.append(SnapshotMetric("County unemployment rate", unemp))

    # ACS market-structure: median household income.
    mhi = census.fetch_median_household_income(state_fips, county_fips, year=acs_year)
    metrics.append(SnapshotMetric("Median household income", mhi))

    # Housing trend is wired per-market via a FRED HPI/permits series id; until a
    # market's series is mapped we narrow rather than invent one.
    metrics.append(SnapshotMetric(
        "Home price trend",
        SignalResult.unavailable(
            "fred", "housing series not mapped for this market yet; omitted.")))

    return Snapshot(firm_id=firm_id, metrics=metrics)
