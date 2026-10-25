# Household distribution, payment default and GDP bridge — QE review, 2026-10-25 UTC

**Stop for review: Q fails; E is accounting-consistent but fails its empirical loss/arrears gate; FB fails initialization and unit-cost gates. No combined run, B2 retest, Phase B or C_dp_005 port.** F_CFC is adopted as the accepted firm-data baseline, with P off, as instructed. That adoption is a data improvement, not a validation pass.

Money is CAD billions unless specified. Every primary 12-quarter result uses seeds 0–2, run serially. Accepted pickles are unchanged; the FB experiment has a new filename and is not promoted. Report date is UTC; the Windows local date during much of the work was 24 October.

C, F, F_CFC and Q retain the old household insolvency rule. E_complete applies E on F_CFC only; Q+E is not run because Q fails. C is a historical pre-F firm-data/rule control; F, F_CFC, Q and E use the accepted firm payment-default rule.

## Steps, commits, tests and gates

| Step | Commit | Tests | Result |
| --- | --- | --- | --- |
| 1 F_CFC baseline | 9cc1563 | 1 regression | Accepted data baseline; earlier margin gate remains failed |
| 2 Q | f0b6aee | 3 propensity regressions | Q-G0 fails on all seeds; see full gate table |
| 3 E | d23d31e | 5 servicing/foreclosure regressions | E empirical gate fails; accounting passes after two mechanical fixes |
| 3 rental PIT scope | f0fc613 | 1 rent-counterparty regression | Public rent excluded from private-landlord PIT base |
| 3 foreclosure occupancy | 4ef8b68 | 1 occupancy regression | Third-party tenant cannot be overwritten without an executed move |
| 3 unsecured overdrafts | a1d55a6 | 1 exact bank-identity regression | Negative-deposit claims included; formal loan stocks preserved |
| 2 secondary SHS ranks | 840a97d | 1 payroll-identity regression | Multiplicative tax gross-up; 15 read-only replays preserve macro/DHEA paths |
| 4 GDP bridge | c89ea09 | 3 valuation regressions | All 13 unchanged GDP checks fail; margin passes; 102 cost exceptions |
| 5 combined / B2 retest | none | not run | Dependencies fail; no tuning |
| 6 gates / report | 367bc04 | Share-gate + direct negative-net-worth regressions; full suite | Review packet only |

## Headline: shrinkage and an initial GDP scope error

The raw Q0→Q12 contraction contains a **64.132B t0 housing-memo addition**. `Economy.from_data` always adds real and imputed rent at initialization; `Country.update_realised_metrics` passes both as zero thereafter when `housing_services_in_household_io=True`. All three accepted inputs carry that flag. The t0 expenditure identity therefore adds housing already inside sector L, while later GDP uses the IO scope. This is a reporting/initialization inconsistency, not an unobserved economic shock. It is recorded, not removed by a cash, inventory or trade plug.

The scope-adjusted column subtracts that identified t0 duplicate **for diagnosis only**; it does not change the model, inputs or gates. PPI-deflated GDP is a proxy, not a chained-volume SNA measure. Consumption uses the model CPI and investment the CFPI. Raw nominal and deflated endpoint levels for every arm are in [headline endpoint levels](outputs/QE/headline_endpoint_levels.csv); employment is expanded persons, price level is nominal GDP divided by the PPI-deflated proxy.

The economy’s t0 C/I series are created before closure reanchoring updates household plans. The single housing-scope adjustment is therefore not a fully reconciled initial equilibrium or an accepted GDP correction. Q1→Q12 is also shown to expose contraction after the first settlement.

