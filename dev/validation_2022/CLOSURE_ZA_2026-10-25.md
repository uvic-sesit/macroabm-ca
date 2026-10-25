# Closure ZA review — 2026-10-25 UTC

Base `ca33da2`, branch `feature/validation-2022`. **FS_T v4 passes the specified source, cost, all-13-region GDP and accounting gates; seeds 0–2 complete. FSG is not built: source preflight exposes material signed negative fixed-capital uses that the nonnegative purchase allocator cannot represent.** No source entries were clipped, reassigned to inventories, redistributed or fitted. The independent exact housing split is complete and read-only. Stop for review; Phase B, C_dp_005, household noncash-layer changes and investment expansion remain on hold.

Passing these gates does not validate the no-shock dynamics. FS_T's nominal contraction worsens on seed 0 and improves on seeds 1–2; losses and roughly 50% constrained households remain substantial. Recommend FS_T as the corrected diagnostic input subject to review, retaining F_CFC as its historical comparator.

## Steps, commits and checks

| Step | Commit / verification | Result |
| --- | --- | --- |
| 1: source-zero convention / effort guard | `1ffdc06`; three regressions; F_CFC seed 0 before/after2Q replay | Same 1M/year output=VA=domestic-FCF path for all 68 exact source-zero cells; zero-target/zero-capacity effort0; contracts/jobs held at build. |
| 2: predeclared cost specification | `a9fee55`; two regressions | Unchanged1pp margin threshold on source-positive nonfloor cells; separate floor check. Old universal result retained. |
| 3: FS_T v4 | `a9fee55`;13 GDP initializations;2Q plus3×12Q | Pass; maximum long-run battery error 1.1e-14, tolerance1e-8. |
| Floor audit schema | `f599a9d`; one regression | Exclude only intentionally unset Q0 target forecast; all defined states and later forecasts still checked. |
| 4: FSG source preflight | `7f9789c`; three budget/rejection regressions |20 negative net-product uses, −3.502B/year; no executable FSG candidate or dependent runs. |
| 5: exact OOH | `41d4e68`; read-only `za_housing.py`; source/allocation reconciliations | Exact provincial source totals, assumed within-province owner allocation; no closure implementation. |
| 6: report / full suite | `run_za_full_tests.py` | 503 passed, 30 failures, 533 cases; 0 additional failures against the exact SG test IDs. Sampler one worker. |

The nine final focused checks pass. The zero-firm unit regression exercises two successive zero-target/capacity effort/production updates. Full v4 integration separately verifies the previously failing NL C21 path and all source-zero holders through two simulation quarters. F_CFC seed 0 before/after replay compares **4,082 numeric per-firm arrays per run**, dtype, shape and bytes after both quarters: identical, both accounting errors4.07e-15. Aggregate noisy Hill-tail estimators are excluded from this per-firm economic-state claim; the original overbroad estimator-comparison attempt is retained.

In the full short integration, **all 68 source-zero firms have actual production0 and productivity0 in bothQ1 andQ2**, with finite captured state and passing accounting. The forecast target is capacity-clamped inside the effort calculation. `zero_runtime_integration_certificate.json` records this direct runtime check; it is not inferred merely from the1M initialization convention.

## Zero-activity path and cost gates

`_floor_empty_provincial_sectors` uses the existing `CAN_2022_EMPTY_SECTOR_FLOOR=1e6` CAD/year. Exact canonical source-zero classification clears tiny allocation remnants before that same path.29 inherited plus39 newly zero cells give **68M/year output and68M/year GOS**, 0.001345% of national output, below 0.01%. The additional39M/year is also domestic FCF, using the existing sector fractions (firm58.6508%, household26.5476%, government14.8016%) and investor shares. Dummy acquisition flows change; installed capital, CFC, loans/deposits, bank stocks, household records and job/employer contracts are held. No forgiveness, deletion or reassignment.

`gate_specification_before_runs.json` was frozen in1ffdc06 before rebuilding/measuring v4. Source-positive max margin gap **0.771775pp**, zero exceptions above 1pp, zero prohibited above-price cases. Old universal gate: **68 exceptions, max 100pp**, exactly floor cells. Every defined captured floor state is finite in2Q and all 3 long runs. Contracts/jobs are held initially; subsequent endogenous employment/default dynamics remain active.

Cost results, including the unnecessary FS diagnostic (margin deviations in percentage points):

| arm | source_positive_margin_exceptions | source_positive_max_pp | above_price | old_universal_exceptions | old_universal_max_pp |
| --- | --- | --- | --- | --- | --- |
| FS_T | 0 | 0.772 | 0 | 68 | 100.000 |
| FS | 211 | 21.011 | 6 | 279 | 100.000 |

The build-provenance `margin_passed` and `max_margin_gap_pp` fields retain the old universal diagnostic. The separately declared `*_pre_run_gates.json` files are the authoritative source-positive/floor adoption checks; historical universal failures are not overwritten.

