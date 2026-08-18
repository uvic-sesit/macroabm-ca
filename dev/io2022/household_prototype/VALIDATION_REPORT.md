# Household Canadianization prototype — Phase-1 validation report

## Task 2 — SHS 2023 consumption + saving (Phase-2, NOT yet committed) — 2026-08

Module `prepare_household_consumption.py` (`--real`). Reads the Phase-1 skeleton (unchanged), donor-matches
SHS 2023, derives consumption + saving, calibrates to the 2022 DHEA control. Phase-1 controls confirmed
untouched (assets $18.30T, income $1.502T, homeownership 0.6541).

**A. Field map / parser.** SHS 2023 fixed-width TXT parsed from its own SAS layout (`pumf_SHS_2023_i.SAS`,
`parse_shs_layout` → column ranges). Model-relevant fields: WEIGHTD (weight), PROV (region), TENURE
(1/2 own,3 rent), RP_AGEGP (6-band), HHTOTINC, TX010 (income tax), TC001 (total current consumption),
TE001 (total expenditure), FD001 (food, sanity only). Numeric fields carry explicit decimals. Per-household
SHS categories are NOT needed — the model takes consumption category vectors from the IOT, not microdata.

**B. Consumption concept = SHS TC001 "Total current consumption"** (actual demand for goods/services), NOT
TE001 total expenditure (= TC001 + income tax TX010 + personal insurance/pension EP011 + gifts/support
MG001). Used as the **BEHAVIOURAL consumption-share** = TC001 / disposable income (matches model field HFCS
HI0220 + driver "…as a Share of Income"; hfcs_synthetic_population.py: SavingRate = 1 − share). Household
levels are **NOT** scaled to national-accounts HFCE — HFCE is retained as a macro accounting control only
(user decision 2026-08).

**C. Donor match.** Hot-deck on tenure × survey-weighted income decile × age-band (HFCS 5-yr → SHS 6-band),
widening drops age first. Transplant the consumption LEVEL, not the raw ratio (ratio TC001/disp is unstable
near zero disposable income → runaway consumption; the level is bounded), then set the AGGREGATE household
APC to the SHS behavioural propensity (see D). Match full-cell 99.85% (126/83,162 widened to 2 keys), donor
5,479/5,481 used, max reuse 151, mean 15.2. 0 negative/NaN consumption.

**D. Behavioural calibration + saving.** Aggregate household APC calibrated to the **SHS 2022-equivalent
propensity 0.823** (= SHS TC001 1,188,923 / SHS disposable 1,444,212; APC is a ratio → vintage-stable, no
separate CPI backcast) applied to the recipient disposable-income base (= 1,502,342 control). Consumption/DI
= **0.823** (HFCE/DI = 1.006 is the macro reference, deliberately not the micro target). **Saving = DI −
out-of-pocket consumption = +265,565 $M (rate 17.7%)** — intentionally higher than DHEA HFCE-based net
saving (+31,545, ~2%) because TC001 excludes imputed rent etc.; not forced ≥0. APC by income quintile
**1.77 / 1.26 / 1.03 / 0.85 / 0.56** (monotone; Q1 dissaves, Q5 saves). Saving by quintile
−58.2/−36.2/−7.6/+51.9/+315.6 $B (bottom-3 dissave, top-2 save). Negative-saving incidence 44.9% of
households. Consumption-share: weighted median **0.903**, 44.7% >1 (low-income dissavers), 0 negative.

**Before → after (HFCE calibration → behavioural TC001/disp + income fix):** C/DI 1.006 → 0.823;
share median 1.05 → 0.903; share>1 56% → 44.7%; saving −9,039 (−0.6%) → +265,565 (+17.7%, out-of-pocket);
NaN income 4.7% → **0**.

