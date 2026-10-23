# Household investment, F and E — 23 October 2026

**Step 1 is implemented. Gate 1 fails: realized Q1 investment remains more
than 10% below the independent benchmark. F and E therefore did not start.**
Saving and constraint trends are reported, not used to stop this step. Phase B,
C_dp_005 and the heterogeneous buffer-stock rule remain on hold. Branch
feature/validation-2022, from e11ff6d; no push.

## Decisions, commits, tests and gates

| Step | Commit / tests | Result |
|---|---|---|
| 1a: read-only household cash ledger | de244bc; individual cash-identity regression passes | Seed-0 baseline reproduced within floating-point tolerance; directly measured Q12 investment 50.700811B including CF tax |
| 1b: initial GFCF level | f1e7b60; 3 focused checks including opt-in/relative propensity/initial-flow checks | One common multiplier, 0.95537 approximately; initial desired investment exactly 60.59825B/quarter, independently sourced |
| 1c: consumption priority | b75d4a7; 12 focused asset/budget/calibration/priority checks plus gate-boundary regression pass | Investment is cut first; no new spending parameter; stock/counterparty identities retained |
| 1d: link to dwellings | Proposal below | Not implemented |
| 2: F debt boundary/default | Not started | Gate 1 prevents entry; no new firm-debt pickle, allocation, N or recovery parameter |
| 3: E household payment default/foreclosure | Not started | No E or D3 rule in the candidate; old household rule retained |

Amounts are CAD billions; flows quarterly unless marked annual or 12Q totals.
Percentages are labelled; cuts are planned purchasers-price amounts before
market rationing. Constrained share means any D budget cut, including a cut
only to discretionary investment. The consumption-constrained share is also
retained separately in quarterly.csv; the definition is not changed to pass a gate.

## Gate 1 and seed comparison

The target is 60.59825B per quarter. Gate 1 requires accounting ≤1e-8 and
realized Q1 investment within ±10% of that level. It does not test saving or
the constraint trend. All three candidate seeds have their own 2Q accounting
run immediately before 12Q; runs are serial. F/E do not begin after a failure.
gate1.json is authoritative. The inherited manifest household_gate_passed
field is only the older Q1 consumption check, not this investment gate.

| seed | Q1_investment | quarterly_benchmark | gap_pct | gate1_pass |
| --- | --- | --- | --- | --- |
| 0 | 50.916 | 60.598 | -15.977 | False |
| 1 | 49.775 | 60.598 | -17.861 | False |
| 2 | 49.383 | 60.598 | -18.507 | False |

## Ledger first: what S-H7 actually does

The previous description “investment at 5% per quarter, not tied to income”
is incorrect. The 5% is depreciation, in households_configuration.py,
WealthFunction.other_real_assets_depreciation_rate. Desired investment is
DefaultHouseholdInvestment.compute_target_investment, investment.py:148:

I_basic[h,j] = weight[j] × investment_rate[h] × expected_income[h] / (1+CF tax).

households.py:732 calls it with current expected income, after income
expectations and before labour/housing/credit/goods clearing. The 13 regional
baseline rates are uniform within region, about 0.1364–0.2533. They originate
from the synthetic population's set_household_investment_rates (initial 0.2
seed, then rescaled to IO household capital inputs), not a 5% wealth rule.
All measured countries use assume_zero_growth=False; the fixed-initial-flow
branch is not active. Goods-market purchases are subsequently split into
consumption up to its target and residual investment. The realized basic
investment enters wealth_other_real_assets through update_wealth, with the
existing 5% quarterly depreciation. It does not add dwellings.

The read-only instrument captures every household before its insolvency
handler: paid consumption including VAT, investment including CF tax,
principal, interest, rent, new loans, OFA liquidation and deposit change.
It also records income, new OFA saving and property transactions, which are
necessary to close a household-level identity:

Δdeposits = income − C_with_VAT − I_with_CF − rent − interest − principal
            + new loans + OFA liquidation − new OFA saving
            − house purchases + house-sale proceeds.

