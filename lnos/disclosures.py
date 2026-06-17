"""Approved disclosure blocks (§4.4) — VERBATIM, provided by compliance.

These are templated into the brief's compliance footer EXACTLY as supplied; we
never draft or alter disclosure language. Selection is by the firm's compliance
structure: dual Carson/Cetera firms get the Cetera block, Carson-only (RIA)
firms get the RIA-only block.
"""

from __future__ import annotations

from .firm_record import ComplianceStructure

_EMAIL_CONFIDENTIALITY = (
    "This email transmission and its attachments, if any, are confidential and "
    "intended only for the use of particular persons and entities. They may also "
    "be work product and/or protected by the attorney-client privilege or other "
    "privileges. Delivery to someone other than the intended recipient(s) shall "
    "not be deemed to waive any privilege. Review, distribution, storage, "
    "transmittal or other use of the email and any attachment by an unintended "
    "recipient is expressly prohibited. If you are not the named addressee (or "
    "its agent) or this email has been addressed to you in error, please "
    "immediately notify the sender by reply email and permanently delete the "
    "email and its attachments."
)

CETERA = (
    "Securities offered through Cetera Wealth Services LLC, Member FINRA/SIPC. "
    "Investment advisory services offered through CWM, LLC, an SEC Registered "
    "Investment Advisor. Cetera is under separate ownership from any other named "
    "entity. Carson Partners, a division of CWM, LLC, is a nationwide "
    "partnership of advisors.\n\n" + _EMAIL_CONFIDENTIALITY
)

RIA_ONLY = (
    "Investment advisory services offered through CWM, LLC, an SEC Registered "
    "Investment Advisor. Carson Partners, a division of CWM, LLC, is a "
    "nationwide partnership of advisors.\n\n" + _EMAIL_CONFIDENTIALITY
)


def for_structure(compliance_structure) -> str:
    """Return the approved disclosure block for a compliance structure."""
    parsed = ComplianceStructure.parse(compliance_structure)
    if parsed is ComplianceStructure.DUAL_CARSON_CETERA:
        return CETERA
    return RIA_ONLY  # default to the more conservative RIA-only block