The first short simulation completed with accounting error 4.55e-15, then its wrapper failed on Q0 target_production, intentionally initializedNaN for all firms and defined fromQ1. Original raw output and failed wrapper are retained; a separate certificate excludes only this unset forecast. No economic value, tolerance or parameter changed. The first controller unnecessarily ran FS fallback prechecks:13 GDP checks pass, but211 positive-source margin and6 above-price exceptions fail. No FS macro run followed. That controller's `adoption_result.json` is superseded by **`adoption_final_result.json`**, which certifies FS_T.

## Initial FS_T accounts and GDP

New input `dev/pkl_files/io2022_fs_t_za_v4_2026_10_25.pkl`, SHA256 `0ef644b38f2ab6945a4af868406ede0f28b03d6237ddc54519c4cfa8e86cc2a6`.

Extra unadopted FS diagnostic input `io2022_fs_za_v4_2026_10_25.pkl`, SHA256 `9590639c97fa6156f68f6f4480d9953f3a5bfd510ae59efafcb27aec374fca4d`. Accepted pickles unchanged.

GOS is **1336.184→1187.287B/year**, down148.896B:48.431914B re-export correction plus100.503564B signed producer taxes, less0.039B incremental floors. Explicit VA6 is unchanged except floors; reader-implied residual VA falls. Physical inputs and CFC are preserved while coefficients are expressed in corrected output units. Taxes have the government counterpart, exports the ROW import counterpart. No cash, trade or stock plug.

Largest industry changes, annual B:

| industry | output_change | old_GOS | new_GOS | GOS_change | signed_other_tax |
| --- | --- | --- | --- | --- | --- |
| L | 0.000 | 288.982 | 232.106 | -56.876 | 56.876 |
| F | -0.001 | 76.289 | 65.216 | -11.073 | 11.073 |
| C29 | -9.804 | 12.448 | 2.220 | -10.228 | 0.424 |
| K | 0.000 | 73.867 | 64.313 | -9.554 | 9.554 |
| C28 | -7.581 | 14.957 | 7.109 | -7.848 | 0.267 |
| C26 | -5.543 | 8.262 | 2.623 | -5.639 | 0.096 |
| C302T309 | -4.776 | 7.046 | 2.067 | -4.979 | 0.203 |
| G | -0.253 | 101.758 | 97.443 | -4.315 | 4.062 |
| O | -0.000 | 61.275 | 57.305 | -3.970 | 3.970 |
| C20 | -2.507 | 13.513 | 9.947 | -3.566 | 1.059 |

All 13 GDP checks: levels B/quarter, residuals CAD/quarter; unchanged np.isclose tolerance:

| region | passed | output | expenditure | income | expenditure_gap | income_gap |
| --- | --- | --- | --- | --- | --- | --- |
| CAN_NL | True | 10.100153 | 10.100153 | 10.100153 | 0.025076 | 0.000004 |
| CAN_PE | True | 2.251669 | 2.251669 | 2.251669 | 0.000002 | 0.000000 |
| CAN_NS | True | 13.356280 | 13.356280 | 13.356280 | 0.000027 | -0.000004 |
| CAN_NB | True | 10.617221 | 10.617221 | 10.617221 | 0.010086 | -0.000006 |
| CAN_QC | True | 133.099398 | 133.099398 | 133.099398 | -0.000107 | -0.000061 |
| CAN_ON | True | 256.949898 | 256.949898 | 256.949898 | 0.000214 | -0.000031 |
| CAN_MB | True | 21.564830 | 21.564830 | 21.564830 | 0.000008 | -0.000004 |
| CAN_SK | True | 28.901431 | 28.901431 | 28.901431 | 0.000439 | -0.000004 |
| CAN_AB | True | 117.704691 | 117.704691 | 117.704691 | -0.000031 | 0.000000 |
| CAN_BC | True | 97.998558 | 97.998558 | 97.998558 | 0.000000 | 0.000015 |
| CAN_YT | True | 0.982255 | 0.982255 | 0.982255 | 0.001445 | 0.000000 |
| CAN_NT | True | 1.338922 | 1.338922 | 1.338922 | 0.001118 | 0.000000 |
| CAN_NU | True | 1.120864 | 1.120864 | 1.120864 | 0.001740 | 0.000000 |

## Twelve-quarter results

F_CFC is the historical IH comparator; FS_T is newly measured, seeds 0–2 serially. No baseline resampling or seed selection. GDP nominal B; real GDP uses each run's PPI deflator.

| arm | seed | GDP_Q0_B | GDP_Q1_B | GDP_Q12_B | GDP_Q0_Q12_pct | GDP_Q1_Q12_pct | GDP_real_Q0_Q12_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F_CFC | 0 | 708.084 | 700.259 | 654.309 | -7.594 | -6.562 | -7.321 |
| F_CFC | 1 | 708.084 | 715.043 | 645.013 | -8.907 | -9.794 | -9.216 |
| F_CFC | 2 | 708.084 | 696.897 | 584.880 | -17.400 | -16.074 | -13.062 |
| FS_T | 0 | 695.986 | 687.910 | 620.775 | -10.806 | -9.759 | -7.610 |
| FS_T | 1 | 695.986 | 702.816 | 660.363 | -5.118 | -6.040 | -9.065 |
| FS_T | 2 | 695.986 | 684.790 | 610.592 | -12.270 | -10.835 | -9.313 |

Loss and recapitalisation totals over 12 quarters, B:

| arm | seed | household_loss_B | firm_loan_loss_B | overdraft_loss_B | bank_loss_B | recap_B | Q12_constrained_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F_CFC | 0 | 233.541 | 54.106 | 30.266 | 317.913 | 165.205 | 50.374 |
| F_CFC | 1 | 233.594 | 102.062 | 36.791 | 372.446 | 199.720 | 50.072 |
| F_CFC | 2 | 233.240 | 66.091 | 25.289 | 324.620 | 99.958 | 49.647 |
| FS_T | 0 | 235.385 | 52.619 | 37.387 | 325.390 | 88.876 | 50.000 |
| FS_T | 1 | 234.380 | 66.734 | 54.922 | 356.036 | 148.100 | 50.408 |
| FS_T | 2 | 234.782 | 82.556 | 35.464 | 352.803 | 118.352 | 49.828 |

Q12 consumption, investment and employment:

| arm | seed | Q12_C_B | Q12_HH_I_B | Q12_firm_I_B | Q12_employment |
| --- | --- | --- | --- | --- | --- |
| F_CFC | 0 | 325.442 | 29.219 | 88.881 | 18206890.000 |
| F_CFC | 1 | 334.172 | 32.133 | 85.133 | 17839920.000 |
| F_CFC | 2 | 304.621 | 27.313 | 72.144 | 16946630.000 |
| FS_T | 0 | 333.562 | 30.107 | 88.036 | 18048180.000 |
| FS_T | 1 | 339.910 | 31.134 | 88.245 | 17779100.000 |
| FS_T | 2 | 323.523 | 30.818 | 79.657 | 17760900.000 |

FS_T lowers starting GDP12.098B/quarter. Seed0 Q12 nominal difference is−33.534B: C+8.120, G−15.370, I+0.043, inventory−8.166, exports−26.241 and imports−8.043B (lower imports add GDP). This is an expenditure decomposition, not identification of each feedback mechanism. Seed1's nominal improvement is much larger than its small real-GDP improvement: prices matter. Seed2 improves both. Tax, profit, fiscal and external-demand feedbacks interact; corrected accounting does not stabilize the unchanged spending rule by itself.

Seed0 also shows the importance of prices: real contraction is7.61% versus7.32%, much closer than the nominal10.81% versus7.59%. The correction changes the level and price path as well as quantities.

Within-run nominal GDP decomposition, B. Each row compares Q12 with its start quarter; the last import column is already signed as a GDP contribution. Full reconciliation residuals, below0.05CAD, are retained in `GDP_component_changes.csv`.

| arm | seed | start | GDP_change_B | C_B | G_B | I_B | inventory_B | X_B | minus_M_B |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_CFC | 0 | 0 | -53.774 | -46.480 | 22.756 | -37.806 | 9.412 | -13.953 | 12.296 |
| F_CFC | 0 | 1 | -45.950 | -53.046 | 19.970 | -28.193 | 3.650 | -2.916 | 14.586 |
| F_CFC | 1 | 0 | -63.071 | -37.697 | 3.259 | -38.641 | 12.211 | -15.560 | 13.357 |
| F_CFC | 1 | 1 | -70.030 | -48.769 | -0.126 | -29.875 | 2.293 | -16.335 | 22.782 |
| F_CFC | 2 | 0 | -123.204 | -67.369 | -21.284 | -56.449 | 23.932 | -50.570 | 48.536 |
| F_CFC | 2 | 1 | -112.018 | -74.783 | -20.634 | -42.086 | 18.348 | -41.964 | 49.102 |
| FS_T | 0 | 0 | -75.211 | -38.324 | 7.384 | -37.772 | 1.246 | -28.086 | 20.340 |
| FS_T | 0 | 1 | -67.135 | -45.916 | 5.279 | -27.947 | -4.272 | -16.878 | 22.599 |
| FS_T | 1 | 0 | -35.623 | -32.079 | 9.333 | -36.537 | 21.485 | -1.964 | 4.139 |
| FS_T | 1 | 1 | -42.453 | -43.334 | 5.969 | -27.784 | 11.464 | -2.382 | 13.614 |
| FS_T | 2 | 0 | -85.394 | -48.403 | 1.784 | -45.439 | 9.140 | -22.001 | 19.526 |
| FS_T | 2 | 1 | -74.198 | -56.403 | 2.879 | -31.125 | 3.622 | -13.248 | 20.078 |

Regional Q12 GDP means across matched seeds, B (all per-seed regional paths retained separately):

| region | F_CFC_Q12_B | FS_T_Q12_B | change_B |
| --- | --- | --- | --- |
| CAN_AB | 118.318 | 101.870 | -16.449 |
| CAN_QC | 124.137 | 122.098 | -2.039 |
| CAN_NS | 14.198 | 13.158 | -1.040 |
| CAN_NB | 9.252 | 9.235 | -0.017 |
| CAN_YT | 0.900 | 1.027 | 0.127 |
| CAN_PE | 2.108 | 2.286 | 0.178 |
| CAN_NT | 1.210 | 1.421 | 0.211 |
| CAN_NU | 0.874 | 1.147 | 0.273 |
| CAN_NL | 8.954 | 9.313 | 0.359 |
| CAN_MB | 20.687 | 21.310 | 0.624 |
| CAN_SK | 27.607 | 29.825 | 2.219 |
| CAN_BC | 80.877 | 84.996 | 4.119 |
| CAN_ON | 218.946 | 232.891 | 13.945 |

