# Closure A/F/E — financial-asset budget gate, 23 October 2026

**Step 1 is implemented and measured. Both parts of its gate fail on every seed.
Steps 2 (F) and 3 (E) therefore did not start, as instructed.** D3 is off in
all runs; the old household and firm rules remain. Phase B and C_dp_005 remain
on hold. Work starts from 3248706 on feature/validation-2022; no push.

## Steps, commits and decision

| Step | Commit / tests | Gate and result |
|---|---|---|
| 1: cash, then non-pension OFA, then proportional cuts | 393bff8; 16 focused checks pass across asset, budget, income and gate tests | Accounting passes; economic gate fails on seeds 0–2 |
| Diagnostic household grouping correction | f140ae2; 9 focused checks pass including new regional-total reconciliation regression | All six final runs repeated from this source; superseded evidence excluded |
| 2: firm debt boundary and payment default (F) | Not started; no F tests or new firm-debt pickle | Blocked by step 1 gate; no change to firm instruments, allocation or default |
| 3: household payment default and foreclosure (E) | Not started; no E tests | Same gate; no new N, haircut or recovery parameter chosen |

## What changed and how it books

The financial_asset_drawdown switch is off by default and on only in iv-ACD′A.
Accepted D timing, C calibration, D2, H7/D4, bank capital/resolution and narrow
D1 remain. Unused credit capacity is zero; no propensity, benchmark, credit
headroom or multiplier changes.

The budget uses opening deposits plus declared current receipts, committed
loans and executed sale proceeds, less rent, interest, principal and executed
house purchases. It then includes existing non-pension OFA before applying the
common consumption/investment cut. At settlement it uses cash first and
liquidates only the remaining shortfall from actual spending and senior
payments; unfilled purchases cause no liquidation. Optional new OFA saving
cannot divert senior-payment cash. Excess senior shortfalls remain payment
distress, not a new default trigger.

The protected pension component is input Voluntary Pension multiplied by
population scale, matching OFA units. It stays protected; there is no separate
pension revaluation path. Remaining non-pension OFA includes later saving.
initial_financial_assets.csv checks original component sums/units in every
region. No input record or pickle changes.

Liquidation uses the existing OFA usage/deposit calculation: OFA falls by L,
and deposit resources rise by L. It is not income or new credit. The reserve
boundary **OFA without issuer** remains −ΔOFA: gross liquidation less new OFA
accumulation. Net boundary and gross liquidation are both reported; no issuer
is invented. Cash, loan, equity, reserve and recapitalisation identities stay
active.

## Gate and seed comparison

Before runs, “must not trend upward over Q4–Q12” was defined as an OLS slope
of population-constrained share ≤0 across those nine quarters. Q4/Q12 endpoints
are also reported. Q12 cash saving must be within ±5 percentage points of the
unchanged −0.602% benchmark. Both conditions must pass on every seed. step_A_gates.json is authoritative
for this gate. The inherited run-manifest field household_gate_passed refers
only to the earlier Q1 consumption check, which passes; it does not indicate
that the present Q4?Q12/saving gate passed. The summary renames that legacy
field to avoid confusing the two.

Amounts in all tables are CAD billions; flows quarterly unless marked 12Q.
Shares/rates are percentages, slopes percentage points/quarter. Cuts are
planned VAT-inclusive consumption cuts before goods-market rationing.

| seed | constrained_Q4 | constrained_Q12 | constrained_slope_per_quarter | Q12_saving_rate | saving_gap_pp | trend_pass | saving_pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 33.358 | 50.008 | 2.084 | 9.741 | 10.343 | False | False |
| 1 | 33.812 | 50.442 | 2.069 | 9.787 | 10.389 | False | False |
| 2 | 33.180 | 50.249 | 2.094 | 9.956 | 10.558 | False | False |

## Quarterly household budget, liquidation and macro outcomes

### Seed 0

