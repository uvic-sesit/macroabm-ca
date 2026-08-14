# NEW-THREAD HANDOFF — 2022 MacroABM integration

Self-contained. A fresh agent can continue from this without the prior thread history.
Branch: `feature/io-2022-integration` (off verified `real-growth-baseline`; baseline untouched).

## ⭐ STATUS UPDATE 2026-08-13 — t0→t1 collapse RESOLVED (capital fix). Read this first.
The t0→t1 labour collapse this document was written to diagnose is **root-caused and FIXED**. It was
**negative capital-technology composition**, NOT employment. Sections C–F below are the original
(pre-fix) forensic framing and are **superseded** by `INTEGRATION_LOG.md` #29–#30; kept for provenance.

- **Root cause:** the 2022 capital matrices held 1646 negative entries (2014: 0) from **negative net
  Fixed Capital Formation** (raw disinvestment + the #10 Changes-in-Inventories fold). neg×neg=pos masks
  it at t0 (GDP identity holds); `np.maximum(0,·)` floors the negative stock to 0 after one step;
  `limiting_capital=min_g(coef×stock)` → 0; `desired_labour=min(target,0)≈0` (consider_capital=1.0) →
  ~98% fired → collapse. Systemic, config-independent. The employment-share suspicion was WRONG
  (population is healthy: ON 6979 employed, all matched).
- **Fix (implemented, no behavioural change):** `ICIOReader._prefold_capital_composition` sources the
  capital composition from **pre-fold FCF** (inventories excluded), clips negatives→0, normalizes over
  positives, makes empty channels non-binding (inf coef) with a warning. Accounting net FCF (incl.
  negatives) + capcomp/GDP-identity path untouched. **ACCOUNTING net investment ≠ CAPITAL-TECHNOLOGY
  composition.** Files: `icio_reader.py`, `default_readers.py` (pre-fold snapshot).
- **Validated** on `dev/pkl_files/io2022_13prov_2022_capfix.pkl`: 0 negative capital entries; GDP identity
  1.00000 all 13 regions; **legacy/default 13q real GVA 893.6B→822.8B (was →0), no t0→t1 collapse**;
  smallest 4q sim 0 non-finite. Exact commands + results in `INTEGRATION_LOG.md` #29.
  **The capital-treatment implementation is VALIDATED. The overall 2022 integration is NOT yet
  production-ready.**

## Accepted integration baseline & the deferred candidate collapse
For integration acceptance use the **simplest/default 2022 baseline** (no candidate growth overlays).
The **candidate** growth baseline still collapses at a **t2 cliff** via `limiting_intermediate`
depletion under its demand overlay — the known **"intermediate lock"/demand-channel** issue, **SEPARATE
from the capital fix and explicitly NOT a failure of it** (`INTEGRATION_LOG.md` #30). Do not mix that
growth work into basic DataWrapper integration.

## LOCAL CHECKPOINT — commit `e9346ff75e63de6944744635d50fd6df2eae9e54` (feature/io-2022-integration)
Latest local checkpoint of the 2022 integration (simple/default baseline; not pushed;
`real-growth-baseline` untouched at `d11edc1`).

**13q simple/default acceptance result:**
- t0 GDP identity: **13/13 balanced**
- NaN/inf over 13q: **0**
- national real GVA: **687.3B → 646.4B (−6.0%)**
- unemployment: 7.7% → 35.7%
- small-region catastrophic collapse (end → ~0): **NL, PE, NB, YT, NT** (large provinces hold)

**Status of the 2022 integration:**
- Capital treatment — **validated** (#29).
- Canadian StatCan 36-10-0489 employment shares — **wired** (#31).
- Observed compensation of employees / wages / employer contributions — **wired** (#32).
- CAD-native IO currency handling — **validated** (#33).
- Candidate-growth baseline — **PARKED** (#30, separate t2 intermediate/demand collapse).
- **Overall 2022 integration is NOT yet complete**: it is mechanically stable *nationally* (0 NaN/inf,
  identity holds) but the **small-region mechanics fail** (NL/PE/NB/YT/NT collapse over 13q).

**NEXT TASK (explicit, in order):**
1. **Zero-sector handling** — replace the ε floor (`_floor_empty_provincial_sectors`, #28) with
   principled model-side handling of genuinely-empty (province, sector) cells.
2. **Principled small-region synthetic-population scaling** — fix the per-province `scale` so small
   provinces/territories have enough synthetic agents to express 50-sector employment shares without
   the ≥1-worker floor injecting `scale` phantom persons per empty sector (supersedes the #21 scale=10
   territory hack).
3. **Rerun the simple/default 13q baseline** and confirm the small-region collapse is resolved.

**Deferred until AFTER regional mechanics are stable:** HFCS-2021 Canadianization, and any post-2022
external-series / vintage work.

## Validated so far (simple/default baseline; see INTEGRATION_LOG #29–#33)
- **Capital treatment (#29)** — pre-fold non-negative capital composition; t0→t1 collapse fixed.
- **StatCan 36-10-0489 employment shares (#31)** — wired to province×sector headcount.
- **Observed compensation of employees (#32)** — firm wage bill = PRM500000 wages + PRM600000 employer
  (from `macroabm-io2022/canonical/VA_tax_output_basic.csv`; regenerate the input with
  `dev/io2022/prepare_compensation_input.py`); `tau_sif` = observed per-province employer ratio.
- **CAD-native IO currency handling (#33)** — `from_usd_to_lcu_io` removes the spurious ~1.30 USD→CAD on
  the 2022 CAD IO/SEA ingestion; Compustat (USD) keeps the real rate. Model CoE/wages/employer/VA now
  match canonical CAD.

13q simple/default acceptance: real GVA −6%, unemployment 7.7→35.7%, **0 NaN/inf**, GDP identity 13/13 at
t0 — mechanically stable nationally, but 5 small regions (NL/PE/NB/YT/NT) collapse (see remaining #1).

## Remaining integration items (NOT yet worked on — do not start without direction)
1. **Zero-sector handling + small-province/territory scaling** — the ε floor (#28,
   `_floor_empty_provincial_sectors`) fabricates tiny output/VA/investment, and territories use
   `scale=10` (#21). At scale=1000 a small province has too few synthetic agents to express 50-sector
   shares (PEI ≈ 61 employed / 50 sectors) and the ≥1-worker floor injects `scale` phantom persons per
   empty sector. This is why NL/PE/NB/YT/NT collapse over 13q. Needs principled model-side zero-sector
   handling + per-province scaling.
2. **HFCS-2021 still raw / non-Canadianized** — household income/wealth/debt/consumption from raw
   European wave; SFS-2016 + CIS-2017 Canadianization (the orphaned `New_*` files, §G) not wired.
3. **Candidate-growth baseline remains PARKED** — separate t2 intermediate/demand-channel collapse
   (#30); do not mix into basic integration.

Original forensic sections C–F (superseded) follow.

---
Read-only forensic phase — do NOT patch/recalibrate until the causal break is demonstrated.

## A. Already validated — DO NOT REDO
- **2022 OECD-50 provincial IO table** (13 regions = 10 provinces + YT/NT/NU; 50 sectors) is built,
  balanced, and reader-compatible. Files: `macroabm-io2022/` pipeline; compat table copied to
  `dev/raw_data/icio/icio_2022_can_provinces.csv`. Do not rebuild the table.
- **Validated 2022 input checkpoints** in `macroabm-io2022/integration_2022_inputs/` (all pass their
  conservation/identity checks — see `VALIDATION_REPORT.md`):
  - `capital_stock_end2021_oecd50_by_province_CADmillions.csv` (opening K, end-2021 net stock, 36-10-0096)
  - `capital_compensation_oecd50_by_province_CADmillions.csv` (GOS+MI+net prod tax = VA−wages−employer-contrib; identity exact 8.5e-14)
  - `employment_shares_oecd50_by_province.csv` (36-10-0489 total jobs → OECD-50; shares sum to 1; all 50 sectors)
- **DataWrapper builds & initializes coherently**: `dev/pkl_files/io2022_13prov_2022.pkl`; all 50 sectors ×
  13 regions populated; GDP output==expenditure identity = ratio 1.0000 for every region; t0 states finite.
- **Reader/build fixes (#0–#28)** are logged with classification in `INTEGRATION_LOG.md` and forensically
  triaged. Generic bug fixes (#5,11,16,17,23,25), the IO reader seam (#0,1), and OECD-50 bridge (#7) are
  SAFE. Do not re-derive these.

## B. Exact transformation / calibration chain (validated input → t0)
1. **IO table** → `use_provincial_can_reader` → `ICIOReader.iot` (×1e6; **FD folded 5→3 symbols**, #10:
   Changes-in-Inventories→Fixed-Capital-Formation, Direct-Purchases-Abroad→Household-Consumption).
2. **Capital stock (end-2021, validated)** injected as SEA "Capital Stock" (injection #2/#26, BEFORE
   reconcile) → `get_capital_inputs_matrix`: `cap_prod = (output/K)/norm_investment` →
   `capital_inputs_stock = (1/u)·output/cap_prod ≈ K·norm_inv`. **Preserved.**
3. **Capital compensation (validated GOS+MI+tax)** injected as SEA "Capital Compensation" → then
   **`_match_country_iot_with_sea` OVERWRITES it** with the investment-matrix column sums (reconciled to
   GFCF), and sets **Labour Compensation := VA − reconciled_capcomp**. So the level that reaches firms is
   GFCF, not the validated StatCan capital income. Only the *sectoral allocation pattern* + capital stock
   survive. `get_capital_inputs_depreciation(capcomp)` → `used_capital_inputs = production × matrix`.
4. **Wages / labour compensation**: the compat IO table exports only VA TOTAL (+ Taxes Less Subsidies),
   NOT the wage/GOS split. So the firm **wage bill = SEA Labour Compensation = VA − reconciled_capcomp**
   (a residual). The validated IO wages+employer-contributions are NEVER wired.
5. **Employment**: synthetic population builds `number_employees_by_industry` from **HFCS-2021 `PE0400`**
   (European/France-proxy), counting individuals per industry (persons). The population is sized by
   eurostat household counts (nearest-year proxy, #14) × scale (territories=10, #21). The **validated
   36-10-0489 employment shares are NEVER wired.**
6. **Labour productivity** = `output / n_employees_per_industry` = **2022 Canadian IO output ÷ HFCS-proxy
   employment** → firm required labour = `production / labour_productivity`.
7. **HFCS-2021** supplies household type/income/wealth/debt/consumption (preserved).
8. **Exogenous scalars** (VAT, benefits, firm counts, deposits, debt, cf_tax): all sources end <2022 →
   nearest-populated-year or FRA/GBR proxy fallbacks (#9,11,12,13,14,15,18,20,24). Pre-2022 vintage.

## C. Known overwrites / missing wiring (the two prime suspects)
1. **Capital compensation is OVERWRITTEN to GFCF** by `match_iot_with_sea` before firms initialize, and
   **labour compensation is the residual VA − GFCF**. The validated capital-income level never reaches
   the firm; the wage bill is therefore a reconciliation output, not observed compensation.
2. **Validated StatCan employment shares are NEVER wired.** t0 employment distribution AND level come from
   the HFCS France-proxy population. Labour productivity = 2022 output ÷ proxy employment → likely a
   scale mismatch.

## D. Current frozen result
Builds ✅  initializes (GDP identity exact, all 13 regions) ✅  smallest sim runs multi-quarter, no NaN ✅.
Candidate AND legacy-default runs **collapse on the first step (t0→t1)**: real GVA → 0, unemployment → ~89%.
2014 control is stable (+0.67%/yr). Collapse is **systemic** (hits Ontario, which has no floored/empty
sectors, so NOT the ε-floor or territories) and config-independent. **Traced mechanism (Ontario, t1):**
target production healthy (~490B), intermediate inputs fine (~490B), but **firm labour input collapses
489.8B → 0.46B** and the wage bill with it (274B → 0.28B) → production labour-starved → mass unemployment,
no recovery. The binding constraint flips to labour on step one.

## E. Highest-priority t0 comparisons + controlled tests
**Compare per (province, sector) between the balanced 2014 pickle and `io2022_13prov_2022.pkl`:**
1. **labour productivity = output / n_employees** (top suspect — expect a scale mismatch).
2. **workers by sector/province** (is the 2022 employment level commensurate with IO output level?).
3. **wage per worker = Labour Compensation / n_employees** (t1 affordability driver; couples both issues).
4. **firm wage bill** vs IO implied compensation of employees (quantify the reconciliation distortion).
5. **desired vs actual labour** at t0 and t1 (locate the 490B→0.46B step).
6. capital stock / capital productivity / used_capital_inputs (confirm capital is NOT the break — firm
   capital cost already matches IO GFCF, e.g. NL 1.61B).
7. household income/consumption (t1 demand) and firm profits/cash/liquidity (t1 affordability).

**Controlled substitution experiment (reviewer's design), each family toggled independently, everything
else held identical to the 2014 build:**
- 2014 build → **swap ONLY the IO table/classification bundle** {table #1, regex #0, FD fold #10, OECD-50
  bridge #7, global-SML fallback #3} → run. If it already collapses (2014 capital/employment/HFCS still
  in place), the cause is the table/classification, NOT employment.
- then add capital (#2/#26) → run; then employment (36-10-0489 shares × IO-consistent persons level) →
  run; then HFCS-2021 → run. Hold ALL exogenous vintage fallbacks FIXED in every arm so they don't confound.
- Resolve the zero-sector policy ONCE up front (see F) so the finer-split empty-sector effect doesn't
  contaminate every arm.

## F. Do NOT patch/recalibrate until the causal break is demonstrated
- Do NOT "wire employment and see if it fixes it" — it may mask the cause after 28 changes.
- Do NOT recalibrate behavioural equations to remove the collapse.
- **REVERT before production** (not before diagnosis, but do not treat as sound): #28 ε zero-sector floor
  (fabricates output/VA/investment — replace with model-side zero-sector handling / don't instantiate an
  active firm for a genuinely zero province-sector cell); #21 territory scale=10 (non-uniform person
  normalization on the collapse margin — justify or replace with a principled rule).
- Treat "GDP balances at init" as partly CONSTRUCTED by `match_iot_with_sea`, not independent evidence.
- First demonstrate WHICH single substitution triggers the labour collapse (Section E experiment), THEN fix.

## G. Canadianized HFCS (SFS-2016 + CIS-2017) is ORPHANED — never wired (2014 or 2022)
Files present at `dev/raw_data/hfcs/`: `New_Household_provincial.csv`, `New_Individuals_provincial.csv`
(+ non-provincial variants). They are the intended Canadianization: household income (rental/financial/
pension/transfers), wealth (deposits/funds/bonds/shares/property/vehicles/business), debt (mortgages/
credit/loans), consumption; and individual **Employment Industry + Employee/Self-Employment income**.

**They are NOT consumed by the build** — neither the working 2014 build nor the current 2022 build.
- Only reference in the entire codebase: `dev/validation/diagnose_gdp_gap.py`, which explicitly lists
  them under "NOT IN PROVINCIAL READER PATH".
- The real HFCS reader (`hfcs_reader.py:221-223`) loads raw European wave files
  `hfcs_data_path/{year}/{P,H,D}{i}.csv` (2014/ for 2014; 2021/ for 2022). No config flag routes to `New_*`.
- So BOTH builds take household income/wealth/debt/consumption AND the employment-industry distribution
  from **raw European HFCS** (exchange-rate scaled). No 2014-vs-2022 divergence on this axis; the only
  HFCS difference is the wave (2014→2021) + lower-case column fix (#5).

**Implication:** these `New_*` files are an older, orphaned Canadianization of household monetary
dimensions, primarily income, wealth, and debt, while retaining HFCS template structure. Do not assume
`Employment Industry` or other non-target variables were Canadianized unless the generating scripts
explicitly show that. For 2022, validated StatCan `36-10-0489` shares remain the preferred candidate for
Canadian employment-industry structure. Broader HFCS-2021 Canadianization using Canadian household data
is a later improvement, not part of the immediate collapse diagnosis.

**Current 2022 household status:** the DataWrapper currently uses raw European HFCS-2021. HFCS-2021 has
NOT been Canadianized using SFS/CIS. The validated StatCan employment shares are prepared and validated
but not yet wired.