Firm loan+overdraft losses, mean12-quarter B across seeds:

| industry_code | FS_T | F_CFC | change |
| --- | --- | --- | --- |
| F | 29.912 | 22.295 | 7.617 |
| J62_63 | 10.697 | 6.515 | 4.183 |
| C31T33 | 9.340 | 3.765 | 5.575 |
| C10T12 | 9.054 | 8.260 | 0.794 |
| C29 | 6.975 | 0.002 | 6.973 |
| C19 | 6.555 | 7.528 | -0.973 |
| C302T309 | 3.742 | 0.012 | 3.730 |
| S | 3.600 | 1.121 | 2.479 |
| H51 | 3.094 | 4.975 | -1.881 |
| A02 | 3.093 | 3.571 | -0.479 |
| C26 | 2.596 | 0.007 | 2.589 |
| C25 | 2.569 | 2.932 | -0.364 |

Construction remains the largest loss industry. Computer/professional services, miscellaneous manufacturing, motor vehicles and other transport equipment worsen. The correction does not universally lower firm losses. Full industry×quarter×seed loan/overdraft losses: `firm_losses_by_industry_quarter.csv`. Bank/quarter resolutions and recaps: `resolution_comparison.csv`. Both arms' full quarterly GDP, deflated quantities, losses, cash DI/saving, constrained share, household/firm investment, CFC, employment and minimum bank ratios: `quarterly_comparison.csv`. Cash saving is not treated as SNA saving without the previously documented scope adjustments.

### FS_T seed 0, quarterly

| quarter | GDP_B | C_B | HH_loss_B | firm_all_loss_B | bank_loss_B | recap_B | constrained_pct | cash_saving_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 687.910 | 379.402 | 84.601 | 0.000 | 84.601 | 0.701 | 18.651 | -1.952 |
| 2 | 680.477 | 369.349 | 56.346 | 0.000 | 56.346 | 0.000 | 24.784 | -0.845 |
| 3 | 674.887 | 361.670 | 33.727 | 0.008 | 33.735 | 2.911 | 29.437 | 0.578 |
| 4 | 662.319 | 354.912 | 24.839 | 0.034 | 24.873 | 0.000 | 33.224 | 1.624 |
| 5 | 655.779 | 345.958 | 9.548 | 0.276 | 9.825 | 0.000 | 36.190 | 2.102 |
| 6 | 642.183 | 343.218 | 9.205 | 7.788 | 16.993 | 8.757 | 38.872 | 2.240 |
| 7 | 634.838 | 338.831 | 6.961 | 12.092 | 19.053 | 0.000 | 41.256 | 2.976 |
| 8 | 628.135 | 338.238 | 2.012 | 11.577 | 13.589 | 0.000 | 43.240 | 2.638 |
| 9 | 626.380 | 333.089 | 2.781 | 14.603 | 17.384 | 0.062 | 45.430 | 3.699 |
| 10 | 624.383 | 331.893 | 1.739 | 7.093 | 8.833 | 42.541 | 47.130 | 3.926 |
| 11 | 626.225 | 330.420 | 2.434 | 23.316 | 25.749 | 29.771 | 48.720 | 4.333 |
| 12 | 620.775 | 333.562 | 1.192 | 13.218 | 14.410 | 4.133 | 50.000 | 4.218 |

### FS_T seed1, quarterly

| quarter | GDP_B | C_B | HH_loss_B | firm_all_loss_B | bank_loss_B | recap_B | constrained_pct | cash_saving_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 702.816 | 383.071 | 92.823 | 0.000 | 92.823 | 0.701 | 18.794 | -3.150 |
| 2 | 696.905 | 372.765 | 46.105 | 0.000 | 46.105 | 0.000 | 25.192 | -0.660 |
| 3 | 690.241 | 365.417 | 30.032 | 0.008 | 30.039 | 5.674 | 29.858 | 0.957 |
| 4 | 686.807 | 365.334 | 27.023 | 0.001 | 27.024 | 0.000 | 33.593 | 0.962 |
| 5 | 682.644 | 359.538 | 12.610 | 0.373 | 12.984 | 0.000 | 36.630 | 2.110 |
| 6 | 676.934 | 351.667 | 8.034 | 4.441 | 12.475 | 0.000 | 39.318 | 3.113 |
| 7 | 664.273 | 350.177 | 6.159 | 17.859 | 24.017 | 3.549 | 41.735 | 2.878 |
| 8 | 660.709 | 344.172 | 4.137 | 8.751 | 12.888 | 23.237 | 43.635 | 3.449 |
| 9 | 654.637 | 352.443 | 2.313 | 19.008 | 21.321 | 0.000 | 45.799 | 2.838 |
| 10 | 656.865 | 344.828 | 2.801 | 23.104 | 25.904 | 70.121 | 47.589 | 4.701 |
| 11 | 658.938 | 341.000 | 1.147 | 23.808 | 24.954 | 44.816 | 48.973 | 4.244 |
| 12 | 660.363 | 339.910 | 1.198 | 24.303 | 25.501 | 0.000 | 50.408 | 4.184 |

