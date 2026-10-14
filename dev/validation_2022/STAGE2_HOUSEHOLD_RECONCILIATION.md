# Stage 2 — Household data and 2022 initialisation: reconciliation

Scope: households, with government, firm, bank and housing counterparties only as needed. No simulation step
was executed: all model values are the **t0 state** of the pickle and of `Simulation.from_datawrapper(...)`
before `iterate()` (scripts in `scripts/`, outputs in `outputs/`). Flows are annualised (×4); $M CAD.

Reproduce:

```bash
.venv/Scripts/python.exe dev/validation_2022/scripts/hh_t0_pickle_extract.py dev/pkl_files/io2022_13prov_2022_canadianized_branchab87ee2.pkl branch
.venv/Scripts/python.exe dev/validation_2022/scripts/hh_t0_model_extract.py dev/pkl_files/io2022_13prov_2022_canadianized_branchab87ee2.pkl branch
.venv/Scripts/python.exe dev/validation_2022/scripts/hh_t0_first_step_static.py
.venv/Scripts/python.exe dev/validation_2022/scripts/hh_reconciliation_2022.py
```

## 2.0 Which 2022 initialisation?

Two pickles were examined:

| Tag | File | Built from | Note |
|---|---|---|---|
| `canonical` | `dev/pkl_files/io2022_13prov_2022_canadianized.pkl` (copy, sha256 `4e103fd5…0d67`) | `c796755` code, 19 Aug | the pickle all 2022 baseline runs used |
| `branch` | `dev/pkl_files/io2022_13prov_2022_canadianized_branchab87ee2.pkl` | this branch (`ab87ee2`), `build_2022_datawrapper.py --canadianized --scale 1000`, raw data read-only from `SESIT/macroabm-ca/dev/raw_data` | log `outputs/rebuild_pickle.log` |

**Finding I-0 (data/initialisation, confirmed).** The canonical pickle predates `43089de` (14 Sep, SOCX public
cash benefits). It therefore carries "Other Social Benefits" from the old fallback (`all_benefits_gdp_pct`,
OECD-average total benefits): 516.4B vs 239.6B with branch code. All other household fields are identical
(`outputs/hh_t0_*_national_{canonical,branch}.csv`), except labour income, which the Option-B reconciliation
sets as a residual (I-6). The branch pickle is the reference below. The canonical figures are in
`outputs/hh_reconciliation_2022.csv`. **Runs on `feature/itc-user-cost` that load the canonical pickle use a
transfer level the branch code no longer produces.**

## 2.1 External benchmarks (provenance)

All values were retrieved 2026-10-13 through the DBnomics API (STATCAN mirror, `indexed_at` 2026-09-30) or the
StatCan WDS full-table CSV. Raw files are in `benchmarks/raw/`; see `benchmarks/BENCHMARKS.md`.

### Saving-rate discrepancy: the published figures are consistent

36-10-0224, 2022 annual, $M (series 1.27, 1.29, 1.32, 1.30, 1.31):

```
Disposable income (DI)                       1,502,340
− Household final consumption expenditure    1,511,382
= DI − HFCE                                     −9,042
+ Change in pension entitlements (D.8)          40,585
= Household net saving (B.8n)                   31,543
Saving rate = 31,543 / 1,502,340             =  2.10 %   (published 2.1)
```

The −$9.1B is not an extraction error or a vintage mismatch. Under the SNA saving identity
(`B.8n = B.6n − P.3 + D.8`), households' pension wealth accrual is added to saving but not to DI. StatCan
divides net saving by DI without D.8 to get the published ratio. Consequences for the model:

* The model has no D.8 and no pension-entitlement accounting. Its household saving concept should be compared
  either with `DI − HFCE = −9.0B` (−0.6% of DI) or with `S − D.8`. It should not be compared with the
  published 2.1%.
* The prototype's DHEA control (36-10-0587) carries the same identity (−9,039 vs +31,545). That earlier
  finding is confirmed.

### Households vs households + NPISH