| quarter | constrained_share | consumption_cut | asset_liquidation | ofa_without_issuer | consumption | cash_DI | cash_saving | cash_saving_rate | gdp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 18.794 | 12.427 | 10.849 | 9.717 | 372.659 | 371.908 | -0.751 | -0.202 | 700.946 |
| 2 | 24.880 | 21.436 | 20.658 | 20.193 | 360.040 | 366.506 | 6.466 | 1.764 | 694.975 |
| 3 | 29.674 | 27.371 | 22.944 | 21.204 | 346.833 | 360.765 | 13.932 | 3.862 | 690.535 |
| 4 | 33.358 | 31.152 | 23.989 | 22.545 | 342.574 | 358.151 | 15.577 | 4.349 | 679.175 |
| 5 | 36.195 | 32.698 | 24.847 | 24.326 | 336.046 | 353.604 | 17.558 | 4.965 | 662.609 |
| 6 | 38.735 | 33.760 | 23.559 | 21.940 | 321.339 | 345.225 | 23.886 | 6.919 | 656.690 |
| 7 | 41.062 | 37.049 | 24.292 | 23.631 | 318.593 | 344.199 | 25.606 | 7.439 | 645.608 |
| 8 | 43.040 | 40.161 | 23.523 | 22.621 | 313.594 | 342.175 | 28.581 | 8.353 | 648.999 |
| 9 | 45.263 | 42.599 | 25.573 | 25.347 | 319.044 | 345.774 | 26.730 | 7.731 | 648.040 |
| 10 | 47.130 | 44.476 | 22.565 | 21.003 | 319.517 | 351.104 | 31.587 | 8.996 | 644.648 |
| 11 | 48.688 | 46.445 | 23.251 | 22.223 | 312.598 | 347.099 | 34.501 | 9.940 | 650.703 |
| 12 | 50.008 | 49.128 | 23.373 | 22.590 | 312.260 | 345.960 | 33.700 | 9.741 | 657.299 |

### Seed 1

| quarter | constrained_share | consumption_cut | asset_liquidation | ofa_without_issuer | consumption | cash_DI | cash_saving | cash_saving_rate | gdp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 18.956 | 12.724 | 11.655 | 11.054 | 376.037 | 371.141 | -4.895 | -1.319 | 715.919 |
| 2 | 25.412 | 22.406 | 20.816 | 20.475 | 363.349 | 370.539 | 7.190 | 1.940 | 710.975 |
| 3 | 30.155 | 28.227 | 22.759 | 21.813 | 350.933 | 366.183 | 15.250 | 4.165 | 702.640 |
| 4 | 33.812 | 32.420 | 25.112 | 24.142 | 346.932 | 365.758 | 18.827 | 5.147 | 691.325 |
| 5 | 36.720 | 34.536 | 24.699 | 23.675 | 337.942 | 362.187 | 24.245 | 6.694 | 694.287 |
| 6 | 39.345 | 35.622 | 23.625 | 22.354 | 335.341 | 362.250 | 26.909 | 7.428 | 687.688 |
| 7 | 41.787 | 40.501 | 26.605 | 26.135 | 334.896 | 360.626 | 25.730 | 7.135 | 688.332 |
| 8 | 43.816 | 44.798 | 26.057 | 25.024 | 330.377 | 359.474 | 29.097 | 8.094 | 686.979 |
| 9 | 45.904 | 44.321 | 24.024 | 20.770 | 319.772 | 355.227 | 35.455 | 9.981 | 676.938 |
| 10 | 47.611 | 43.406 | 22.271 | 21.824 | 316.316 | 351.354 | 35.038 | 9.972 | 674.716 |
| 11 | 49.046 | 44.695 | 26.388 | 25.156 | 317.436 | 347.144 | 29.708 | 8.558 | 671.723 |
| 12 | 50.442 | 48.323 | 23.574 | 23.221 | 308.285 | 341.731 | 33.445 | 9.787 | 667.060 |

### Seed 2