Cash saving elsewhere in this report is income − interest − C_with_VAT − rent.
It excludes investment/principal. Liquidation is a stock conversion, not income.
Every individual identity closes to 1e-4 CAD absolute or better. Group ledgers
are available by quarter, decile, asset band and their cross-classification.
The household files remain locally under each run's micro/ledger_*.csv;
household_ledger_manifest.json records their hashes. Aggregates are committed.

### Baseline seed-0 paid spending, measured directly

| quarter | consumption_VAT | investment_CF | principal | interest | rent |
| --- | --- | --- | --- | --- | --- |
| 1 | 367.102 | 55.551 | 29.946 | 3.297 | 5.557 |
| 2 | 354.483 | 56.790 | 28.718 | 3.123 | 5.557 |
| 3 | 341.269 | 53.468 | 27.906 | 3.043 | 5.564 |
| 4 | 336.985 | 49.970 | 27.339 | 3.006 | 5.589 |
| 5 | 330.445 | 50.560 | 27.087 | 3.055 | 5.601 |
| 6 | 315.735 | 49.033 | 26.975 | 3.135 | 5.604 |
| 7 | 312.988 | 50.134 | 26.853 | 3.191 | 5.605 |
| 8 | 307.977 | 49.606 | 26.712 | 3.240 | 5.617 |
| 9 | 313.418 | 52.327 | 26.684 | 3.320 | 5.626 |
| 10 | 313.890 | 49.282 | 26.693 | 3.413 | 5.627 |
| 11 | 306.952 | 51.182 | 26.663 | 3.480 | 5.646 |
| 12 | 306.613 | 50.701 | 26.657 | 3.552 | 5.647 |

### Baseline seed-0 financing and stock movement

| quarter | income | new_loans | asset_liquidation | new_OFA_saving | house_purchases | house_sale_proceeds | deposit_change | cash_residual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 375.204 | 1.308 | 10.849 | 1.133 | 1.029 | 1.029 | -75.224 | -0.000 |
| 2 | 369.630 | 0.135 | 20.658 | 0.465 | 0.213 | 0.213 | -58.714 | -0.000 |
| 3 | 363.808 | 0.107 | 22.944 | 1.740 | 0.994 | 0.994 | -46.132 | -0.000 |
| 4 | 361.157 | 0.278 | 23.989 | 1.444 | 0.000 | 0.000 | -38.909 | -0.000 |
| 5 | 356.658 | 1.552 | 24.847 | 0.521 | 1.314 | 1.314 | -34.213 | -0.000 |
| 6 | 348.360 | 2.630 | 23.559 | 1.620 | 0.778 | 0.778 | -27.553 | -0.000 |
| 7 | 347.390 | 0.767 | 24.292 | 0.661 | 1.597 | 1.597 | -26.983 | -0.000 |
| 8 | 345.414 | 0.077 | 23.523 | 0.902 | 0.000 | 0.000 | -25.040 | -0.000 |
| 9 | 349.095 | 1.382 | 25.573 | 0.226 | 0.575 | 0.575 | -25.551 | -0.000 |
| 10 | 354.517 | 2.014 | 22.565 | 1.563 | 0.000 | 0.000 | -21.371 | -0.000 |
| 11 | 350.579 | 0.739 | 23.251 | 1.029 | 1.106 | 1.106 | -20.382 | -0.000 |
| 12 | 349.511 | 0.760 | 23.373 | 0.782 | 0.000 | 0.000 | -20.307 | -0.000 |

At Q12, direct investment is 50.700811B. It agrees with the old cash bridge's
implied value. This confirms the cash use, not excessive aggregate initial
investment: baseline Q1 paid I is 55.551B, already below the 60.598B quarterly
benchmark. Allocation, financing, stock destination and priority remain
separate questions. The earlier positive cash-saving figure was not accumulating
financial wealth. The new ledger distinguishes cash uses rather than
redefining saving to remove the overshoot.