The handoff's balance-sheet figures (assets 18,561; NW 15,602; deposits 2,092; mortgages ≈ 2,118) are
**households + NPISH** (series 1.3.1.x). The model's household concept and the prototype's controls use
**households only** (1.4.1.x): assets 18,298.6; NW 15,404.8; deposits 2,034.7; mortgages 2,127.0 (all mortgages)
/ 2,115.4 (residential). NPISH hold 262.3B of assets. The figure of about 2,118 in the handoff is HH+NPISH
*residential* mortgages (1.3.1.105). The households-only series are used throughout.

## 2.2 Reconciliation table (branch pickle, t0)

`count-adj` rescales household-calibrated model quantities by 15,455,000 / 17,778,710 = 0.8693 (see I-1).
It does not apply to firm-side (CoE) or IO-pinned (HFCE) items.

| SNA / balance-sheet line | StatCan | Model t0 | Resid. | Count-adj. resid. | Attribution |
|---|---:|---:|---:|---:|---|
| Households (number) | 15,455,000 | 17,778,710 | +15.0% | — | **I-1 initialisation error** |
| Compensation of employees | 1,378,529 | firm wage bill 1,386,338 | +0.6% | n/a | data OK (firm side). Households receive 1,076,913 net at t≥1 (I-6, A2) |
| Net mixed income (incl. 127.6B rental) | 224,841 | 0 | −100% | — | **missing account** (S-H9) |
| Rental income of households | 127,567 | 12,104 (landlords, net of PIT) | −90.5% | −91.8% | concept (owner-occupied net imputed income excluded) **+** data error (I-8) |
| Property income received | 246,588 | FA income 97,965 + deposit interest 8,008 = 105,973 | −57.0% | — | concept + calibration (I-10). FA income has no payer (A4) |
| Property income paid | 84,211 | 35,121 (interest on M + L) | −58% | −64% | **rates** (I-11): mortgage 0.97%/yr, consumer 3.06%/yr; consumer credit missing (I-9) |
| Transfers from general government | 286,670 | TR 239,615 + UB 16,710 = 256,324 | −10.6% | −22.3% | concept + source (I-4). Private pensions folded in; UB not received (A3) |
|   of which EI | 20,631 | 16,710 | −19.0% | | source (OECD UB % GDP, nearest year) |
| Transfers from corporations | 121,500 | 0 | −100% | | **missing account** |
| Personal income tax | 348,148 | 112,392 (booked; not paid by hh) | −67.7% | | **calibration error** (I-3: τ_inc = 0.09 default) + **accounting** (A2, A5) |
| Contributions to social insurance | 131,280 | 194,076 (ee 18.3 + er 175.8) | +47.8% | | concept (employer SSC routed via firms) + calibration (τ_ee = 1.58%) |
| Disposable income | 1,502,340 | "Income" 1,733,298 | +15.4% | **+0.3%** | per-household level = DI by construction; aggregate = count error |
| HFCE | 1,511,382 | (1+τ_vat)·C = 1,465,014 | −3.1% | n/a (IO-pinned) | basic→purchaser margin: VAT 2.74% vs all taxes on products |
| DI − HFCE | −9,042 | +268,284 | | +41,739 | **artefact of I-1** (count-adjusted saving 2.8% of income) |
| Paid rent (HFCE) | 81,506 | rent transfers 13,301 | −83.7% | −85.8% | **data error** (I-8: French HFCS "Rent Paid") |
| Imputed rent (HFCE) | 235,938 | 218,283 | −7.5% | | source (ICIO national × proxy fraction, allocated by output) |
| Currency & deposits | 2,034,716 | 2,405,428 | +18.2% | **+2.8%** | count error |
| Total financial assets | 9,190,499 | 10,748,825 | +17.0% | **+1.7%** | count error |
| Dwellings + land under dwellings | 7,789,772 | 8,500,499 | +9.1% | −5.1% | count error + dwelling outlier/imputation at build |
| Consumer durables (+ SE businesses) | 878,804 (+439,518 SFS) | 1,490,256 | +13.0% vs 1,318,322 | −1.7% | count error; concept merge (S-H9) |
| Mortgages | 2,126,996 | 2,442,310 | +14.8% | **−0.2%** | count error |
| Consumer credit | 597,597 | 0 | −100% | | **initialisation error** (I-9: credit lines/cards zeroed) |
| Non-mortgage loans | 132,335 | 380,117 | +187% | | SFS "other loans" ≠ SNA split; compare consumer total 729,932 → −48% (count-adj −55%) |
| Total liabilities | 2,893,808 | 2,822,427 | −2.5% | −15.2% | I-9 (missing consumer credit) offset by count error |
| Net worth | 15,404,785 | 17,917,152 | +16.3% | **+1.1%** | count error |