| quarter | constrained_share | consumption_cut | asset_liquidation | ofa_without_issuer | consumption | cash_DI | cash_saving | cash_saving_rate | gdp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 18.698 | 12.276 | 11.859 | 11.345 | 372.904 | 370.753 | -2.152 | -0.580 | 698.339 |
| 2 | 25.030 | 22.006 | 19.508 | 18.319 | 353.135 | 363.187 | 10.052 | 2.768 | 687.976 |
| 3 | 29.670 | 26.930 | 22.845 | 21.470 | 341.457 | 355.741 | 14.284 | 4.015 | 673.375 |
| 4 | 33.180 | 29.474 | 25.399 | 25.181 | 336.440 | 352.071 | 15.631 | 4.440 | 673.579 |
| 5 | 36.398 | 35.991 | 24.951 | 23.519 | 330.096 | 351.508 | 21.412 | 6.091 | 672.540 |
| 6 | 39.074 | 36.748 | 25.813 | 25.428 | 328.881 | 351.376 | 22.495 | 6.402 | 676.248 |
| 7 | 41.562 | 42.433 | 23.501 | 20.717 | 321.351 | 354.190 | 32.840 | 9.272 | 674.916 |
| 8 | 43.397 | 42.255 | 23.249 | 22.609 | 318.582 | 350.770 | 32.188 | 9.176 | 662.688 |
| 9 | 45.497 | 42.385 | 22.990 | 21.658 | 311.534 | 345.841 | 34.307 | 9.920 | 664.330 |
| 10 | 47.236 | 42.419 | 26.670 | 25.628 | 317.414 | 347.127 | 29.713 | 8.560 | 645.754 |
| 11 | 48.775 | 46.576 | 22.296 | 20.037 | 304.295 | 339.643 | 35.349 | 10.408 | 641.728 |
| 12 | 50.249 | 45.322 | 23.650 | 22.282 | 304.466 | 338.130 | 33.664 | 9.956 | 621.244 |

## Accepted D timing/D1 base comparison

All other flags/input match. This is a dynamic comparison, not a fixed-income causal decomposition. Q12 GDP rises against the accepted base in seeds 0 and 2, but falls in seed 1; no seed-independent GDP stabilisation is claimed. Consumption still falls 16.2?18.4% from Q1 to Q12 in the new runs.

| seed | quarter | version | constrained_share | consumption | cash_saving_rate | gdp |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | + asset drawdown | 18.794 | 372.659 | -0.202 | 700.946 |
| 0 | 1 | accepted base | 29.003 | 365.233 | 1.795 | 701.118 |
| 0 | 12 | + asset drawdown | 50.008 | 312.260 | 9.741 | 657.299 |
| 0 | 12 | accepted base | 58.492 | 287.489 | 13.138 | 607.142 |
| 1 | 1 | + asset drawdown | 18.956 | 376.037 | -1.319 | 715.919 |
| 1 | 1 | accepted base | 29.250 | 365.753 | 1.452 | 715.529 |
| 1 | 12 | + asset drawdown | 50.442 | 308.285 | 9.787 | 667.060 |
| 1 | 12 | accepted base | 59.131 | 339.556 | 12.708 | 715.707 |
| 2 | 1 | + asset drawdown | 18.698 | 372.904 | -0.580 | 698.339 |
| 2 | 1 | accepted base | 28.881 | 363.364 | 1.993 | 697.757 |
| 2 | 12 | + asset drawdown | 50.249 | 304.466 | 9.956 | 621.244 |
| 2 | 12 | accepted base | 58.372 | 269.554 | 15.128 | 579.550 |

## Who drives saving and rising constraints

Deciles are fixed t0 national income ranks, population weighted. Asset bins
are t0 non-pension OFA per represented household, kept fixed as assets run down.
Positive saving and dissaving are summed separately. Assets are captured before
the old insolvency handler. Full Q1–Q12 panels by decile, assets, and both are
in saving_by_decile.csv, saving_by_assets.csv and saving_by_decile_assets.csv.

Across seeds, the 45.24% of households starting with zero or at most 10,000
CAD of non-pension OFA account for 73.99?74.36% of Q12 constraints and
59.94?64.98% of net cash saving. Households starting above 100,000 CAD hold
97.51?97.59% of remaining non-pension assets at Q12; only 3.09?3.29% are
constrained. This is not an aggregate shortage of OFA.

Income deciles 6?10 contribute 80.31?83.67% of Q12 net saving. Their low-asset
subgroup is 18.11% of all households but contributes 43.79?45.02% of saving.
The bottom two deciles together dissave 0.58?1.75B in Q12. The income/asset
cross-panel therefore matters: higher income does not imply a liquid buffer.