### Q12 ledger by income decile and assets, baseline seed 0

Deciles are fixed national t0 income ranks with population weights. Asset bands
are t0 non-pension OFA per represented household: zero, 0–10k, 10–100k, >100k.
All quarters and all candidate seeds are in cash_ledger_decile.csv,
cash_ledger_assets.csv and cash_ledger_decile_assets.csv.

| decile | consumption_VAT | investment_CF | principal | interest | rent | new_loans | asset_liquidation | deposit_change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 9.205 | 1.055 | 0.549 | -0.038 | 0.744 | 0.132 | 0.506 | -1.233 |
| 2 | 13.331 | 1.814 | 1.093 | -0.196 | 0.535 | 0.267 | 1.167 | -1.831 |
| 3 | 18.794 | 2.967 | 1.325 | -0.250 | 0.541 | 0.119 | 1.348 | -1.903 |
| 4 | 23.237 | 3.782 | 1.410 | -0.181 | 0.730 | 0.041 | 1.333 | -1.218 |
| 5 | 27.598 | 4.629 | 1.833 | 0.224 | 0.616 | 0.055 | 1.381 | -1.512 |
| 6 | 32.837 | 5.457 | 2.255 | 0.192 | 0.605 | 0.046 | 1.794 | -1.517 |
| 7 | 35.778 | 5.938 | 2.931 | 0.495 | 0.562 | 0.042 | 2.251 | -1.778 |
| 8 | 40.289 | 6.822 | 3.458 | 0.598 | 0.476 | 0.025 | 2.563 | -2.344 |
| 9 | 46.045 | 7.805 | 4.578 | 1.141 | 0.398 | 0.025 | 4.007 | -2.714 |
| 10 | 59.499 | 10.434 | 7.225 | 1.567 | 0.440 | 0.009 | 7.024 | -4.257 |

| asset_band | consumption_VAT | investment_CF | principal | interest | rent | new_loans | asset_liquidation | deposit_change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0-10k | 33.328 | 5.615 | 3.416 | 1.086 | 0.757 | 0.107 | 0.316 | -1.453 |
| 10-100k | 78.305 | 12.932 | 7.209 | 1.917 | 1.213 | 0.077 | 5.287 | -4.924 |
| 100k+ | 116.660 | 19.321 | 10.052 | -0.905 | 1.212 | 0.001 | 17.363 | -10.368 |
| zero | 78.320 | 12.832 | 5.979 | 1.454 | 2.464 | 0.576 | 0.406 | -3.562 |

## Independent initial investment calibration

StatCan 36-10-0112, household sector Fixed capital, **v62305994**: 2022 quarterly
current-dollar SAAR values 269.468, 240.876, 225.284 and 233.944B/year. Mean
242.393B/year, or 60.59825B/quarter. Unadjusted v62306041 independently sums to
the same annual total. This is household-sector GFCF, including unincorporated
enterprises, not a consumer-durable allowance or net investment.

At initialization, one common propensity multiplier matches this purchasers'
price level using the existing expected-income base including funded D2.
Relative household/regional propensities, industry weights and dynamic
income dependence are retained. No realized outcome, saving rate, bank loss
or gate statistic enters calibration. Initial wealth/debt/housing stocks are
unchanged. Target investment is not reset to the benchmark every quarter.

| measure | quarterly |
| --- | --- |
| Old initial recorded flow | 56.185 |
| Old propensity on initial D2 expected income | 63.429 |
| New initial desired / StatCan quarterly target | 60.598 |

