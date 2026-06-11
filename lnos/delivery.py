"""Delivery wrapper (§4.5) — APP-ONLY, never inside the .docx.

This is the internal wrapper Ty sees in the app when sending a brief. It is
rendered by the Streamlit shell (Phase 8); this module builds its CONTENT as a
plain data structure. It deliberately shares NO state with docx_export.py and
does not import it — the separation between the firm-facing document and this
internal wrapper is structural (§4.5).

Contents (§4.5):
  * Ty's one-paragraph prioritization read (which play to lead with and why) —
    Ty's own input; this is the internal layer where ranking/score may live
    (D1), so it is not subject to the firm-facing constraints.
  * Any missing-input flags, each with an owner.
  * A Cetera reminder for dual Carson/Cetera firms.
  * A suggested one-line intro for sending the brief (kept compliance-clean).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import compliance
from .firm_record import FirmRecord, ValidationResult, validate_firm_record, NicheTaxonomy

CETERA_REMINDER = (
    "Dual Carson/Cetera firm — downstream live assets require separate "
    "Cetera/AdTrax review before they go out."
)


@dataclass
class DeliveryWrapper:
    prioritization_read: str
    missing_input_flags: list[str] = field(default_factory=list)
    cetera_reminder: Optional[str] = None
    suggested_intro: str = ""


def _suggested_intro(firm_record: FirmRecord) -> str:
    name = firm_record.legal_name or "your firm"
    intro = (f"Hi — attached is a short local marketing-opportunity brief for "
             f"{name}, with the first play to start with called out inside.")
    # Keep the intro clean against the same deny-list the brief prose uses.
    if not compliance.lint(intro).ok:
        intro = (f"Hi — attached is a short local marketing-opportunity brief "
                 f"for {name}.")
    return intro


def build_delivery_wrapper(
    firm_record: FirmRecord,
    *,
    prioritization_read: Optional[str] = None,
    validation: Optional[ValidationResult] = None,
    taxonomy: Optional[NicheTaxonomy] = None,
) -> DeliveryWrapper:
    """Build the internal delivery wrapper for a firm.

    `prioritization_read` is Ty's paragraph; if omitted, a placeholder prompts
    for it. Missing-input flags come from the input contract (with owners).
    """
    result = validation if validation is not None else \
        validate_firm_record(firm_record, taxonomy=taxonomy)
    flags = [f"{reason} {field} — owner {owner}"
             for field, reason, owner in result.problems]

    read = (prioritization_read or "").strip() or \
        "[Add your one-paragraph prioritization read: which play to lead with and why.]"

    return DeliveryWrapper(
        prioritization_read=read,
        missing_input_flags=flags,
        cetera_reminder=CETERA_REMINDER if firm_record.requires_cetera_review else None,
        suggested_intro=_suggested_intro(firm_record),
    )
