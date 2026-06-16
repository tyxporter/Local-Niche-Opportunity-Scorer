"""Streamlit shell (§6, Phase 8) — UI + delivery wrapper.

Internal app for the Local Niche Opportunity Scorer / Local Marketing
Opportunity Brief. Pick a firm, complete the firm record, see the fail-loud
input contract live, preview the snapshot, generate the branded .docx, and read
the app-only delivery wrapper beside it.

Guardrails honored in the UI:
  * The firm-facing .docx and the internal delivery wrapper are rendered by
    SEPARATE functions that share no state (§4.5).
  * Sections 2–4 prose runs through the compliance lint (§4.4). With no
    ANTHROPIC_API_KEY, the app uses a clearly-watermarked PREVIEW prose mode for
    layout only — never represented as client-ready.
  * The scorer-derived Where-to-Start ranking is §2.1 (blocked); until then Ty
    hand-orders the plays in the UI.
"""

from __future__ import annotations

import os

import streamlit as st


# --- Secrets bridge ---------------------------------------------------------
# On Streamlit Community Cloud, secrets land in st.secrets, NOT os.environ.
# Our data/LLM layers read os.environ, so mirror them across once at startup.
def _load_secrets_into_env() -> None:
    keys = ("ANTHROPIC_API_KEY", "FRED_API_KEY", "CENSUS_API_KEY", "LNOS_MODEL")
    try:
        secrets = st.secrets
    except Exception:
        return
    for k in keys:
        try:
            if not os.environ.get(k) and k in secrets:
                os.environ[k] = str(secrets[k])
        except Exception:
            continue


_load_secrets_into_env()

from lnos import brand, firms as firms_mod          # noqa: E402
from lnos import firm_record as fr                  # noqa: E402
from lnos import snapshot as snap_mod               # noqa: E402
from lnos import brief as brief_mod                 # noqa: E402
from lnos import delivery as delivery_mod           # noqa: E402
from lnos import docx_export                        # noqa: E402
from lnos.brief import RankedPlay, Brief, BlockedBrief, LLMUnavailable  # noqa: E402
from lnos.compliance import ComplianceBlocked       # noqa: E402

st.set_page_config(page_title="Local Niche Opportunity Scorer",
                   page_icon="◆", layout="wide",
                   initial_sidebar_state="expanded")

# --- brand styling ----------------------------------------------------------
st.markdown(f"""
<style>
  #MainMenu, footer, header[data-testid="stHeader"] {{ visibility:hidden; }}
  .stApp {{ background:{brand.GOLD_TINT_10};
            font-family:"Helvetica Neue LT Pro","Helvetica Neue",Helvetica,Arial,sans-serif; }}
  .block-container {{ padding-top:1.2rem; max-width:1180px; }}
  h1,h2,h3,h4 {{ color:{brand.NAVY}; letter-spacing:-0.01em; }}

  /* Branded header band with a 30/60 chevron accent (§5 geometry) */
  .lnos-band {{ position:relative; overflow:hidden; background:{brand.NAVY};
    color:#fff; padding:1.3rem 1.6rem; border-radius:4px; margin-bottom:1rem; }}
  .lnos-band:after {{ content:""; position:absolute; top:0; right:-40px; width:160px;
    height:100%; background:{brand.GOLD}; transform:skewX(-30deg); opacity:.92; }}
  .lnos-band:before {{ content:""; position:absolute; top:0; right:60px; width:80px;
    height:100%; background:{brand.LIGHT_GOLD}; transform:skewX(-30deg); opacity:.55; }}
  .lnos-logo {{ font-weight:800; font-size:.82rem; letter-spacing:.22em;
    color:{brand.LIGHT_GOLD}; }}
  .lnos-logo span {{ color:#fff; }}
  .lnos-title {{ font-size:1.7rem; font-weight:800; margin:.15rem 0 0; }}
  .lnos-sub {{ color:{brand.GRAY_LIGHT}; font-size:.92rem; }}

  /* status chips */
  .chips {{ display:flex; flex-wrap:wrap; gap:.4rem; margin:.2rem 0 1rem; }}
  .chip {{ font-size:.74rem; font-weight:600; padding:.22rem .6rem; border-radius:999px;
    border:1px solid transparent; }}
  .chip-ok {{ background:{brand.GOLD_TINT_50}; color:#5b4a16; border-color:{brand.GOLD}; }}
  .chip-wait {{ background:#fff; color:{brand.GRAY_DARK}; border-color:{brand.GRAY_MID}; }}

  h2 {{ border-bottom:2px solid {brand.GOLD}; padding-bottom:.25rem; margin-top:1.4rem; }}
  div.stButton > button {{ background:{brand.NAVY}; color:#fff; border:0; border-radius:3px;
    font-weight:700; padding:.45rem 1.1rem; }}
  div.stButton > button:hover {{ background:{brand.GOLD}; color:{brand.NAVY}; }}
  .sidebar-card {{ background:{brand.NAVY}; color:#fff; padding:.8rem .9rem; border-radius:4px; }}
  .sidebar-card .k {{ color:{brand.LIGHT_GOLD}; font-size:.78rem; }}
  .internal {{ background:{brand.GOLD_TINT_25}; border:1px dashed {brand.GOLD};
    padding:.2rem .2rem .2rem .9rem; border-radius:4px; }}
</style>
""", unsafe_allow_html=True)