| region | old_rate | new_rate | multiplier | target |
| --- | --- | --- | --- | --- |
| CAN_NL | 0.174 | 0.167 | 0.955 | 0.714 |
| CAN_PE | 0.159 | 0.152 | 0.955 | 0.183 |
| CAN_NS | 0.148 | 0.141 | 0.955 | 1.085 |
| CAN_NB | 0.141 | 0.135 | 0.955 | 0.809 |
| CAN_QC | 0.151 | 0.144 | 0.955 | 11.055 |
| CAN_ON | 0.158 | 0.151 | 0.955 | 22.585 |
| CAN_MB | 0.155 | 0.148 | 0.955 | 1.639 |
| CAN_SK | 0.212 | 0.202 | 0.955 | 2.245 |
| CAN_AB | 0.198 | 0.189 | 0.955 | 10.059 |
| CAN_BC | 0.193 | 0.184 | 0.955 | 9.854 |
| CAN_YT | 0.251 | 0.240 | 0.955 | 0.133 |
| CAN_NT | 0.136 | 0.130 | 0.955 | 0.093 |
| CAN_NU | 0.253 | 0.242 | 0.955 | 0.145 |

### Retained initial goods basket (largest sectors)

| industry_code | old_initial_purchasers | new_initial_purchasers | share |
| --- | --- | --- | --- |
| F | 32.281 | 34.856 | 57.519 |
| C28 | 3.388 | 3.654 | 6.030 |
| C29 | 2.921 | 3.143 | 5.186 |
| L | 2.679 | 2.886 | 4.763 |
| J62_63 | 2.446 | 2.631 | 4.342 |
| C26 | 1.791 | 1.927 | 3.180 |
| P | 1.204 | 1.294 | 2.135 |
| M | 1.169 | 1.258 | 2.077 |
| C31T33 | 0.757 | 0.815 | 1.344 |
| C302T309 | 0.733 | 0.788 | 1.300 |
| A01 | 0.621 | 0.672 | 1.110 |
| O | 0.613 | 0.659 | 1.087 |

Positive education/public-administration or other service weights cannot be verified as household fixed-capital uses from this industry vector alone. The asset-use mapping needs separate review; no claim that every such purchase matches SNA capital is made.

### Concept boundary and limitations

SNA household GFCF includes residential construction, renovations and
ownership-transfer costs plus unincorporated-enterprise fixed capital. Land,
within-sector existing-house purchase prices as such, ordinary repairs and private consumer
durables are not GFCF. The model retains its IO capital-input goods basket;
vehicles/equipment can be business capital, but industry alone does not
identify end use. No private car, furniture or training expense is newly
reclassified as investment to match the level.

The calibrated flow is an aggregate household-GFCF proxy. Existing purchases
still accumulate in a generic other-real-assets stock rather than distinct
dwellings/business capital. The IO basket does not separately identify new
houses, renovations and transfer fees, or verify each commodity's capital use;
a full asset-category concept reconciliation remains incomplete. Numerical
Gate 1 fails regardless, so no full concept-validation claim is needed to
permit a later step. The original S-H7 dwelling-stock concern remains open.

## Consumption priority under D

After senior obligations and available non-pension assets, allocate resources
to planned consumption first. Investment receives only resources left after
consumption, up to its plan. Cut investment within its existing sector mix;
reduce consumption within its own mix only after investment is zero. Existing
OFA liquidation books only actual cash need after clearing. The priority is
opt-in for this candidate; old controls/defaults remain reproducible. No new
numeric preference or gate-fitting parameter is introduced.

## Quarterly candidate results

Cash saving is compared with −0.601861%, the unchanged 2022 DI/C comparison
excluding D.8. Saving and constrained-share slopes are diagnostics only here.
The fixed investment comparison is 60.59825B/quarter, not a refitted path.

### Budget versus consumption constraints at Q1/Q12

| seed | quarter | constrained_share | consumption_constrained_share |
| --- | --- | --- | --- |
| 0 | 1 | 18.631 | 12.026 |
| 0 | 12 | 50.269 | 41.539 |
| 1 | 1 | 18.762 | 12.414 |
| 1 | 12 | 50.944 | 39.771 |
| 2 | 1 | 18.561 | 11.626 |
| 2 | 12 | 49.648 | 39.843 |

### Seed 0

