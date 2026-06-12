"""Streamlit shell (§6, Phase 8) — UI + delivery wrapper.

Internal app for the Local Niche Opportunity Scorer / Local Marketing
Opportunity Brief. It is the working surface: pick a firm, complete the firm
record, see the fail-loud input contract live, preview the snapshot, generate
the branded .docx, and read the app-only delivery wrapper beside it.

Guardrails honored in the UI:
  * The firm-facing .docx and the internal delivery wrapper are rendered by
    SEPARATE functions that share no state (§4.5). The wrapper never goes in
    the document.
  * Sections 2–4 prose runs through the compliance lint (§4.4). With no
    ANTHROPIC_API_KEY, the app offers a clearly-watermarked PREVIEW prose mode
    for layout only — never represented as client-ready.
  * The scorer-derived Where-to-Start ranking is §2.1 (blocked); until then Ty
    hand-orders the plays in the UI.
"""

from __future__ import annotations

import os

import streamlit as st

from lnos import brand, firms as firms_mod
from lnos import firm_record as fr
from lnos import snapshot as snap_mod
from lnos import brief as brief_mod
from lnos import delivery as delivery_mod
from lnos import docx_export
from lnos.brief import RankedPlay, Brief, BlockedBrief, LLMUnavailable
from lnos.compliance import ComplianceBlocked

st.set_page_config(page_title="Local Niche Opportunity Scorer",
                   page_icon="◆", layout="wide")

# --- brand styling ----------------------------------------------------------
st.markdown(f"""
<style>
:root {{ --navy:{brand.NAVY}; --gold:{brand.GOLD}; }}
.stApp {{ background:{brand.GOLD_TINT_10}; }}
h1, h2, h3 {{ color:{brand.NAVY}; font-family:'Helvetica Neue',Helvetica,Arial,sans-serif; }}
.lnos-tag {{ color:{brand.GRAY_DARK}; font-size:0.85rem; }}
.lnos-card {{ background:#fff; border-left:4px solid {brand.GOLD};
             padding:0.8rem 1rem; border-radius:2px; margin-bottom:0.6rem; }}
div.stButton > button {{ background:{brand.NAVY}; color:#fff; border:0;
             border-radius:2px; font-weight:600; }}
div.stButton > button:hover {{ background:{brand.GOLD}; color:{brand.NAVY}; }}
</style>
""", unsafe_allow_html=True)


# --- preview LLM (no key) ---------------------------------------------------
class PreviewLLM:
    """Layout-only placeholder prose when no ANTHROPIC_API_KEY is set.

    Output is compliance-clean and clearly marked as preview — NOT client-ready.
    """

    _TEXT = {
        "Local Signal Read": (
            "[PREVIEW] Local employers and sectors anchor this market, and the "
            "firm's niche audience is reachable through its existing channels. "
            "This is outreach context only."),
        "Niche Alignment": (
            "[PREVIEW] The firm's niche maps onto the dominant local audience; "
            "where it does not intersect the strongest signal, lead with the "
            "audience it does."),
        "Recommended Plays": (
            "[PREVIEW] Two to three marketing activations, each delivered with a "
            "named Carson asset/kit and staffable on the firm's existing "
            "channels."),
    }

    def complete(self, *, system, prompt, temperature):
        for title, text in self._TEXT.items():
            if title.lower() in prompt.lower() or title in system:
                return text
        # Fall back by matching the instruction keywords.
        if "observations" in prompt:
            return self._TEXT["Local Signal Read"]
        if "Bridge" in prompt or "niche" in prompt:
            return self._TEXT["Niche Alignment"]
        return self._TEXT["Recommended Plays"]


def _llm(preview: bool):
    if not preview and os.environ.get("ANTHROPIC_API_KEY"):
        from lnos.brief import ClaudeClient
        return ClaudeClient()
    return PreviewLLM()


# --- data -------------------------------------------------------------------
@st.cache_data
def load_spine():
    return firms_mod.load_firms()