**E. Status of prior open issues.**
1. **Consumption-share concept — RESOLVED** (user decision): behavioural SHS TC001/disp, not HFCE-scaled.
2. **NaN income — FIXED.** The SFS market-income sentinel (99999999, "not stated", spread across the
   distribution — not a top-code) is now hot-deck imputed within (tenure × after-tax-income-decile) cells in
   `load_donor`. NaN income 4,421 → 0; income aggregate stays $1.502T and **all Phase-1 controls are
   unchanged** (wealth quintiles 12.2/11.4/15.4/20.6/40.5, assets $18.30T, homeownership 0.6541).
3. **Household weight scale — RESOLVED.** See "Task 3" below.

## Task 3 — household weight scale — 2026-08

**Diagnosis of downstream weight use.** (a) Household *count* is set externally by
`readers.eurostat.number_of_households(country, year) / scale` (hfcs_synthetic_population.py:217), NOT by
`Weight.sum()`. (b) Synthetic sampling normalizes weights to probabilities `Weight/Weight.sum()` (:944) —
relative only. (c) Monetary values are re-anchored to external controls downstream: consumption and
investment to the IOT household columns (:795,:736), household deposits/loans to bank-data totals via
`rescale()` (matching_households_with_banks.py:101-102,190). So the model normalizes absolute weight AND
value scale away — the scale error was a **deliverable-correctness** issue (weighted aggregates and
per-household levels), not a model-breaking one.

**Problem.** Recipient HFCS weights summed to **161.5M** (Eurozone scale, ×10.45 the Canadian count), so the
Phase-1 value calibration deflated per-household values ~10× to hit the $ controls (mean income $9.3k, mean
assets $113k — both an order of magnitude too low), even though aggregates matched.

**Fix.** Rescale the recipient weights **uniformly** to the **CHS 2022 count = 15,455,000** households
(table 46-10-0083, provinces only — the SAME universe as the tenure control), in `load_recipient_hfcs`. A
uniform scale leaves weighted income-deciles (→ donor assignments), tenure shares, wealth-quintile shares,
APC/saving ratios and (unweighted) joint correlations exactly invariant; the accompanying value calibration
now lands per-household levels at realistic Canadian magnitudes. No donor re-matching; no relative-structure
change. Province could NOT be calibrated — the HFCS skeleton carries no province (all "CAN"); a region
imputation would be required and is out of scope.

**Validation (after rescale).** Represented households **15,455,000** (= target); owners **10,109,116** /
renters **5,345,884** (CHS controls 10,109,100 / 5,345,900); homeownership **0.6541**. Per-household means
now realistic: income **$97,208**, assets **$1,183,992**, consumption **$80,024**, saving **$17,183**.
Unchanged: assets $18.30T, income $1.502T, mortgage $2.127T, consumer $0.730T, deposits $2.035T; wealth
quintiles 12.2/11.4/15.4/20.6/40.5; joint mean|corr| donor 0.139 → after 0.140; consumption C/DI 0.823, APC
by q 1.77/1.26/1.03/0.85/0.56, saving by q −58/−36/−8/+52/+316 $B; match full-cell 99.99%. Province: not
calibrated (national skeleton) — the only residual gap.

**Household block status: READY for DataWrapper integration** — count, tenure, assets/debt/income, wealth
quintiles, consumption/saving, and joint structure all validate at Canadian scale; province is the sole
documented limitation (national pool), to be addressed only if the 13-region build needs household-level
province.



## Task 1 — distributional calibration (wealth concentration + tenure) — 2026-08

Both Phase-1 residuals are now resolved. Pipeline: HFCS skeleton → SFS-2023 donor match
(**tenure × income-decile × age-band**, national pool) → joint transplant → **tenure weight
post-stratification (CHS 2022)** → aggregate $ calibration.