| quarter | constrained_share | investment_cut | consumption_cut | asset_liquidation | investment | consumption | cash_DI | cash_saving | cash_saving_rate | gdp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 18.631 | 8.494 | 5.404 | 11.027 | 50.916 | 378.859 | 371.908 | -6.952 | -1.869 | 700.194 |
| 2 | 24.842 | 12.561 | 12.374 | 19.818 | 46.199 | 367.858 | 366.517 | -1.341 | -0.366 | 693.179 |
| 3 | 29.475 | 15.074 | 15.670 | 23.186 | 43.542 | 359.428 | 361.030 | 1.602 | 0.444 | 689.718 |
| 4 | 33.300 | 17.237 | 18.391 | 23.915 | 40.840 | 352.887 | 359.092 | 6.205 | 1.728 | 683.544 |
| 5 | 36.163 | 18.534 | 19.208 | 24.130 | 39.350 | 350.236 | 357.512 | 7.276 | 2.035 | 684.742 |
| 6 | 38.832 | 20.540 | 21.300 | 24.543 | 37.493 | 349.064 | 355.742 | 6.678 | 1.877 | 690.083 |
| 7 | 41.325 | 22.397 | 22.318 | 24.043 | 36.143 | 350.039 | 359.306 | 9.266 | 2.579 | 685.005 |
| 8 | 43.290 | 23.227 | 22.865 | 24.042 | 34.684 | 348.319 | 359.075 | 10.756 | 2.996 | 667.501 |
| 9 | 45.480 | 24.355 | 26.009 | 23.251 | 32.616 | 336.364 | 349.459 | 13.095 | 3.747 | 667.528 |
| 10 | 47.270 | 24.599 | 27.038 | 23.041 | 31.830 | 332.282 | 346.714 | 14.432 | 4.163 | 657.679 |
| 11 | 48.796 | 25.527 | 24.720 | 22.325 | 30.842 | 334.617 | 346.792 | 12.176 | 3.511 | 666.885 |
| 12 | 50.269 | 26.968 | 27.377 | 23.526 | 30.723 | 341.167 | 353.495 | 12.328 | 3.487 | 660.089 |

### Seed 1

| quarter | constrained_share | investment_cut | consumption_cut | asset_liquidation | investment | consumption | cash_DI | cash_saving | cash_saving_rate | gdp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 18.762 | 8.661 | 5.579 | 11.618 | 49.775 | 382.888 | 371.141 | -11.746 | -3.165 | 714.585 |
| 2 | 25.128 | 13.018 | 12.658 | 19.761 | 47.192 | 371.334 | 370.740 | -0.594 | -0.160 | 709.898 |
| 3 | 29.813 | 15.617 | 15.866 | 22.842 | 43.799 | 362.697 | 366.837 | 4.140 | 1.129 | 703.103 |
| 4 | 33.367 | 17.502 | 18.183 | 25.254 | 42.200 | 361.922 | 367.331 | 5.409 | 1.473 | 704.073 |
| 5 | 36.345 | 19.436 | 19.938 | 24.106 | 40.606 | 361.760 | 369.829 | 8.069 | 2.182 | 716.155 |
| 6 | 39.415 | 22.461 | 23.927 | 27.453 | 39.952 | 375.367 | 377.100 | 1.733 | 0.460 | 724.729 |
| 7 | 42.012 | 24.690 | 26.137 | 27.728 | 37.962 | 374.524 | 382.926 | 8.402 | 2.194 | 723.922 |
| 8 | 43.996 | 25.959 | 25.711 | 25.397 | 36.829 | 374.165 | 385.020 | 10.855 | 2.819 | 728.223 |
| 9 | 46.147 | 26.654 | 25.899 | 25.957 | 35.733 | 373.990 | 383.841 | 9.851 | 2.566 | 729.960 |
| 10 | 48.009 | 28.070 | 27.415 | 24.605 | 34.607 | 373.882 | 386.371 | 12.489 | 3.232 | 722.709 |
| 11 | 49.567 | 28.799 | 28.651 | 23.923 | 33.363 | 369.883 | 382.418 | 12.535 | 3.278 | 729.694 |
| 12 | 50.944 | 29.001 | 29.995 | 23.387 | 32.555 | 364.727 | 380.639 | 15.912 | 4.180 | 730.817 |