(`outputs/hh_reconciliation_2022.csv` has full precision and the canonical-pickle rows.)

## 2.3 Initialisation findings (households)

**I-1 Household count and provincial allocation (initialisation error, confirmed).**
`n_households = Eurostat households(FRA) × pop(CAN)·va_ratio(r) / pop(FRA) / scale`
(`hfcs_synthetic_population.py:219`, `synthetic_country.py:468-470`, `world_bank_reader.py:203-222`). Two
consequences follow.
(a) National count: 17.78M vs CHS 15.455M (+15.0%). French household size is applied to the Canadian population.
(b) Provincial allocation follows **value-added share, not population**. Ratio of model to CHS households:
AB 1.85, SK 1.61, BC 1.15, NL 1.14, ON 1.13, MB 1.04, QC 0.91, PE 0.80, NS 0.78, NB 0.77
(`outputs/hh_counts_vs_chs2022.csv`). Per-household magnitudes are Canadian (SFS/CIS/SHS), so every aggregate
household stock and income inherits the count error. Count-adjusted, DI, deposits, financial assets,
mortgages and net worth are within ±3%.

**I-2 Regional saving rates are calibration residuals of I-1 (confirmed).** Consumption is pinned per region
to the IO household column (`normalise_household_consumption`, `hfcs_synthetic_population.py:820-887`). Income
scales with the (mis)allocated household count, so the implied regional saving rate absorbs the count error.
The income-weighted rates range from −10.0% (NS) and −9.8% (NB) to 38–40% (AB, SK) and 61% (NU). Across the 10
provinces, **corr(model/CHS household ratio, saving rate) = 0.83**. The national rate (15.5% of model income)
is also an artefact. Count-adjusted, it is (1,506.7 − 1,465.0)/1,506.7 = **2.8%**, against the comparable
SNA concept `(DI − HFCE)/DI = −0.6%`. The remaining gap is the basic-price C plus 2.74% "VAT" falling short of
HFCE by 46B.

**I-3 Personal income tax rate (calibration error, confirmed).** `τ_inc = 0.09` for every region: CAN is not
in `force_tau_income`, and `read_tau_income` returns the hard-coded "OECD average"
(`oecd_economic_data.py:601-627`). The implied PIT is 112B against 348B in StatCan. The same 9% sets the
gross/net wage wedge Θ (I-6) and the landlords' net rental income. Employee SSC is 1.58%. Employer SSC is
13.1–18.2% by region.

**I-4 Government transfers (source and concept; partly fixed on branch).** Branch: `OSB = SOCX cash 10.1% ×
GDP_r/4 − UB`, giving TR = 239.6B, plus UB of 12.2B (government total) or 16.7B (sum over unemployed
individuals). The government's UB total and the individual-level sum differ by 4.5B (+37%) at t0. The
benchmark is 286.7B. Concept problems: (i) at build, private pensions (`Income from Pensions`, CIS
private-pension share) are **added to "Regular Social Transfers"** and then rescaled to the government total
(`hfcs_synthetic_population.py:619-665`); (ii) the distribution is then replaced in the model by an equal
amount per household (H4); (iii) GDP comes from World Bank data that end in 2021 (nearest-year fallback).
Canonical pickle: 516.4B (I-0).