**A. Wealth concentration — root cause found and fixed.** The under-concentration was **not** a
matching-key deficiency; it was a **binning bug**. Income deciles were built with unweighted
`pd.qcut` on rank (equal *count* per bin). SFS PUMF weights are highly unequal, so equal-count bins
misplace households and smear the income→wealth gradient, collapsing the top quintile from ~40 to 30.
Diagnostic proof: SFS's *own* weighted NW-share-by-income-quintile is 8.6/12.5/18.0/21.1/**39.8** (≈ the
40.2 control), but unweighted rank-quintiles give **30.9** — the entire gap. Switching to
**population-weighted deciles** (matching the DHEA definition) took L1 23.7 → **4.9**. Adding **age-band**
as a shared match key (HFCS `dhageh1b` → SFS `PAGEMIEG` 7-band) captures the asset-rich/income-poor
retiree effect and took L1 → **3.5**. `family_type` was **tested and rejected** (over-partitions cells,
dilutes the top to 38.9, max reuse 71→237). Result: **12.2 / 11.4 / 15.4 / 20.6 / 40.5** vs control
11.5/11.1/14.9/22.3/40.2 (top quintile 40.5; retiree "high bottom" Q1≥Q2 reproduced). No raking of the
balance sheet; the SFS joint structure is untouched.

**B. Tenure / homeownership — official 2022 control identified and calibrated.** Target =
**CHS 2022, table 46-10-0083** (Household characteristics by tenure): owner 10,109,100 / total
15,455,000 → **homeownership 65.41%**. Universe = private households in the 10 provinces (excl.
institutions, military camps, reserves/Indigenous settlements, collective dwellings, territories); unit =
household/dwelling (a member owns vs rents) — matches the model concept. Cross-checks: Census 2021 66.5%,
SFS 2023 64.8% (donor diagnostic only). Calibrated by **post-stratifying household weights on the tenure
margin** (owners/renters scaled to hit 65.41%, total count preserved, within-tenure structure intact) —
not an SFS-spine switch, not marginal rescaling. Result: **0.6541** (was 0.596).

**Full battery after Task 1 (REAL run):** aggregates still hit exactly (assets 18.30T, net worth 15.44T,
mortgage 2.127T, consumer 0.730T, deposits 2.035T, income 1.502T); joint mean|corr| donor 0.1395 →
after 0.1400 (preserved); match full-cell **99.99%** (10/83,162 widened by one key), donor reuse
15,894/16,241 (98%), max 41, mean 5.2; 0 negative asset/debt stocks, 64 negative incomes retained.

## REAL Phase-1 run (SFS 2023 donor + CIS 2022 + official 2022 controls) — 2026-08

Real PUMFs now present (`dev/raw_data/can_2022/pumf/`). `--real` builds: HFCS household skeleton →
SFS-2023 donor match (tenure × income-decile, national pool) → joint wealth/debt/income transplant →
calibrate to 2022 NBSA/DHEA controls. Employment stays 36-10-0489; Individuals.csv untouched.

**Aggregate controls — hit exactly (calibration):** total assets **$18.30T** (control 18.30), net worth
**$15.44T** (15.40), mortgage **$2.13T** (2.127), consumer debt **$0.73T** (0.730), deposits **$2.03T**
(2.035), income **$1.50T** (1.502). Business/other assets calibrated as the NBSA total-assets residual.

**Joint transplant vs marginal rescaling (REAL SFS):** donor mean|corr| **0.139** → joint transplant
**0.140** (reproduces the true Canadian dependence) vs marginal rescale **0.384** (wrong — the French
HFCS copula). Confirmed with real data: **joint transplant is correct, marginal rescaling is not.**

**Match / reuse:** 100% matched at full cell (tenure × income-decile); donor reuse 16,102 / 16,241
(99%), max 21, mean 5.2. **Missing/impossible:** 0 negatives in asset/debt stocks after selective clip;
42 negative incomes retained (legitimate losses); SFS income top-code (99999999) and CIS sentinel
(999999999996) handled.

**Known limitations (next refinements, not blockers):** — both RESOLVED in Task 1 (see top section).
1. ~~Net-worth top-quintile under-concentration (30.4 vs 40.2)~~ → fixed via weighted deciles + age-band
   match key → **40.5** (L1 3.5). Root cause was the unweighted `pd.qcut` binning, not coarse matching.
2. ~~Homeownership stays 0.596~~ → calibrated to the CHS 2022 control **0.6541** via tenure weight
   post-stratification.

