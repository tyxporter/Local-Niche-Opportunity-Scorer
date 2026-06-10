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
| 5 | Firm input layer + fail-loud input contract | ⬜ not started |
| 6 | Brief generator + compliance lint (sections 2–4) | ⬜ not started |
| 7 | Branded `.docx` export + delivery wrapper separation | ⬜ not started |
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
  errors.py       # MethodologyNotProvided (the §2.1 guardrail as a raised error)
data/
  Carson-WhollyOwned-Firm-AUM-Verified-2026-06-10.xlsx   # canonical firm source
  firm_geography.csv                                     # geography template (Ty to fill)
tests/            # 19 tests: spine integrity, blocked math, graceful degrade
```

Data modules return **raw** observations plus freshness metadata. Normalizing
them into Wealth/Demand/Saturation and combining into Opp is §2.1 — done in
`scoring.py` only, and currently blocked.

## Firm spine

Loaded from the verified workbook only (do not substitute another export). The
loader is data-driven and self-checks against the verified baseline (45 matched
firms, $26,702,566,296.72 total); it fails loud if the file ever drifts.

- **47 scoreable firms** = 45 with verified AUM + 2 AUM-pending
  (Johnson City, Las Vegas — AUM left **null**, never inferred).
- House accounts (Carson Group, Corporate Accounts) are **excluded** from the
  firm set.
- AUM is descriptive input data only — never a scorer signal, never blocks
  scoring.

## Open items blocking later phases

1. **§2.1 methodology spec** — unblocks Phase 4 (and Read in Phase 3).
2. **F1 — firm count.** Brief says "49 wholly-owned offices"; the workbook
   yields **47** once the 2 house accounts are excluded. Confirm 47, or supply
   the 2 missing offices.
3. **F2 — geography.** The workbook has no geography; `data/firm_geography.csv`
   is a blank template (one row per firm) for county + CBSA (needed for FRED).
   We do not infer geography from firm names.
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