### Seed 2

| quarter | constrained_share | investment_cut | consumption_cut | asset_liquidation | investment | consumption | cash_DI | cash_saving | cash_saving_rate | gdp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 18.561 | 8.339 | 5.390 | 11.410 | 49.383 | 378.706 | 370.753 | -7.953 | -2.145 | 696.684 |
| 2 | 24.708 | 12.279 | 12.302 | 18.578 | 43.405 | 362.435 | 363.418 | 0.984 | 0.271 | 686.134 |
| 3 | 29.108 | 14.649 | 15.770 | 22.414 | 42.894 | 353.758 | 356.600 | 2.842 | 0.797 | 674.041 |
| 4 | 32.947 | 16.717 | 18.035 | 24.271 | 40.315 | 346.655 | 350.708 | 4.053 | 1.156 | 658.287 |
| 5 | 35.862 | 17.920 | 19.373 | 23.513 | 37.539 | 333.440 | 341.015 | 7.575 | 2.221 | 649.716 |
| 6 | 38.524 | 19.196 | 20.067 | 24.819 | 35.595 | 330.605 | 336.202 | 5.597 | 1.665 | 645.734 |
| 7 | 40.942 | 20.155 | 22.451 | 24.686 | 33.951 | 326.217 | 333.604 | 7.387 | 2.214 | 634.912 |
| 8 | 42.783 | 21.169 | 23.419 | 22.662 | 32.012 | 317.780 | 330.016 | 12.236 | 3.708 | 625.140 |
| 9 | 44.929 | 22.525 | 24.718 | 24.692 | 30.856 | 317.413 | 326.777 | 9.364 | 2.866 | 623.804 |
| 10 | 46.816 | 23.171 | 26.025 | 22.107 | 30.351 | 315.665 | 329.016 | 13.350 | 4.058 | 621.715 |
| 11 | 48.200 | 23.442 | 27.336 | 23.742 | 29.887 | 316.277 | 328.215 | 11.938 | 3.637 | 614.239 |
| 12 | 49.648 | 24.567 | 27.358 | 20.536 | 27.688 | 303.424 | 321.198 | 17.774 | 5.534 | 602.782 |

## Before/after realized household investment, seed 0

| quarter | investment_CF | investment | consumption |
| --- | --- | --- | --- |
| 1 | 55.551 | 50.916 | 378.859 |
| 2 | 56.790 | 46.199 | 367.858 |
| 3 | 53.468 | 43.542 | 359.428 |
| 4 | 49.970 | 40.840 | 352.887 |
| 5 | 50.560 | 39.350 | 350.236 |
| 6 | 49.033 | 37.493 | 349.064 |
| 7 | 50.134 | 36.143 | 350.039 |
| 8 | 49.606 | 34.684 | 348.319 |
| 9 | 52.327 | 32.616 | 336.364 |
| 10 | 49.282 | 31.830 | 332.282 |
| 11 | 51.182 | 30.842 | 334.617 |
| 12 | 50.701 | 30.723 | 341.167 |

## Household/firm losses and bank support

These retain both old default rules and the old firm-debt boundary; they are not F/E results.

| seed | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | resolution_events | min_capital_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 233.726 | 174.634 | 178.061 | 586.421 | 475.519 | 22 | 2.638 |
| 1 | 234.792 | 137.634 | 194.643 | 567.069 | 370.190 | 20 | 3.063 |
| 2 | 234.014 | 179.531 | 172.345 | 585.890 | 399.164 | 19 | 2.392 |

### Quarterly losses and recapitalisations