### Income deciles at Q12, all seeds

| seed | decile | households | constrained_share | cash_DI | consumption | cash_saving | positive_saving | dissaving | opening_assets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 1549000 | 68.108 | 9.703 | 9.949 | -0.245 | 1.037 | 1.283 | 18.138 |
| 0 | 2 | 1550190 | 43.456 | 13.530 | 13.865 | -0.336 | 1.527 | 1.863 | 98.438 |
| 0 | 3 | 1549700 | 40.401 | 20.290 | 19.336 | 0.954 | 2.262 | 1.307 | 181.779 |
| 0 | 4 | 1549280 | 49.983 | 26.635 | 23.966 | 2.669 | 3.358 | 0.689 | 263.386 |
| 0 | 5 | 1549740 | 53.932 | 31.807 | 28.215 | 3.593 | 4.006 | 0.413 | 278.433 |
| 0 | 6 | 1549880 | 55.213 | 37.878 | 33.442 | 4.436 | 4.931 | 0.495 | 285.714 |
| 0 | 7 | 1549340 | 54.333 | 41.236 | 36.341 | 4.895 | 5.456 | 0.561 | 368.530 |
| 0 | 8 | 1550180 | 50.628 | 46.225 | 40.765 | 5.460 | 6.136 | 0.677 | 498.196 |
| 0 | 9 | 1549460 | 47.244 | 52.190 | 46.442 | 5.748 | 6.666 | 0.919 | 650.214 |
| 0 | 10 | 1550550 | 36.795 | 66.466 | 59.939 | 6.527 | 8.161 | 1.634 | 1319.349 |
| 1 | 1 | 1549000 | 68.689 | 9.408 | 10.312 | -0.904 | 0.943 | 1.847 | 17.992 |
| 1 | 2 | 1550190 | 43.649 | 13.059 | 13.430 | -0.371 | 1.499 | 1.870 | 98.131 |
| 1 | 3 | 1549700 | 40.853 | 19.827 | 18.898 | 0.929 | 2.261 | 1.332 | 181.591 |
| 1 | 4 | 1549280 | 49.985 | 26.210 | 23.623 | 2.587 | 3.327 | 0.740 | 262.802 |
| 1 | 5 | 1549740 | 54.387 | 31.445 | 27.915 | 3.530 | 3.982 | 0.452 | 277.849 |
| 1 | 6 | 1549880 | 55.600 | 37.256 | 32.762 | 4.494 | 5.021 | 0.527 | 285.069 |
| 1 | 7 | 1549340 | 54.464 | 40.520 | 35.663 | 4.858 | 5.463 | 0.605 | 367.725 |
| 1 | 8 | 1550180 | 51.340 | 45.294 | 39.810 | 5.485 | 6.165 | 0.680 | 497.073 |
| 1 | 9 | 1549460 | 47.892 | 51.686 | 45.796 | 5.890 | 6.799 | 0.908 | 648.609 |
| 1 | 10 | 1550550 | 37.574 | 67.025 | 60.078 | 6.947 | 8.539 | 1.591 | 1317.661 |
| 2 | 1 | 1549000 | 69.141 | 9.474 | 10.805 | -1.331 | 0.849 | 2.180 | 18.077 |
| 2 | 2 | 1550190 | 43.972 | 13.316 | 13.731 | -0.415 | 1.469 | 1.884 | 98.235 |
| 2 | 3 | 1549700 | 40.530 | 20.074 | 19.029 | 1.044 | 2.253 | 1.209 | 181.835 |
| 2 | 4 | 1549280 | 49.729 | 26.236 | 23.659 | 2.577 | 3.278 | 0.701 | 263.229 |
| 2 | 5 | 1549740 | 54.256 | 30.919 | 27.297 | 3.622 | 4.029 | 0.407 | 278.395 |
| 2 | 6 | 1549880 | 55.149 | 36.913 | 32.394 | 4.520 | 4.998 | 0.478 | 285.746 |
| 2 | 7 | 1549340 | 54.659 | 40.102 | 35.075 | 5.026 | 5.527 | 0.501 | 368.781 |
| 2 | 8 | 1550180 | 51.017 | 44.831 | 39.126 | 5.705 | 6.278 | 0.573 | 497.977 |
| 2 | 9 | 1549460 | 47.118 | 51.356 | 45.354 | 6.002 | 6.734 | 0.732 | 650.013 |
| 2 | 10 | 1550550 | 36.931 | 64.910 | 57.997 | 6.913 | 8.276 | 1.363 | 1318.727 |