## SHS consumption vintage — SELECTED: **2023** (deferred build)

Files present: `SHS_EDM_2019/2021/2023.zip` (in `pumf/shs_2019/`; naming to be corrected to a neutral
`pumf/shs/`). Decision: **SHS 2023** — temporally closest to 2022 (1 yr), post-pandemic-normalized, and
cleanly backcast to 2022 via CPI (×0.964, already in controls). **SHS 2021 rejected** (pandemic-distorted
spending — restaurants/travel/services suppressed). **SHS 2019 rejected** (pre-pandemic, pre-inflation,
3 yr stale, composition shift). SHS ships as fixed-width TXT + codebook PDF → needs a layout-parse step;
that plus a consumption donor-match + saving derivation is a **substantial Phase-2** → deferred.

## Data-availability caveat (historical — now resolved)

The SFS 2023 / CIS 2022 PUMFs and the 2022 DHEA/NBSA control tables **could not be obtained in this
environment** (manual StatCan portal download + licence). Therefore **no production Canadian numbers
were produced.** This report validates the **pipeline mechanics** and the **method choice** using the
local `New_Household.csv` (old SFS-2016/CIS-2017 output) as a **stand-in donor**. All absolute levels
below are NON-PRODUCTION (recipient is raw HFCS in EUR, unweighted to Canada, mixed units). Only the
**unit-invariant / structural** results are interpretable; they establish the method, not the values.

Recipient = 83,162 raw HFCS-2021 households (skeleton + IDs kept). Donor (stand-in) = 10,422 families.

## Headline result — donor joint transplant vs marginal rescaling

Two independent, unit-invariant measures both show **joint transplant preserves the Canadian joint
structure; marginal rescaling destroys it**:

| measure | donor (target) | **joint transplant** | marginal rescale | HFCS before |
|---|---|---|---|---|
| mean \|corr\| across the 12 balance-sheet fields | 0.255 | **0.240** (retains ~94%) | 0.193 | 0.178 |
| aggregate debt-to-income ratio | (donor) | **0.80** (donor-consistent) | 0.27 (mangled) | 0.69 |

Marginal rescaling matches each *marginal* but re-shuffles which household holds what, collapsing the
dependence back toward the recipient's (French) structure and producing an incoherent debt↔income
alignment. **Joint transplant is materially better** and is the correct choice for a balance-sheet ABM
where liquidity-constraint / leverage dynamics depend on the joint distribution. This conclusion is a
property of the method and is independent of the stand-in data.

## Requested validation outputs

**Structural / method (interpretable now):**
- homeownership (tenure is a match key, preserved): before **59.6%** (HFCS/French) → after 59.6%; real run must **benchmark to the Canadian 2022 rate (~0.66)** via SFS + control 17-10-0009.
- match quality: **99.1%** matched at the full 4-key cell (Type × Tenure × income-decile × province); 732/83,162 widened by one key.
- donor reuse: 9,918 / 10,422 donors used (95%); mean reuse 8.4, max 220 — even coverage, no pathological concentration.
- negatives / impossible values: **22–273** per field in the transplanted vector — inherited from the
  stand-in donor (the old file has some negative wealth/income cells). **Flags a required
  non-negativity guard** in the real pipeline (clip at 0 after transplant, before calibration).

**Levels / distributions (PENDING real data + controls):**
- total assets, net worth, mortgage debt, consumer debt, deposits, income: computed by the harness but
  NON-PRODUCTION here (see caveat); real values must be calibrated to 36-10-0580 / 38-10-0238 / 36-10-0587.
- wealth deciles/quintiles: require 36-10-0660 quintile shares (not filled) — `backcast_calibrate` is a
  no-op until `controls_2022.template.json` is populated.

## Known issues to harden before `--real`

1. **Non-negativity guard** — clip transplanted asset/debt/income at 0 (donors can carry negatives).
2. **Weight calibration** — calibrate donor/household weights to StatCan 2022 households by province
   (17-10-0009 / 11-10-0012); current prototype is unweighted-to-Canada.