| seed | quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 73.692 | 0.000 | 0.000 | 73.692 | 0.000 |
| 0 | 2 | 60.095 | 0.442 | 0.050 | 60.587 | 8.090 |
| 0 | 3 | 24.679 | 38.167 | 16.787 | 79.633 | 4.688 |
| 0 | 4 | 36.060 | 15.943 | 9.906 | 61.909 | 109.929 |
| 0 | 5 | 12.986 | 11.723 | 8.585 | 33.295 | 66.118 |
| 0 | 6 | 7.556 | 10.929 | 7.389 | 25.874 | 53.748 |
| 0 | 7 | 4.691 | 5.172 | 25.698 | 35.561 | 8.849 |
| 0 | 8 | 6.010 | 32.905 | 14.670 | 53.585 | 0.693 |
| 0 | 9 | 1.819 | 12.865 | 33.305 | 47.989 | 28.528 |
| 0 | 10 | 2.024 | 43.332 | 23.467 | 68.824 | 177.734 |
| 0 | 11 | 1.398 | 0.625 | 23.067 | 25.090 | 6.813 |
| 0 | 12 | 2.714 | 2.533 | 15.136 | 20.383 | 10.329 |
| 1 | 1 | 89.778 | 0.278 | 0.003 | 90.060 | 1.233 |
| 1 | 2 | 56.254 | 4.682 | 0.586 | 61.522 | 0.000 |
| 1 | 3 | 34.261 | 33.092 | 14.797 | 82.150 | 11.283 |
| 1 | 4 | 22.541 | 9.569 | 9.325 | 41.435 | 39.166 |
| 1 | 5 | 9.835 | 10.627 | 6.393 | 26.855 | 68.360 |
| 1 | 6 | 4.085 | 31.449 | 17.534 | 53.068 | 111.276 |
| 1 | 7 | 5.032 | 8.952 | 9.742 | 23.725 | 32.859 |
| 1 | 8 | 3.690 | 6.994 | 11.027 | 21.711 | 15.194 |
| 1 | 9 | 3.925 | 5.360 | 24.025 | 33.311 | 0.441 |
| 1 | 10 | 1.528 | 14.575 | 38.729 | 54.832 | 52.854 |
| 1 | 11 | 1.885 | 9.224 | 25.214 | 36.324 | 10.548 |
| 1 | 12 | 1.978 | 2.830 | 37.267 | 42.075 | 26.976 |
| 2 | 1 | 76.431 | 0.278 | 0.003 | 76.712 | 0.000 |
| 2 | 2 | 62.114 | 32.125 | 1.449 | 95.687 | 0.000 |
| 2 | 3 | 31.586 | 35.227 | 10.946 | 77.759 | 10.371 |
| 2 | 4 | 20.168 | 28.205 | 15.073 | 63.446 | 197.682 |
| 2 | 5 | 11.481 | 25.928 | 13.418 | 50.827 | 41.763 |
| 2 | 6 | 13.204 | 6.889 | 8.690 | 28.783 | 42.191 |
| 2 | 7 | 6.940 | 3.823 | 7.556 | 18.320 | 7.956 |
| 2 | 8 | 3.319 | 18.654 | 23.179 | 45.151 | 0.603 |
| 2 | 9 | 1.953 | 1.960 | 4.587 | 8.500 | 0.000 |
| 2 | 10 | 1.565 | 0.638 | 13.152 | 15.355 | 15.173 |
| 2 | 11 | 3.092 | 2.818 | 34.708 | 40.618 | 82.645 |
| 2 | 12 | 2.162 | 22.986 | 39.583 | 64.731 | 0.779 |

Full by-industry firm failures, by-bank capital ratios, resolution events
and new-loan vintages remain in their named CSV panels. Minimum ratios above
are model end-quarter equity/loans, not CET1/RWA. Support is not netted from losses.

### Firm debt before/after