| arm | seed | nominal_GDP_pct | PPI_deflated_GDP_pct | scope_adjusted_GDP_pct | Q1_Q12_GDP_pct | national_account_C_pct | investment_pct | employment_pct | price_level_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C | 0 | -3.701 | -7.824 | 0.525 | 0.813 | 4.071 | -5.025 | -1.241 | 4.473 |
| C | 1 | -8.545 | -9.198 | -0.974 | -0.802 | 0.005 | -3.085 | -2.115 | 0.718 |
| C | 2 | -14.978 | -10.673 | -2.582 | -2.473 | -6.761 | -8.606 | -3.751 | -4.820 |
| E | 0 | -12.755 | -14.746 | -7.024 | -6.602 | -9.839 | -20.009 | -6.857 | 2.336 |
| E | 1 | -14.025 | -16.303 | -8.722 | -8.398 | -8.872 | -22.147 | -6.355 | 2.722 |
| E | 2 | -25.712 | -18.240 | -10.835 | -10.618 | -23.072 | -34.433 | -10.678 | -9.140 |
| F | 0 | -13.184 | -14.582 | -6.846 | -6.427 | -8.115 | -20.294 | -6.953 | 1.637 |
| F | 1 | -13.643 | -16.500 | -8.937 | -8.555 | -7.069 | -19.092 | -6.967 | 3.422 |
| F | 2 | -18.143 | -18.058 | -10.636 | -10.390 | -12.792 | -23.997 | -8.197 | -0.104 |
| F_CFC | 0 | -15.269 | -15.018 | -7.321 | -6.901 | -12.691 | -24.249 | -5.180 | -0.295 |
| F_CFC | 1 | -16.472 | -16.756 | -9.216 | -8.893 | -10.293 | -24.785 | -7.091 | 0.340 |
| F_CFC | 2 | -24.260 | -20.282 | -13.062 | -12.851 | -18.394 | -36.207 | -11.744 | -4.989 |
| Q | 0 | -15.694 | -13.520 | -5.687 | -5.233 | -8.813 | -24.317 | -4.909 | -2.514 |
| Q | 1 | -9.083 | -13.678 | -5.859 | -5.522 | 4.446 | -20.215 | -4.864 | 5.323 |
| Q | 2 | -19.334 | -16.945 | -9.423 | -9.197 | -12.378 | -27.965 | -7.930 | -2.876 |

For F_CFC seed 0, raw nominal GDP is 772.215B at Q0 and 654.309B at Q12. The comparable t0 scope diagnostic is 708.084B; the Q1 PPI-deflated level is 704.885B and Q12 is 656.243B. A material contraction remains after allowing for the initialization artifact.

### Expenditure decomposition, Q0→Q12

| arm | seed | C | G | I | M | X | initial_housing_scope_change | inventories |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C | 0 | 14.911 | 26.950 | -7.834 | -28.040 | 18.703 | -64.132 | 10.864 |
| C | 1 | 0.018 | 2.391 | -4.810 | -20.622 | 10.128 | -64.132 | 11.037 |
| C | 2 | -24.763 | -8.460 | -13.418 | 18.049 | -29.469 | -64.132 | 6.531 |
| E | 0 | -36.037 | 23.462 | -31.195 | 3.213 | -5.335 | -64.132 | 11.532 |
| E | 1 | -32.494 | 20.945 | -34.529 | 1.733 | -3.749 | -64.132 | 3.923 |
| E | 2 | -84.501 | -15.659 | -53.682 | 62.948 | -64.206 | -64.132 | 20.678 |
| F | 0 | -29.720 | 21.497 | -31.640 | 6.745 | -8.733 | -64.132 | 4.177 |
| F | 1 | -25.892 | 3.773 | -29.765 | 7.494 | -9.475 | -64.132 | 12.647 |
| F | 2 | -46.853 | -5.554 | -37.413 | 32.176 | -35.532 | -64.132 | 17.207 |
| F_CFC | 0 | -46.480 | 22.756 | -37.806 | 12.296 | -13.953 | -64.132 | 9.412 |
| F_CFC | 1 | -37.697 | 3.259 | -38.641 | 13.357 | -15.560 | -64.132 | 12.211 |
| F_CFC | 2 | -67.369 | -21.284 | -56.449 | 48.536 | -50.570 | -64.132 | 23.932 |
| Q | 0 | -32.277 | 11.224 | -37.911 | -1.357 | -4.639 | -64.132 | 7.902 |
| Q | 1 | 16.282 | 7.079 | -31.516 | -20.325 | 18.255 | -64.132 | 4.216 |
| Q | 2 | -45.336 | -13.665 | -43.600 | 30.298 | -36.021 | -64.132 | 23.153 |

The table sums exactly to the model expenditure-GDP change. `initial_housing_scope_change` is −64.132B, not a new flow. C and I contract in the accepted firm baseline while G rises. The model also has an existing multi-country GDP routine that balances reported exports/imports against output GDP. Thus this is a descriptive accounting bridge; the X/M changes cannot all be interpreted as independently observed trade-demand responses. No new balancing trade flow was introduced here. Firm CFC changes alter replacement demand, costs and household income jointly; this round does not causally isolate those channels.

## Initial consumption distribution: inherited failure and Q