3. **Units** — recipient HFCS is EUR; the real donor (SFS) is CAD, so transplant replaces units cleanly,
   but confirm no residual EUR value survives on non-transplanted monetary fields.
4. **Territory fallback** — SFS has no YT/NT/NU; the prototype uses a national ("CAN") pool. Document and,
   for the 13-region model, map territories to the national distribution explicitly.
5. **Tenure/type code alignment** — verify HFCS `hb0300`/`dhhtype` code values map to the SFS
   tenure/family-type categories (codebook) before matching; owner==1 assumed, must be checked.
6. **CIS 2022 income reconciliation** — Phase-1 keeps donor income; add the CIS 2022 level/source
   reconciliation step (source composition + 2022 levels) before wiring.

## 2022 official controls — OBTAINED and populated (`controls_2022.json`)

Downloaded programmatically via the StatCan WDS full-table endpoint (`download_controls.py`) and
extracted (`extract_controls.py`). Balance sheet = **Households sector, market value, Q4 2022 (2022-10)**;
flows = 2022 annual. Class totals ($M CAD):

| model target | 2022 control ($M) | source |
|---|---|---|
| residential real estate (main + other) | **7,789,772** | 36-10-0580 Dwellings + Land underlying dwellings |
| deposits | **2,034,716** | Total currency and deposits |
| financial assets (ex deposits/pensions) | **4,348,606** | Total financial assets − deposits − pensions |
| pensions | **2,807,177** | Life insurance and pensions |
| vehicles | **878,804** | Consumer durables (approx) |
| mortgages (liability) | **2,126,996** | Mortgages (liability side) |
| consumer debt | **729,932** | Consumer credit + Non-mortgage loans (liability) |
| total assets | **18,298,593** | Total assets |
| total liabilities | **2,893,808** | = assets − net worth |
| **net worth** | **15,404,785** | Net worth |
| disposable income (2022, annual) | **1,502,342** | 36-10-0587 Household disposable income |

Net-worth quintile shares (by income quintile, 2022 Q4, %): 11.5 / 11.1 / 14.9 / 22.3 / 40.2
(36-10-0660). Backcast 2023→2022: housing NHPI ×**1.002**, general CPI ×**0.964** (18-10-0205 / 18-10-0004).

Calibration mechanism **verified** on the stand-in run: the single-field target binds exactly
(deposits → 2,034,716 $M). Group targets (mortgages/consumer/residential) and the derived net worth are
corrupted **in the stand-in only** by the old file's NaN/negative/missing-column values — which is exactly
the missing-value handling `--real` must apply (below).

## Source-variable classification (step 5) — handling rule per variable type

Applied per source column **before** transplant/calibration. Exact special/missing codes come from the
SFS 2023 / CIS 2022 codebooks (pending PUMF); the class + rule are fixed now:

| class | model fields | rule |
|---|---|---|
| **stock, must be ≥ 0** | residence, other property, vehicles, deposits, financial assets, business equity, pensions | treat negatives as data error → set to 0 (or missing → impute); never legitimately negative |
| **debt liability (positive magnitude)** | HMR/other mortgages, credit line, credit card, other non-mortgage | reported as positive amount owed; enforce ≥ 0; 0 = no debt (not missing) |
| **net position, may be legitimately negative** | **net worth**, saving | **do NOT clip** — assets − liabilities can be < 0; carry through |
| **income (mostly ≥ 0, some sources signed)** | total income, employee/self-emp; investment/self-emp income can be negative (losses) | keep sign for income components; clip only the fields that are conceptually non-negative |
| **special / missing codes** | any | map SFS/CIS sentinel codes (e.g. blank / 96–99 per codebook) to NaN → impute within match cell; never treat sentinel as a real value |

Non-negativity is therefore applied **selectively** (asset/debt stocks yes; net worth / saving no), per the
above — not a blanket clip.

## Files

