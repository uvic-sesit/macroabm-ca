# Buffer-stock consumption and firm payouts - 24 October 2026 UTC

**Gate B fails on all three seeds. E has not started. Phase B and C_dp_005 remain on hold.**
The approved buffer-stock rule is implemented as an opt-in candidate, and the
firm cost diagnostic and prudent dividend rule have been evaluated separately.
The old household insolvency rule remains in every measured arm; D3 is off.
No parameter was changed to improve a gate result. Work continues from e386f4e
on feature/validation-2022; no push or changes to protected inputs.

## Decisions and implementation

| Step | Commit / regression | Result |
|---|---|---|
| B spending rule and fixed SFS buffers | 2948b08; above/below wealth target, nonnegative spending, exact D and cash flow | Default off; kappa .10, smoothing .25; IO basket and consumption-before-investment preserved |
| B initial debt service | 47e6002; initial contract service regression | Initial interest TS is unset; initialize from scheduled contractual principal/interest and opening overdraft interest |
| Cost/price diagnostic | 6a973a6; exact multiplicative price decomposition | Read-only, no additional random draws; t0 and every quarter, all industries |
| B gate and audits | 1e83c42; percentage-point boundary regression | Gate B fails; no E or foreclosure implementation |
| Prudent discretionary firm payout | 95cf3e6; retained-profit/cash/reserve and declaration-settlement regressions | Candidate flag only; mixed income and corporate transfers retain their existing treatment |
| Pricing and producer adjustment | Proposal below | Not implemented |

Amounts in tables are CAD B unless percentages or other units are labelled.
Consumption includes VAT and paid rent. Investment includes capital-formation
tax. Cash DI is net household income less interest paid; saving excludes D.8,
principal payments and capital purchases. Financial saving is separately shown
in the group ledger evidence; cash saving is not a deposit-accumulation rate.

## Buffer-stock specification and initial level

The unanchored rule is max(0, Yperm + kappa*(L - target)). L is positive deposits
plus existing non-pension OFA; overdrafts and unsecured debt are reported as
separate liabilities rather than negative assets. Yperm is smoothed net cash
receipts after principal, interest and rent, using weight .25. Initial service
comes from the loan contracts because interest-paid TS values are unset at t0.
The receipts declaration and final settlement still agree household by household.
The D cap still covers house transactions and other senior obligations, with
zero unused consumer-credit capacity. Investment is cut before consumption.