### FS_T seed2, quarterly

| quarter | GDP_B | C_B | HH_loss_B | firm_all_loss_B | bank_loss_B | recap_B | constrained_pct | cash_saving_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 684.790 | 379.813 | 78.861 | 0.000 | 78.861 | 0.000 | 18.561 | -2.379 |
| 2 | 674.616 | 366.068 | 56.081 | 0.000 | 56.081 | 0.681 | 24.759 | -0.858 |
| 3 | 675.237 | 354.390 | 32.889 | 0.008 | 32.897 | 0.000 | 29.347 | 0.910 |
| 4 | 664.408 | 353.640 | 25.560 | 0.092 | 25.652 | 0.000 | 33.122 | 1.470 |
| 5 | 645.966 | 346.913 | 18.407 | 2.405 | 20.812 | 2.939 | 36.159 | 2.392 |
| 6 | 630.482 | 343.648 | 5.833 | 6.904 | 12.737 | 0.000 | 38.719 | 2.170 |
| 7 | 629.936 | 336.380 | 7.508 | 25.337 | 32.845 | 46.312 | 41.206 | 2.577 |
| 8 | 612.654 | 334.248 | 2.922 | 5.989 | 8.910 | 0.200 | 43.035 | 2.732 |
| 9 | 616.189 | 331.067 | 2.861 | 11.204 | 14.065 | 18.122 | 45.322 | 2.365 |
| 10 | 606.491 | 319.697 | 1.514 | 12.365 | 13.879 | 1.651 | 47.236 | 6.328 |
| 11 | 605.187 | 324.714 | 0.921 | 40.857 | 41.779 | 48.414 | 48.587 | 5.012 |
| 12 | 610.592 | 323.523 | 1.425 | 12.860 | 14.285 | 0.033 | 49.828 | 5.859 |

## FSG source reconciliation: no executable build

IO fixed capital is **624.510840B/year including68M floors** (unfloored624.442840B), separate from55.631098B inventory change.36-10-0096 investor observations and36-10-0099 residential observations supply **shares**, not a second regional level. Scope budgets below are diagnostic allocations, never adopted inputs.

| sector | observed_quarterly_purchaser_CAD | normalized_IO_basic_CAD |
| --- | --- | --- |
| NPISH | 1.517 | 1.431 |
| business | 311.343 | 295.279 |
| government | 98.480 | 92.760 |
| residential | 249.779 | 235.042 |
| valuation_bridge | 661.119 | 624.511 |

The13-region observed purchaser-price total is661.119B/year (Canada661.120B, rounding); source GFCF net product taxes36.651344B/year. With68M floors retained, the residual price/scope gap is−43.184M/year; unfloored it is+24.816M. Reported, not allocated as a business-investment plug. Government is98.480B, NPISH1.517B in the13-region sum, business residual311.343B, residential249.779B. Actual source vectors and regional budgets are cached.

An additional independent valuation check is retained in `FSG_legacy_tax_scope_diagnostic.csv`. Applying the existing24.4738997% household capital-formation tax to the diagnostic235.041603B basic residential budget would yield **292.565449B purchaser spending**, 42.786449B above the249.779B residential source. No rate, price or fiscal flow was changed. Also, total residential investment across all sectors is not identical to household-sector GFCF: the previously accepted household benchmark v62305994 is242.393B/year, a7.386B scope difference. A future executable FSG needs a sector/asset and product-tax valuation crosswalk as well as a signed-use accounting path. Reusing the legacy rate and relabelling all residential formation household investment would not establish a source-consistent scope bridge.

The7.386B difference is not an estimate of corporate residential investment: household-sector fixed capital also includes unincorporated-enterprise nonresidential assets, while the residential table covers an asset class across sectors. Prior benchmark provenance is [the IFE source record](benchmarks/IFE/provenance.json):36-10-0112 v62305994,2022 quarterly SAAR annual mean, retrieved2026-10-23, selected CSV SHA256 c579dbedd2fe33449d43eab7d565b552fab61b17d0a9ac08e6c2e9448b46584c; source zip b577daa453e1527602f55000d301624143bdaf3dba87bfbd458f44d6ab797d1e. Its exact quarterly source rows remain in `benchmarks/IFE/household_gfcf_2022.csv`.

**20 negative product×destination-region net uses total−3.501614B/year.** Largest entries, B/quarter:

| region | product | fixed_B_q |
| --- | --- | --- |
| CAN_ON | C24B | -0.424613 |
| CAN_ON | C24A | -0.150189 |
| CAN_QC | C24A | -0.106476 |
| CAN_QC | C24B | -0.053002 |
| CAN_BC | C24B | -0.028025 |
| CAN_AB | C24A | -0.025850 |
| CAN_BC | C24A | -0.021736 |
| CAN_MB | C24A | -0.018848 |