**I-5 "Income" concept (specification/initialisation, confirmed).** The validated per-household income is
calibrated to DHEA disposable income (`controls_2022.json`, "Income" → 1,502,342). The model then uses
`Income` as follows. Its labour component is net of PIT and employee SSC (A2). Transfers and FA income are
gross; PIT on FA income is booked by the government but never charged (A5). Rental income is net. The t0
household `Income` is therefore a disposable-income concept per household. At t≥1, however, household income is
rebuilt from model components (§2.4), so it is not anchored to DI.

**I-6 Labour income is a reconciliation residual and is overwritten at t=1 (initialisation error,
confirmed).** At t0, household labour income = validated income − (TR + rent + FA)
(`reconcile_labour_income`, `hfcs_synthetic_population.py:574-617`). It is called *after* individuals are matched
to firms and rescaled to the firm wage bill (`matching_individuals_with_firms.py:185-205`), so it undoes that
rescaling. At t=1 `WorkEffortFirmWageSetter` resets every employee's wage to the firm-consistent net wage.
National t0 → t1 labour income: branch 1,383.6B → 1,076.9B (**−22.2%**); canonical 1,123.7B → 1,076.9B
(−4.2%). Provincial changes on branch range from −52% (SK) and −39% (AB, NL) to −12% (NB). In the
canonical pickle the provincial changes have both signs. Also, 196B (branch) / 144B (canonical) of
"employee income" sits with non-employed individuals at t0 and disappears at t=1. The CoE side is consistent:
the firm wage bill of 1,386.3B matches StatCan CoE of 1,378.5B to within 0.6%.

**I-7 Saving-rate rule discards the calibrated distribution (specification/calibration, confirmed).**
`AverageSavingRatesSetter` sets every household's `s` to the **unweighted mean** of the t0 household rates
(`households.py:217`, `saving_rates.py:89`). That mean is far from the income-weighted rate implied by t0
consumption (QC 0.030 vs 0.133; ON 0.022 vs 0.102; national 0.083 vs 0.155). Static first-step indicator
(`outputs/hh_t0_first_step_static.csv`; cpi = 1, π^e = 0, expected income = firm-consistent income): the t=1
consumption target departs from t0 consumption by **−8.5%** nationally on branch (+8.3% canonical). The
provincial range is −30% (SK) to +2% (YT) on branch and −13% to +19% on canonical. The t0 economy is
therefore not a fixed point of the household rules; first-step jumps in C are expected from initialisation
alone. Stage 4 should quantify them in simulation.

**I-8 Actual rent (data error, confirmed).** "Rent Paid" is carried from the retained French HFCS row
(`canadianized_household_adapter.py:62, 113-123`). The adapter flags it as cad-native, so the EUR amounts are
treated as CAD and never Canadianised. Total renter payments are 13.3B against HFCE paid rent of 81.5B
(−84%). Landlord rental income (12.1B = 0.91 × 13.3B) is rescaled to this total
(`matching_households_with_houses.py:326-332`). The `rental_gross_yield` residual in the adapter therefore
affects only the allocation, as documented, and not the level.

