"""Firm input layer + input contract (§4.1, Phase 5) — FAIL LOUD.

Per-firm record that drives the Local Marketing Opportunity Brief. Records are
stored as one JSON file per firm under data/firm_records/ (cleanest path:
version-controllable, testable; the Streamlit sidebar form in Phase 8 writes
these same files).

THE INPUT CONTRACT IS A HARD REQUIREMENT. If any required field is missing or
invalid, generation is BLOCKED: the gate returns
    "cannot generate — missing [field], owner [owner]"
(one line per problem) and the brief generator produces NO document (§4.1).

Required fields (all must resolve):
  * legal_name            — firm legal name
  * county + cbsa         — market geography, specific enough for FRED series
  * niche_profile         — primary Blue Ocean profile; must be one of the
                            defined eight (validated against the taxonomy)
  * local_employers       — top local employers / dominant sectors
  * compliance_structure  — Carson-only or dual Carson/Cetera
  * disclosure_block      — firm's APPROVED disclosure text, VERBATIM
                            (never generated — §4.4)
  * channel_inventory     — what the firm can actually execute

Optional enriching fields NEVER block: aum_usd, household_count, advisor_count,
marketing_maturity_stage, plays_run, prior_brief_date.

We do not generate disclosure language and we do not invent niche names.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Mapping, Optional

from .errors import InputContractError

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FIRM_RECORDS_DIR = _DATA_DIR / "firm_records"
NICHE_TAXONOMY_PATH = _DATA_DIR / "blue_ocean_niches.json"


class ComplianceStructure(Enum):
    CARSON_ONLY = "Carson-only"
    DUAL_CARSON_CETERA = "dual Carson/Cetera"

    @classmethod
    def parse(cls, value) -> Optional["ComplianceStructure"]:
        if isinstance(value, cls):
            return value
        if not value:
            return None
        norm = str(value).strip().lower().replace("_", " ").replace("-", " ")
        for member in cls:
            if member.value.lower().replace("-", " ").replace("/", " ") \
                    .replace("  ", " ") == norm.replace("/", " ").replace("  ", " "):
                return member
        # tolerant aliases
        if "cetera" in norm or "dual" in norm:
            return cls.DUAL_CARSON_CETERA
        if "carson" in norm and "only" in norm:
            return cls.CARSON_ONLY
        return None


# Required fields and the owner accountable for each. Owners are DEFAULTS,
# flagged for Ty's confirmation (open item: confirm field ownership).
DEFAULT_FIELD_OWNERS: dict[str, str] = {
    "legal_name": "Ty",
    "county": "Ty (geography, F2)",
    "cbsa": "Ty (geography, F2)",
    "niche_profile": "Ty (Blue Ocean)",
    "local_employers": "Firm",
    "compliance_structure": "Compliance",
    "disclosure_block": "Compliance",
    "channel_inventory": "Firm",
}
REQUIRED_FIELDS: tuple[str, ...] = tuple(DEFAULT_FIELD_OWNERS.keys())


# --- Niche taxonomy (open item #4; not provided -> unavailable) --------------
@dataclass
class NicheTaxonomy:
    available: bool
    profiles: tuple[str, ...] = ()
    salesforce_schema: dict = field(default_factory=dict)
    note: str = ""

    def is_valid_profile(self, value: Optional[str]) -> bool:
        if not value:
            return False
        return value.strip() in self.profiles


def load_niche_taxonomy(path: Optional[Path] = None) -> NicheTaxonomy:
    """Load the eight Blue Ocean profiles. Empty/absent -> unavailable."""
    p = Path(path) if path else NICHE_TAXONOMY_PATH
    if not p.exists():
        return NicheTaxonomy(False, note="taxonomy file absent")
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return NicheTaxonomy(False, note=f"taxonomy unreadable: {exc}")
    profiles = tuple(s for s in data.get("profiles", []) if isinstance(s, str) and s.strip())
    if not profiles:
        return NicheTaxonomy(False, note="taxonomy present but profiles empty (NOT PROVIDED)")
    return NicheTaxonomy(
        True, profiles=profiles,
        salesforce_schema=data.get("salesforce_schema", {}) or {},
        note=f"{len(profiles)} profiles loaded",
    )


# --- Firm record ------------------------------------------------------------
@dataclass
class FirmRecord:
    # Required
    legal_name: Optional[str] = None
    county: Optional[str] = None
    cbsa: Optional[str] = None
    niche_profile: Optional[str] = None
    local_employers: list = field(default_factory=list)
    compliance_structure: Optional[str] = None
    disclosure_block: Optional[str] = None      # VERBATIM, never generated
    channel_inventory: list = field(default_factory=list)

    # Optional enriching (never block)
    firm_id: Optional[str] = None               # link to the spine
    state: Optional[str] = None
    city: Optional[str] = None
    zip: Optional[str] = None
    aum_usd: Optional[float] = None
    household_count: Optional[int] = None
    advisor_count: Optional[int] = None
    marketing_maturity_stage: Optional[str] = None
    plays_run: list = field(default_factory=list)
    prior_brief_date: Optional[str] = None

    @staticmethod
    def _as_list(v):
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return list(v)

    @classmethod
    def from_dict(cls, d: Mapping) -> "FirmRecord":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kw = {k: v for k, v in d.items() if k in known}
        for list_field in ("local_employers", "channel_inventory", "plays_run"):
            if list_field in kw:
                kw[list_field] = cls._as_list(kw[list_field])
        return cls(**kw)

    @classmethod
    def from_json_file(cls, path) -> "FirmRecord":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def requires_cetera_review(self) -> bool:
        """Dual firms: downstream live assets need separate Cetera/AdTrax
        review — surfaced in the delivery wrapper (§4.4)."""
        return ComplianceStructure.parse(self.compliance_structure) is \
            ComplianceStructure.DUAL_CARSON_CETERA


# --- Validation gate (FAIL LOUD) --------------------------------------------
@dataclass
class ValidationResult:
    ok: bool
    problems: list[tuple[str, str, str]] = field(default_factory=list)
    # each problem: (field, reason, owner)

    def message(self) -> str:
        """The firm-blocking message (§4.1). Empty string when ok."""
        if self.ok:
            return ""
        return "\n".join(
            f"cannot generate — {reason} {field}, owner {owner}"
            for field, reason, owner in self.problems
        )


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def validate_firm_record(
    record: FirmRecord,
    *,
    taxonomy: Optional[NicheTaxonomy] = None,
    owners: Optional[Mapping[str, str]] = None,
) -> ValidationResult:
    """Validate a firm record against the §4.1 input contract.

    Does not raise — returns a ValidationResult so the brief generator can
    surface the blocking message and produce no document. Use `assert_valid`
    if you want a hard exception instead.
    """
    owners = dict(DEFAULT_FIELD_OWNERS, **(owners or {}))
    tax = taxonomy if taxonomy is not None else load_niche_taxonomy()
    problems: list[tuple[str, str, str]] = []

    for fld in REQUIRED_FIELDS:
        value = getattr(record, fld)
        owner = owners.get(fld, "Ty")
        if _is_empty(value):
            problems.append((fld, "missing", owner))
            continue
        if fld == "compliance_structure":
            if ComplianceStructure.parse(value) is None:
                problems.append(
                    (fld, "invalid (must be 'Carson-only' or 'dual Carson/Cetera')",
                     owner))
        elif fld == "niche_profile":
            if not tax.available:
                problems.append(
                    (fld, "unvalidatable — Blue Ocean taxonomy not provided;",
                     owner))
            elif not tax.is_valid_profile(value):
                problems.append(
                    (fld, f"invalid '{value}' (not one of the defined eight);",
                     owner))

    return ValidationResult(ok=not problems, problems=problems)


def assert_valid(record: FirmRecord, **kw) -> None:
    """Raise InputContractError if the record fails the contract."""
    result = validate_firm_record(record, **kw)
    if not result.ok:
        raise InputContractError(result.message())


# --- Record store -----------------------------------------------------------
def record_path(firm_id: str) -> Path:
    return FIRM_RECORDS_DIR / f"{firm_id}.json"


def save_firm_record(record: FirmRecord) -> Path:
    if not record.firm_id:
        raise InputContractError("firm_id is required to save a firm record.")
    FIRM_RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    path = record_path(record.firm_id)
    path.write_text(json.dumps(record.to_dict(), indent=2))
    return path


def load_firm_record(firm_id: str) -> FirmRecord:
    path = record_path(firm_id)
    if not path.exists():
        raise FileNotFoundError(
            f"No firm record for '{firm_id}' at {path}. Create one before "
            f"generating a brief.")
    return FirmRecord.from_json_file(path)