These signed entries are not rounding remnants. Distributing them to investors creates negative household purchase weights, incompatible with the nonnegative goods allocator. Clipping inflates fixed capital3.502B/year; offsetting with inventories violates the requested separation. Neither is done. No FSG pickle or opening stock/cash change. The >50M/q mapped-group2% gate, FSG GDP/accounting checks and dependent12Q runs are **not evaluated**, not falsely marked passed or assigned numerical failures. This is a source-to-model representation blocker; it does not show failure of the investor-share gate.

This constraint comes from the existing implementation, not a new statistical acceptance threshold: `macromodel/agents/agent/agent.py` clips recorded negative purchases, and `macromodel/markets/goods_market/func/settlement.py:104` explicitly requires negative buyer spending to be zero. `ICIOReader._prefold_capital_composition` already distinguishes signed accounting investment from nonnegative capital-technology weights; its technology-only clipping is not an exact signed-GFCF accounting path. Copying that clip into the new accounting budget would lose the3.502B net-use term.

Next decision: establish these negative net uses' source meaning, including the commodity/valuation bridge; then specify the appropriate signed non-purchase or disposal account and counterparties if valid. Correct source only if an independently demonstrated source error exists. No disposal rule, rescale or capital basket invented. Initial failed build trace and complete preflight retained in logs/.

The independent investor concordance was nevertheless completed. `FSG_investor_groups_diagnostic.csv` and `FSG_investor_industries_diagnostic.csv` retain every actual vector, missing-regional fallback, scope normalization, source group and within-group canonical-output share. Government education/health are separated from private P/Q, government residual maps to O, NPISH to P/Q/R/S. The normalized nonresidential target is389.469237B/year; 171 mapped groups exceed50M/quarter. No material target lacks an existing capital-stock/acquisition support total; residuals are floating-point noise (national1.79e-06CAD/year). This is an allocation-only support check, not an executable product-flow or adoption-gate pass; no new product basket is assigned to any firm.

## Exact owner-occupied housing, read-only

Pinned IO commit **eb40128**, SUT BS5311A0/HFCE PEC04200 inside L. Annual exact source output/imputed consumption **235.939587B**, owner cash costs **66.623975B**, noncash gross mixed income **169.315612B**. Cash costs are basic inputs, net product taxes on inputs and net property/production taxes. The existing model memo differs nationally1.587M; provincial differences are larger because its regional allocation differs (full differences in `OOH_owner_allocation_by_province.csv`).

F_CFC L revenue404.928565B, GOS288.982141B, profit271.532846B/year. Attributable OOH revenue235.939587B and current model gross-surplus contribution**204.725982B**, including the35.410370B property/production tax F_CFC omits from costs. FS_T charges that tax; source noncash mixed income is169.315612B. Source OOH has no employee compensation or corporate GOS; the model embeds it in the mixed L corporate producer. Actual OOH **net profit cannot be identified** without dwelling CFC and interest/ownership allocation.

Province bridge, annual B. *Market profit residual retains all modeled nonresidential L CFC and firm interest in market L: a diagnostic convention, not an observed OOH profit.*

| region | L revenue | L GOS | L profit | OOH revenue | OOH model GOS | market L revenue | market L GOS | market L profit residual* |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAN_NL | 3.982 | 3.044 | 2.905 | 2.927 | 2.499 | 1.055 | 0.546 | 0.406 |
| CAN_PE | 1.574 | 1.210 | 1.167 | 1.105 | 1.002 | 0.470 | 0.208 | 0.165 |
| CAN_NS | 10.396 | 7.800 | 7.374 | 6.793 | 6.043 | 3.603 | 1.757 | 1.331 |
| CAN_NB | 6.666 | 4.885 | 4.646 | 4.483 | 3.829 | 2.183 | 1.056 | 0.817 |
| CAN_QC | 71.299 | 47.411 | 44.478 | 36.427 | 30.467 | 34.872 | 16.944 | 14.011 |
| CAN_ON | 159.666 | 111.076 | 103.382 | 90.675 | 78.055 | 68.991 | 33.022 | 25.327 |
| CAN_MB | 13.036 | 9.783 | 9.268 | 8.445 | 7.492 | 4.592 | 2.292 | 1.776 |
| CAN_SK | 10.515 | 7.913 | 7.530 | 7.285 | 6.369 | 3.230 | 1.544 | 1.161 |
| CAN_AB | 49.579 | 36.451 | 34.119 | 30.361 | 26.178 | 19.218 | 10.273 | 7.940 |
| CAN_BC | 76.736 | 58.246 | 55.558 | 46.680 | 42.084 | 30.056 | 16.162 | 13.475 |
| CAN_YT | 0.589 | 0.484 | 0.461 | 0.401 | 0.375 | 0.188 | 0.109 | 0.086 |
| CAN_NT | 0.569 | 0.433 | 0.415 | 0.250 | 0.231 | 0.319 | 0.202 | 0.184 |
| CAN_NU | 0.320 | 0.246 | 0.229 | 0.108 | 0.103 | 0.212 | 0.143 | 0.126 |

Read-only calculation: remove each province's exact OOH consumption from existing owners, add its exact owner cash costs, both **proportional to existing owner imputed memos within that province**. Survey weights, cash DI, consumption target, firms and all actual flows unchanged. No VAT gross-up, clipping or calibration. Income deciles are model unequivalised household after-tax income per represented household, household-weighted, not a new source-income fit.