C, F and F_CFC all inherit the t0 distribution failure without a B2 wealth term. Seed 0 shares below; [all seeds, endpoints and raw annualised levels](outputs/QE/distribution_endpoints.csv) and [all quarters](outputs/QE/consumption_distribution.csv) are retained.

DHEA income-rank comparison, percent of total household consumption:

| arm | quarter | Q1_share_pct | Q2_share_pct | Q3_share_pct | Q4_share_pct | Q5_share_pct |
| --- | --- | --- | --- | --- | --- | --- |
| C | 0 | 4.109 | 7.550 | 13.008 | 21.719 | 53.614 |
| C | 12 | 7.498 | 12.790 | 19.239 | 24.284 | 36.188 |
| E | 0 | 4.109 | 7.550 | 13.008 | 21.719 | 53.614 |
| E | 12 | 6.342 | 11.812 | 18.599 | 24.775 | 38.471 |
| F | 0 | 4.109 | 7.550 | 13.008 | 21.719 | 53.614 |
| F | 12 | 6.058 | 11.741 | 18.723 | 24.946 | 38.533 |
| F_CFC | 0 | 4.109 | 7.550 | 13.008 | 21.719 | 53.614 |
| F_CFC | 12 | 6.149 | 12.151 | 18.790 | 24.788 | 38.123 |
| Q | 0 | 7.813 | 11.308 | 16.770 | 22.749 | 41.360 |
| Q | 12 | 7.399 | 13.032 | 18.807 | 24.390 | 36.373 |

SHS before-tax household-income-rank comparison, percent:

| arm | quarter | Q1_share_pct | Q2_share_pct | Q3_share_pct | Q4_share_pct | Q5_share_pct |
| --- | --- | --- | --- | --- | --- | --- |
| C | 0 | 3.527 | 6.706 | 12.349 | 21.294 | 56.124 |
| C | 12 | 6.827 | 10.880 | 17.030 | 24.602 | 40.660 |
| E | 0 | 3.527 | 6.706 | 12.349 | 21.294 | 56.124 |
| E | 12 | 5.899 | 10.293 | 16.702 | 24.518 | 42.588 |
| F | 0 | 3.527 | 6.706 | 12.349 | 21.294 | 56.124 |
| F | 12 | 5.624 | 10.267 | 16.811 | 24.767 | 42.530 |
| F_CFC | 0 | 3.527 | 6.706 | 12.349 | 21.294 | 56.124 |
| F_CFC | 12 | 5.747 | 10.517 | 16.857 | 24.560 | 42.318 |
| Q | 0 | 6.620 | 10.533 | 15.709 | 22.784 | 44.354 |
| Q | 12 | 7.118 | 11.361 | 17.006 | 24.153 | 40.362 |

Primary benchmark: [StatCan DHEA 36-10-0587-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610058701), 2022 HFCE vectors v116884012/035/058/081/104; disposable-income vectors **v116884005/028/051/074/097**. The source consumption/disposable-income ratios are 1.978521, 1.284347, 1.172217, 0.913873, 0.740618. Q interpolates linearly across household-weighted equivalised-income percentiles .1/.3/.5/.7/.9, clamps outside those midpoints, freezes initial propensities, and applies one national multiplier **1.097931**. Initial account C is 377.8455B/q, matching 36-10-0112 v62305982. F’s consumption function and floors are retained; Q has no B2 wealth term.

DHEA quintiles use OECD-modified equivalised household disposable income, household weights, adult/child factors 1/.5/.3. Model rank income is per-household cash DI divided by those units, with regional expansion factors removed. DHEA DI includes noncash/imputed items missing from the model proxy. Applying source ratios to a different income distribution **does not guarantee source consumption shares**: Q-G0 fails, rather than passing “by construction”. No quintile-specific second rescale or parameter tuning was applied.

The five DHEA consumption values total 1,511.381B/year; the retained 36-10-0112 national target is 1,511.382B/year. The 1M source/vintage-rounding difference is preserved. The permitted single national rescale does not enforce five quintile totals; interpolation also does not impose exact within-quintile totals.

DHEA target shares: 13.384/15.924/19.428/21.693/29.571%. Secondary [SHS 11-10-0223-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110022301), 2023 revised 2026-09-18, uses un-equivalised before-tax household-income quintiles and current-consumption mean vectors v54529951/993, v54530035/077/119. Its shares normalise equal-quintile published means (an approximation, because quintile household counts are not published). Owner-imputed rent and other national-account imputations differ from SHS scope; reference year and coverage also differ. Executed imputed housing services cannot be separated from the model L bundle, so no SHS-comparable subtraction is fabricated. Including owner-imputed rent tends to raise upper-quintile shares.

