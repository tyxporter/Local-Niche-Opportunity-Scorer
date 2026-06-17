"""Blue Ocean niche auto-selection.

Given the eight profiles (Ty's framework) and a firm's data — geography, market
snapshot, local employers/sectors, AUM — Claude SELECTS the single best-fit
profile and explains why. This is an internal classification (a recommendation
surfaced for confirmation in the app), not firm-facing prose, so it is not
subject to the §4.4 prose lint. The pick is constrained to the defined eight
(validated), so the model classifies — it never invents a profile.

Requires the taxonomy (profiles) and an LLM client. Degrades gracefully: if the
taxonomy is absent, the LLM is unavailable, or the model returns something off
the list, it returns an unavailable selection rather than guessing silently.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from .firm_record import NicheTaxonomy

_SYSTEM = (
    "You classify a wealth-management firm's primary client niche by choosing "
    "exactly ONE profile from a fixed list. You never invent a profile. "
    "Respond ONLY with JSON: {\"profile\": \"<exact name from the list>\", "
    "\"rationale\": \"<one sentence, marketing/segmentation reasoning>\"}."
)


@dataclass
class NicheSelection:
    available: bool
    profile: Optional[str] = None
    rationale: str = ""


def select_niche(*, taxonomy: NicheTaxonomy, firm_context: dict, llm) -> NicheSelection:
    """Pick the best-fit profile for a firm from the taxonomy, with reasoning."""
    if not taxonomy.available or not taxonomy.profiles:
        return NicheSelection(False, rationale="Blue Ocean taxonomy not provided.")
    if llm is None:
        return NicheSelection(False, rationale="No LLM available for niche selection.")

    profile_lines = "\n".join(
        f"- {name}" + (f": {taxonomy.descriptions[name]}"
                       if name in taxonomy.descriptions else "")
        for name in taxonomy.profiles)
    prompt = (
        "Profiles (choose exactly one by its exact name):\n" + profile_lines +
        "\n\nFirm data:\n" +
        f"- Market: {firm_context.get('county')} / {firm_context.get('cbsa')}\n" +
        f"- Median household income: {firm_context.get('mhi')}\n" +
        f"- County unemployment: {firm_context.get('unemployment')}\n" +
        f"- Home price index: {firm_context.get('hpi')}\n" +
        f"- Local employers/sectors: {firm_context.get('employers')}\n" +
        f"- Firm AUM (USD): {firm_context.get('aum')}\n\n" +
        "Choose the single best-fit profile.")

    try:
        raw = llm.complete(system=_SYSTEM, prompt=prompt, temperature=0)
    except Exception as exc:  # noqa: BLE001 - degrade gracefully
        return NicheSelection(False, rationale=f"selection failed: {type(exc).__name__}")

    profile, rationale = _parse(raw)
    match = _match_profile(profile, taxonomy.profiles)
    if not match:
        return NicheSelection(
            False, rationale=f"model returned an off-list profile ({profile!r}).")
    return NicheSelection(True, profile=match, rationale=rationale or "")


def _parse(raw: str):
    """Extract (profile, rationale) from the model's JSON (tolerant)."""
    if not raw:
        return None, ""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            return (obj.get("profile"), obj.get("rationale", ""))
        except json.JSONDecodeError:
            pass
    return raw.strip().splitlines()[0].strip(), ""


def _match_profile(value: Optional[str], profiles) -> Optional[str]:
    if not value:
        return None
    v = value.strip().lower()
    for p in profiles:
        if p.lower() == v:
            return p
    for p in profiles:  # tolerant: model echoed extra words around the name
        if p.lower() in v or v in p.lower():
            return p
    return None