- `prepare_household_canadianization.py` — reproducible pipeline (`--standin` default; `--real` once
  PUMFs + `SFS_COLUMN_MAP`/`CIS_COLUMN_MAP`/`CONTROLS_2022` are filled).
- `SOURCE_MANIFEST.md` — exact datasets, IDs, vintages, URLs, control tables.
- `controls_2022.template.json` — 2022 aggregate/quintile control targets to fill from the tables.
- `PROTOTYPE_STANDIN_household.csv` — stand-in mechanics output (NON-PRODUCTION; git-ignored, not committed).
- `validation_report.json` — machine-readable metrics.

## DataWrapper MVP integration + Option B income reconciliation (2026-08)

The validated household block is wired into the 2022 DataWrapper behind a `canadianized_can_households_csv`
flag (CAN-2022; legacy/raw-HFCS path unchanged). See `dev/io2022/INTEGRATION_LOG.md` for the code seam.

**Currency:** Canadianized household monetary fields **bypass** EUR→CAD (`cad_native`); pooled-European
individual monetary fields convert **once**. Verified: household wealth $1.18M/hh (Canadian, not ×fx).

**Individuals (MVP):** the full pooled-European HFCS member pool is loaded (`no_country_filter`) to restore
exact household↔individual linkage over the 83,162-household ID space. Age/sex/education/member composition
and the within-household income split remain **pooled-European — not yet Canadianized**.

**Option B income reconciliation:** `set_household_income()` derives household Income from components whose
labour term comes from the (European) members. `reconcile_labour_income()` resets that labour term to
`validated_income − Canadian non-labour` and rescales members multiplicatively (within-household shares
preserved), so pre-matching household Income matches the validated Canadian distribution. Firm wage bill
(observed CoE, $346.6B/q unchanged) and 36-10-0489 employment are untouched; firm-matching still
renormalizes individual employee incomes to CoE. Verified: ON household income mean ≈ $98.8k (validated
$97.2k), quantiles ≈ validated; 0 NaN/negative; linkage intact.

**Income-floor limitation (~11% weighted):** households whose model-imputed non-labour income exceeds their
validated total income have labour floored at 0, so Income slightly exceeds validated (aggregate **+1.1%**).
Distribution by quintile:

| bottom→top | INCOME quintile floored | NET-WORTH quintile floored |
|---|---|---|
| Q1 | **54.2%** | 22.4% |
| Q2 | 0.4% | 11.1% |
| Q3 | 0.2% | 10.4% |
| Q4 | 0.1% | 5.7% |
| Q5 | 0.2% | 5.4% |

**Mechanism (confirmed): the model's endogenous social-transfer imputation, NOT a data/mapping error and
NOT the wealth→financial rule.** Among floored households, model-imputed transfers ($24.2k/hh annual) alone
exceed validated income ($17.9k/hh); financial income ($3.6k) is minor (only 5.3% of floored weight have
financial>income). The adapter's own transfers are a CIS share of income (always < income) and are
overwritten by `set_household_social_transfers` (regression on income/debt rescaled to
`total_social_transfers`). It is concentrated in the bottom income quintile (transfer-dependent, low
income). Documented MVP limitation; no household redesign.

**13q simple/default baseline (Canadianized) vs pre-household checkpoint:** real GVA 687.3→676.0B (−1.6%)
vs 687.3→676.9B (−1.5%) — essentially identical; unemployment 7.6→9.8% vs 7.7→9.1% (+0.7pp, household-demand
driven); all 13 regions stable; 0 NaN/inf.

**Provincial source data already available for a future refinement (deferred):** SFS 2023 (regional
geography, 10 provinces, no territories), CIS 2022 (province), SHS 2023 (province/region), CHS (provincial
tenure controls), 36-10-0489 (province×industry employment, already wired), provincial IO household
consumption/investment totals (already used). Territories (YT/NT/NU) need a fallback; small-province donor
pools may be sparse. Legacy `New_Household_provincial.csv` / `New_Individuals_provincial.csv` contain **no
province field** and were **not production inputs** (referenced only by `dev/validation/diagnose_gdp_gap.py`).
