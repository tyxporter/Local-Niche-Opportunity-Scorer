"""Streamlit shell (§6, Phase 8) — UI + delivery wrapper.

Internal app for the Local Niche Opportunity Scorer / Local Marketing
Opportunity Brief. Pick a firm → geography, AUM, market snapshot and web
context auto-resolve → fill the two inputs only Ty/compliance can supply
(Blue Ocean niche + approved disclosure) → generate the branded .docx.

Guardrails honored in the UI:
  * Firm-facing .docx and the internal delivery wrapper are rendered by SEPARATE
    functions that share no state (§4.5).
  * Sections 2–4 prose runs through the compliance lint (§4.4); with no
    ANTHROPIC_API_KEY the app uses clearly-watermarked PREVIEW prose (layout
    only, not client-ready).
  * Scorer-derived Where-to-Start ranking is §2.1 (blocked); Ty hand-orders the
    plays (sensible defaults provided).
  * Geography is RESOLVED from supplied city/state via the Census geocoder —
    never inferred from a firm name.
"""

from __future__ import annotations

import os

import streamlit as st


# --- Secrets bridge ---------------------------------------------------------
# Streamlit Cloud puts secrets in st.secrets, NOT os.environ. Our data/LLM
# layers read os.environ, so mirror them once at startup.
def _load_secrets_into_env() -> None:
    keys = ("ANTHROPIC_API_KEY", "FRED_API_KEY", "CENSUS_API_KEY", "LNOS_MODEL",
            "GOOGLE_CSE_KEY", "GOOGLE_CSE_CX")
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
from lnos import customsearch                       # noqa: E402
from lnos import geocode as geocode_mod             # noqa: E402
from lnos import disclosures as disclosures_mod      # noqa: E402
from lnos.brief import RankedPlay, Brief, BlockedBrief, LLMUnavailable  # noqa: E402
from lnos.compliance import ComplianceBlocked       # noqa: E402

st.set_page_config(page_title="Local Niche Opportunity Scorer",
                   page_icon="◆", layout="wide", initial_sidebar_state="expanded")

DEFAULT_CHANNELS = "email, seminars, referrals, LinkedIn"
DEFAULT_PLAYS = [("Niche seminar series",
                  "fits the firm's strongest channel and core local audience"),
                 ("Employer-sector email nurture",
                  "low lift across the firm's existing lists")]

# --- brand styling ----------------------------------------------------------
st.markdown(f"""
<style>
  #MainMenu, footer {{ visibility:hidden; }}
  /* NOTE: never hide header[data-testid="stHeader"] — it holds the sidebar
     collapse/expand control. Keep it visible so the sidebar can reopen. */
  .stApp {{ background:{brand.GOLD_TINT_10};
            font-family:"Helvetica Neue LT Pro","Helvetica Neue",Helvetica,Arial,sans-serif; }}
  .block-container {{ padding-top:1rem; max-width:1180px; }}
  h1,h2,h3,h4 {{ color:{brand.NAVY}; letter-spacing:-0.01em; }}
  .lnos-band {{ position:relative; overflow:hidden; background:{brand.NAVY};
    color:#fff; padding:1.2rem 1.5rem; border-radius:4px; margin-bottom:.8rem; }}
  .lnos-band:after {{ content:""; position:absolute; top:0; right:-40px; width:160px;
    height:100%; background:{brand.GOLD}; transform:skewX(-30deg); opacity:.92; }}
  .lnos-band:before {{ content:""; position:absolute; top:0; right:60px; width:80px;
    height:100%; background:{brand.LIGHT_GOLD}; transform:skewX(-30deg); opacity:.55; }}
  .lnos-logo {{ font-weight:800; font-size:.8rem; letter-spacing:.22em; color:{brand.LIGHT_GOLD}; }}
  .lnos-logo span {{ color:#fff; }}
  .lnos-title {{ font-size:1.6rem; font-weight:800; margin:.1rem 0 0; }}
  .lnos-sub {{ color:{brand.GRAY_LIGHT}; font-size:.9rem; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:.4rem; margin:.1rem 0 .8rem; }}
  .chip {{ font-size:.74rem; font-weight:600; padding:.22rem .6rem; border-radius:999px;
    border:1px solid transparent; }}
  .chip-ok {{ background:{brand.GOLD_TINT_50}; color:#5b4a16; border-color:{brand.GOLD}; }}
  .chip-wait {{ background:#fff; color:{brand.GRAY_DARK}; border-color:{brand.GRAY_MID}; }}
  h2 {{ border-bottom:2px solid {brand.GOLD}; padding-bottom:.25rem; margin-top:1.3rem; }}
  div.stButton > button {{ background:{brand.NAVY}; color:#fff; border:0; border-radius:3px;
    font-weight:700; padding:.45rem 1.1rem; }}
  div.stButton > button:hover {{ background:{brand.GOLD}; color:{brand.NAVY}; }}
  .sidebar-card {{ background:{brand.NAVY}; color:#fff; padding:.8rem .9rem; border-radius:4px; }}
  .sidebar-card .k {{ color:{brand.LIGHT_GOLD}; font-size:.78rem; }}
</style>
""", unsafe_allow_html=True)


