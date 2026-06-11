# Local Niche Opportunity Scorer

Internal prioritization tool that scores local markets for Carson Wealth
Management Group's wholly-owned partner advisor firms. The firm-facing
**Local Marketing Opportunity Brief** generator (Phases 5–8) is built on top
of this scorer's output.

> Naming is locked: the scorer is the *Local Niche Opportunity Scorer*; the
> deliverable is the *Local Marketing Opportunity Brief*. No variants.

## Methodology ownership (§2.1 / D6)

The scoring methodology — the Opp formula, normalization method, Read
computation, bucket thresholds, and quadrant cut points — is supplied by Ty
**directly** and is **never** derived, inferred, or fitted from any data
export, sample, or prior file. No data export is a source of truth for the
build.

**§2.1 is currently TO-BE-PROVIDED → scoring math is intentionally BLOCKED.**
Every function that needs the methodology raises `MethodologyNotProvided`
rather than returning an invented number. There are no placeholder weights
anywhere in the codebase.

## Build status

| Phase | Scope | Status |
|------:|-------|--------|
| 0 | Scaffold, secrets template, brand tokens, cache + freshness | ✅ done |
| 1 | Firm spine (`firms.py`) from the verified AUM workbook | ✅ done |
| 2 | Data layer: `census.py`, `trends.py`, `competition.py`, `fred.py` | ✅ done |
| 3 | Readiness overlay (`readiness.py`), single-source design | ✅ plumbing done; Read math blocked on §2.1 |
| 4 | Scoring (`scoring.py`) | ⛔ output schema only; combination math **blocked on §2.1** |
| 5 | Firm input layer + fail-loud input contract | ✅ done; niche validation blocked on taxonomy (#4) |
| 6 | Brief generator + compliance lint (sections 2–4) | ✅ done; §5 ranking blocked on §2.1; prose needs `ANTHROPIC_API_KEY` |
| 7 | Branded `.docx` export + delivery wrapper separation | ✅ done; logo is a flagged placeholder |
| 8 | Streamlit shell + acceptance suite | ⬜ not started |

## Layout

```
lnos/
  brand.py        # Carson Wealth brand tokens (§5); logo/typography placeholders flagged
  cache.py        # disk cache + FreshnessMeta/SignalResult (graceful degrade, §4.3)
  firms.py        # firm spine loader (47 scoreable firms; house accounts excluded)
  census.py       # ACS -> raw Wealth observation (lagged, "market structure")
  trends.py       # Google Trends -> raw Demand observation (optional pytrends)
  competition.py  # FINRA BrokerCheck -> raw Saturation observation (best-effort)
  fred.py         # FRED -> current-data snapshot layer (county LAUS, HPI, permits)
  readiness.py    # Read overlay: firm-record single source; compute_read blocked
  scoring.py      # §1 output schema (5 fields, 4 buckets, 4 quadrants); math blocked
  firm_record.py  # §4.1 firm input layer + FAIL-LOUD input contract gate
  compliance.py   # §4.4 deny-list lint + system-prompt constraints + D2 label boundary
  snapshot.py     # §4.2 section 1: FRED/ACS facts, narrowed never fabricated (§4.3)
  brief.py        # §4.2 fixed 6-section assembly; §5 ranking blocked on §2.1
  docx_export.py  # §4.5 branded .docx (firm-facing); renders only the Brief model
  delivery.py     # §4.5 app-only delivery wrapper (separate; never in the .docx)
  errors.py       # MethodologyNotProvided / InputContractError / NicheTaxonomyNotProvided
data/
  Carson-WhollyOwned-Firm-AUM-Verified-2026-06-10.xlsx   # canonical firm + AUM source
  Carson-Firm-Geography-Template-2026-06-11.xlsx         # canonical geography source (Ty completing)
  blue_ocean_niches.json                                 # niche taxonomy (placeholder; Ty to fill)
  firm_records/_TEMPLATE.json                            # per-firm record template
tests/            # 69 tests: spine, geography join, blocked math, degrade, input contract, compliance lint, brief assembly, docx + wrapper separation
```

Data modules return **raw** observations plus freshness metadata. Normalizing
them into Wealth/Demand/Saturation and combining into Opp is §2.1 — done in
`scoring.py` only, and currently blocked.

## Firm spine

Loaded from the verified workbook only (do not substitute another export). The
loader is data-driven and self-checks against the verified baseline (45 matched
firms, $26,702,566,296.72 total); it fails loud if the file ever drifts.

- **47 scoreable firms** = 45 with verified AUM + 2 AUM-pending
  (Johnson City, Las Vegas — AUM left **null**, never inferred). Brief v2.3
  locks this count (49 roster rows − 2 house accounts).
- House accounts (Carson Group, Corporate Accounts) are **excluded** from the
  firm set.
- AUM is descriptive input data only — never a scorer signal, never blocks
  scoring.
- **Geography** is a separate spine input (v2.3), joined from
  `Carson-Firm-Geography-Template-2026-06-11.xlsx`. It ships with County/CBSA
  blank, so all 47 firms currently lack FRED-keyable geography; the unverified
  office-name city hints are carried as `city_suggested` only, never promoted
  to authoritative `city` until a row's County + CBSA are filled.

## Open items blocking later phases

1. **§2.1 methodology spec** — unblocks Phase 4 (and Read in Phase 3).
2. ~~F1 — firm count~~ **RESOLVED** by brief v2.3: 47 advisor firms (loader matches).
3. **F2 — geography.** `Carson-Firm-Geography-Template-2026-06-11.xlsx` is wired
   in as the canonical source but still blank for County + CBSA (the FRED keys).
   Complete it from Salesforce and re-send; the data layer (Phase 2) keys off it.
4. **Blue Ocean niche taxonomy** (eight profiles + Salesforce schema) — Phase 5.
5. **Approved disclosure blocks** (Carson-only, dual Carson/Cetera) — Phase 6/7.
6. `FRED_API_KEY`, Carson Wealth **logo**, optional **typography guide**.
7. **Readiness single-source** — confirm Read derives from the firm record only.

## Develop

```bash
pip install -r requirements.txt
cp .env.example .env        # add keys locally; never commit
python -m lnos.firms        # print firm spine summary
python -m pytest -q         # run the suite
```

Secrets come from env vars / Streamlit Secrets only — never hardcoded.