### Initial non-pension assets at Q12, all seeds

| seed | asset_bin | households | constrained_share | cash_saving | positive_saving | dissaving | opening_assets | liquidation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0-10k | 1882380 | 83.004 | 7.299 | 7.652 | 0.353 | 2.488 | 0.316 |
| 0 | 10-100k | 3917340 | 47.129 | 10.103 | 12.357 | 2.255 | 94.021 | 5.287 |
| 0 | 100k+ | 4568410 | 3.089 | 1.699 | 7.506 | 5.807 | 3864.061 | 17.363 |
| 0 | zero | 5129190 | 81.886 | 14.599 | 16.025 | 1.426 | 1.608 | 0.406 |
| 1 | 0-10k | 1882380 | 83.590 | 7.213 | 7.617 | 0.404 | 2.287 | 0.318 |
| 1 | 10-100k | 3917340 | 48.078 | 10.321 | 12.689 | 2.368 | 91.955 | 5.184 |
| 1 | 100k+ | 4568410 | 3.286 | 1.941 | 7.935 | 5.994 | 3859.042 | 17.652 |
| 1 | zero | 5129190 | 82.082 | 13.971 | 15.758 | 1.787 | 1.217 | 0.420 |
| 2 | 0-10k | 1882380 | 83.271 | 6.996 | 7.429 | 0.433 | 2.705 | 0.528 |
| 2 | 10-100k | 3917340 | 47.619 | 10.318 | 12.568 | 2.250 | 93.842 | 5.257 |
| 2 | 100k+ | 4568410 | 3.177 | 3.169 | 8.379 | 5.210 | 3862.281 | 16.820 |
| 2 | zero | 5129190 | 82.063 | 13.180 | 15.317 | 2.137 | 2.186 | 1.045 |

### Q4–Q12 change in constraints and saving

| seed | group | bin | extra_constrained | saving_change |
| --- | --- | --- | --- | --- |
| 0 | asset | 0-10k | 364790 | 1.965 |
| 0 | asset | 10-100k | 1249680 | 9.546 |
| 0 | asset | 100k+ | 134120 | 2.381 |
| 0 | asset | zero | 831690 | 4.231 |
| 0 | income | 1 | 279000 | 1.160 |
| 0 | income | 2 | 221550 | 0.582 |
| 0 | income | 3 | 197630 | 0.622 |
| 0 | income | 4 | 226790 | 0.972 |
| 0 | income | 5 | 258310 | 1.483 |
| 0 | income | 6 | 240300 | 1.591 |
| 0 | income | 7 | 281260 | 2.134 |
| 0 | income | 8 | 293300 | 2.551 |
| 0 | income | 9 | 297390 | 3.126 |
| 0 | income | 10 | 284750 | 3.901 |
| 1 | asset | 0-10k | 356770 | 1.359 |
| 1 | asset | 10-100k | 1269770 | 8.926 |
| 1 | asset | 100k+ | 143120 | 1.762 |
| 1 | asset | zero | 807510 | 2.573 |
| 1 | income | 1 | 288000 | 0.397 |
| 1 | income | 2 | 221510 | 0.465 |
| 1 | income | 3 | 198640 | 0.393 |
| 1 | income | 4 | 217770 | 0.614 |
| 1 | income | 5 | 258330 | 1.084 |
| 1 | income | 6 | 239260 | 1.239 |
| 1 | income | 7 | 271260 | 1.717 |
| 1 | income | 8 | 297290 | 2.103 |
| 1 | income | 9 | 299360 | 2.810 |
| 1 | income | 10 | 285750 | 3.797 |
| 2 | asset | 0-10k | 375750 | 1.804 |
| 2 | asset | 10-100k | 1279760 | 9.379 |
| 2 | asset | 100k+ | 135120 | 3.277 |
| 2 | asset | zero | 854530 | 3.572 |
| 2 | income | 1 | 299000 | 0.505 |
| 2 | income | 2 | 233510 | 0.576 |
| 2 | income | 3 | 197630 | 0.738 |
| 2 | income | 4 | 225770 | 0.918 |
| 2 | income | 5 | 271300 | 1.499 |
| 2 | income | 6 | 240290 | 1.609 |
| 2 | income | 7 | 286270 | 2.130 |
| 2 | income | 8 | 306280 | 2.729 |
| 2 | income | 9 | 297370 | 3.210 |
| 2 | income | 10 | 287740 | 4.119 |

