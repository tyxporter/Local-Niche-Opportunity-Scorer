"""Local Niche Opportunity Scorer (LNOS).

Internal prioritization tool that scores local markets for Carson Wealth's
wholly-owned partner advisor firms. The firm-facing *Local Marketing
Opportunity Brief* generator (Phases 5–8) is built on top of this package's
scorer output.

Build status (this package): Phases 0–3 complete; Phase 4 (`scoring.py`) is
the §2.1 boundary — output schema only, combination math blocked pending the
methodology spec from Ty. See README for details.

Naming is locked:
    Scorer     -> "Local Niche Opportunity Scorer"
    Deliverable-> "Local Marketing Opportunity Brief"

The scoring methodology (§2.1) is supplied directly by Ty and is NOT derived
from any data export, sample, or prior file (D6).
"""

__version__ = "0.8.1-dev"  # tracks phase progress; 0.<phase>.x

# Submodules are imported explicitly by callers (some pull optional deps that
# degrade gracefully). Keep this package __init__ free of heavy imports.