The fixed target is b*Yperm for positive Yperm. For nonpositive Yperm it is the
initial cell weighted-median liquid-asset level, preventing a negative buffer.
b is the SFS weighted median of L/(annual after-tax income/4), by weighted
income decile and age of the major income recipient. The SFS source is the
[2023 economic-family PUMF, catalogue 13M0006X](https://www150.statcan.gc.ca/n1/en/catalogue/13M0006X).
Liquid variables are PWASTDEP, PWASTMUI, PWASTSTK, PWASTBND, PWASTOIN and PWATFS;
pensions are excluded. PWEIGHT is unchanged. The 80 reference cells include a
pooled-age fallback for each income decile. Model age uses the initial
highest-income linked individual's age as a major-recipient proxy; it is not a
new observation of Canadian household age. Group membership and buffers stay fixed.

Uncertainty: SFS economic families differ from model households; wealth is from
2023, and the model's senior-payment-adjusted income differs from the SFS
after-tax denominator. The model retains its member-age skeleton. These are
reported mapping assumptions, not calibration targets. Source/extract hashes,
variable names, date and cell estimates are in benchmarks/BE/buffer_provenance.json
and sfs_liquid_buffers.csv.

The national level is anchored once to
[36-10-0112](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201),
v62305982: 1,511.382B/year, or 377.8455B/quarter. The implemented anchor is a
single fixed CAD-per-represented-household additive intercept inside max(0,...),
solved by bisection including D1's actual private-rent offset and paid rent.
It leaves kappa, b and smoothing unchanged and is not recalibrated during a run.
Every sensitivity gets its own t0 level anchor to the same target.
The payout arm also initializes C and planned investment to the same national
targets using its own declared D2 receipts; its household-level starting plans
can therefore differ. This standard t0 initialization is part of the reported
comparison, not a refit of response coefficients to outcomes.
This distributional choice matters: an aggregate level match is not evidence
that individual consumption levels are plausible.
The calibrated rule is explicitly max(0, Yperm + kappa*(L-target) + level).
Consequently the intercept shifts the effective wealth-gap threshold by
-level/kappa. The above/below-target regression checks establish the raw
wealth response at level zero; they do not validate the distribution after
anchoring. This distinction and the resulting zero-consumption incidence
are central to the failed candidate, not concealed by the aggregate match.

| arm | variant | seed | level_CAD_per_household | initial_account_C | initial_Yperm |
| --- | --- | --- | --- | --- | --- |
| iv-ACDpAIFB | base | 0 | -83544.521 | 377.846 | 330.335 |
| iv-ACDpAIFB | base | 1 | -83544.521 | 377.846 | 330.335 |
| iv-ACDpAIFB | base | 2 | -83544.521 | 377.846 | 330.335 |
| iv-ACDpAIFB | k005 | 0 | -21155.243 | 377.845 | 330.335 |
| iv-ACDpAIFB | k015 | 0 | -225753.179 | 377.845 | 330.335 |
| iv-ACDpAIFB | l0125 | 0 | -83544.521 | 377.846 | 330.335 |
| iv-ACDpAIFB | l0375 | 0 | -83544.521 | 377.846 | 330.335 |
| iv-ACDpAIFBP | base | 0 | -83532.497 | 377.846 | 330.263 |
| iv-ACDpAIFBP | base | 1 | -83532.497 | 377.846 | 330.263 |
| iv-ACDpAIFBP | base | 2 | -83532.497 | 377.846 | 330.263 |

The cash-saving benchmark is -0.601861%, using v62305980 disposable income
and v62305982 consumption, excluding v105775422 pension entitlements.
Published v62305984 saving includes that adjustment and is 2.1% in 2022.
The selected vectors, retrieval date, full-source and extract hashes are
in benchmarks/BE/benchmark_index.json and household_targets_2022.csv.

## Gate B and four requested sensitivities

| arm | variant | seed | constrained_slope_pp | Q12_constrained_pct | Q12_saving_pct | gate_passed |
| --- | --- | --- | --- | --- | --- | --- |
| iv-ACDpAIFB | base | 0 | 0.040 | 0.679 | 48.222 | False |
| iv-ACDpAIFB | base | 1 | 0.039 | 0.678 | 47.408 | False |
| iv-ACDpAIFB | base | 2 | 0.050 | 0.743 | 48.239 | False |
| iv-ACDpAIFB | k005 | 0 | 0.017 | 0.706 | 15.645 | False |
| iv-ACDpAIFB | k015 | 0 | 0.041 | 0.692 | 70.102 | False |
| iv-ACDpAIFB | l0125 | 0 | 0.045 | 0.711 | 47.702 | False |
| iv-ACDpAIFB | l0375 | 0 | 0.041 | 0.685 | 46.776 | False |

Gate: accounting <=1e-8, Q4-Q12 OLS slope <=.25 percentage points/q,
and Q12 cash saving in [-5.6%,4.4%], on every base seed. Sensitivities
are seed 0 only as requested; they do not qualify E independently.

![Consumption, saving and constrained-share paths](outputs/BE/buffer_gate_paths.png)

## Household diagnosis

| seed | quarter | zero_goods_pct | positive_income_zero_goods_pct | cash_DI | consumption_with_rent |
| --- | --- | --- | --- | --- | --- |
| 0 | 1 | 85.648 | 85.648 | 371.908 | 367.950 |
| 0 | 12 | 79.123 | 79.123 | 306.552 | 158.725 |
| 1 | 1 | 85.655 | 85.655 | 371.141 | 372.207 |
| 1 | 12 | 78.474 | 78.474 | 307.425 | 161.681 |
| 2 | 1 | 85.648 | 85.648 | 370.753 | 370.925 |
| 2 | 12 | 79.850 | 79.850 | 292.881 | 151.598 |

A zero goods purchase does not imply zero paid rent. Low constrained
shares cannot validate a rule that itself plans very little consumption.
The large negative common intercept clips many positive-income households
to zero goods demand. Initial aggregate consumption is concentrated in
wealth-rich households, then falls as their assets are drawn down.
This is a failure of this anchored candidate, not evidence that Canadian
households choose these consumption levels. No gate-oriented refit was made.

| seed | diagnosis | households | constrained | income_down | wages_down | firm_receipts_down | employment_down | assets_down |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | income_restoration_sufficient | 9010 | 9010 | 9010 | 4010 | 9010 | 3000 | 5010 |
| 0 | other_or_combined | 96160 | 96160 | 77160 | 18060 | 96160 | 11000 | 52070 |
| 0 | unconstrained | 15392150 | 0 | 12724830 | 7800560 | 15120170 | 3722870 | 965040 |
| 1 | income_restoration_sufficient | 8010 | 8010 | 8010 | 4000 | 8010 | 4000 | 2010 |
| 1 | other_or_combined | 97120 | 97120 | 81070 | 24000 | 97120 | 11000 | 52050 |
| 1 | unconstrained | 15392190 | 0 | 12636800 | 8999970 | 15120210 | 3945900 | 969040 |
| 2 | income_restoration_sufficient | 7000 | 7000 | 7000 | 3000 | 6000 | 3000 | 1000 |
| 2 | other_or_combined | 108120 | 108120 | 89060 | 29000 | 105120 | 19000 | 55050 |
| 2 | unconstrained | 15382200 | 0 | 12620360 | 8709170 | 15084220 | 4524350 | 967030 |

Classes match FE: income-restoration sufficient, persistent spending gap
with assets down, and other/combined. Restoring Q1 receipts is an
accounting counterfactual, not a causal employment estimate. Fixed
decile x initial OFA-band details are in constraint_diagnosis.csv;
the zero-consumption and saving panel is household_zero_consumption_diagnosis.csv.

| seed | decile | households | zero_goods_pct | cash_saving | consumption_with_rent |
| --- | --- | --- | --- | --- | --- |
| 0 | 1 | 1549000 | 98.257 | 7.922 | 1.173 |
| 0 | 2 | 1550190 | 94.575 | 9.595 | 2.754 |
| 0 | 3 | 1549700 | 87.462 | 13.699 | 5.256 |
| 0 | 4 | 1549280 | 82.219 | 15.796 | 8.739 |
| 0 | 5 | 1549740 | 83.725 | 19.615 | 9.446 |
| 0 | 6 | 1549880 | 81.675 | 20.963 | 12.957 |
| 0 | 7 | 1549340 | 77.856 | 21.015 | 15.798 |
| 0 | 8 | 1550180 | 73.597 | 19.572 | 21.081 |
| 0 | 9 | 1549460 | 64.808 | 18.979 | 26.248 |
| 0 | 10 | 1550550 | 47.081 | 0.671 | 55.273 |
| 1 | 1 | 1549000 | 98.257 | 7.575 | 1.177 |
| 1 | 2 | 1550190 | 94.380 | 9.279 | 2.818 |
| 1 | 3 | 1549700 | 87.519 | 13.305 | 5.328 |
| 1 | 4 | 1549280 | 81.961 | 14.944 | 8.862 |
| 1 | 5 | 1549740 | 83.595 | 18.932 | 9.429 |
| 1 | 6 | 1549880 | 81.159 | 20.879 | 13.319 |
| 1 | 7 | 1549340 | 76.552 | 20.639 | 16.008 |
| 1 | 8 | 1550180 | 72.500 | 19.696 | 21.307 |
| 1 | 9 | 1549460 | 63.247 | 19.237 | 26.893 |
| 1 | 10 | 1550550 | 45.589 | 1.259 | 56.540 |
| 2 | 1 | 1549000 | 98.257 | 7.883 | 1.170 |
| 2 | 2 | 1550190 | 94.508 | 9.415 | 2.712 |
| 2 | 3 | 1549700 | 87.907 | 12.788 | 5.137 |
| 2 | 4 | 1549280 | 83.060 | 14.725 | 8.423 |
| 2 | 5 | 1549740 | 84.112 | 18.289 | 8.996 |
| 2 | 6 | 1549880 | 81.869 | 20.492 | 12.586 |
| 2 | 7 | 1549340 | 77.911 | 20.184 | 15.000 |
| 2 | 8 | 1550180 | 74.372 | 18.847 | 20.090 |
| 2 | 9 | 1549460 | 66.671 | 18.227 | 24.624 |
| 2 | 10 | 1550550 | 49.857 | 0.434 | 52.860 |
| seed | asset_band | households | zero_goods_pct | cash_saving | consumption_with_rent |
| --- | --- | --- | --- | --- | --- |
| 0 | 0-10k | 1882380 | 94.070 | 34.789 | 2.268 |
| 0 | 10-100k | 3917340 | 90.360 | 70.524 | 8.557 |
| 0 | 100k+ | 4568410 | 45.639 | -35.927 | 139.659 |
| 0 | zero | 5129190 | 94.880 | 78.440 | 8.241 |
| 1 | 0-10k | 1882380 | 93.369 | 35.178 | 2.567 |
| 1 | 10-100k | 3917340 | 89.440 | 70.508 | 9.224 |
| 1 | 100k+ | 4568410 | 44.869 | -36.823 | 141.321 |
| 1 | zero | 5129190 | 94.563 | 76.881 | 8.569 |
| 2 | 0-10k | 1882380 | 94.703 | 33.418 | 2.205 |
| 2 | 10-100k | 3917340 | 90.919 | 68.264 | 7.969 |
| 2 | 100k+ | 4568410 | 46.555 | -35.375 | 134.099 |
| 2 | zero | 5129190 | 95.601 | 74.976 | 7.325 |

Decision needed before reopening E: review the distributional t0 anchor and
the SFS/model liquidity and income mapping. One option is household-specific
initial level offsets that preserve an independently validated consumption
distribution while retaining fixed wealth responses; another is a
structural target-wealth rule with heterogeneity and precautionary motives.
An additional data-mapping option is an independently specified SFS
within-cell wealth-rank matching rule, rather than treating one cell
median as every wealth-rich household's desired buffer. Observed
wealth is not itself an estimated desired wealth target. Small SFS
cells (minimum eight records) and the family/household boundary add
uncertainty. These possibilities need a specification before rerunning.
Both change the specification and need review. Neither is implemented,
and no coefficient is selected using this gate.

## Quarterly macro outcomes and loss attribution

### iv-ACDpAIFB, seed 0

| quarter | constrained_pct | cash_saving_pct | consumption | C_target_gap_pct | planned_investment | investment | asset_liquidation | gdp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.395 | 1.064 | 367.950 | -2.619 | 53.584 | 53.489 | 102.166 | 700.336 |
| 2 | 0.304 | 7.528 | 338.402 | -10.439 | 54.415 | 54.311 | 151.328 | 693.166 |
| 3 | 0.323 | 13.730 | 308.573 | -18.333 | 54.774 | 54.663 | 157.484 | 679.537 |
| 4 | 0.336 | 19.706 | 283.150 | -25.062 | 56.514 | 56.380 | 154.508 | 659.296 |
| 5 | 0.446 | 24.690 | 259.661 | -31.279 | 56.318 | 56.158 | 144.030 | 633.733 |
| 6 | 0.452 | 28.517 | 240.757 | -36.282 | 55.314 | 55.171 | 134.858 | 607.151 |
| 7 | 0.498 | 31.781 | 222.174 | -41.200 | 53.288 | 53.144 | 122.400 | 589.052 |
| 8 | 0.536 | 35.803 | 205.493 | -45.615 | 52.416 | 52.261 | 111.413 | 578.887 |
| 9 | 0.575 | 40.010 | 191.904 | -49.211 | 52.545 | 52.381 | 101.855 | 562.799 |
| 10 | 0.620 | 43.310 | 179.348 | -52.534 | 52.061 | 51.891 | 92.984 | 551.223 |
| 11 | 0.653 | 45.908 | 168.771 | -55.333 | 49.981 | 49.809 | 84.446 | 536.062 |
| 12 | 0.679 | 48.222 | 158.725 | -57.992 | 50.146 | 49.956 | 76.723 | 531.724 |
| quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | min_capital_ratio | min_resolution_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 42.165 | 0.000 | 0.000 | 42.165 | 0.000 | 0.058 | 0.086 |
| 2 | 31.080 | 0.000 | 0.000 | 31.080 | 0.000 | 0.057 | 0.086 |
| 3 | 17.300 | 0.104 | 0.032 | 17.436 | 0.000 | 0.057 | 0.088 |
| 4 | 8.509 | 17.747 | 17.481 | 43.738 | 0.148 | 0.040 | 0.064 |
| 5 | 11.005 | 14.370 | 4.928 | 30.303 | 0.000 | 0.038 | 0.062 |
| 6 | 3.671 | 5.495 | 2.253 | 11.420 | 0.000 | 0.035 | 0.058 |
| 7 | 3.088 | 16.056 | 28.207 | 47.351 | 8.170 | 0.040 | 0.051 |
| 8 | 3.244 | 19.909 | 9.052 | 32.205 | 26.334 | 0.038 | 0.053 |
| 9 | 1.455 | 18.745 | 14.198 | 34.398 | 31.702 | 0.034 | 0.051 |
| 10 | 0.987 | 10.152 | 34.653 | 45.791 | 54.263 | 0.043 | 0.053 |
| 11 | 1.824 | 11.918 | 10.851 | 24.593 | 70.808 | 0.065 | 0.051 |
| 12 | 0.620 | 24.656 | 20.250 | 45.526 | 16.420 | 0.056 | 0.051 |
### iv-ACDpAIFB, seed 1

| quarter | constrained_pct | cash_saving_pct | consumption | C_target_gap_pct | planned_investment | investment | asset_liquidation | gdp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.382 | -0.287 | 372.207 | -1.492 | 53.606 | 53.506 | 104.119 | 715.028 |
| 2 | 0.323 | 8.431 | 338.642 | -10.375 | 58.623 | 58.512 | 151.856 | 709.738 |
| 3 | 0.349 | 15.154 | 307.953 | -18.498 | 56.322 | 56.202 | 156.848 | 690.019 |
| 4 | 0.362 | 21.251 | 281.958 | -25.377 | 58.188 | 58.062 | 152.464 | 665.910 |
| 5 | 0.433 | 26.122 | 259.616 | -31.290 | 56.916 | 56.783 | 143.163 | 648.315 |
| 6 | 0.465 | 31.636 | 241.195 | -36.166 | 58.186 | 58.038 | 133.520 | 615.898 |
| 7 | 0.478 | 33.911 | 224.597 | -40.558 | 55.737 | 55.608 | 122.474 | 598.675 |
| 8 | 0.517 | 37.801 | 207.782 | -45.009 | 54.644 | 54.506 | 110.840 | 573.918 |
| 9 | 0.582 | 41.408 | 191.278 | -49.377 | 53.482 | 53.330 | 99.946 | 560.319 |
| 10 | 0.614 | 43.544 | 182.918 | -51.589 | 52.879 | 52.716 | 92.923 | 541.217 |
| 11 | 0.652 | 45.131 | 172.076 | -54.459 | 51.244 | 51.077 | 84.601 | 530.320 |
| 12 | 0.678 | 47.408 | 161.681 | -57.210 | 49.995 | 49.820 | 76.741 | 525.032 |
| quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | min_capital_ratio | min_resolution_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 52.588 | 0.000 | 0.000 | 52.588 | 0.694 | 0.056 | 0.083 |
| 2 | 26.901 | 0.000 | 0.000 | 26.901 | 0.000 | 0.057 | 0.086 |
| 3 | 14.472 | 0.125 | 0.055 | 14.652 | 0.000 | 0.056 | 0.089 |
| 4 | 16.937 | 22.462 | 18.973 | 58.372 | 0.135 | 0.034 | 0.057 |
| 5 | 5.871 | 10.408 | 4.726 | 21.005 | 0.000 | 0.031 | 0.052 |
| 6 | 5.314 | 9.024 | 4.812 | 19.150 | 9.195 | 0.048 | 0.060 |
| 7 | 2.052 | 27.173 | 35.990 | 65.215 | 53.037 | 0.057 | 0.060 |
| 8 | 1.279 | 10.356 | 6.783 | 18.419 | 0.000 | 0.053 | 0.056 |
| 9 | 0.797 | 6.843 | 6.574 | 14.214 | 0.060 | 0.051 | 0.053 |
| 10 | 2.352 | 10.319 | 34.754 | 47.425 | 75.486 | 0.045 | 0.051 |
| 11 | 0.269 | 9.183 | 8.194 | 17.646 | 37.219 | 0.051 | 0.056 |
| 12 | 0.810 | 4.987 | 9.286 | 15.083 | 0.050 | 0.044 | 0.059 |
### iv-ACDpAIFB, seed 2

| quarter | constrained_pct | cash_saving_pct | consumption | C_target_gap_pct | planned_investment | investment | asset_liquidation | gdp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.408 | -0.046 | 370.925 | -1.832 | 57.643 | 57.529 | 104.035 | 698.058 |
| 2 | 0.349 | 6.750 | 338.045 | -10.534 | 49.536 | 49.410 | 151.627 | 686.538 |
| 3 | 0.343 | 13.197 | 306.753 | -18.815 | 54.061 | 53.936 | 156.508 | 665.097 |
| 4 | 0.336 | 18.007 | 282.425 | -25.254 | 55.235 | 55.103 | 154.022 | 642.062 |
| 5 | 0.420 | 22.770 | 259.168 | -31.409 | 54.165 | 54.027 | 144.634 | 626.216 |
| 6 | 0.485 | 27.944 | 238.531 | -36.871 | 54.210 | 54.041 | 134.917 | 602.188 |
| 7 | 0.523 | 31.839 | 220.025 | -41.768 | 52.790 | 52.632 | 121.999 | 581.066 |
| 8 | 0.556 | 37.703 | 198.291 | -47.521 | 52.197 | 52.033 | 107.545 | 555.818 |
| 9 | 0.639 | 39.796 | 186.492 | -50.643 | 50.539 | 50.362 | 100.095 | 533.471 |
| 10 | 0.652 | 43.247 | 172.586 | -54.324 | 49.191 | 49.015 | 91.264 | 516.918 |
| 11 | 0.723 | 45.113 | 163.038 | -56.850 | 49.012 | 48.827 | 83.532 | 501.347 |
| 12 | 0.743 | 48.239 | 151.598 | -59.878 | 48.338 | 48.150 | 75.361 | 483.763 |
| quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | min_capital_ratio | min_resolution_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 39.537 | 0.000 | 0.000 | 39.537 | 0.000 | 0.056 | 0.083 |
| 2 | 36.541 | 0.000 | 0.000 | 36.541 | 0.000 | 0.057 | 0.086 |
| 3 | 23.488 | 0.147 | 0.070 | 23.705 | 0.656 | 0.057 | 0.087 |
| 4 | 9.071 | 23.241 | 17.424 | 49.736 | 0.234 | 0.052 | 0.082 |
| 5 | 8.288 | 12.282 | 7.008 | 27.578 | 0.000 | 0.048 | 0.062 |
| 6 | 4.604 | 4.969 | 1.881 | 11.454 | 5.416 | 0.052 | 0.060 |
| 7 | 1.239 | 21.532 | 31.117 | 53.888 | 47.725 | 0.052 | 0.065 |
| 8 | 1.623 | 18.778 | 13.919 | 34.320 | 48.876 | 0.049 | 0.057 |
| 9 | 0.523 | 8.919 | 3.473 | 12.915 | 0.048 | 0.048 | 0.060 |
| 10 | 0.594 | 16.581 | 31.185 | 48.361 | 5.569 | 0.045 | 0.056 |
| 11 | 0.403 | 6.416 | 8.972 | 15.791 | 0.000 | 0.042 | 0.050 |
| 12 | 0.413 | 19.955 | 8.083 | 28.451 | 89.485 | 0.056 | 0.060 |
### iv-ACDpAIFBP, seed 0

| quarter | constrained_pct | cash_saving_pct | consumption | C_target_gap_pct | planned_investment | investment | asset_liquidation | gdp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.395 | 1.177 | 367.458 | -2.749 | 52.967 | 52.872 | 101.879 | 700.201 |
| 2 | 0.304 | 7.589 | 338.044 | -10.534 | 56.331 | 56.228 | 151.280 | 693.534 |
| 3 | 0.317 | 13.679 | 309.106 | -18.192 | 56.442 | 56.333 | 157.935 | 678.354 |
| 4 | 0.356 | 18.945 | 283.298 | -25.023 | 56.868 | 56.733 | 154.555 | 666.789 |
| 5 | 0.414 | 24.967 | 260.608 | -31.028 | 56.424 | 56.282 | 144.196 | 649.710 |
| 6 | 0.446 | 30.475 | 240.927 | -36.237 | 57.075 | 56.935 | 133.990 | 624.059 |
| 7 | 0.478 | 34.507 | 223.376 | -40.882 | 56.089 | 55.945 | 122.387 | 614.460 |
| 8 | 0.498 | 38.335 | 208.128 | -44.917 | 55.534 | 55.395 | 111.283 | 586.289 |
| 9 | 0.562 | 41.127 | 193.827 | -48.702 | 53.544 | 53.388 | 102.036 | 568.438 |
| 10 | 0.581 | 43.333 | 182.188 | -51.782 | 52.469 | 52.307 | 93.627 | 550.585 |
| 11 | 0.607 | 45.320 | 171.424 | -54.631 | 51.301 | 51.130 | 84.642 | 534.484 |
| 12 | 0.640 | 47.597 | 160.743 | -57.458 | 49.684 | 49.502 | 76.814 | 517.005 |
| quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | min_capital_ratio | min_resolution_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 42.891 | 0.000 | 0.000 | 42.891 | 0.000 | 0.056 | 0.083 |
| 2 | 17.240 | 0.000 | 0.000 | 17.240 | 0.000 | 0.057 | 0.086 |
| 3 | 16.069 | 0.109 | 0.035 | 16.213 | 0.678 | 0.057 | 0.088 |
| 4 | 17.065 | 17.854 | 17.464 | 52.384 | 0.162 | 0.039 | 0.063 |
| 5 | 11.494 | 13.097 | 5.349 | 29.940 | 0.000 | 0.038 | 0.062 |
| 6 | 3.900 | 7.614 | 1.665 | 13.179 | 7.878 | 0.061 | 0.075 |
| 7 | 1.949 | 19.315 | 31.786 | 53.049 | 0.483 | 0.048 | 0.062 |
| 8 | 5.070 | 13.990 | 9.964 | 29.024 | 25.311 | 0.052 | 0.059 |
| 9 | 1.300 | 14.224 | 5.484 | 21.008 | 0.000 | 0.045 | 0.050 |
| 10 | 4.224 | 12.311 | 39.213 | 55.748 | 135.592 | 0.040 | 0.055 |
| 11 | 1.007 | 5.865 | 11.246 | 18.118 | 6.179 | 0.059 | 0.053 |
| 12 | 0.635 | 10.119 | 8.025 | 18.779 | 0.000 | 0.055 | 0.050 |
### iv-ACDpAIFBP, seed 1

| quarter | constrained_pct | cash_saving_pct | consumption | C_target_gap_pct | planned_investment | investment | asset_liquidation | gdp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.382 | -0.303 | 372.196 | -1.495 | 55.381 | 55.282 | 104.185 | 715.377 |
| 2 | 0.324 | 8.390 | 338.603 | -10.386 | 58.155 | 58.034 | 151.968 | 709.643 |
| 3 | 0.323 | 14.475 | 309.391 | -18.117 | 56.832 | 56.727 | 158.500 | 697.896 |
| 4 | 0.330 | 20.940 | 281.929 | -25.385 | 58.135 | 58.024 | 153.066 | 670.845 |
| 5 | 0.407 | 25.187 | 259.307 | -31.372 | 56.518 | 56.397 | 143.904 | 639.587 |
| 6 | 0.446 | 28.491 | 237.815 | -37.060 | 53.527 | 53.387 | 133.663 | 610.389 |
| 7 | 0.491 | 31.796 | 221.807 | -41.297 | 53.413 | 53.274 | 122.336 | 594.474 |
| 8 | 0.543 | 36.010 | 204.022 | -46.004 | 52.000 | 51.851 | 110.971 | 577.672 |
| 9 | 0.607 | 38.883 | 189.907 | -49.739 | 51.113 | 50.942 | 102.208 | 563.094 |
| 10 | 0.633 | 42.937 | 177.198 | -53.103 | 50.931 | 50.754 | 92.974 | 549.109 |
| 11 | 0.665 | 45.509 | 167.260 | -55.733 | 50.374 | 50.190 | 84.289 | 538.865 |
| 12 | 0.691 | 48.002 | 158.456 | -58.063 | 50.275 | 50.087 | 77.322 | 531.788 |
| quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | min_capital_ratio | min_resolution_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 35.753 | 0.000 | 0.000 | 35.753 | 0.000 | 0.058 | 0.086 |
| 2 | 43.221 | 0.000 | 0.000 | 43.221 | 0.000 | 0.057 | 0.087 |
| 3 | 15.972 | 0.129 | 0.055 | 16.156 | 0.676 | 0.057 | 0.089 |
| 4 | 7.960 | 21.706 | 19.270 | 48.936 | 0.128 | 0.049 | 0.076 |
| 5 | 8.031 | 11.497 | 6.461 | 25.989 | 5.899 | 0.051 | 0.070 |
| 6 | 5.294 | 9.193 | 3.772 | 18.259 | 0.000 | 0.049 | 0.051 |
| 7 | 4.226 | 26.887 | 31.533 | 62.646 | 49.754 | 0.053 | 0.060 |
| 8 | 1.111 | 12.912 | 12.873 | 26.897 | 0.000 | 0.049 | 0.055 |
| 9 | 0.894 | 6.991 | 5.459 | 13.344 | 0.088 | 0.048 | 0.052 |
| 10 | 0.916 | 57.152 | 28.933 | 87.002 | 115.559 | 0.042 | 0.051 |
| 11 | 0.793 | 11.434 | 14.604 | 26.831 | 53.224 | 0.038 | 0.059 |
| 12 | 1.585 | 4.926 | 7.141 | 13.652 | 12.294 | 0.053 | 0.059 |
### iv-ACDpAIFBP, seed 2

| quarter | constrained_pct | cash_saving_pct | consumption | C_target_gap_pct | planned_investment | investment | asset_liquidation | gdp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.408 | -0.047 | 370.855 | -1.850 | 57.630 | 57.516 | 104.032 | 698.054 |
| 2 | 0.336 | 7.345 | 335.817 | -11.123 | 55.183 | 55.045 | 150.890 | 687.587 |
| 3 | 0.362 | 12.265 | 308.148 | -18.446 | 54.611 | 54.461 | 157.839 | 675.137 |
| 4 | 0.381 | 18.552 | 282.627 | -25.200 | 56.487 | 56.344 | 154.781 | 656.618 |
| 5 | 0.439 | 24.320 | 259.998 | -31.189 | 55.995 | 55.846 | 144.567 | 648.690 |
| 6 | 0.459 | 29.530 | 239.757 | -36.546 | 55.241 | 55.110 | 133.761 | 619.375 |
| 7 | 0.491 | 32.062 | 222.055 | -41.231 | 53.063 | 52.929 | 122.434 | 589.514 |
| 8 | 0.524 | 34.996 | 205.442 | -45.628 | 51.254 | 51.123 | 112.449 | 573.829 |
| 9 | 0.601 | 39.415 | 191.183 | -49.402 | 51.480 | 51.332 | 102.008 | 557.877 |
| 10 | 0.665 | 42.555 | 179.100 | -52.600 | 50.907 | 50.742 | 93.684 | 542.167 |
| 11 | 0.665 | 45.748 | 168.650 | -55.365 | 50.836 | 50.664 | 84.463 | 532.044 |
| 12 | 0.717 | 48.242 | 159.044 | -57.908 | 50.148 | 49.965 | 76.258 | 510.995 |
| quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | min_capital_ratio | min_resolution_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 38.945 | 0.000 | 0.000 | 38.945 | 0.000 | 0.056 | 0.083 |
| 2 | 41.144 | 0.000 | 0.000 | 41.144 | 0.000 | 0.057 | 0.086 |
| 3 | 7.478 | 0.146 | 0.069 | 7.692 | 0.000 | 0.057 | 0.088 |
| 4 | 17.663 | 21.661 | 17.445 | 56.770 | 0.894 | 0.037 | 0.060 |
| 5 | 8.956 | 12.461 | 6.309 | 27.726 | 0.000 | 0.032 | 0.054 |
| 6 | 6.734 | 6.020 | 1.567 | 14.321 | 0.000 | 0.032 | 0.055 |
| 7 | 4.868 | 18.618 | 30.874 | 54.359 | 58.851 | 0.061 | 0.074 |
| 8 | 0.739 | 7.152 | 8.990 | 16.881 | 0.170 | 0.058 | 0.062 |
| 9 | 0.413 | 27.910 | 9.005 | 37.328 | 18.823 | 0.056 | 0.058 |
| 10 | 0.732 | 21.097 | 36.094 | 57.923 | 67.264 | 0.035 | 0.053 |
| 11 | 0.370 | 2.388 | 9.130 | 11.889 | 27.221 | 0.045 | 0.052 |
| 12 | 1.679 | 4.318 | 4.780 | 10.778 | 1.694 | 0.046 | 0.052 |

### Twelve-quarter totals and final levels

| arm | seed | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | Q12_GDP | Q12_consumption | Q12_saving_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| iv-ACDpAIFB | 0 | 124.949 | 139.153 | 141.904 | 406.007 | 207.844 | 531.724 | 158.725 | 48.222 |
| iv-ACDpAIFB | 1 | 129.642 | 110.881 | 130.148 | 370.671 | 175.875 | 525.032 | 161.681 | 47.408 |
| iv-ACDpAIFB | 2 | 126.324 | 132.820 | 123.134 | 382.278 | 198.009 | 483.763 | 151.598 | 48.239 |
| iv-ACDpAIFBP | 0 | 122.845 | 114.497 | 130.231 | 367.573 | 176.281 | 517.005 | 160.743 | 47.597 |
| iv-ACDpAIFBP | 1 | 125.758 | 162.827 | 130.100 | 418.684 | 237.622 | 531.788 | 158.456 | 48.002 |
| iv-ACDpAIFBP | 2 | 129.723 | 121.771 | 124.262 | 375.756 | 174.918 | 510.995 | 159.044 | 48.242 |

The full quarterly sensitivity outputs, OFA boundary flows, debt/overdrafts,
bank stocks and named fiscal recapitalisations remain in outputs/BE.
The OFA liquidation path is still explicitly without issuer; no offsetting
issuer is invented. Retained F collateral is not a cash recovery.

## Firm starting costs, pricing and demand

All industry-quarter observations, all three base seeds and payout reruns
are in industry_costs.csv; firm_costs.csv in each run retains regional
firm observations and exact price decomposition. Industry unit costs are
output-weighted. Components are intermediate inputs, wages, taxes and
depreciation per unit; interest is additional in profit.

| industry_code | price | intermediates_per_unit | wages_per_unit | taxes_per_unit | depreciation_per_unit | unit_cost | GOS | IO_GOS | profit | t0_class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A01 | 1.000 | 0.602 | 0.082 | 0.005 | 0.113 | 0.802 | 8.822 | 8.479 | 4.999 | initial profit/nonnegative |
| A02 | 1.000 | 0.579 | 0.212 | 0.015 | 0.276 | 1.082 | 0.827 | 0.761 | -0.441 | initial loss |
| A03 | 1.000 | 0.442 | 0.148 | 0.010 | 0.241 | 0.841 | 0.618 | 0.600 | 0.212 | initial profit/nonnegative |
| B05 | 1.000 | 0.243 | 0.135 | 0.010 | 0.253 | 0.640 | 1.979 | 1.946 | 1.126 | initial profit/nonnegative |
| B06 | 1.000 | 0.364 | 0.060 | 0.003 | 0.031 | 0.458 | 39.340 | 39.106 | 36.743 | initial profit/nonnegative |
| B07 | 1.000 | 0.371 | 0.177 | 0.005 | 0.256 | 0.809 | 4.346 | 4.283 | 1.748 | initial profit/nonnegative |
| B08 | 1.000 | 0.224 | 0.120 | 0.007 | 0.155 | 0.507 | 4.192 | 4.142 | 3.114 | initial profit/nonnegative |
| B09 | 1.000 | 0.337 | 0.359 | 0.007 | 0.181 | 0.884 | 2.095 | 2.042 | 0.769 | initial profit/nonnegative |
| C10T12 | 1.000 | 0.737 | 0.141 | 0.004 | 0.066 | 0.948 | 5.016 | 4.591 | 1.930 | initial profit/nonnegative |
| C13T15 | 1.000 | 0.491 | 0.221 | 0.003 | 0.282 | 0.997 | 0.643 | 0.215 | -0.020 | initial loss |
| C16 | 1.000 | 0.625 | 0.160 | 0.003 | 0.118 | 0.905 | 2.866 | 2.775 | 1.242 | initial profit/nonnegative |
| C17_18 | 1.000 | 0.674 | 0.198 | 0.004 | 0.131 | 1.007 | 1.379 | 1.256 | -0.106 | initial loss |
| C19 | 1.000 | 0.797 | 0.023 | 0.002 | 0.062 | 0.883 | 5.454 | 5.093 | 3.322 | initial profit/nonnegative |
| C20 | 1.000 | 0.675 | 0.111 | 0.004 | 0.105 | 0.894 | 3.378 | 2.691 | 1.700 | initial profit/nonnegative |
| C21 | 1.000 | 0.529 | 0.175 | 0.001 | 0.170 | 0.875 | 1.579 | 0.767 | 0.611 | initial profit/nonnegative |
| C22 | 1.000 | 0.678 | 0.200 | 0.002 | 0.113 | 0.993 | 1.251 | 1.001 | 0.039 | initial profit/nonnegative |
| C23 | 1.000 | 0.610 | 0.213 | 0.005 | 0.229 | 1.058 | 0.979 | 0.874 | -0.357 | initial loss |
| C24A | 1.000 | 0.717 | 0.141 | 0.001 | 0.058 | 0.918 | 1.064 | 0.966 | 0.591 | initial profit/nonnegative |
| C24B | 1.000 | 0.834 | 0.057 | 0.001 | 0.046 | 0.938 | 2.001 | 1.838 | 1.071 | initial profit/nonnegative |
| C25 | 1.000 | 0.606 | 0.251 | 0.002 | 0.085 | 0.944 | 1.950 | 1.399 | 0.720 | initial profit/nonnegative |
| C26 | 1.000 | 0.424 | 0.232 | 0.001 | 0.159 | 0.816 | 2.066 | 0.673 | 1.070 | initial profit/nonnegative |
| C27 | 1.000 | 0.579 | 0.219 | 0.002 | 0.205 | 1.005 | 0.824 | 0.235 | -0.035 | initial loss |
| C28 | 1.000 | 0.531 | 0.221 | 0.002 | 0.071 | 0.825 | 3.739 | 1.818 | 2.604 | initial profit/nonnegative |
| C29 | 1.000 | 0.743 | 0.126 | 0.002 | 0.032 | 0.904 | 3.112 | 0.600 | 2.290 | initial profit/nonnegative |
| C301 | 1.000 | 0.607 | 0.273 | 0.003 | 0.292 | 1.175 | 0.107 | 0.088 | -0.165 | initial loss |
| C302T309 | 1.000 | 0.580 | 0.214 | 0.001 | 0.088 | 0.884 | 1.762 | 0.556 | 0.949 | initial profit/nonnegative |
| C31T33 | 1.000 | 0.622 | 0.240 | 0.002 | 0.106 | 0.970 | 1.263 | 0.582 | 0.167 | initial profit/nonnegative |
| D | 1.000 | 0.273 | 0.234 | -0.098 | 0.343 | 0.752 | 9.658 | 11.252 | 3.640 | initial profit/nonnegative |
| E | 1.000 | 0.464 | 0.261 | 0.010 | 0.441 | 1.176 | 1.147 | 1.106 | -0.870 | initial loss |
| F | 1.000 | 0.551 | 0.275 | 0.008 | 0.010 | 0.844 | 19.072 | 18.175 | 17.190 | initial profit/nonnegative |
| G | 1.000 | 0.364 | 0.399 | 0.005 | 0.023 | 0.791 | 25.440 | 24.825 | 21.171 | initial profit/nonnegative |
| H49 | 1.000 | 0.579 | 0.219 | -0.030 | 0.054 | 0.823 | 8.298 | 9.360 | 5.491 | initial profit/nonnegative |
| H50 | 1.000 | 0.683 | 0.286 | -0.092 | 0.395 | 1.272 | 0.165 | 0.289 | -0.398 | initial loss |
| H51 | 1.000 | 0.681 | 0.237 | 0.009 | 0.288 | 1.215 | 0.506 | 0.447 | -1.651 | initial loss |
| H52 | 1.000 | 0.529 | 0.297 | 0.010 | 0.101 | 0.936 | 2.447 | 2.306 | 0.585 | initial profit/nonnegative |
| H53 | 1.000 | 0.462 | 0.343 | 0.012 | 0.478 | 1.295 | 1.263 | 1.180 | -2.200 | initial loss |
| I | 1.000 | 0.525 | 0.353 | 0.015 | 0.429 | 1.323 | 3.060 | 2.625 | -9.447 | initial loss |
| J58T60 | 1.000 | 0.557 | 0.343 | 0.003 | 0.087 | 0.990 | 1.281 | 1.225 | 0.049 | initial profit/nonnegative |
| J61 | 1.000 | 0.387 | 0.197 | 0.002 | 0.235 | 0.821 | 6.810 | 6.771 | 2.754 | initial profit/nonnegative |
| J62_63 | 1.000 | 0.426 | 0.441 | 0.002 | 0.039 | 0.908 | 3.843 | 3.792 | 2.531 | initial profit/nonnegative |
| K | 1.000 | 0.421 | 0.320 | 0.026 | 0.031 | 0.799 | 18.467 | 16.367 | 16.139 | initial profit/nonnegative |
| L | 1.000 | 0.234 | 0.039 | 0.013 | 0.018 | 0.304 | 72.246 | 70.932 | 69.118 | initial profit/nonnegative |
| M | 1.000 | 0.359 | 0.396 | 0.003 | 0.029 | 0.786 | 11.536 | 11.384 | 9.709 | initial profit/nonnegative |
| N | 1.000 | 0.402 | 0.356 | 0.007 | 0.175 | 0.941 | 7.828 | 7.598 | 1.760 | initial profit/nonnegative |
| O | 1.000 | 0.472 | 0.371 | 0.005 | 0.018 | 0.865 | 15.319 | 14.806 | 13.732 | initial profit/nonnegative |
| P | 1.000 | 0.193 | 0.619 | 0.012 | 0.031 | 0.855 | 7.137 | 6.641 | 5.949 | initial profit/nonnegative |
| Q | 1.000 | 0.309 | 0.513 | 0.007 | 0.061 | 0.889 | 11.967 | 11.512 | 7.848 | initial profit/nonnegative |
| R | 1.000 | 0.501 | 0.286 | 0.023 | 0.449 | 1.258 | 1.857 | 1.636 | -2.572 | initial loss |
| S | 1.000 | 0.466 | 0.407 | 0.017 | 0.162 | 1.052 | 2.044 | 1.729 | -1.023 | initial loss |
| T | 1.000 | 0.000 | 1.000 | 0.000 | 0.958 | 1.958 | -0.000 | -0.000 | -0.650 | initial loss |

The reconstructed and stored t0 unit costs agree numerically. Sector I,
H53 and A02 already have costs above price. Their gross surplus is positive,
but the existing depreciation burden makes net profit negative. The
industry IO benchmark is the accepted input residual VA minus employee
compensation and production taxes, not a net-profit target. Current
depreciation comes from the inherited GFCF/investment-calibrated capital
consumption matrix (icio_sea_matching.py and icio_reader.py), rather than
industry observed CFC. This is an existing conceptual proxy requiring
an empirical CFC bridge; it is not proof of a mechanical scaling error.
No t0 firm input is changed in this round.

The price rule uses expected PPI inflation with speed 1, demand-pull and
cost-push speeds 0, and firm noise standard deviation .05. Thus there is
no direct correction toward an individual producer cost-plus price.
The diagnostic records the deterministic expected-inflation price and
recovers the multiplicative noise from the actual draw, without drawing
another random number. Price-floor observations are flagged as censored.
Subsequent demand loss, capacity use and cost/price gaps are descriptive
joint outcomes; the decomposition alone does not identify causation.

Cumulative price paths below use fixed t0 output weights; actual price
index = expected-inflation index times noise residual index. The
residual aggregates the realized firm noise and any censored floors.

| seed | industry_code | actual_price_index | expected_inflation_index | noise_residual_index |
| --- | --- | --- | --- | --- |
| 0 | A02 | 1.089 | 1.063 | 1.024 |
| 0 | C10T12 | 1.056 | 1.010 | 1.046 |
| 0 | C19 | 1.041 | 1.016 | 1.025 |
| 0 | F | 1.042 | 1.018 | 1.024 |
| 0 | H53 | 1.218 | 1.006 | 1.211 |
| 0 | I | 0.940 | 1.019 | 0.922 |
| 1 | A02 | 1.329 | 1.087 | 1.222 |
| 1 | C10T12 | 0.978 | 1.027 | 0.953 |
| 1 | C19 | 1.069 | 1.022 | 1.046 |
| 1 | F | 1.018 | 1.039 | 0.980 |
| 1 | H53 | 1.053 | 1.029 | 1.024 |
| 1 | I | 0.975 | 1.042 | 0.936 |
| 2 | A02 | 0.918 | 0.997 | 0.920 |
| 2 | C10T12 | 1.018 | 1.012 | 1.006 |
| 2 | C19 | 0.993 | 1.024 | 0.970 |
| 2 | F | 0.849 | 1.010 | 0.841 |
| 2 | H53 | 0.989 | 1.004 | 0.985 |
| 2 | I | 1.124 | 1.006 | 1.118 |
### Focus industries, seed 0, t0 and Q12

| quarter | industry_code | price | unit_cost | profit | capacity_use | demand | output | expected_price | realised_noise_price_effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | A02 | 1.000 | 1.082 | -0.441 | 1.000 | 4.263 | 4.263 | 1.000 | 0.000 |
| 0 | C10T12 | 1.000 | 0.948 | 1.930 | 1.000 | 42.683 | 42.683 | 1.000 | 0.000 |
| 0 | C19 | 1.000 | 0.883 | 3.322 | 0.000 | 30.476 | 30.476 | 1.000 | 0.000 |
| 0 | F | 1.000 | 0.844 | 17.190 | 1.000 | 114.951 | 114.951 | 1.000 | 0.000 |
| 0 | H53 | 1.000 | 1.295 | -2.200 | 1.000 | 6.899 | 6.899 | 1.000 | 0.000 |
| 0 | I | 1.000 | 1.323 | -9.447 | 1.000 | 28.760 | 28.760 | 1.000 | 0.000 |
| 12 | A02 | 1.078 | 1.114 | -0.131 | 0.795 | 3.426 | 3.388 | 1.085 | -0.006 |
| 12 | C10T12 | 1.056 | 0.935 | 2.686 | 0.531 | 22.554 | 22.670 | 1.117 | -0.054 |
| 12 | C19 | 1.032 | 0.926 | 2.204 | 0.000 | 20.207 | 20.848 | 1.018 | 0.014 |
| 12 | F | 1.042 | 0.838 | 23.765 | 1.000 | 114.951 | 114.951 | 1.040 | 0.002 |
| 12 | H53 | 1.215 | 1.303 | -0.466 | 0.658 | 4.391 | 4.543 | 1.156 | 0.051 |
| 12 | I | 0.936 | 1.331 | -6.513 | 0.565 | 15.894 | 16.249 | 0.966 | -0.031 |
### Focus industries, seed 1, t0 and Q12

| quarter | industry_code | price | unit_cost | profit | capacity_use | demand | output | expected_price | realised_noise_price_effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | A02 | 1.000 | 1.082 | -0.441 | 1.000 | 4.263 | 4.263 | 1.000 | 0.000 |
| 0 | C10T12 | 1.000 | 0.948 | 1.930 | 1.000 | 42.683 | 42.683 | 1.000 | 0.000 |
| 0 | C19 | 1.000 | 0.883 | 3.322 | 0.000 | 30.476 | 30.476 | 1.000 | 0.000 |
| 0 | F | 1.000 | 0.844 | 17.190 | 1.000 | 114.951 | 114.951 | 1.000 | 0.000 |
| 0 | H53 | 1.000 | 1.295 | -2.200 | 1.000 | 6.899 | 6.899 | 1.000 | 0.000 |
| 0 | I | 1.000 | 1.323 | -9.447 | 1.000 | 28.760 | 28.760 | 1.000 | 0.000 |
| 12 | A02 | 1.315 | 1.194 | 0.384 | 0.762 | 3.178 | 3.249 | 1.313 | 0.001 |
| 12 | C10T12 | 0.970 | 0.949 | 0.484 | 0.590 | 24.435 | 25.176 | 0.988 | -0.018 |
| 12 | C19 | 1.073 | 0.793 | 5.946 | 0.000 | 20.374 | 21.094 | 1.054 | 0.018 |
| 12 | F | 1.020 | 0.878 | 13.916 | 0.851 | 95.897 | 97.819 | 1.009 | 0.010 |
| 12 | H53 | 1.049 | 1.304 | -1.254 | 0.677 | 4.512 | 4.668 | 1.004 | 0.046 |
| 12 | I | 0.967 | 1.354 | -6.534 | 0.577 | 15.676 | 16.595 | 0.959 | 0.008 |
### Focus industries, seed 2, t0 and Q12

| quarter | industry_code | price | unit_cost | profit | capacity_use | demand | output | expected_price | realised_noise_price_effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | A02 | 1.000 | 1.082 | -0.441 | 1.000 | 4.263 | 4.263 | 1.000 | 0.000 |
| 0 | C10T12 | 1.000 | 0.948 | 1.930 | 1.000 | 42.683 | 42.683 | 1.000 | 0.000 |
| 0 | C19 | 1.000 | 0.883 | 3.322 | 0.000 | 30.476 | 30.476 | 1.000 | 0.000 |
| 0 | F | 1.000 | 0.844 | 17.190 | 1.000 | 114.951 | 114.951 | 1.000 | 0.000 |
| 0 | H53 | 1.000 | 1.295 | -2.200 | 1.000 | 6.899 | 6.899 | 1.000 | 0.000 |
| 0 | I | 1.000 | 1.323 | -9.447 | 1.000 | 28.760 | 28.760 | 1.000 | 0.000 |
| 12 | A02 | 0.916 | 1.023 | -0.357 | 0.749 | 3.050 | 3.192 | 0.889 | 0.030 |
| 12 | C10T12 | 1.016 | 0.959 | 1.258 | 0.550 | 22.093 | 23.496 | 1.011 | 0.004 |
| 12 | C19 | 0.981 | 0.889 | 1.844 | 0.000 | 19.239 | 19.999 | 1.016 | -0.034 |
| 12 | F | 0.859 | 0.840 | 1.509 | 0.753 | 84.320 | 86.556 | 0.892 | -0.037 |
| 12 | H53 | 0.987 | 1.237 | -1.170 | 0.644 | 4.244 | 4.443 | 0.999 | -0.012 |
| 12 | I | 1.122 | 1.288 | -2.507 | 0.506 | 13.420 | 14.538 | 1.084 | 0.035 |

Initial losses are a starting cost/IO-calibration issue. Newly loss-making
industries are classified jointly by relative price/cost and demand/output
changes in industry_loss_classification.csv. C10T12, C19 and F begin
profitable nationally, so their later losses cannot all be attributed to
initial negative profit. Losses within a profitable national industry may
still be concentrated in particular regional firms.

## Approved prudent payout rule

Only discretionary firm dividends are screened. Mixed income and corporate
transfers retain the existing D2 requests, cash cap, tax and household
allocation. Released dividend capacity is not reassigned to those flows.
The discretionary dividend is capped by positive retained profit and cash
above declared mixed/transfers plus a reserve for next-quarter scheduled
principal, interest (including overdraft interest), and the latest nominal
wage bill. The latest observed wages are the no-new-parameter forecast.
Opening distributable retained profit is one initial quarter of positive
after-tax profit, explicitly a proxy because a historical retained-earnings
ledger is not available. Thereafter the ledger carries realized after-tax
profits less all firm distributions; negative balances carry forward.
Current asset revaluations do not create distributable profit.

The screen runs before the irrevocable D2 declaration used in household
budgets. End-quarter payment settles that declaration exactly. Later
operating losses can still reduce cash; this is not a guarantee of positive
end-quarter deposits. Non-discretionary transfers can themselves breach the
reserve. No payout is retrospectively cancelled after households spend it.

All nationally loss-making Q12 industries, with overlapping diagnostic
flags (demand down does not rule out pricing/cost effects):

| seed | industry_code | profit | classification | demand_down | noise_sufficient_for_cost_crossing | cost_above_no_noise_price |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | A02 | -0.131 | initial cost/IO loss | True | False | True |
| 0 | C13T15 | -0.094 | initial cost/IO loss | True | False | True |
| 0 | C17_18 | -0.148 | initial cost/IO loss | True | False | True |
| 0 | C22 | -0.836 | later loss with demand decline | True | False | True |
| 0 | C23 | -0.316 | initial cost/IO loss | True | False | True |
| 0 | C24A | -0.470 | later loss with demand decline | True | False | True |
| 0 | C301 | -0.108 | initial cost/IO loss | True | False | True |
| 0 | E | -0.337 | initial cost/IO loss | True | False | True |
| 0 | H50 | -0.321 | initial cost/IO loss | True | False | True |
| 0 | H51 | -1.615 | initial cost/IO loss | True | False | True |
| 0 | H53 | -0.466 | initial cost/IO loss | True | False | True |
| 0 | I | -6.513 | initial cost/IO loss | True | False | True |
| 0 | R | -2.064 | initial cost/IO loss | True | False | True |
| 0 | S | -1.271 | initial cost/IO loss | True | False | True |
| 0 | T | -0.001 | initial cost/IO loss | True | False | False |
| 1 | C23 | -0.698 | initial cost/IO loss | True | False | True |
| 1 | C27 | -0.000 | initial cost/IO loss | True | False | True |
| 1 | C29 | -0.073 | later loss with demand decline | True | True | False |
| 1 | E | -0.292 | initial cost/IO loss | True | False | True |
| 1 | H50 | -0.242 | initial cost/IO loss | True | False | True |
| 1 | H51 | -1.241 | initial cost/IO loss | True | False | True |
| 1 | H53 | -1.254 | initial cost/IO loss | True | False | True |
| 1 | I | -6.534 | initial cost/IO loss | True | False | True |
| 1 | R | -0.429 | initial cost/IO loss | True | False | True |
| 1 | S | -0.053 | initial cost/IO loss | True | False | True |
| 1 | T | -0.001 | initial cost/IO loss | True | False | False |
| 2 | A02 | -0.357 | initial cost/IO loss | True | False | True |
| 2 | C21 | -0.171 | later loss with demand decline | True | False | True |
| 2 | C23 | -0.331 | initial cost/IO loss | True | False | True |
| 2 | C24A | -0.059 | later loss with demand decline | True | True | False |
| 2 | C27 | -0.074 | initial cost/IO loss | True | True | False |
| 2 | C301 | -0.105 | initial cost/IO loss | True | False | True |
| 2 | C31T33 | -0.490 | later loss with demand decline | True | False | True |
| 2 | E | -0.276 | initial cost/IO loss | True | False | True |
| 2 | H50 | -0.102 | initial cost/IO loss | True | False | True |
| 2 | H51 | -1.084 | initial cost/IO loss | True | False | True |
| 2 | H52 | -0.654 | later loss with demand decline | True | False | True |
| 2 | H53 | -1.170 | initial cost/IO loss | True | False | True |
| 2 | I | -2.507 | initial cost/IO loss | True | False | True |
| 2 | J58T60 | -1.013 | later loss with demand decline | True | False | True |
| 2 | R | -1.870 | initial cost/IO loss | True | False | True |
| 2 | S | -0.038 | initial cost/IO loss | True | False | True |
| 2 | T | -0.001 | initial cost/IO loss | True | False | False |
| seed | firm_loss_B | firm_loss_P | payout_B | payout_P | Q12_GDP_B | Q12_GDP_P | Q12_income_B | Q12_income_P |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 281.057 | 244.728 | 727.589 | 742.999 | 531.724 | 517.005 | 310.198 | 310.366 |
| 1 | 241.029 | 292.927 | 742.445 | 722.057 | 525.032 | 531.788 | 311.016 | 308.412 |
| 2 | 255.954 | 246.033 | 707.765 | 728.285 | 483.763 | 510.995 | 296.556 | 310.952 |

Firm losses fall on seeds 0 and 2 but rise on seed 1. The payout rule
therefore does not provide a robust firm-loss reduction. Discretionary
and non-discretionary flows must be separated because altered prices,
profits and cash positions can increase total distributions even when
dividends are restricted. Twelve-quarter components:

| arm | seed | paid_mixed | paid_transfers | paid_dividends |
| --- | --- | --- | --- | --- |
| iv-ACDpAIFB | 0 | 230.906 | 295.456 | 201.227 |
| iv-ACDpAIFB | 1 | 237.900 | 304.584 | 199.961 |
| iv-ACDpAIFB | 2 | 228.489 | 292.493 | 186.782 |
| iv-ACDpAIFBP | 0 | 239.574 | 306.085 | 197.341 |
| iv-ACDpAIFBP | 1 | 233.316 | 298.804 | 189.937 |
| iv-ACDpAIFBP | 2 | 236.549 | 302.274 | 189.462 |

Detailed retained-profit, reserve and declared/paid dividend observations
are in each payout run payout_log.csv. Quarterly payouts and household
income are in quarterly.csv; event-by-event fiscal support is in
resolution_log.csv. The payout arm is a separate comparison, not a
replacement for the original Gate B measurement.

## Firm-behaviour proposals only

1. Replace unanchored price noise with a cost/markup target: form expected
   unit intermediate, wage and tax costs and separately validated CFC;
   target price = expected unit cost/(1 - target operating margin).
   Anchor industry margins to concept-matched IO/QFSE observations, with
   partial adjustment and a floor covering variable cost. Estimate the
   adjustment speed independently; do not choose it to remove defaults.
   A limited idiosyncratic shock, if retained, should mean-revert around
   the target. Separate financing costs from operating margins and avoid
   using the initial investment proxy as observed depreciation.
2. For persistent operating losses, specify either capacity contraction
   with worker reallocation and asset transfers or explicit exit/entry.
   Entry requires start-up equity, working capital, product supply and
   worker matching; exit needs creditor recoveries and an asset buyer.
   Public O/P/Q producers need a government financing counterparty.
   Duration thresholds, scrapping/recovery and entry rates need sourced
   Canadian evidence or labelled sensitivities. Do not delete continuing
   overdrafts, forgive debt, or create production capacity without funding.

Neither proposal is implemented. The approved payout restriction alone
does not repair structurally negative operating margins or capital-cost
measurement.

## Plausibility and review recommendation

Household losses still use the old rule. Aggregate reductions under B
coincide with implausibly weak consumption, so they do not validate the
household default mechanism. E remains necessary to evaluate payment
failure and collateral recovery, but its explicit gate has not passed.

Initial household debt is 2,883.063B. Annualised model losses below
are 12Q write-offs / 3 / initial debt; this is not an average-loan net
charge-off rate. The initial bank-equity denominator is 456.221B
(36-10-0580 v62696428 + v62696533, 2022Q4; inherited bank-capital provenance).

| arm | seed | annualised_HH_loss_initial_debt_pct | recap_initial_bank_equity_pct |
| --- | --- | --- | --- |
| iv-ACDpAIFB | 0 | 1.445 | 45.558 |
| iv-ACDpAIFB | 1 | 1.499 | 38.550 |
| iv-ACDpAIFB | 2 | 1.461 | 43.402 |
| iv-ACDpAIFBP | 0 | 1.420 | 38.639 |
| iv-ACDpAIFBP | 1 | 1.454 | 52.085 |
| iv-ACDpAIFBP | 2 | 1.500 | 38.341 |

For scale, [RBC 2023 annual report](https://www.rbc.com/investor-relations/_assets-custom/pdf/ar_2023_e.pdf)
has retail net write-offs .604B/.881B in 2022/2023 and wholesale
.136B/.293B; total write-off ratios .10%/.14% of average loans. These
are one consolidated bank, not national household totals.
[TransUnion Q4 2024](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q4-24-ciir-report.pdf)
reports 60+ day mortgage delinquency .25% of accounts and .23% of
balances, stocks rather than loss flows. [OSB 2024](https://ised-isde.canada.ca/site/office-superintendent-bankruptcy/en/statistics-and-research/insolvency-statistics/annual-reports/annual-2024)
reports 4,810/6,188 business insolvencies in 2023/2024; composite model
restructurings do not equal legal filings. Original dates, tables/pages
and hashes remain in benchmarks/ABCD and benchmarks/FE; BE benchmark_index
links their exact provenance hashes. No levels are fitted to these figures.

Firm losses and repeated recapitalisations remain too large to accept as
normal Canadian baseline magnitudes. They combine an inherited starting
capital-cost proxy and producer/pricing behaviour. They can be stated as
limitations in exploratory runs, but should not be presented as a validated
firm closure. In this round Phase B is not ready regardless: Gate B fails,
and the required household default step has not run. Review the household
level/mapping issue first; decide separately which firm limitations are
acceptable for a future conditional Phase B.

## Verification and evidence

Full suite: 443 passed, 30 known failures, 0 extra failures, 473 cases. Maximum accounting residual across 16 runs: 1.44e-14.

The full suite uses run_pre_D3_tests.py, sampler n_cores=1. The exact
30 pre-existing Nan in transactor_total_real_supply failure IDs are
compared with FE. All final base/payout 2Q prefixes match their 12Q
counterparts. Protected pickle hashes, source revisions and all run
metadata are audited. Local household micro ledgers are not committed;
their hashes and aggregate group panels are retained.

Evidence: [quarterly](outputs/BE/quarterly.csv), [summary](outputs/BE/summary.csv),
[all-industry costs](outputs/BE/industry_costs.csv), [constraints](outputs/BE/constraint_diagnosis.csv),
[resolution log](outputs/BE/resolution_log.csv), [audit](outputs/BE/audit.json).
Reproduce with run_be_measurements.py, summarise_be.py,
be_household_diagnosis.py, run_be_full_tests.py, audit_be.py and this renderer.
Stop here for review. No Phase B or C_dp_005 work has started.