### Cash saving versus financial-asset accumulation

Cash saving is cash DI minus consumption (VAT and paid rent included). It does
not subtract principal or household capital purchases. A constrained borrower
can therefore record positive cash saving while repaying principal, buying
capital goods and losing financial assets. The exact battery bridge is:

S_cash = Δdeposits + ΔOFA + principal − new loans + net house purchases
         + household investment including CF tax.

“Implied investment including CF tax” is the residual from this identity,
not an independently observed estimate. House sales cancel nationally to
floating-point precision. This bridge changes neither definition nor gate.
It cannot identify principal/investment by decile; a household-level ledger
would resolve that attribution.

| seed | cash_saving | deposit_change | net_OFA_accumulation | principal_repayment | new_loans | house_sales_net | investment_including_CF_tax_implied |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 33.700 | -20.307 | -22.590 | 26.657 | 0.760 | 0.000 | 50.701 |
| 1 | 33.445 | -19.453 | -23.221 | 26.788 | 1.401 | 0.000 | 50.733 |
| 2 | 33.664 | -18.434 | -22.282 | 26.765 | 2.836 | 0.000 | 50.451 |

## Household/firm losses and bank support

Combined firm principal/overdraft losses are about 58?67% of total bank losses across seeds. These retain legacy default rules and the legacy firm-debt boundary. They
are not F/E validation results. Principal losses, firm overdraft losses and
recapitalisations are separate flows.

### Twelve-quarter totals

| seed | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | resolution_events | min_capital_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 222.967 | 217.951 | 162.487 | 603.406 | 457.666 | 20 | 2.478 |
| 1 | 221.335 | 264.851 | 178.654 | 664.840 | 494.298 | 19 | 3.002 |
| 2 | 219.207 | 153.576 | 152.635 | 525.418 | 376.512 | 19 | 2.866 |

### Quarterly losses/support, all seeds