National annual B, gap=planned C−cash DI (positive means planned dissaving):

| arm | C | DI | old_gap | new_cash_C | new_gap | old_dissaver_share | new_dissaver_share | negative_residual_households |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_CFC | 1564.269 | 1468.386 | 95.884 | 1394.954 | -73.432 | 71.941 | 37.114 | 206250.000 |
| CIS_candidate | 1555.905 | 1468.386 | 87.519 | 1386.590 | -81.796 | 70.100 | 35.879 | 189170.000 |

Gap falls exactly169.315612B/year. But proportional attribution gives **206,250 F_CFC households negative residual cash consumption (−5.540B/year)**; CIS candidate189,170 (−5.246B). Retained, never clipped. Exact provincial totals do not identify exact household imputed purchases: this cannot simply be installed as a cash rule. A matched noncash layer needs coherent household/memo allocation, cash inputs, dwelling stocks/CFC and fiscal ownership boundaries. No closure change here.

Cash DI is held fixed solely to size the initial accounting boundary. An implemented closure would also change L cash sales, the corporate-profit/payout base and the counterparties for owner expenses; these results are not a general-equilibrium forecast of that implementation.

Decile×tenure planned-dissaver shares and new annual gap B; full components/counts in `OOH_cash_by_decile_tenure.csv`:

### F_CFC

| decile | tenure | households | old_dissaver_pct | new_dissaver_pct | new_gap_B | negative_residual_households |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | owner | 673000.000 | 99.703 | 57.058 | 0.160 | 48000.000 |
| 1 | renter_or_other | 876000.000 | 100.000 | 100.000 | 12.978 | 0.000 |
| 2 | owner | 961280.000 | 94.070 | 34.139 | -3.894 | 64120.000 |
| 2 | renter_or_other | 588560.000 | 98.129 | 98.129 | 6.777 | 0.000 |
| 3 | owner | 979200.000 | 83.116 | 20.662 | -7.005 | 46260.000 |
| 3 | renter_or_other | 570190.000 | 87.183 | 87.183 | 3.736 | 0.000 |
| 4 | owner | 935970.000 | 71.270 | 14.229 | -9.765 | 27270.000 |
| 4 | renter_or_other | 614690.000 | 68.454 | 68.454 | 2.657 | 0.000 |
| 5 | owner | 984200.000 | 63.047 | 8.028 | -11.145 | 17330.000 |
| 5 | renter_or_other | 564650.000 | 53.554 | 53.554 | 1.365 | 0.000 |
| 6 | owner | 963760.000 | 67.366 | 10.792 | -10.033 | 2150.000 |
| 6 | renter_or_other | 586590.000 | 57.284 | 57.284 | 1.528 | 0.000 |
| 7 | owner | 1046790.000 | 66.109 | 11.179 | -11.696 | 80.000 |
| 7 | renter_or_other | 502810.000 | 55.291 | 55.291 | 1.708 | 0.000 |
| 8 | owner | 1145740.000 | 67.992 | 13.877 | -13.307 | 1010.000 |
| 8 | renter_or_other | 403610.000 | 50.546 | 50.546 | 0.868 | 0.000 |
| 9 | owner | 1216520.000 | 68.393 | 17.509 | -14.522 | 20.000 |
| 9 | renter_or_other | 334010.000 | 50.304 | 50.304 | 0.938 | 0.000 |
| 10 | owner | 1283940.000 | 57.951 | 19.939 | -24.026 | 10.000 |
| 10 | renter_or_other | 265810.000 | 43.640 | 43.640 | -0.751 | 0.000 |

### CIS_candidate

| decile | tenure | households | old_dissaver_pct | new_dissaver_pct | new_gap_B | negative_residual_households |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | owner | 790850.000 | 93.924 | 44.783 | -4.157 | 108330.000 |
| 1 | renter_or_other | 758070.000 | 99.207 | 99.207 | 9.150 | 0.000 |
| 2 | owner | 884960.000 | 86.082 | 33.908 | -3.629 | 28160.000 |
| 2 | renter_or_other | 665420.000 | 91.846 | 91.846 | 5.762 | 0.000 |
| 3 | owner | 910190.000 | 78.851 | 21.542 | -6.542 | 18090.000 |
| 3 | renter_or_other | 639170.000 | 78.000 | 78.000 | 3.794 | 0.000 |
| 4 | owner | 953480.000 | 70.339 | 16.261 | -8.583 | 14200.000 |
| 4 | renter_or_other | 596600.000 | 63.969 | 63.969 | 2.758 | 0.000 |
| 5 | owner | 1007740.000 | 67.321 | 11.812 | -10.026 | 6120.000 |
| 5 | renter_or_other | 541490.000 | 57.473 | 57.473 | 1.600 | 0.000 |
| 6 | owner | 1017870.000 | 66.728 | 10.021 | -12.427 | 9110.000 |
| 6 | renter_or_other | 531560.000 | 58.912 | 58.912 | 1.651 | 0.000 |
| 7 | owner | 1063030.000 | 65.107 | 9.784 | -12.954 | 5090.000 |
| 7 | renter_or_other | 487160.000 | 52.350 | 52.350 | 1.313 | 0.000 |
| 8 | owner | 1111380.000 | 65.150 | 14.307 | -13.451 | 30.000 |
| 8 | renter_or_other | 438110.000 | 53.188 | 53.188 | 1.132 | 0.000 |
| 9 | owner | 1179940.000 | 66.191 | 15.509 | -15.515 | 30.000 |
| 9 | renter_or_other | 369780.000 | 47.866 | 47.866 | 0.339 | 0.000 |
| 10 | owner | 1270960.000 | 60.034 | 18.490 | -21.727 | 10.000 |
| 10 | renter_or_other | 279560.000 | 42.925 | 42.925 | -0.286 | 0.000 |