# --- preview LLM (no key) ---------------------------------------------------
class PreviewLLM:
    """Layout-only placeholder prose when no ANTHROPIC_API_KEY is set.
    Output is compliance-clean and clearly marked — NOT client-ready."""

    _TEXT = {
        "signal": ("[PREVIEW] Local employers and sectors anchor this market, and "
                   "the firm's niche audience is reachable through its existing "
                   "channels. This is outreach context only."),
        "niche": ("[PREVIEW] The firm's niche maps onto the dominant local "
                  "audience; where it does not intersect the strongest signal, "
                  "lead with the audience it does."),
        "plays": ("[PREVIEW] Two to three marketing activations, each delivered "
                  "with a named Carson asset/kit and staffable on the firm's "
                  "existing channels."),
    }

    def complete(self, *, system, prompt, temperature):
        if "observations" in prompt:
            return self._TEXT["signal"]
        if "Bridge" in prompt or "niche" in prompt:
            return self._TEXT["niche"]
        return self._TEXT["plays"]


def _llm(preview: bool):
    if not preview and os.environ.get("ANTHROPIC_API_KEY"):
        return brief_mod.ClaudeClient()
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
ss = st.session_state
ss.setdefault("generated", {})  # firm_id -> dict(path, sections)

have_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
have_fred = bool(os.environ.get("FRED_API_KEY"))


def chip(label: str, ok: bool) -> str:
    return f'<span class="chip {"chip-ok" if ok else "chip-wait"}">{label}</span>'


# --- header -----------------------------------------------------------------
st.markdown(
    '<div class="lnos-band">'
    '<div class="lnos-logo">CARSON <span>WEALTH</span></div>'
    '<div class="lnos-title">Local Niche Opportunity Scorer</div>'
    '<div class="lnos-sub">Internal tool — generates the firm-facing '
    'Local Marketing Opportunity Brief</div></div>',
    unsafe_allow_html=True)

# --- sidebar: firm picker ---------------------------------------------------
with st.sidebar:
    st.subheader("Firm")
    pick = st.selectbox("Select a firm (47 in spine)", list(by_name.keys()))
    firm = by_name[pick]
    geo = "resolved" if firm.has_geography else "pending (F2)"
    sugg = f" · suggested {firm.city_suggested}" if firm.city_suggested else ""
    aum = "—" if firm.aum_usd is None else f"${firm.aum_usd_m:,.1f}M"
    st.markdown(
        f"<div class='sidebar-card'><b>{firm.roster_name}</b><br>"
        f"<span class='k'>firm_id</span> {firm.firm_id}<br>"
        f"<span class='k'>AUM</span> {aum}{' (pending)' if firm.aum_pending else ''}<br>"
        f"<span class='k'>geography</span> {geo}{sugg}</div>", unsafe_allow_html=True)
    existing = fr.record_path(firm.firm_id).exists()
    st.caption("✓ Saved record found." if existing else "No saved record yet.")
    st.divider()
    st.caption("Logo placeholder — supply the Carson Wealth lockup to brand the "
               ".docx header.")

# --- live/pending status ----------------------------------------------------
st.markdown(
    '<div class="chips">'
    + chip("Live copy (Claude)" if have_anthropic else "Preview prose — add ANTHROPIC_API_KEY", have_anthropic)
    + chip("FRED connected" if have_fred else "FRED key missing", have_fred)
    + chip("Niche taxonomy loaded" if taxonomy.available else "Niche taxonomy pending (#4)", taxonomy.available)
    + chip("Geography resolved" if firm.has_geography else "Geography pending (F2)", firm.has_geography)
    + chip("Scoring spec pending (§2.1)", False)
    + '</div>', unsafe_allow_html=True)

# --- firm record form -------------------------------------------------------
st.header("1 · Firm record")
prefill = fr.load_firm_record(firm.firm_id) if existing else fr.FirmRecord(
    firm_id=firm.firm_id, legal_name=firm.roster_name.replace("-CIA", ""),
    county=firm.county, cbsa=firm.cbsa, aum_usd=firm.aum_usd)