# --- preview LLM (no key) ---------------------------------------------------
class PreviewLLM:
    """Layout-only placeholder prose when no ANTHROPIC_API_KEY. Compliance-clean,
    clearly marked — NOT client-ready."""

    _TEXT = {
        "signal": ("[PREVIEW] Local employers and sectors anchor this market, and "
                   "the firm's niche audience is reachable through its existing "
                   "channels. Outreach context only."),
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


# --- cached data ------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_spine():
    return firms_mod.load_firms()


@st.cache_data(show_spinner=False)
def load_taxonomy():
    return fr.load_niche_taxonomy()


@st.cache_data(show_spinner=False)
def resolve_geo(city, state):
    if not (city and state):
        return None
    try:
        r = geocode_mod.resolve(city, state)
    except Exception:
        return None
    return r if r.available else None


@st.cache_data(show_spinner=False)
def get_snapshot(firm_id, state_fips, county_fips, state_abbr):
    return snap_mod.build_snapshot(firm_id, state_fips=state_fips,
                                   county_fips=county_fips, state_abbr=state_abbr)


@st.cache_data(show_spinner=False)
def auto_employers(county, cbsa):
    """Best-effort auto-fill of local employers/sectors from the web (CSE),
    distilled to a short comma list by Claude when available. Empty on any
    miss — never fabricated, never blocks."""
    if not os.environ.get("GOOGLE_CSE_KEY"):
        return ""
    snips = customsearch.employer_context_snippets(county=county, cbsa=cbsa)
    if not snips:
        return ""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return ""
    try:
        llm = brief_mod.ClaudeClient()
        txt = llm.complete(
            system=("Extract only a comma-separated list (max 6) of the top local "
                    "employers or dominant sectors named in the text. Output just "
                    "the list — no prose, no numbering."),
            prompt="Snippets:\n" + "\n".join(snips), temperature=0)
        items = [s.strip() for s in txt.replace("\n", ",").split(",") if s.strip()]
        return ", ".join(items[:6])
    except Exception:
        return ""


@st.cache_data(show_spinner=False)
def auto_niche(firm_id, profiles_sig, county, cbsa, employers, mhi, unemp, hpi, aum):
    """Auto-select the firm's Blue Ocean niche from its data (Claude), returning
    {profile, rationale} or None. Needs the taxonomy + ANTHROPIC_API_KEY."""
    if not profiles_sig or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        from lnos import niche as niche_mod
        sel = niche_mod.select_niche(
            taxonomy=load_taxonomy(),
            firm_context={"county": county, "cbsa": cbsa, "employers": employers,
                          "mhi": mhi, "unemployment": unemp, "hpi": hpi, "aum": aum},
            llm=brief_mod.ClaudeClient())
        return {"profile": sel.profile, "rationale": sel.rationale} if sel.available else None
    except Exception:
        return None


spine = load_spine()
taxonomy = load_taxonomy()
by_name = {f.roster_name: f for f in spine}
ss = st.session_state
ss.setdefault("generated", {})

have_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
have_fred = bool(os.environ.get("FRED_API_KEY"))
have_cse = bool(os.environ.get("GOOGLE_CSE_KEY"))


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

geo_res = resolve_geo(firm.city, firm.state)
county_auto = geo_res.county_name if geo_res else None
cbsa_auto = geo_res.cbsa if geo_res else None

with st.sidebar:
    aum = "—" if firm.aum_usd is None else f"${firm.aum_usd_m:,.1f}M"
    loc = f"{firm.city}, {firm.state}" if firm.city and firm.state else "—"
    resolved = f"{county_auto} · {cbsa_auto}" if (geo_res and geo_res.has_fips) else "pending"
    st.markdown(
        f"<div class='sidebar-card'><b>{firm.roster_name}</b><br>"
        f"<span class='k'>firm_id</span> {firm.firm_id}<br>"
        f"<span class='k'>AUM</span> {aum}{' (pending)' if firm.aum_pending else ''}<br>"
        f"<span class='k'>location</span> {loc}<br>"
        f"<span class='k'>resolved</span> {resolved}</div>", unsafe_allow_html=True)
    if firm.geo_confidence and "Confirmed" not in firm.geo_confidence:
        st.caption(f"⚠ Location confidence: {firm.geo_confidence} — verify.")
    existing = fr.record_path(firm.firm_id).exists()
    st.caption("✓ Saved record found." if existing else "No saved record yet.")
    st.divider()
    st.caption("Logo placeholder — supply the Carson Wealth lockup to brand the "
               ".docx header.")

# --- status chips -----------------------------------------------------------
st.markdown(
    '<div class="chips">'
    + chip("Live copy (Claude)" if have_anthropic else "Preview prose — add ANTHROPIC_API_KEY", have_anthropic)
    + chip("FRED connected" if have_fred else "FRED key missing", have_fred)
    + chip("Web context (CSE)" if have_cse else "Web context off", have_cse)
    + chip("Niche taxonomy loaded" if taxonomy.available else "Niche taxonomy pending (#4)", taxonomy.available)
    + chip("Geography resolved" if (geo_res and geo_res.has_fips) else "Geography pending", bool(geo_res and geo_res.has_fips))
    + chip("Scoring spec pending (§2.1)", False)
    + '</div>', unsafe_allow_html=True)

with st.expander("How this works", expanded=not existing):
    st.markdown(
        "1. **Pick a firm** (left). Geography, AUM, the market snapshot, local "
        "employers, the approved disclosure, and the Blue Ocean niche all "
        "auto-fill/auto-select from the firm's data.\n"
        "2. **Review and override** anything (the niche shows the AI's reasoning).\n"
        "3. **Generate .docx** and download. Sections 2–4 are written by Claude "
        "and run through the compliance lint.\n\n"
        "Pending: load the **8 Blue Ocean profiles** (`data/blue_ocean_niches.json`) "
        "to enable niche auto-select, and the **§2.1 scoring spec** for automatic "
        "play ranking (until then plays use sensible defaults).")

# --- auto-resolve snapshot + employers + niche (before the form) ------------
sfips = geo_res.state_fips if geo_res else None
cfips = geo_res.county_fips if geo_res else None
snapshot = get_snapshot(firm.firm_id, sfips, cfips, firm.state)


def _metric(key):
    for m in snapshot.metrics:
        if key in m.label.lower() and m.available:
            return m.result.value
    return None


mhi_val, unemp_val, hpi_val = _metric("income"), _metric("unemployment"), _metric("home price")
emp_default = auto_employers(county_auto, cbsa_auto)
ai_niche = (auto_niche(firm.firm_id, tuple(taxonomy.profiles), county_auto, cbsa_auto,
                       emp_default, mhi_val, unemp_val, hpi_val, firm.aum_usd)
            if taxonomy.available else None)

# --- firm record form -------------------------------------------------------
st.header("1 · Firm record")
prefill = fr.load_firm_record(firm.firm_id) if existing else fr.FirmRecord(
    firm_id=firm.firm_id, legal_name=firm.roster_name.replace("-CIA", ""),
    county=county_auto, cbsa=cbsa_auto, aum_usd=firm.aum_usd,
    channel_inventory=fr.FirmRecord._as_list(DEFAULT_CHANNELS))

with st.container(border=True):
    c1, c2 = st.columns(2)
    with c1:
        legal_name = st.text_input("Firm legal name *", prefill.legal_name or "")
        county = st.text_input("County *", prefill.county or county_auto or "")
        cbsa = st.text_input("Metro / CBSA *", prefill.cbsa or cbsa_auto or "")
        niche_opts = list(taxonomy.profiles) if taxonomy.available else []
        if niche_opts:
            default_niche = (prefill.niche_profile
                             or (ai_niche and ai_niche["profile"]) or niche_opts[0])
            niche = st.selectbox(
                "Blue Ocean niche profile * (auto-selected — override if needed)",
                niche_opts,
                index=niche_opts.index(default_niche)
                if default_niche in niche_opts else 0)
            if ai_niche and ai_niche["profile"]:
                st.caption(f"🤖 Auto-selected **{ai_niche['profile']}** — "
                           f"{ai_niche['rationale']}")
            elif os.environ.get("ANTHROPIC_API_KEY"):
                st.caption("Auto-selection unavailable for this firm — defaulted; verify.")
        else:
            niche = st.text_input(
                "Blue Ocean niche profile * (paste the 8 profiles to enable auto-select)",
                prefill.niche_profile or "")
    with c2:
        compliance_structure = st.selectbox(
            "Compliance structure *", [s.value for s in fr.ComplianceStructure],
            index=0 if (prefill.compliance_structure or "Carson").startswith("Carson") else 1)
        local_employers = st.text_area(
            "Top local employers / sectors * (auto-filled from web)",
            ", ".join(prefill.local_employers) or emp_default, height=70,
            help="Auto-pulled from the web for this market; edit if needed.")
        channel_inventory = st.text_area(
            "Channel inventory * (comma-separated)",
            ", ".join(prefill.channel_inventory) or DEFAULT_CHANNELS, height=70)
    # Disclosure auto-fills VERBATIM from the approved block for this compliance
    # structure (never drafted — §4.4). Switching the structure swaps the block.
    disc_default = prefill.disclosure_block or disclosures_mod.for_structure(
        compliance_structure)
    disclosure_block = st.text_area(
        "Approved disclosure block * (verbatim — auto-filled by structure)",
        disc_default, height=120,
        help="Auto-filled from compliance's approved block for this structure.")

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
        st.warning("To generate, still need: "
                   + ", ".join(f"**{fld}**" for fld, _, _ in validation.problems))
with right:
    if st.button("💾 Save record"):
        fr.save_firm_record(record)
        st.toast("Saved.")

# --- snapshot ---------------------------------------------------------------
st.header("2 · Local market snapshot")
st.caption("Section 1 of the brief — FRED/ACS facts, no interpretation. "
           "Thin/unavailable sources are narrowed, never faked (§4.3).")
with st.container(border=True):
    for m in snapshot.metrics:
        st.markdown(f"{'🟢' if m.available else '⚪'} {m.display()}")
    if snapshot.is_thin and not (geo_res and geo_res.has_fips):
        st.caption("Resolves once a firm's city/state is on file (geocoded to "
                   "county FIPS) and FRED is connected.")
    elif snapshot.is_thin and not have_fred:
        st.caption("Geography resolved — add FRED_API_KEY to populate the numbers.")

# --- where to start ---------------------------------------------------------
st.header("3 · Where to start (rank the plays)")
st.caption("Scorer-derived ranking is blocked on §2.1 — defaults provided; "
           "edit/reorder. Ranking only, no numbers reach the firm (D1).")
with st.container(border=True):
    n = st.number_input("How many plays?", 1, 3, 2)
    ranked = []
    for i in range(int(n)):
        a, b = st.columns([1, 2])
        dname, dwhy = (DEFAULT_PLAYS[i] if i < len(DEFAULT_PLAYS) else ("", ""))
        name = a.text_input(f"Play {i+1} name", value=dname, key=f"pn{i}")
        why = b.text_input(f"Play {i+1} reasoning", value=dwhy, key=f"pr{i}")
        if name:
            ranked.append(RankedPlay(name, why))

# --- generate ---------------------------------------------------------------
st.header("4 · Generate the brief")
preview_mode = st.checkbox(
    "Preview prose (placeholder, layout only)", value=not have_anthropic,
    help="Unchecked uses Claude for live sections 2–4 (needs ANTHROPIC_API_KEY).")
if st.button("Generate .docx", type="primary"):
    if not validation.ok:
        st.error("Fill the remaining required fields above first: "
                 + ", ".join(fld for fld, _, _ in validation.problems))
    elif not ranked:
        st.error("Add at least one ranked play in section 3.")
    else:
        try:
            with st.spinner("Generating…"):
                web_ctx = (customsearch.employer_context_snippets(
                    county=record.county, cbsa=record.cbsa) if have_cse else None)
                result = brief_mod.generate_brief(
                    record, snapshot, llm=_llm(preview_mode),
                    ranked_plays=ranked, taxonomy=taxonomy, web_context=web_ctx)
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