The secondary wage gross-up is corrected to net wages / [(1−PIT)×(1−employee contributions)], matching the payroll identity, rather than the legacy additive denominator. All 15 primary configurations are replayed serially with accounting checks and exact macro/DHEA path comparisons; only secondary SHS rank assignments change. [Corrected distributions and replay proofs](outputs/QE/distribution_corrected) supersede original SHS CSVs. Income concepts still lack unobserved SNA/SHS components; no missing income is invented.

### Q gates, unchanged after measurement

| seed | Q_G0 | Q_G1 | Q_G2 | Q_G3 | constrained_slope_pp | Q12_saving_pct | max_zero_goods_pct | max_accounting_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | False | True | False | False | 1.962 | 0.542 | 1.085 | 7.918e-15 |
| 1 | False | True | False | False | 1.922 | -3.098 | 1.014 | 8.887e-15 |
| 2 | False | True | False | False | 1.894 | 1.117 | 1.240 | 6.909e-15 |

Q-G0 is only the construction check, relative SHARE deviation ≤15%; it is not validation. Q-G1 tests positive-income zero-goods share strictly <2% at t0 and every quarter. Q-G2 tests Q12 relative shares. Q-G3 retains Gate B: constrained-share Q4–Q12 OLS slope ≤.25 percentage point/q, saving [−5.6%,4.4%], Q1 C≥95% of benchmark, accounting ≤1e−8. All gate details remain in [gates.csv](outputs/QE/gates.csv).

### Deposits-only sensitivity, read-only at t0

| definition | L | target | gap | hypothetical_kappa_gap | kappa_gap_pct_C |
| --- | --- | --- | --- | --- | --- |
| deposits_only | 2,035.768 | 132.090 | 1,903.678 | 19.037 | 5.038 |
| deposits_only_fixed_broad_buffer | 2,035.768 | 627.844 | 1,407.925 | 14.079 | 3.726 |
| deposits_plus_OFA | 6,232.694 | 627.844 | 5,604.850 | 56.049 | 14.834 |

An SFS deposits-only buffer **is available**: recompute the same weighted decile/age medians using PWASTDEP alone, retaining survey weights, PEFATINC income, PAGEMIEG age and the existing family-to-household mapping. The broad definition uses the unchanged BE reference. At κ=.01/q, the aggregate hypothetical wealth term is 14.834% of C with deposits+nonpension OFA, versus 5.038% with deposits and its own SFS median buffer; holding the broad buffer fixed gives 3.726%. These are t0 sensitivity audits; neither wealth term enters Q. [SFS source/hash/method](benchmarks/QE/sfs_deposit_provenance.json).

## E: cash payments, arrears and foreclosure

E replaces the net-worth trigger and D3 only when selected. Scheduled payments are cash-constrained using deposits, current funded receipts, net deposit interest, new credit, executed property proceeds and existing non-pension assets, after rent/property obligations. Interest is paid first and principal second, pro rata by contract. Unpaid principal stays in the loan book; unpaid interest is a non-accrual memo, not bank income or capitalised credit. Uncured arrears persist. Monthly 30/60/90+ buckets are inferred from equally spaced due dates and cash available first within a quarter; the model does not observe monthly receipts. Negative net worth alone never defaults. Unfunded senior payments/negative deposits also age as unsecured overdraft distress under the approved zero-unused-capacity proxy; after the same N the deposit bank absorbs that claim. This noncash debt cancellation is named household_overdraft_relief in both the household cash and reserve batteries; it never enters the formal-loan principal counter. [Scope/timing assumption](benchmarks/QE/overdraft_resolution_assumption.json).

N=3 consecutive distressed quarters is the **unchanged, labelled assumption shared with firms** (roughly 7–9 months from first missed due date under the buckets). The 20% stress-sale discount is also a labelled assumption, with 10–30% illustrative uncertainty; it is not an estimated legal fee or Canadian foreclosure-cost rate. Neither was tuned. Existing non-pension financial assets fund service before residual unsecured principal is written off. Pensions stay protected. Initial arrears are unobserved and set to zero, so a zero Q1 write-off is partly a construction consequence, not independent validation.