@st.cache_data
def load_taxonomy():
    return fr.load_niche_taxonomy()


spine = load_spine()
taxonomy = load_taxonomy()
by_name = {f.roster_name: f for f in spine}

st.title("Local Niche Opportunity Scorer")
st.markdown('<div class="lnos-tag">Internal tool · generates the firm-facing '
            '<b>Local Marketing Opportunity Brief</b></div>', unsafe_allow_html=True)

# --- status banners ---------------------------------------------------------
if not taxonomy.available:
    st.warning("Blue Ocean niche taxonomy not provided yet — niche validation is "
               "blocked (open item #4). Enter a niche as free text for now.")
if not os.environ.get("ANTHROPIC_API_KEY"):
    st.info("ANTHROPIC_API_KEY not set — sections 2–4 use PREVIEW placeholder "
            "prose (layout only, not client-ready). Set the key for live copy.")

# --- sidebar: firm picker ---------------------------------------------------
with st.sidebar:
    st.header("Firm")
    pick = st.selectbox("Select a firm (47 in spine)", list(by_name.keys()))
    firm = by_name[pick]
    st.markdown(f"<div class='lnos-card'><b>{firm.roster_name}</b><br>"
                f"<span class='lnos-tag'>firm_id: {firm.firm_id}<br>"
                f"AUM: {'—' if firm.aum_usd is None else f'${firm.aum_usd_m:,.1f}M'}"
                f"{' (pending)' if firm.aum_pending else ''}<br>"
                f"Geography: {'resolved' if firm.has_geography else 'pending (F2)'}"
                f"{f' · suggested: {firm.city_suggested}' if firm.city_suggested else ''}"
                f"</span></div>", unsafe_allow_html=True)
    existing = fr.record_path(firm.firm_id).exists()
    st.caption("Saved record found." if existing else "No saved record yet.")

# --- firm record form -------------------------------------------------------
st.header("1 · Firm record")
prefill = fr.load_firm_record(firm.firm_id) if existing else fr.FirmRecord(
    firm_id=firm.firm_id, legal_name=firm.roster_name,
    county=firm.county, cbsa=firm.cbsa, aum_usd=firm.aum_usd)

c1, c2 = st.columns(2)
with c1:
    legal_name = st.text_input("Firm legal name *", prefill.legal_name or "")
    county = st.text_input("County *", prefill.county or (firm.county or ""))
    cbsa = st.text_input("Metro / CBSA *", prefill.cbsa or (firm.cbsa or ""))
    niche_opts = list(taxonomy.profiles) if taxonomy.available else []
    if niche_opts:
        niche = st.selectbox("Blue Ocean niche profile *", niche_opts,
                             index=niche_opts.index(prefill.niche_profile)
                             if prefill.niche_profile in niche_opts else 0)
    else:
        niche = st.text_input("Blue Ocean niche profile * (taxonomy pending)",
                              prefill.niche_profile or "")
with c2:
    compliance_structure = st.selectbox(
        "Compliance structure *",
        [s.value for s in fr.ComplianceStructure],
        index=0 if (prefill.compliance_structure or "").startswith("Carson") else 1)
    local_employers = st.text_area(
        "Top local employers / sectors * (comma-separated)",
        ", ".join(prefill.local_employers))
    channel_inventory = st.text_area(
        "Channel inventory * (comma-separated)",
        ", ".join(prefill.channel_inventory))
disclosure_block = st.text_area(
    "Approved disclosure block * (verbatim — never generated)",
    prefill.disclosure_block or "", height=90)

record = fr.FirmRecord(
    firm_id=firm.firm_id, legal_name=legal_name or None, county=county or None,
    cbsa=cbsa or None, niche_profile=niche or None,
    local_employers=fr.FirmRecord._as_list(local_employers),
    compliance_structure=compliance_structure,
    disclosure_block=disclosure_block or None,
    channel_inventory=fr.FirmRecord._as_list(channel_inventory),
    aum_usd=firm.aum_usd)