| Item | Before | After |
|---|---:|---|
| Initial firm loan debt | 2,271.807B (accepted model audit) | Unchanged |
| Intercompany consolidation / external bank-credit boundary / O/P/Q | Legacy | F not entered; unchanged |
| Industry allocation and default trigger | Legacy | Unchanged |
| io2022_household_agreed_bankcap_firmdebt.pkl | Not built by this task | Not built |

F industry before/after tables and E foreclosure/recovery tables would imply
an implementation that did not occur. No provisional/final N or haircut is
chosen; E and D3 are not enabled.

## Deferred dwellings proposal (1d), not implemented

Separate the capital budget into new residential construction, renovations,
ownership-transfer costs and unincorporated-business capital using asset-use
data. Exclude personal consumer durables and non-produced land. Builders'
production/input costs, work in progress and completed units must reconcile
to purchaser finance before adding properties to the housing market.
Renovations should improve existing structures without automatically creating
units; transfer fees require separate capitalization and depreciation.
Allocate each completed dwelling to an owner/property ID, distinguish structure
from land, and link new mortgages, cash payments, occupancy and later rents.
Existing-house trades remain transfers, not newly produced dwellings.
Redirect each residential capital flow out of the generic other-real-assets
addition when recognized as a dwelling, so a purchase does not create both stocks. Replace
the generic stock/depreciation treatment only with independently sourced
residential/business capital stocks and service lives. Do not add a housing
producer without its costs or duplicate the existing F-sector output.

## Recommendation

Gate 1 fails on realized capital purchases despite a correct initial target.
Consumption priority reduces investment whenever household resources bind;
rescaling propensities to undo that cut would fit the gate and is not done.
The next unresolved investment issue is the allocation and funding of capital
projects, including their dwelling/business destination, rather than a proven
5%-of-wealth investment error. Firm feedback remains uncorrected because F is
gated. Review planned investment, affordability and the realized-investment
gate separately before changing the instruction sequence.

Household/firm losses and recapitalisations remain economically unvalidated;
legacy firm/default problems prevent a plausibility claim. The buffer-stock
rule stays deferred: these results do not establish that it is necessary or
sufficient, and it would not by itself identify/fund household capital projects.
The model is **not ready for Phase B**. Stop for review before F/E.

## Provenance and verification

Investment benchmark selection, exact vector/date/values, full upstream CSV/ZIP
hashes, local extract hashes and concept-source snapshot are in
benchmarks/IFE/provenance.json. Official sources:
[36-10-0112](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201),
[capital concepts](https://www150.statcan.gc.ca/n1/pub/13-017-x/2008001/themes/ch09/5213371-eng.htm),
[residential components](https://www150.statcan.gc.ca/n1/pub/13-017-x/2008001/themes/ch09/5213372-eng.htm).
The cached source retrieval date is 2026-10-23. The same table's v62305982
(1,511.382B annual C) and v62305981 (1,502.340B annual cash-comparison DI)
retain their accepted provenance for −0.601861% saving excluding D.8.
Prior RBC/TransUnion/OSB orders-of-magnitude sources remain under benchmarks/ABCD/;
no source level is fitted and F/E comparisons are not claimed.

Manifests retain head, exact input/source hashes, quarter count and seed.
The read-only baseline is frozen at de244bc; corrected pairs at b75d4a7.
Its numerical paths reproduce the accepted AFE seed-0 baseline, and the direct
ledger confirms the implied investment. Every short run reproduces its long
run's first two quarters. Household-level flows and aggregates reconcile;
OFA/pension bounds, D2 funding and accounting identities are checked. All
accepted input hashes are preserved. Historical source hashes are checked
against their git version, allowing Windows/Unix newline representations.

### Full suite

**421 passed; 30 known NaN failures, zero additional failures/errors.** run_pre_D3_tests.py; sampler n_cores=1. Failure identities are checked against AFE. JUnit, logs and audit are in outputs/IFE/.

Original macroabm-ca, ITC/user-cost files and accepted pickles unchanged. No new pickle built. Nothing pushed. Stop for review.
