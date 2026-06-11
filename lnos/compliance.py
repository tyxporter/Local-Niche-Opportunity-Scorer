"""Compliance guardrails on generated text (§4.4) — LOAD-BEARING.

Two layers, plus two boundaries:

1. SYSTEM-PROMPT CONSTRAINTS (preventive): the instruction block prepended to
   any LLM generation of brief sections 2–4. Forbids forward-looking market
   language, client-advice posture, and statements about what the market or a
   sector will do.

2. POST-GENERATION LINT (detective): a deny-list scan of the generated prose.
   On a hit we log the phrase, regenerate up to N times, and if it still trips
   we BLOCK — the draft is never shipped.

Boundaries:
  * D1/D3 framing is reinforced in the system prompt (no numbers, pure
    marketing-opportunity framing).
  * D2 label guard (`assert_no_scorer_labels`): a hard code boundary so bucket/
    quadrant/score never reach a firm-facing builder.

We NEVER draft disclosure language (§4.4) — disclosure is templated verbatim
from the firm's approved block elsewhere (brief.py section 6).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from .brand import VOICE
from .errors import LnosError

logger = logging.getLogger("lnos.compliance")


# --- Deny-list (§4.4 verbatim) ----------------------------------------------
# (canonical label, compiled pattern). Word-boundary, case-insensitive.
_DENY_SPECS: tuple[tuple[str, str], ...] = (
    ("expect", r"expect(?:s|ed|ing|ation|ations)?"),
    ("poised", r"poised"),
    ("set to", r"set\s+to"),
    ("will outperform", r"will\s+outperform"),
    ("predict", r"predict(?:s|ed|ing|ion|ions|able)?"),
    ("forecast", r"forecast(?:s|ed|ing)?"),
    ("recommend", r"recommend(?:s|ed|ing|ation|ations)?"),
    ("should buy/sell", r"should\s+(?:buy|sell)"),
    ("return", r"returns?"),
    ("performance", r"performance"),
    ("outlook", r"outlook"),
)
_DENY_PATTERNS: tuple[tuple[str, re.Pattern], ...] = tuple(
    (label, re.compile(rf"\b{pat}\b", re.IGNORECASE)) for label, pat in _DENY_SPECS
)

# Plain phrasing of what the standing footer line must convey (§4.2 section 6).
STANDING_DISCLOSURE_LINE = (
    "This is a local marketing-opportunity brief, not investment advice or a "
    "market forecast."
)

SYSTEM_PROMPT_CONSTRAINTS = f"""\
You are writing prose for a Carson Wealth *Local Marketing Opportunity Brief*.
This is a MARKETING document about local outreach opportunity — never market
commentary, never investment advice, never a forecast.

Hard rules (a single violation makes the draft unusable):
- Do NOT use forward-looking market language: no "expect", "poised", "set to",
  "will outperform", "predict", "forecast", "outlook", or any claim about what
  the market, a sector, or an investment WILL do.
- Do NOT take a client-advice posture: no "recommend", no "should buy/sell",
  no advising anyone to take an investment action.
- Do NOT use investment return/performance framing: no "return(s)", no
  "performance".
- Do NOT state numeric scores or rankings as numbers (ranking is words only).
- Frame everything as marketing/outreach context for the firm — who to reach,
  which local signal supports outreach, which Carson asset delivers it.

Voice: {VOICE}
Write tight, concrete prose. No disclosures (those are templated separately).
"""


# --- Lint -------------------------------------------------------------------
@dataclass
class LintHit:
    label: str          # canonical deny-list term
    matched: str        # the actual text that matched
    start: int


@dataclass
class LintResult:
    ok: bool
    hits: list[LintHit] = field(default_factory=list)

    def summary(self) -> str:
        return ", ".join(f"{h.label!r}→{h.matched!r}" for h in self.hits)


def lint(text: str) -> LintResult:
    """Scan generated prose against the deny-list. ok=False on any hit."""
    hits: list[LintHit] = []
    for label, pattern in _DENY_PATTERNS:
        for m in pattern.finditer(text or ""):
            hits.append(LintHit(label=label, matched=m.group(0), start=m.start()))
    hits.sort(key=lambda h: h.start)
    return LintResult(ok=not hits, hits=hits)


# --- Generate-with-retry-then-block -----------------------------------------
class ComplianceBlocked(LnosError):
    """Raised when generated prose still trips the lint after N attempts.

    The draft is NOT returned — blocking is the safe failure (§4.4).
    """


@dataclass
class CompliantText:
    text: str
    attempts: int


def generate_compliant(
    generate_fn: Callable[[int], str],
    *,
    max_attempts: int = 3,
    section: str = "prose",
) -> CompliantText:
    """Call `generate_fn(attempt)` until its output passes the lint, then block.

    `generate_fn` takes the attempt index (0-based) so it can vary temperature/
    nudge on retry, and returns the raw prose. We never ship a draft that trips
    the lint; instead we raise ComplianceBlocked.
    """
    last: Optional[LintResult] = None
    for attempt in range(max_attempts):
        text = generate_fn(attempt)
        result = lint(text)
        if result.ok:
            return CompliantText(text=text, attempts=attempt + 1)
        last = result
        logger.warning(
            "Compliance lint hit in %s (attempt %d/%d): %s",
            section, attempt + 1, max_attempts, result.summary(),
        )
    raise ComplianceBlocked(
        f"{section}: generated prose tripped the compliance deny-list after "
        f"{max_attempts} attempts ({last.summary() if last else 'n/a'}). "
        f"Draft blocked — not shipped."
    )


# --- D2 label boundary ------------------------------------------------------
# Field names that are INTERNAL scorer labels/metrics and must never reach a
# firm-facing section/docx builder (D1/D2).
_FORBIDDEN_FIRM_FACING_KEYS = frozenset({
    "opp", "read", "wealth", "demand", "saturation",
    "bucket", "quadrant", "score", "scorer_output",
})


def assert_no_scorer_labels(payload) -> None:
    """Hard boundary: raise if a firm-facing payload carries scorer internals.

    Accepts a mapping or an object; checks keys/attributes against the forbidden
    set. This is the safeguard (D2) — the label rename is only backup insurance.
    """
    if isinstance(payload, dict):
        present = _FORBIDDEN_FIRM_FACING_KEYS & {str(k).lower() for k in payload}
    else:
        present = {k for k in _FORBIDDEN_FIRM_FACING_KEYS if hasattr(payload, k)}
    if present:
        raise LnosError(
            f"D2 boundary violation: firm-facing payload carries scorer "
            f"internals {sorted(present)}. Scores/labels never reach the brief."
        )