Dwelling CFC is **missing, not zero**.36-10-0096/0098 extracts are nonresidential. Required residential source: [StatCan36-10-0099-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610009901), Current prices / Geometric depreciation / Total residential / province /2022, followed by owner-occupied versus rented allocation. No number assumed or imported. `OOH_dwelling_CFC` and `OOH_actual_net_profit` remain missing provincially and nationally.

## Provenance and final review

All IO reads use immutable git show, never the working tree. Native v-numbers do not exist for the mapped custom SUT/OOH split; industry/use/component codes and pinned blobs supply identifiers. IO source:2022 provincial detailed SUT/[StatCan36-10-0478-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610047801) handoff (table identification checked2026-10-25; the actual numeric input remains the pinned git blob). Blob hashes and dates:

| commit | file | sha256 | retrieved_utc |
| --- | --- | --- | --- |
| d847fb2e22fee298c7af31803d3ab6543126dda4 | compatibility/compat_icio_2022_can_provinces.csv | f0004ad3d40e465cceba3d9735d6dda5b00658fe6ca88af5ffed944917a8adb9 | 2026-10-25 |
| d847fb2e22fee298c7af31803d3ab6543126dda4 | canonical/VA_tax_output_basic.csv | 6fbdf9db8985e7cafde8974ebfad0032776416bb4db84d6ca2f04c3408952940 | 2026-10-25 |
| eb40128bdfb24d46771b5a3788e9b530fc4268c4 | OOH_SPLIT_2026-10-25.md | 40fff9b497db4a9c64a31b801ff984d2d7e65569898489e30802413bb3d42576 | 2026-10-25 |
| eb40128bdfb24d46771b5a3788e9b530fc4268c4 | canonical/ooh_by_province_basic.csv | 516e3c50527caa784090a87663ab605222fe91828b3ceb6997a69ff00c6d6495 | 2026-10-25 |
| eb40128bdfb24d46771b5a3788e9b530fc4268c4 | canonical/ooh_inputs_by_province_commodity_basic.csv | 3eb122c9bcc42c0ac5cb6e4d4dd5d01c4fd065edcf8f9f402d30b7844da21c8f | 2026-10-25 |
| d847fb2 | canonical/product_taxes_final_gross_by_province.csv | 7845023e0bcf74614229598b891c426eff93d8dd758db6e5b1851ca65f20bcf4 | 2026-10-25 |

The compatibility LF blob f0004ad3… and handoff CRLF representation41590fdb… were reconciled byte-for-byte in SG. FSG caches actual regional vectors. Examples:36-10-0096 Canada2022 Current prices/Investment/Total nonresidential v90968052 (411.341B), Government v90970252 (98.480B), NPISH v90970012 (1.519B), Government education v90970292, Hospitals v90970332, Nursing/residential care v90970372. Residential36-10-0099 v91665012 (249.779B). Investment observations are not dwelling CFC.

Nonresidential downloaded2026-10-24T19:59:02.951130Z, zip SHA256b5ec714f9eef4cedf80759f1ed5bf0f08ed1b18f2753f6933aee8a68fb1f0bd6; fullCSV e790e88e5808acc587c33b7e6f4de32b7ab046a839c48ae9ad1065f31255b8e0; selected2022CSV c80839b83259cdce64e053e1a5172f73d82845a682935eb90ce7d4140e45ddfd. Residential downloaded2026-10-24T20:22:32.343037Z, zip f6d5ed033f4e902d91e9fd747b564d41cc2d66b9bfdc03de51474acdec482d37; fullCSV ff5992b66c3127a24c56eb9484051ec8afb436f2843e5dd4d263f24590502f76. URLs/dates/hashes in `FSG_build_gate.json` and benchmarks/ZA.

503 passed, 30 failures, 533 cases; 0 additional failures against the exact SG test IDs. Sampler one worker. Exact IDs/messages and sampler worker property in `full_test_execution.json`, full log/XML retained. `audit.json` and `artifact_manifest.json` verify protected input/source/candidate hashes, floor certificates, sequential long-run order and frozen aggregate evidence. No pickles or household microdata in the evidence commit; no push or original/ITC writes.

**Recommendation:** retain the zero-activity mechanical correction and corrected gate specification; review FS_T as the corrected diagnostic starting input. Keep FSG blocked on signed source-use representation. Housing makes the cash/noncash question material, but negative household residuals preclude adopting the aggregate subtraction as a rule. Passing accounting does not validate household losses/default or spending dynamics. Phase B and C_dp_005 remain on hold.
