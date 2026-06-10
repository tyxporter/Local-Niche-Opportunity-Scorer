"""Carson Wealth brand tokens (§5).

Sub-brand is Carson Wealth Management Group (CWMG) — NOT parent Carson
Partners. These constants are the single source of brand truth for the
.docx export (Phase 7) and the Streamlit shell (Phase 8).

Two flagged placeholders below are intentional and must be resolved by Ty
before a firm-facing brief ships:
  * LOGO_PATH            — official Carson Wealth lockup not yet supplied.
  * TYPOGRAPHY_GUIDE     — a formal CW typography guide may exist and, if
                           supplied, OVERRIDES the type rules here.
"""

from __future__ import annotations

# --- Colors -----------------------------------------------------------------
# Primary
NAVY = "#0d304a"            # primary dark
GOLD = "#d6b556"           # Carson Wealth Gold — primary accent
LIGHT_GOLD = "#ebd48d"     # secondary
WHITE = "#ffffff"

# Gold tints for fills / section backgrounds
GOLD_TINT_50 = "#f5e9c6"
GOLD_TINT_25 = "#faf4e2"
GOLD_TINT_10 = "#fdfbf4"

# Grays
GRAY_DARK = "#6e7b82"
GRAY_MID = "#afbdc7"
GRAY_LIGHT = "#cadae6"

COLORS = {
    "navy": NAVY,
    "gold": GOLD,
    "light_gold": LIGHT_GOLD,
    "white": WHITE,
    "gold_tint_50": GOLD_TINT_50,
    "gold_tint_25": GOLD_TINT_25,
    "gold_tint_10": GOLD_TINT_10,
    "gray_dark": GRAY_DARK,
    "gray_mid": GRAY_MID,
    "gray_light": GRAY_LIGHT,
}

# --- Typography -------------------------------------------------------------
FONT_PRIMARY = "Helvetica Neue LT Pro"
FONT_FALLBACK_CHAIN = [
    "Helvetica Neue",
    "Helvetica",
    "Arial",
    "system-ui",
    "sans-serif",
]
# Headings: bold, title case, punchy/benefit-led. Subheads may use accent color.
HEADING_WEIGHT = "bold"
HEADING_CASE = "title"
SUBHEAD_ACCENT_COLOR = GOLD
# Body: thin/light weight, generous leading + whitespace.
BODY_WEIGHT = "light"

# A Carson Wealth–specific typography guide may exist for formal pieces.
# If supplied, it OVERRIDES the rules above. None until Ty provides it.
TYPOGRAPHY_GUIDE = None  # TODO(Ty): path to CW typography guide if one exists

# --- Design system ----------------------------------------------------------
# Geometry derives from the logo mark: 30°/60° angles (diagonal blocks,
# chevrons). On-brand: triangular/chevron. Off-brand: rounded shapes for
# primary structure. Clean, breathable layout, lots of whitespace.
BRAND_ANGLES_DEG = (30, 60)
ON_BRAND_SHAPES = ("triangle", "chevron")
OFF_BRAND_FOR_PRIMARY_STRUCTURE = ("rounded",)

# --- Voice (sections 2–4 LLM generation) ------------------------------------
# Authoritative, intelligent, inspiring, confident-but-humble ("we've been
# there"). Hard no on promissory/overpromising language — reinforces the
# compliance lint (§4.4).
VOICE = (
    "Authoritative, intelligent, inspiring, confident-but-humble. "
    "No promissory or overpromising language."
)

# --- Logo (FLAGGED PLACEHOLDER) ---------------------------------------------
# Carson Wealth lockup: navy + two-tone-blue triangle mark + wordmark.
# File not yet in the sandbox. None until Ty supplies it; the .docx export
# (Phase 7) must fail loud / render a visible placeholder rather than ship a
# brief with no logo.
LOGO_PATH = None  # TODO(Ty): PNG or SVG of the official Carson Wealth lockup

LOGO_AVAILABLE = LOGO_PATH is not None
TYPOGRAPHY_GUIDE_AVAILABLE = TYPOGRAPHY_GUIDE is not None