Mortgaged properties enter the existing housing market at market value less the stated discount. **Only executed sales** repay principal; only the remaining shortfall after pooled collateral is disposed of is written off; surplus remains with the household. The property-to-loan link is missing, so mortgages use a pooled household collateral assumption. A dispossessed owner becomes a renter through the existing public-housing fallback. No buyer/vacant possession: retain the encumbering bank mortgage claim in a foreclosure queue, without REO cash or hypothetical recovery. Existing third-party tenants keep their homes until an executable move allows vacant possession. This holding treatment delays loss realization and is an explicit limitation. Mortgage insurance/guarantor claims are not added.

### E gates and benchmark scope

| seed | E_G1 | E_G2 | E_G3 | annual_writeoff_pct | Q12_60plus_pct | Q12_90plus_pct | Q1_writeoffs | Q4_Q12_mean_writeoffs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | False | True | True | 1.034 | 1.269 | 1.269 | 0.000 | 7.144 |
| 1 | False | True | True | 1.048 | 1.377 | 1.377 | 0.000 | 7.233 |
| 2 | False | True | True | 1.172 | 1.993 | 1.993 | 0.000 | 8.321 |

E-G1 compares each reported Q1–Q12 arrears observation with factor-two bands and the 12-quarter annualised principal-loss ratio with [0.05%,0.28%]. No hidden warm-up is dropped. Arrears use pooled mortgage-borrower counts, whereas source account counts can include multiple mortgages per household. Annualised write-offs include formal principal and household overdrafts, divided by three years and mean formal debt plus overdrafts over Q0–Q12 (initial SFS deposits are nonnegative). The formal-only-denominator alternative is also retained. These scope limits prevent a claim of exact household-portfolio validation. E-G2 compares Q1 losses with twice Q4–Q12 mean; E-G3 is accounting.

Q12 arrears alone exceed the factor-two bands, and the annualised loss ratio independently fails, so the empirical failure does not depend on counting the initially low-arrears quarters.

