"""Brief generator — fixed 6-section template (§4.2).

Same shape for every firm; variability lives only in the firm record and data.
This module assembles the six sections as a content model; the branded .docx
rendering is Phase 7 (docx_export.py) and the app-only delivery wrapper is
Phase 8 — kept in separate functions that don't share state (§4.5).

Section ownership of the guardrails:
  * Sections 2–4 are LLM prose, generated through compliance.generate_compliant
    (system-prompt constraints + post-gen deny-list lint, §4.4). An LLM client
    is INJECTED so the module is testable and provider-agnostic.
  * Section 5 (Where to Start) is "scorer logic applied: ranked play order".
    The ranking is DERIVED FROM SCORER OUTPUT, which is §2.1 — so
    `rank_plays_from_scorer` is a loud blocked stub. The renderer that turns an
    already-ranked list into prose is built (ranking only, NO numbers — D1).
  * Section 6 is the firm's APPROVED disclosure block, templated VERBATIM, plus
    the standing line. We never draft disclosure language (§4.4).

D2 boundary: only `firm_facing_context` data reaches the section builders, and
it is asserted clean of scorer internals before any prose is generated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional, Protocol

from . import compliance
from .compliance import SYSTEM_PROMPT_CONSTRAINTS, STANDING_DISCLOSURE_LINE
from .errors import LnosError, MethodologyNotProvided
from .firm_record import FirmRecord, NicheTaxonomy, validate_firm_record
from .snapshot import Snapshot

# Fixed section titles (§4.2). Order is load-bearing.
SECTION_TITLES = (
    "Local Market Snapshot",
    "Local Signal Read",
    "Niche Alignment",
    "Recommended Plays",
    "Where to Start",
    "Compliance Footer",
)

DEFAULT_MODEL = "claude-opus-4-8"


class LLMUnavailable(LnosError):
    """Raised when sections 2–4 are requested but no LLM client is available.

    This is a fail-loud (cannot generate), never a fabricated section.
    """


# --- Section / brief model --------------------------------------------------
@dataclass
class Section:
    number: int
    title: str
    body: str


@dataclass
class Brief:
    firm_id: str
    firm_legal_name: str
    generated_on: str
    sections: list[Section] = field(default_factory=list)

    def filename_base(self) -> str:
        """[Firm]-Local-Opportunity-Brief-[YYYY-MM-DD] (extension added by export)."""
        safe = "".join(c if c.isalnum() else "-" for c in self.firm_legal_name)
        safe = "-".join(p for p in safe.split("-") if p)
        return f"{safe}-Local-Opportunity-Brief-{self.generated_on}"


@dataclass
class BlockedBrief:
    """The fail-loud result: a message and NO document (§4.1)."""

    message: str


@dataclass
class RankedPlay:
    name: str
    reasoning: str   # plain language; NO numeric score (D1)


# --- LLM client (injected) --------------------------------------------------
class LLMClient(Protocol):
    def complete(self, *, system: str, prompt: str, temperature: float) -> str: ...


class ClaudeClient:
    """Default LLM client (Anthropic). Optional — import-guarded.

    Uses the latest capable Claude model for section 2–4 prose. Requires
    ANTHROPIC_API_KEY; raises LLMUnavailable if the SDK/key are absent so the
    caller fails loud instead of fabricating.
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:
            raise LLMUnavailable(
                "anthropic SDK not installed — cannot generate sections 2–4. "
                "`pip install anthropic` and set ANTHROPIC_API_KEY."
            ) from exc
        import os
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise LLMUnavailable("ANTHROPIC_API_KEY not set — cannot generate prose.")
        self._anthropic = __import__("anthropic")
        self._client = self._anthropic.Anthropic()
        self.model = model

    def complete(self, *, system: str, prompt: str, temperature: float) -> str:
        msg = self._client.messages.create(
            model=self.model, max_tokens=1024, temperature=temperature,
            system=system, messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


# --- D2 boundary: firm-facing context ---------------------------------------
def firm_facing_context(firm_record: FirmRecord, snapshot: Snapshot) -> dict:
    """Build the ONLY data dict that reaches section builders — no scorer fields.

    Asserts clean of scorer internals (D2) before returning.
    """
    ctx = {
        "legal_name": firm_record.legal_name,
        "county": firm_record.county,
        "cbsa": firm_record.cbsa,
        "niche_profile": firm_record.niche_profile,
        "local_employers": list(firm_record.local_employers),
        "channel_inventory": list(firm_record.channel_inventory),
        "snapshot_facts": [m.display() for m in snapshot.available_metrics],
        "snapshot_narrowed": snapshot.narrowed,
    }
    compliance.assert_no_scorer_labels(ctx)
    return ctx


# --- Section builders -------------------------------------------------------
def build_section1_snapshot(snapshot: Snapshot) -> Section:
    """FRED facts, presented cleanly, NO interpretation (§4.2)."""
    lines = [m.display() for m in snapshot.metrics]
    if snapshot.is_thin:
        lines.append(
            "Note: current data is thin for this market; the snapshot above is "
            "narrowed to what could be confirmed.")
    return Section(1, SECTION_TITLES[0], "\n".join(lines))


def _prose_section(
    number: int, ctx: dict, instruction: str, llm: LLMClient, *, max_attempts: int = 3
) -> Section:
    title = SECTION_TITLES[number - 1]

    def _generate(attempt: int) -> str:
        prompt = (
            f"{instruction}\n\nFirm context (marketing only):\n"
            f"- Niche: {ctx['niche_profile']}\n"
            f"- Market: {ctx['county']} / {ctx['cbsa']}\n"
            f"- Local employers/sectors: {', '.join(ctx['local_employers'])}\n"
            f"- Channels the firm can execute: {', '.join(ctx['channel_inventory'])}\n"
            f"- Confirmed local facts: {ctx['snapshot_facts'] or 'none confirmed'}\n"
            f"- Thin/unavailable data (narrow these, do not fill in): "
            f"{ctx['snapshot_narrowed'] or 'none'}\n"
        )
        return llm.complete(
            system=SYSTEM_PROMPT_CONSTRAINTS, prompt=prompt,
            temperature=min(0.3 + 0.2 * attempt, 0.9))

    result = compliance.generate_compliant(
        _generate, max_attempts=max_attempts, section=title)
    return Section(number, title, result.text.strip())


def build_section2_signal_read(ctx: dict, llm: LLMClient) -> Section:
    return _prose_section(
        2, ctx, llm=llm,
        instruction=(
            "Write 2–4 observations on local employer/sector/demographic "
            "movement, framed strictly as MARKETING/outreach context — who is "
            "in this market to reach. Never a market prediction or event."))


def build_section3_niche_alignment(ctx: dict, llm: LLMClient) -> Section:
    return _prose_section(
        3, ctx, llm=llm,
        instruction=(
            "Bridge the local signal to the firm's Blue Ocean niche. If the "
            "niche does not intersect the strongest local signal, say so plainly "
            "and point to the signal it does intersect."))


def build_section4_recommended_plays(ctx: dict, llm: LLMClient) -> Section:
    return _prose_section(
        4, ctx, llm=llm,
        instruction=(
            "Describe 2–3 specific marketing activations. Each must name the "
            "Carson asset/kit that delivers it, be staffable on the firm's "
            "existing channels, and state the marketing opportunity it captures. "
            "No investment-advice language."))


def rank_plays_from_scorer(scorer_output, plays: list[RankedPlay]) -> list[RankedPlay]:
    """Order the plays using scorer logic for section 5.

    BLOCKED: the ranking derives from Opp/Read (the §2.1 methodology). This
    raises rather than inventing an order.
    """
    raise MethodologyNotProvided("Where-to-Start ranking (scorer-derived)")


def build_section5_where_to_start(ranked_plays: list[RankedPlay]) -> Section:
    """Render an ALREADY-ranked play order with reasoning. Ranking only — no
    numeric score reaches the firm (D1). The ordering itself comes from
    rank_plays_from_scorer (blocked on §2.1)."""
    if not ranked_plays:
        raise LnosError("Where to Start requires a ranked play order.")
    lines = [f"{i}. {p.name} — {p.reasoning}" for i, p in enumerate(ranked_plays, 1)]
    lines.append("Start with #1.")
    return Section(5, SECTION_TITLES[4], "\n".join(lines))


def build_section6_compliance_footer(firm_record: FirmRecord) -> Section:
    """Firm's APPROVED disclosure block, VERBATIM, plus the standing line.

    Disclosure is never generated — only templated (§4.4).
    """
    if not firm_record.disclosure_block or not firm_record.disclosure_block.strip():
        raise LnosError(
            "Compliance footer requires the firm's approved disclosure block "
            "(verbatim) — it is never generated.")
    body = f"{firm_record.disclosure_block.strip()}\n\n{STANDING_DISCLOSURE_LINE}"
    return Section(6, SECTION_TITLES[5], body)


# --- Orchestrator -----------------------------------------------------------
def generate_brief(
    firm_record: FirmRecord,
    snapshot: Snapshot,
    *,
    llm: Optional[LLMClient] = None,
    ranked_plays: Optional[list[RankedPlay]] = None,
    taxonomy: Optional[NicheTaxonomy] = None,
):
    """Assemble the full 6-section brief, or fail loud.

    Returns a `Brief` on success, or a `BlockedBrief` (message, no document) if
    the input contract is not satisfied (§4.1). Sections 2–4 require an LLM
    client; section 5 requires a `ranked_plays` order (whose scorer-derived
    source is blocked on §2.1).
    """
    contract = validate_firm_record(firm_record, taxonomy=taxonomy)
    if not contract.ok:
        return BlockedBrief(message=contract.message())

    if llm is None:
        raise LLMUnavailable(
            "No LLM client provided — sections 2–4 cannot be generated. "
            "Pass a ClaudeClient (or compatible) to generate_brief.")
    if ranked_plays is None:
        raise MethodologyNotProvided(
            "Where-to-Start ranking — provide a scorer-derived ranked play order")

    ctx = firm_facing_context(firm_record, snapshot)
    sections = [
        build_section1_snapshot(snapshot),
        build_section2_signal_read(ctx, llm),
        build_section3_niche_alignment(ctx, llm),
        build_section4_recommended_plays(ctx, llm),
        build_section5_where_to_start(ranked_plays),
        build_section6_compliance_footer(firm_record),
    ]
    return Brief(
        firm_id=firm_record.firm_id or "",
        firm_legal_name=firm_record.legal_name or "firm",
        generated_on=date.today().isoformat(),
        sections=sections,
    )
