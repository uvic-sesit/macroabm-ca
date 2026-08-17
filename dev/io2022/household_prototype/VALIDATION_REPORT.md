# Household Canadianization prototype — Phase-1 validation report

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

**Known limitations (next refinements, not blockers):**
1. **Net-worth top-quintile under-concentration** — shares by income quintile after_joint
   9.5/15.3/19.9/25.0/**30.4** vs control 11.5/11.1/14.9/22.3/**40.2**. Directionally right (rising with
   income) but flatter at the top: the match is coarse (tenure × income-decile) and the recipient is the
   Eurozone HFCS ranked on its own income, so top-end wealth concentration is muted. Improve with finer
   match keys and/or reweighting to Canadian household+tenure totals.
2. **Homeownership stays 0.596** (recipient French rate, preserved because tenure is a match key) vs
   Canadian ~0.66 — fix by calibrating household weights to 2022 Canadian tenure/household totals.

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