| Benchmark | Verified value / scope | Source and provenance |
|---|---|---|
| TransUnion | Q3 2024 mortgage account 60+ DPD **0.25%**; not 90+ | [Mortgage Loan Summary, p12](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q3_24_ciir_report.pdf); direct PDF download returned 403, so the cached factual extract—not inaccessible PDF bytes—is hashed |
| CBA | December 2022 **0.15%**, 7,740/5,106,262 mortgages; three or more months overdue | [Canada historical table](https://cba.ca/Assets/CanadianBankersAssociation/Documents/Articles/Statistics/stat-mortgages-arrears-november-2025-en.pdf), PDF p3; full PDF hash recorded |
| RBC | 2022 **0.10%**, 2023 **0.14%** annual net write-off ratio, **consolidated all loans**, not household-only | [RBC 2023 annual report](https://www.rbc.com/investor-relations/_assets-custom/pdf/ar_2023_e.pdf), Table78; retained verified extraction/full PDF hash |

All source dates, vectors (or not-applicable labels), hashes, parameter assumptions and limitations: [credit benchmarks](benchmarks/QE/credit_benchmarks.json), [DHEA extraction](benchmarks/QE/provenance.json), and inherited [DHEA/SHS definitions](benchmarks/B2/distribution_provenance.json). The requested RBC range is retained as an imperfect order-of-magnitude gate; it is not falsely relabelled a household-only benchmark.

The complete [benchmark index](benchmarks/QE/benchmark_index.json) hashes selected and inherited inputs, including the observed-CFC source/allocation used by the accepted firm baseline.

### Old rule versus E, by quarter

| seed | quarter | household_writeoffs_old | household_writeoffs_E | bank_losses_old | bank_losses_E | recapitalisation_old | recapitalisation_E |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 76.936 | 0.000 | 76.936 | 0.000 | 0.693 | 0.000 |
| 0 | 2 | 50.451 | 0.000 | 50.451 | 0.000 | 0.000 | 0.000 |
| 0 | 3 | 44.173 | 18.748 | 44.181 | 18.757 | 8.442 | 0.000 |
| 0 | 4 | 25.361 | 14.397 | 25.397 | 14.433 | 0.000 | 0.000 |
| 0 | 5 | 12.196 | 10.001 | 12.567 | 10.379 | 0.000 | 0.000 |
| 0 | 6 | 7.966 | 8.856 | 9.969 | 10.411 | 0.000 | 0.000 |
| 0 | 7 | 7.296 | 9.761 | 15.113 | 16.712 | 0.000 | 5.674 |
| 0 | 8 | 3.722 | 6.152 | 19.216 | 12.737 | 18.035 | 0.000 |
| 0 | 9 | 2.321 | 4.402 | 10.464 | 8.924 | 6.823 | 0.000 |
| 0 | 10 | 1.337 | 3.951 | 6.710 | 9.732 | 0.000 | 0.000 |
| 0 | 11 | 1.248 | 1.199 | 22.676 | 32.218 | 46.086 | 0.000 |
| 0 | 12 | 0.534 | 5.577 | 24.232 | 23.776 | 85.125 | 2.020 |
| 1 | 1 | 80.859 | 0.000 | 80.859 | 0.000 | 0.000 | 0.000 |
| 1 | 2 | 60.205 | 0.000 | 60.205 | 0.000 | 0.000 | 0.000 |
| 1 | 3 | 32.328 | 18.966 | 32.335 | 18.973 | 0.000 | 0.000 |
| 1 | 4 | 20.067 | 14.491 | 20.068 | 14.492 | 0.000 | 0.000 |
| 1 | 5 | 16.556 | 10.362 | 18.125 | 11.601 | 6.126 | 0.000 |
| 1 | 6 | 7.592 | 8.348 | 8.588 | 9.272 | 0.617 | 0.000 |
| 1 | 7 | 7.791 | 10.329 | 13.813 | 17.986 | 21.304 | 7.172 |
| 1 | 8 | 3.038 | 5.743 | 18.015 | 18.445 | 5.039 | 0.000 |
| 1 | 9 | 1.048 | 5.215 | 24.334 | 17.237 | 45.418 | 0.168 |
| 1 | 10 | 1.401 | 4.213 | 8.383 | 13.107 | 22.780 | 0.000 |
| 1 | 11 | 1.890 | 2.168 | 76.413 | 9.409 | 98.373 | 0.000 |
| 1 | 12 | 0.821 | 4.226 | 11.310 | 37.750 | 0.062 | 5.643 |
| 2 | 1 | 75.262 | 0.000 | 75.262 | 0.000 | 0.693 | 0.000 |
| 2 | 2 | 65.396 | 0.000 | 65.396 | 0.000 | 0.000 | 0.000 |
| 2 | 3 | 30.123 | 19.140 | 30.131 | 19.148 | 0.000 | 0.000 |
| 2 | 4 | 29.773 | 14.690 | 29.874 | 14.801 | 8.757 | 0.000 |
| 2 | 5 | 10.304 | 10.238 | 11.625 | 11.459 | 0.000 | 0.000 |
| 2 | 6 | 7.390 | 7.998 | 8.357 | 11.294 | 0.000 | 0.000 |
| 2 | 7 | 4.949 | 9.748 | 11.259 | 15.567 | 0.000 | 5.611 |
| 2 | 8 | 3.182 | 10.738 | 9.359 | 14.230 | 0.000 | 0.000 |
| 2 | 9 | 2.888 | 7.207 | 24.505 | 13.441 | 65.171 | 0.000 |
| 2 | 10 | 0.924 | 7.255 | 9.128 | 24.712 | 0.000 | 0.000 |
| 2 | 11 | 2.129 | 3.486 | 13.405 | 12.688 | 25.337 | 0.000 |
| 2 | 12 | 0.919 | 3.528 | 36.318 | 12.493 | 0.000 | 0.000 |

### Bank-loss composition and recapitalisation totals, 12 quarters

| arm | seed | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation |
| --- | --- | --- | --- | --- | --- | --- |
| C | 0 | 384.235 | 195.178 | 219.673 | 799.086 | 615.831 |
| C | 1 | 395.191 | 267.968 | 176.748 | 839.907 | 684.432 |
| C | 2 | 388.947 | 439.297 | 196.848 | 1,025.092 | 864.414 |
| E | 0 | 83.044 | 43.006 | 32.027 | 158.077 | 7.694 |
| E | 1 | 84.062 | 50.142 | 34.067 | 168.271 | 12.983 |
| E | 2 | 94.028 | 32.425 | 23.381 | 149.834 | 5.611 |
| F | 0 | 236.453 | 91.135 | 114.264 | 441.852 | 220.141 |
| F | 1 | 237.065 | 115.013 | 149.990 | 502.068 | 310.153 |
| F | 2 | 237.015 | 89.926 | 140.063 | 467.004 | 235.207 |
| F_CFC | 0 | 233.541 | 54.106 | 30.266 | 317.913 | 165.205 |
| F_CFC | 1 | 233.594 | 102.062 | 36.791 | 372.446 | 199.720 |
| F_CFC | 2 | 233.240 | 66.091 | 25.289 | 324.620 | 99.958 |
| Q | 0 | 281.400 | 24.776 | 18.600 | 324.777 | 100.059 |
| Q | 1 | 281.640 | 45.990 | 24.901 | 352.531 | 170.942 |
| Q | 2 | 284.672 | 92.151 | 32.330 | 409.154 | 213.332 |

C’s bank decomposition is a read-only serial replay, required to match its original macro paths and consumption distributions exactly; accounting is independently checked. Full quarterly components, capital ratios and resolution events are in the primary run folders and [quarterly.csv](outputs/QE/quarterly.csv); C’s components are in [C_bank_replays](outputs/QE/C_bank_replays). New E losses go through the same by-bank capital/resolution paths as the old rule. Household losses include household overdrafts; the separate overdraft_losses column is firm overdrafts. E_metrics additionally isolates household overdraft write-offs, avoiding double counting. Mortgage foreclosure losses also populate the existing mortgage NPL reporting path.

Detailed E defaults, 30/60/90+ arrears, executed-sale recoveries, pending foreclosures, mortgage/unsecured losses and non-accrual interest are in [E_metrics.csv](outputs/QE/E_metrics.csv). Counts are expanded households; “foreclosure_sales” counts borrowers with a positive executed collateral repayment, not individual dwellings. Firm-default counts in the raw panels are model province/industry agents, not observed Canadian business insolvency counts.

The legacy loan-vintage loss field is not validated for E’s bespoke servicing path and is not used as a new-lending loss estimate. [Diagnostic exclusions](outputs/QE/diagnostic_exclusions.json) identify that field and all failed/superseded outputs. Portfolio principal losses, overdraft relief, bank losses and counterparties are independently checked.

### Rejected accounting attempt and mechanical corrections

The first E seed-0 12-quarter attempt is retained and **rejected** (maximum relative battery residual 1.4296e−4; rent-counterparty residual up to 5.762M). Foreclosure exposed two mechanical defects: public-housing rent was taxed as private-landlord rent when the household became tenure-status 3; sales could overwrite third-party tenants’ occupancy. The two isolated fixes leave N/haircut unchanged. The subsequent `E_cashfix` runs pass accounting but omitted overdraft resolution and are superseded, not accepted as complete E. `E_complete` includes all unsecured claims and passes fresh 2- and 4-quarter diagnostics before the primary 12-quarter measurements. An initial C instrumentation attempt also hit a D-only budget hook; its read-only wrapper was corrected without changing C. Failed/superseded diagnostics are retained and not spliced into primary results. Interrupted test logs remain under verification and verification_final; the final suite uses verification_complete, after corrected secondary-distribution replays.

## Independent FB GDP/tax/output bridge

Accepted source: F_CFC. New experimental input: `io2022_household_f_cfc_qe_bridge_2026_10_25.pkl`; its SHA-256 and unchanged source hash are in [provenance](outputs/QE/bridge/provenance.json). Preserve financial stocks, debt, capital stocks and initial capital purchases. Zero-source producers are marked inactive holders; **no debt is forgiven**. The source is the cached provincial 2022 detailed SUT mapped to OECD50, with PRM100000–PRM800000 vectors and concordance/file hashes recorded.

National annual signed other-production taxes are **100.504B**, input-product taxes **26.546B**, and the cost-side row/column adjustment **48.338B**. Production at the source basic-price valuation equals cost-side output less basic intermediate use and the input-product valuation; income is compensation + GOS/mixed income + signed other production taxes. Final product taxes then give market-price GDP. Housing already inside L is excluded from an additional producer block in the SNA-scope diagnostic. The remaining expenditure excess is **74.883B/year**, decomposing into the row/column adjustment plus input-product valuation (rounding retained). It is not absorbed by a fictitious buyer, inventory or cash transfer.

| region | production_market | income_market | expenditure_market_scope_adjusted | production_income_residual | expenditure_residual |
| --- | --- | --- | --- | --- | --- |
| CAN_NL | 10.034957 | 10.034957 | 10.204818 | 0.000000 | 0.169861 |
| CAN_PE | 2.223383 | 2.223383 | 2.278314 | 0.000000 | 0.054931 |
| CAN_NS | 13.183466 | 13.183466 | 13.546295 | -3.815e-15 | 0.362830 |
| CAN_NB | 10.443454 | 10.443454 | 10.789748 | 5.722e-15 | 0.346295 |
| CAN_QC | 132.225859 | 132.225859 | 135.505884 | -1.526e-14 | 3.280025 |
| CAN_ON | 254.908676 | 254.908438 | 262.901610 | 0.000238 | 7.992935 |
| CAN_MB | 21.107039 | 21.107039 | 21.870556 | 3.815e-15 | 0.763518 |
| CAN_SK | 28.395930 | 28.395930 | 29.208403 | -3.815e-15 | 0.812473 |
| CAN_AB | 117.102889 | 117.102889 | 119.364788 | 3.052e-14 | 2.261899 |
| CAN_BC | 96.343665 | 96.343665 | 98.953447 | -1.526e-14 | 2.609782 |
| CAN_YT | 0.971217 | 0.971217 | 0.986450 | 0.000000 | 0.015233 |
| CAN_NT | 1.311037 | 1.311037 | 1.354071 | -2.384e-16 | 0.043034 |
| CAN_NU | 1.111326 | 1.111326 | 1.119380 | 2.384e-16 | 0.008054 |

The bridge’s production/income residual is at most 0.000239B/q (source/mapping rounding), retained visibly. [Unchanged model initializer checks](outputs/QE/bridge/unchanged_GDP_checks.csv) fail in **all 13 regions**: Newfoundland output/expenditure ratio is 0.990609, improved from the older 0.929 prototype by preserving capital purchases and fiscal initial conditions, but still not one. The initializer also contains a pre-existing repeated output/expenditure assertion where its message says output/income; independent income ratios are therefore recorded rather than trusting that second check. No assertion or tolerance was changed.

Gross-margin residual passes at 0.000978 percentage point, but **102 active region/industry cells** have cost above price despite non-negative source GOS. GOS is gross of CFC: positive GOS alone does not guarantee a positive surplus after CFC and financing. The requested gate is applied unchanged; no depreciation or cost is removed to force it. [Cell-level bridge](outputs/QE/bridge/firm_bridge.csv) and [industry exceptions](outputs/QE/bridge/above_price_by_industry.csv) are retained. FB is unaccepted and not iterated; its accounting/dynamic gates cannot be passed. The consistent read-only GDP bridge does not manufacture a balanced runnable data set.

## Verification, limitations and recommendation

Full `tests/` via `run_pre_D3_tests.py`: **476 passed, 30 known failures, 506 cases**. The sampler uses one worker. Exact failure IDs are compared with the known 30 “Nan in transactor_total_real_supply” cases; no additional failures are accepted. [Full execution](outputs/QE/verification_complete/full_test_execution.json). Focused regressions cover baseline selection, rank interpolation, share gates, cash servicing, foreclosure cash/occupancy, rental PIT, unsecured overdraft resolution, payroll gross-up and GDP valuation.

**Not ready for Phase B.** Keep F_CFC as the accepted data baseline, retain Q and E as opt-in unvalidated candidates, and do not combine them. E removes the false net-worth default mechanism and initial loss spike, but its loss and arrears levels remain too high to call Canadian orders of magnitude plausible. Large firm losses, public recapitalisations and the failed IO/tax/cost reconciliation remain unresolved; reduced losses alone are not validation.

Next review decisions concern: reconciling cash versus DHEA imputed income before another distribution rule; applying the existing IO-housing scope consistently to GDP initialization/income reporting; resolving the observed IO row/column/product-valuation gap without a plug; specifying the treatment of genuinely negative net operating surplus versus the gross-GOS cost gate; and validating payment/default/foreclosure timing and pooled collateral against loan-level data. The default constant-propensity income feedback and remaining asset exhaustion still need attention; no buffer-stock parameter was tuned here. Initial bank funding/reserve boundaries and unmodelled mortgage insurance remain limitations.

Inherited credit screens and post-default credit re-entry have not been validated against the new arrears ledger. Housing affordability/price observations also retain the host market’s conventions for matched offers and partial mortgage funding. These are possible mechanisms to diagnose before accepting E; no extra credit-ban, recovery or price parameter was fitted in this round.

All household consumption, disposable income, saving (against −0.6%), constraints, investment, asset drawdown and GDP paths: [household/GDP quarterly table](outputs/QE/household_and_GDP_paths_B_pct.csv). Gates, seeds, complete source hashes, protected-input checks and excluded attempts are in the evidence folder and final audit. No push; stop for review.