**I-9 Consumer credit dropped (initialisation error, confirmed).** `set_household_deposits` sets credit-line
and credit-card balances to 0 (`hfcs_synthetic_population.py:442-446`). Model consumer debt is 380B ("other
non-mortgage loans") against an SNA total of 729.9B. Count-adjusted it is −55%.

**I-10 Financial-asset income (calibration/concept).** `c_FA` = 0.31% per quarter, or 1.25% per year
(`hfcs_synthetic_population.py:667-685`), on OFA of 8,343B. OFA includes the 2,807B of pension and
life-insurance reserves. FA income = CIS investment-income share × validated income ≈ 98B. The SNA property
income received is 246.6B (interest, dividends, withdrawals, and investment income attributed to
insurance/pension holders). The model has no payer for this income (A4).

**I-11 Interest rates (data, suspected).** At t0 the annual rates are: mortgages 0.97%, consumer loans 3.06%,
deposits 0.33%, policy 1.48%. They are set from the pickle bank data (converted annual→quarterly,
`3d2be8e`). A mortgage rate below the policy rate is implausible for 2022; the effective rate on outstanding
Canadian mortgages was roughly 3%. The benchmark still has to be retrieved (Bank of Canada effective household
rates) before this is confirmed. Interest paid of 35B vs 84B is consistent with rates that are too low.

**I-12 Tenure (calibration, partly confirmed).** Model owner share (codes 1, 2, 4) is 71.8% against CHS
65.4%. Code 4 ("free use", 5.8%) is counted as owner. The share is uniform across provinces (68–73%) because
one national file is sampled everywhere; CHS ranges from 60.2% (QC) to 75.0% (NL). Code 2 (owner with
mortgage) covers only ≈3% of households although mortgages total 2.4T, so the codes do not separate mortgagors.
Social housing: 0 households.

**I-13 Imputed rent and sector L (accounting, confirmed with data).** The provincial IO household vector
contains sector L = 312.7B. Paid plus imputed rent in HFCE is 317.4B. Separately the model attaches imputed rent of
218.3B to owner-occupied dwellings and adds it to every GDP measure (`economy.py:993-1001, 1209-1217,
1268-1278`). The ICIO-path removal of imputed rent from household L consumption (`icio_reader.py:236-266`) is
**not** applied in the 2022 provincial path: `default_readers.py:497-513` replaces the IOT and only
re-allocates the national imputed-rent number by regional **output** share. Households therefore buy imputed
rent as cash consumption from L-sector firms without receiving the matching income, and GDP counts imputed
rent twice. This supersedes the July-2026 checkpoint lead, which applied to the 2014 ICIO path where only
*actual* rent overlapped.

**I-14 Other inherited items.** Individuals are the French HFCS skeleton (age, sex, composition). Consumption
weights by income quantile are French ("Overwriting Consumption Weights by Income with French Data" in the
build log). Dividend payout ratio = 1.116 (>1, Eurostat), unused. Zero FIRM/BANK_INVESTOR individuals.
Household investment of 180.6B at basic prices (225B with τ_cf = 24.5%) is pinned to the IO household-capital
column.

## 2.4 Implied first-quarter household account (static, branch)

Under the t0 rules, with the wage reset applied and no market rationing (cpi = 1, π^e = 0):

| Item | $B/yr | Note |
|---|---:|---|
| Wages received (net, real) | 1,076.9 | A2: firms pay 1,386.3; government books PIT 95.4 + SSC 181.7; 32.3 (2.3% of the wage bill) is unrecorded at cpi = 1 and grows with cpi |
| Social transfers | 239.6 | equal per household |
| UB | 0 received / 16.7 planned | A3 |
| Rental income | 12.1 | |
| FA income | 98.0 | no payer (A4) |
| **Realised income** | **1,426.6** | vs t0 "Income" 1,733.3 |
| Consumption target (basic) | ≈1,304.7 | I-7 static indicator |
| VAT | 0 paid / 35.7 booked | A1 |
| Rent transfers | 13.3 | |
| Investment (basic) | ≈150–181 | rate × expected income |

Realised income falls about 18% below the t0 calibration in the first quarter. This is not a behavioural
response; it follows from I-6 and A3.

## 2.5 HFCS spending propensity (≈0.61) revisited

The July-2026 "≈0.61 non-consumption propensity" came from the French HFCS consumption-share variable on the
2014 build. On the Canadianised branch it no longer exists. Per-household shares come from SHS 2023 TC001 /
disposable income (median 0.903, aggregate 0.823). `normalise_household_consumption` then rescales `(1 − s)`
multiplicatively so that aggregate basic-price consumption equals the IO household column, and the rule
finally replaces all household rates with the regional unweighted mean (I-7). The checkpoint's conclusion still
holds, now for different reasons: `s` is a calibration residual (I-2) and should not be read as an SNA saving
rate or as a behavioural parameter.

## 2.6 Provincial aggregation

The household block is the same national file in every province. Provincial differences come only from (i)
the VA-based household count, (ii) the regional IO consumption pin, and (iii) the provincial labour-force
rates. Owner shares, income distributions, wealth per household and rent per renter are identical in
distribution across provinces. Province-specific household benchmarks (CHS tenure, DHEA by province) are not
yet targeted. Provincial totals add to national for every flow and stock (sums by construction).