| seed | quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | min_capital_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 78.755 | 0.000 | 0.000 | 78.755 | 0.970 | 3.678 |
| 0 | 2 | 56.265 | 0.442 | 0.051 | 56.757 | 0.000 | 3.043 |
| 0 | 3 | 36.900 | 38.167 | 17.107 | 92.174 | 7.837 | 3.764 |
| 0 | 4 | 17.286 | 35.940 | 10.547 | 63.773 | 178.047 | 3.940 |
| 0 | 5 | 10.401 | 18.131 | 10.616 | 39.147 | 39.179 | 3.849 |
| 0 | 6 | 7.607 | 15.575 | 9.460 | 32.642 | 5.189 | 3.364 |
| 0 | 7 | 8.558 | 11.993 | 27.609 | 48.160 | 0.684 | 2.967 |
| 0 | 8 | 2.367 | 49.902 | 17.981 | 70.250 | 79.468 | 2.478 |
| 0 | 9 | 1.341 | 2.491 | 5.866 | 9.698 | 15.320 | 4.245 |
| 0 | 10 | 1.982 | 21.413 | 26.885 | 50.279 | 32.169 | 3.773 |
| 0 | 11 | 0.989 | 1.619 | 16.782 | 19.391 | 7.524 | 3.638 |
| 0 | 12 | 0.517 | 22.278 | 19.585 | 42.380 | 91.281 | 4.240 |
| 1 | 1 | 94.819 | 0.278 | 0.003 | 95.100 | 1.233 | 3.921 |
| 1 | 2 | 51.966 | 4.682 | 0.581 | 57.229 | 0.000 | 3.756 |
| 1 | 3 | 21.001 | 33.092 | 15.146 | 69.240 | 7.447 | 4.016 |
| 1 | 4 | 23.847 | 45.843 | 14.893 | 84.583 | 131.398 | 3.002 |
| 1 | 5 | 7.623 | 3.195 | 4.389 | 15.208 | 102.866 | 3.954 |
| 1 | 6 | 7.185 | 98.467 | 10.332 | 115.984 | 0.000 | 3.660 |
| 1 | 7 | 6.701 | 27.578 | 18.643 | 52.921 | 33.100 | 3.544 |
| 1 | 8 | 3.348 | 4.006 | 26.195 | 33.549 | 119.054 | 4.492 |
| 1 | 9 | 1.904 | 8.708 | 25.697 | 36.308 | 35.761 | 4.048 |
| 1 | 10 | 1.324 | 2.804 | 8.274 | 12.402 | 0.000 | 3.301 |
| 1 | 11 | 0.781 | 5.899 | 14.055 | 20.735 | 0.789 | 3.873 |
| 1 | 12 | 0.837 | 30.297 | 40.447 | 71.581 | 62.649 | 3.582 |
| 2 | 1 | 76.545 | 0.278 | 0.003 | 76.826 | 0.000 | 3.678 |
| 2 | 2 | 57.728 | 32.125 | 1.448 | 91.301 | 1.374 | 3.256 |
| 2 | 3 | 35.189 | 35.227 | 11.044 | 81.460 | 115.477 | 4.040 |
| 2 | 4 | 21.451 | 27.740 | 15.116 | 64.307 | 57.373 | 3.890 |
| 2 | 5 | 12.739 | 6.721 | 9.625 | 29.086 | 1.420 | 3.324 |
| 2 | 6 | 7.376 | 20.982 | 7.078 | 35.437 | 40.095 | 3.139 |
| 2 | 7 | 3.255 | 1.727 | 2.473 | 7.455 | 0.251 | 3.101 |
| 2 | 8 | 2.078 | 10.776 | 14.206 | 27.060 | 53.555 | 2.866 |
| 2 | 9 | 0.961 | 2.141 | 33.717 | 36.818 | 0.259 | 2.893 |
| 2 | 10 | 0.892 | 7.421 | 13.663 | 21.976 | 62.339 | 4.725 |
| 2 | 11 | 0.561 | 0.058 | 2.283 | 2.902 | 7.254 | 5.941 |
| 2 | 12 | 0.433 | 8.379 | 41.978 | 50.790 | 37.116 | 5.565 |

Resolution_log.csv and banks_by_quarter.csv retain events and before/after
rescue capital. Minimum ratios above are end-quarter equity/loans, not
CET1/RWA. Firm loss allocation is in firm_insolvencies_by_industry.csv;
origination overdrafts and principal losses are in new_lending_vintages.csv.

### Firm debt before/after

| Item | Before | After this step |
|---|---:|---|
| Initial firm loan debt | 2,271.807B, accepted model audit | Unchanged |
| External-loan/mortgage boundary, intercompany consolidation, bonds and O/P/Q | Legacy boundary | F not implemented: gate fails |
| Industry allocation/default | Legacy | Unchanged |
| io2022_household_agreed_bankcap_firmdebt.pkl | Not built by this task | Not built |

An F industry before/after table or F loss comparison would imply work that
did not occur. F/E remain pending behind the gate; neither is validated here.

## Diagnosis and options for review

Asset drawdown improves consumption/constraint levels but does not stabilise
the trajectory. Wealth is concentrated: unused assets elsewhere cannot fund
another household without a transfer or credit, neither authorized here.
Low-asset groups can be constrained and still contribute positive cash saving
because principal/capital purchases use resources outside consumption. The
initial uniform income-weighted propensity remains unchanged. Liquidity
permission alone does not create a buffer-stock consumption rule. Goods
rationing and legacy firm failures also remain in the dynamic feedback;
these runs do not separately identify their causal effects.