with st.container(border=True):
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
            "Compliance structure *", [s.value for s in fr.ComplianceStructure],
            index=0 if (prefill.compliance_structure or "Carson").startswith("Carson") else 1)
        local_employers = st.text_area(
            "Top local employers / sectors * (comma-separated)",
            ", ".join(prefill.local_employers), height=70)
        channel_inventory = st.text_area(
            "Channel inventory * (comma-separated)",
            ", ".join(prefill.channel_inventory), height=70)
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
left, right = st.columns([3, 1])
with left:
    if validation.ok:
        st.success("Input contract satisfied — ready to generate.")
    else:
        st.error("Cannot generate yet — resolve these (fail-loud, §4.1):")
        for fld, reason, owner in validation.problems:
            st.markdown(f"- **{reason} {fld}** — owner *{owner}*")
with right:
    if st.button("💾 Save record"):
        fr.save_firm_record(record)
        st.toast("Saved.")

# --- snapshot preview -------------------------------------------------------
st.header("2 · Local market snapshot")
st.caption("Section 1 of the brief — FRED/ACS facts, presented cleanly, no "
           "interpretation. Thin/unavailable sources are narrowed, never faked (§4.3).")
with st.container(border=True):
    snapshot = snap_mod.build_snapshot(firm.firm_id)
    for m in snapshot.metrics:
        icon = "🟢" if m.available else "⚪"
        st.markdown(f"{icon} {m.display()}")
    if snapshot.is_thin:
        st.caption("Resolves once geography→FIPS lands (F2) — county/CBSA in the "
                   "geography template — and FRED is connected.")

# --- where to start (manual ranking until §2.1) -----------------------------
st.header("3 · Where to start (rank the plays)")
st.caption("Scorer-derived ranking is blocked on §2.1 — hand-order the plays for "
           "now. Ranking only; no numbers reach the firm (D1).")
with st.container(border=True):
    n = st.number_input("How many plays?", 1, 3, 2)
    ranked = []
    for i in range(int(n)):
        a, b = st.columns([1, 2])
        name = a.text_input(f"Play {i+1} name", key=f"pn{i}")
        why = b.text_input(f"Play {i+1} reasoning", key=f"pr{i}")
        if name:
            ranked.append(RankedPlay(name, why))

# --- generate ---------------------------------------------------------------
st.header("4 · Generate the brief")
default_preview = not have_anthropic
preview_mode = st.checkbox(
    "Preview prose (placeholder, layout only)", value=default_preview,
    help="Unchecked uses Claude for live sections 2–4 (needs ANTHROPIC_API_KEY).")
if st.button("Generate .docx", type="primary"):
    if not validation.ok:
        st.error("Resolve the missing required fields above first.")
    elif not ranked:
        st.error("Add at least one ranked play in section 3.")
    else:
        try:
            with st.spinner("Generating…"):
                result = brief_mod.generate_brief(
                    record, snapshot, llm=_llm(preview_mode),
                    ranked_plays=ranked, taxonomy=taxonomy)
            if isinstance(result, BlockedBrief):
                st.error("Cannot generate — missing inputs:\n\n" + result.message)
            elif isinstance(result, Brief):
                path = docx_export.render_brief_docx(result, out_dir="/tmp/lnos_out")
                ss.generated[firm.firm_id] = {
                    "path": str(path),
                    "sections": [(s.number, s.title, s.body) for s in result.sections]}
                st.toast("Brief generated.")
        except ComplianceBlocked as e:
            st.error(f"Compliance lint blocked the draft — not shipped.\n\n{e}")
        except LLMUnavailable as e:
            st.error(f"LLM error: {e}")
        except Exception as e:  # noqa: BLE001
            st.error(f"Generation error: {type(e).__name__}: {e}")

gen = ss.generated.get(firm.firm_id)
if gen:
    with st.container(border=True):
        st.markdown(f"**Generated:** `{os.path.basename(gen['path'])}`")
        with open(gen["path"], "rb") as fh:
            st.download_button("⬇ Download .docx", fh,
                               file_name=os.path.basename(gen["path"]))
        for num, title, body in gen["sections"]:
            with st.expander(f"{num}. {title}", expanded=num <= 2):
                st.write(body)

# --- delivery wrapper (APP-ONLY, separate render) ---------------------------
st.header("5 · Delivery wrapper")
st.caption("Internal only — never inside the .docx (§4.5).")
with st.container(border=True):
    st.markdown('<div class="internal">', unsafe_allow_html=True)
    ty_read = st.text_area("Your prioritization read (which play to lead with & why)", "")
    wrapper = delivery_mod.build_delivery_wrapper(
        record, prioritization_read=ty_read or None, validation=validation,
        taxonomy=taxonomy)
    st.markdown(f"**Prioritization read** — {wrapper.prioritization_read}")
    if wrapper.cetera_reminder:
        st.warning("⚑ " + wrapper.cetera_reminder)
    if wrapper.missing_input_flags:
        st.markdown("**Missing-input flags**")
        for f in wrapper.missing_input_flags:
            st.markdown(f"- {f}")
    st.markdown(f"**Suggested intro** — {wrapper.suggested_intro}")
    st.markdown('</div>', unsafe_allow_html=True)