validation = fr.validate_firm_record(record, taxonomy=taxonomy)
if validation.ok:
    st.success("Input contract satisfied — ready to generate.")
else:
    st.error("Cannot generate — fix the following (fail-loud, §4.1):")
    for fld, reason, owner in validation.problems:
        st.markdown(f"- **{reason} {fld}** — owner *{owner}*")

cols = st.columns(3)
if cols[0].button("Save record"):
    fr.save_firm_record(record)
    st.toast("Saved.")

# --- snapshot preview -------------------------------------------------------
st.header("2 · Local market snapshot (section 1 preview)")
snapshot = snap_mod.build_snapshot(firm.firm_id)
for m in snapshot.metrics:
    st.markdown(f"- {m.display()}")
if snapshot.is_thin:
    st.caption("Snapshot is thin — narrowed to confirmed facts (§4.3). Resolves "
               "once geography→FIPS lands (F2) and FRED_API_KEY is set.")

# --- where to start (manual ranking until §2.1) -----------------------------
st.header("3 · Where to start (rank plays)")
st.caption("Scorer-derived ranking is blocked on §2.1 — hand-order the plays "
           "for now. Ranking only, no numbers reach the firm (D1).")
n = st.number_input("How many plays?", 1, 3, 2)
ranked = []
for i in range(int(n)):
    a, b = st.columns([1, 2])
    name = a.text_input(f"Play {i+1} name", key=f"pn{i}")
    why = b.text_input(f"Play {i+1} reasoning", key=f"pr{i}")
    if name:
        ranked.append(RankedPlay(name, why))

# --- generate ---------------------------------------------------------------
st.header("4 · Generate brief")
preview_mode = st.checkbox("Preview prose (placeholder, layout only)",
                           value=not bool(os.environ.get("ANTHROPIC_API_KEY")))
if st.button("Generate .docx", type="primary"):
    if not ranked:
        st.error("Add at least one ranked play (section 5).")
    else:
        try:
            result = brief_mod.generate_brief(
                record, snapshot, llm=_llm(preview_mode),
                ranked_plays=ranked, taxonomy=taxonomy)
        except ComplianceBlocked as e:
            st.error(f"Compliance lint blocked the draft — not shipped. {e}")
            result = None
        except (LLMUnavailable, Exception) as e:  # noqa: BLE001
            st.error(f"Generation error: {e}")
            result = None
        if isinstance(result, BlockedBrief):
            st.error("Cannot generate — missing inputs:\n\n" + result.message)
        elif isinstance(result, Brief):
            path = docx_export.render_brief_docx(result, out_dir="/tmp/lnos_out")
            st.success(f"Generated {path.name}")
            for s in result.sections:
                with st.expander(f"{s.number}. {s.title}", expanded=s.number <= 2):
                    st.write(s.body)
            with open(path, "rb") as fh:
                st.download_button("Download .docx", fh, file_name=path.name)

# --- delivery wrapper (APP-ONLY, separate render) ---------------------------
st.header("5 · Delivery wrapper (internal — never in the .docx)")
ty_read = st.text_area("Your prioritization read (which play to lead with & why)", "")
wrapper = delivery_mod.build_delivery_wrapper(
    record, prioritization_read=ty_read or None, validation=validation,
    taxonomy=taxonomy)
st.markdown(f"<div class='lnos-card'><b>Prioritization read</b><br>"
            f"{wrapper.prioritization_read}</div>", unsafe_allow_html=True)
if wrapper.cetera_reminder:
    st.warning(wrapper.cetera_reminder)
if wrapper.missing_input_flags:
    st.markdown("**Missing-input flags:**")
    for f in wrapper.missing_input_flags:
        st.markdown(f"- {f}")
st.markdown(f"<div class='lnos-card'><b>Suggested intro</b><br>"
            f"{wrapper.suggested_intro}</div>", unsafe_allow_html=True)