Options, **not implemented**:

1. Audit desired/filled consumption, investment and principal at household
   level. Consider consumption priority over discretionary capital purchases,
   rather than scaling both together. That changes the proportional rule and
   needs review; do not choose it merely to force the gate to pass.
2. Specify heterogeneous spending/saving with independently sourced income
   and liquid-wealth evidence and an explicit asset-buffer objective. Source
   parameters and sensitivities; no quarterly national consumption rescaling.
3. Review contractual burdens and E workouts alongside that ledger. Principal
   is not consumption; liquidity distress is not negative net worth. F/E stay
   gated; no silent change to debt service, benchmark or default clock.

Recommendation: retain the asset option as a diagnostic and resolve the
spending/investment/payment ledger before accepting closure. Household/firm
losses and recapitalisations remain too large to claim plausible orders of
magnitude. Phase B is **not ready**. F may explain part of the feedback, but
the user's gate prevents starting it here.

## Provenance and execution

Unchanged saving comparison: StatCan 36-10-0112, 2022 mean of quarterly SAAR;
C v62305982 = 1,511.382B/year; cash-comparison DI v62305981 = 1,502.340B/year;
excluding D.8 gives −0.601861%. This remains an approximate model cash/SNA
comparison, not a complete boundary bridge.
[Source](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201).
Retrieved 2026-10-23; ZIP SHA256
b577daa453e1527602f55000d301624143bdaf3dba87bfbd458f44d6ab797d1e;
CSV SHA256 5cfe7a3c5a9cd3610faa2d7fd19b591b1cfed01750d0c493568f0c1f25cc7d97.
Original provenance: benchmarks/household_corrections/36100112_provenance.json.

No new benchmark/parameter is introduced. Earlier RBC net write-offs,
TransUnion arrears and OSB insolvency figures retain sources, scopes, dates
and hashes in benchmarks/ABCD/ and the accepted ABCD report. One bank's net
losses, national arrears stocks and legal-business counts are not equated
to model gross cancellations or 650 composite producers. Accepted figures
are RBC consolidated retail net write-offs 0.604B/0.881B in 2022/2023;
TransUnion Q4 2024 mortgage 60+ arrears 0.25% of accounts; OSB business BIA
insolvencies 4,810/6,188 in 2023/2024. These are not matching denominators.
[RBC](https://www.rbc.com/investor-relations/_assets-custom/pdf/ar_2023_e.pdf),
[TransUnion](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q4-24-ciir-report.pdf),
[OSB](https://ised-isde.canada.ca/site/office-superintendent-bankruptcy/en/statistics-and-research/insolvency-statistics/annual-reports/annual-2024).
Snapshot provenance and full-source hashes where available remain in
benchmarks/ABCD/order_benchmarks_snapshot.json and provenance.json; the
TransUnion full PDF was unavailable and uses its checked snapshot. The accepted
2,271.807B is the initial model debt audit, not a new bank-holder estimate.

For each seed 0–2 a 2Q accounting run immediately preceded its 12Q measurement,
serially. Final source is f140ae2-compatible; manifests retain exact source
and input hashes/seed. Every budgeted receipt reconciles household by household
to booked income. All accounting errors are below 1e-8. Short runs reproduce
the first two quarters of long runs. Group income, consumption, constraints
and liquidation reconcile to outcomes; liquidation never exceeds available
non-pension OFA. Initial components, protected pickles and opening cash funding
of D2 declarations are independently checked.

The initial 393bff8 2Q/partial 12Q runs were superseded because group consumption
broadcast a regional total. National flows/accounting were unaffected. Those
runs were stopped and retained locally under AFE_superseded_393bff8; all final
runs repeat after f140ae2's individual-series reconciliation and regression.
No superseded number enters this report. See superseded_run_note.json.

Full tests/ through run_pre_D3_tests.py: **416 passed, 30 known NaN failures**, no new failures/errors. Sampler n_cores=1; failed identities checked against DF. Logs, JUnit, execution metadata and final audit are under outputs/AFE/.

No original repository, ITC/user-cost file or accepted pickle modified. No new pickle built. Nothing pushed. Stop for review.
