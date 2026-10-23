# Household closure corrections — 22 October 2026

Review candidate on `feature/validation-2022`, original base `4bdef06`.
The quota correction applies to the default. H7 uses a separately rebuilt file;
D1–D4 remain independent opt-in specifications. No push, Phase B or C_dp_005 port.

| Order | Commit | Scope | Focused tests |
|---|---|---|---:|
| a | c4862de | Currency loan-category quotas in both allocators, including default; regression | 29 |
| b | 4cea6e2 | Fixed-weight, common-property scaling and capped mortgage top-up (H7) | 31 |
| c | 1fdedd2 | D4 uninsured originations, annual income, service/collateral and 49/145-quarter terms | 36 |
| d | 4e9ac88 | D2 observed dividends and funded mixed income/corporate transfers | 39 |
| e | f549246 | D1 private-rent offset within each renter's L demand | 40 |
| f | 8fabeee | D3 distress scenario, reset regression, write-off instrumentation and runner | 44 |

## Write-off attribution

All five arms passed 2-quarter accounting **before** their 12-quarter runs.
There was one simulation at a time, seed 0, 13 Canadian regions. Arms i–iv
retain `DefaultHouseholdInsolvencyHandler`; v changes only D3 relative to iv.
No D1 or deposit-only-saving switch is present in arms i–v.

| Arm | Specification |
|---|---|
| i | Corrected default, original Phase-A household file |
| ii | i + agreed H7 file |
| iii | ii + D4 |
| iv | iii + D2 |
| v | iv + D3 persistent-distress rule |

12-quarter totals, CAD billions (bank losses include firm and household loan write-offs plus cancelled firm overdrafts):

| arm | household_writeoffs_bn | bank_loan_losses_bn | q12_gdp_bn | q12_saving_pct |
|---|---|---|---|---|
| i | 520.471 | 862.109 | 708.704 | -13.714 |
| ii | 421.807 | 742.811 | 718.807 | -16.584 |
| iii | 551.732 | 945.914 | 701.161 | -14.859 |
| iv | 488.848 | 936.527 | 647.874 | -9.853 |
| v | 178.915 | 616.205 | 698.206 | -10.581 |

Household write-offs per quarter, CAD billions:

| quarter | i | ii | iii | iv | v |
|---|---|---|---|---|---|
| 1 | 234.767 | 172.360 | 173.741 | 171.143 | 0.000 |
| 2 | 65.055 | 48.061 | 53.320 | 50.561 | 0.000 |
| 3 | 28.285 | 22.493 | 28.755 | 25.849 | 71.742 |
| 4 | 36.156 | 23.658 | 31.123 | 29.072 | 14.351 |
| 5 | 20.038 | 13.934 | 22.115 | 19.605 | 7.096 |
| 6 | 19.539 | 14.421 | 26.521 | 22.830 | 17.215 |
| 7 | 30.454 | 20.246 | 31.026 | 25.757 | 8.012 |
| 8 | 18.742 | 20.014 | 34.912 | 22.687 | 10.755 |
| 9 | 15.461 | 16.213 | 34.040 | 28.940 | 10.837 |
| 10 | 21.095 | 21.715 | 35.868 | 31.125 | 22.565 |
| 11 | 19.185 | 22.256 | 40.867 | 28.747 | 8.741 |
| 12 | 11.694 | 26.436 | 39.443 | 32.532 | 7.600 |

Bank losses charged to equity per quarter, CAD billions (artifact field `bank_loan_losses`):

| quarter | i | ii | iii | iv | v |
|---|---|---|---|---|---|
| 1 | 234.767 | 172.360 | 173.741 | 171.143 | 0.000 |
| 2 | 65.383 | 48.389 | 53.648 | 50.889 | 0.328 |
| 3 | 54.829 | 49.035 | 69.148 | 79.572 | 125.467 |
| 4 | 60.691 | 48.024 | 43.483 | 45.274 | 30.553 |
| 5 | 66.056 | 48.357 | 52.123 | 77.878 | 38.574 |
| 6 | 36.538 | 35.896 | 50.917 | 58.375 | 71.170 |
| 7 | 66.411 | 56.199 | 74.724 | 30.900 | 20.218 |
| 8 | 35.234 | 21.452 | 57.662 | 58.827 | 57.059 |
| 9 | 63.450 | 69.030 | 91.946 | 222.785 | 91.958 |
| 10 | 46.456 | 71.677 | 73.481 | 47.105 | 39.226 |
| 11 | 53.581 | 50.263 | 120.610 | 39.318 | 70.194 |
| 12 | 78.715 | 72.127 | 84.431 | 54.461 | 71.457 |

D4 expands 12-quarter household lending from 24.913B in ii to 309.897B in iii;
write-offs also rise from 421.807B to 551.732B. D2 reduces household write-offs
but leaves substantial firm/bank losses. Neither credit access nor sourced extra
income by itself repairs the old insolvency trigger.

Arm iv still writes off **488.85B** over 12 quarters. Retain D3 as a review
candidate: it produces **178.91B** in v. This satisfies the requested condition
for retaining D3; it does not validate a Canadian insolvency law or an arrears model.
Its trigger is three consecutive increases in overdraft capped at scheduled service,
with a 20% collateral haircut and recoverable nonhousing assets. Collateral-backed
claims survive; actual write-downs reduce bank equity and household liabilities.

## H7: weights, mortgage composition and wealth

H7 holds the inherited survey/tenure-calibrated weights fixed through mortgage
calibration. It does not apply the candidate's mortgage entropy reweighting.
Properties are scaled by one factor to NBSA real estate (7,789.772B), with the
same factor applied to each associated mortgage. A remaining **661.749B** mortgage
gap is distributed pro rata to positive mortgage holders with headroom to 95% LTV,
iteratively capping and redistributing. No new mortgagors or underwater records
are created. The top-up deliberately changes LTVs within that cap; the preceding
property scaling preserves survey LTVs. Infeasible residuals raise an error.

| Diagnostic | Agreed build | SFS 2023 benchmark |
|---|---:|---:|
| Underwater main-residence mortgagors | 0.616% | 0.825% (about 0.8%) |
| Underwater other-property mortgagors | 9.260% | 9.144% (about 9.1%) |
| Main-residence mortgage balance | 1,515.043B (71.229%) | 1,556.804B (76.901%) |
| Other-property mortgage balance | 611.953B (28.771%) | 467.615B (23.099%) |
| Net-worth income-quintile shares, low to high | 9.337 / 11.808 / 15.587 / 20.837 / 42.431% | 11.5 / 11.1 / 14.9 / 22.3 / 40.2% (36-10-0660, 2022 Q4) |

After model sampling, underwater shares are 0.714% (main) and 8.463% (other);
modeled mortgage stocks are 1,524.694B / 615.534B. Sampling moves balances away
from exact weighted-file targets; these sampled diagnostics are saved separately
in `h7_sampled.json`. The table above describes the weighted input file.

The mortgage split remains less concentrated on main residences than SFS; it is
reported, not silently fitted. SFS economic families are a 2023 comparison, while
the NBSA target is households in 2022 Q4. Model income quintiles use mapped gross
income, versus DHEA equivalized disposable income. `h7.json` records source hashes.
Assets sum to 18,298.593B and represented debt to 2,856.928B, giving derived net
worth 15,441.665B: 36.880B above NBSA because other-liability coverage remains
incomplete. Net worth is not separately rescaled to conceal that discrepancy.

The entropy version is an **alternative only** (`--mortgage-method reweight`),
not the default build. Its effective sample size is 14,452.6 / 83,162 = 17.4%,
weight multipliers span 0.00329–23.5917, and other-property mortgages are 963.9B,
45.3% of the total. The earlier pickle and source archive remain preserved locally.

## D4 and D2 boundaries

D4's single 80% new-loan LTV limit explicitly covers **uninsured originations**.
An insured channel up to 95% needs insurance premiums, a guarantor and a matching
balance sheet; these are absent. High-LTV initial stock is retained. New consumer
and mortgage terms are 49 and 145 quarters, matching initial-stock effective
straight-line principal repayment, rather than the previous unexplained 20/100.
These are effective debt-to-principal-flow terms, not legal contract maturities.
The 4.5-times annual disposable-income and 40% service limits are scenario screens.
[OSFI's LTI measure](https://www.osfi-bsif.gc.ca/en/supervision/financial-institutions/banks/loan-income-limits-uninsured-mortgage-portfolios)
is a **portfolio** measure from fiscal 2025, not a 2022 individual cap.

D2 targets **92.052B/year gross dividends received by households**, from
[StatCan 36-10-0482](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610048201),
2022 `Dividends`, v80013659. Provincial observations set regional payout targets;
initial positive after-tax private firm/bank profits determine each payout ratio.
Required rates range from **0.1854% to 15.5595%**, with zero initial benchmark
shortfall and aggregate initial requested dividends **23.013B/quarter**. Rates
are held fixed thereafter; realized receipts vary with profits, cash and bank
capital. Within-province total financial wealth plus self-employment business value
proxies dividend allocation; the synthetic financial aggregate includes deposits
and pensions, so it is broader than direct equity ownership. Provincial receipt
allocation is benchmarked; this individual allocation is an assumption and does
not establish an observed dividend-income distribution. Pension assets proxy
transfer recipients. This limitation remains open for review.
No extra unverified withdrawals residual or entire 246.588B property-income
receipt is inserted as dividends. Nonrent mixed income (97.274B/year) and current
corporate transfers (121.5B/year) use the existing sourced audit controls.
Firm cash/bank equity funds the receipts and PIT has a government counterparty.
Requested versus actual payments are retained. The model still lacks pension
institutions and parts of household interest/property-income accounts.

## D1 and saving

Housing services remain in sector L. Each renter's **actual private rent**, before
the next goods clearing, reduces only that renter's L purchase budget by
rent/(1+VAT). The cash reduction includes avoided VAT. Offset cannot exceed that
household's L demand; uncovered rent is reported. There is no household housing
producer, change to consumption weights, or removal of owner households' L bundle.
At Q12, 0.313B of private rent exceeds the available L purchase budgets. This
is a budget-coverage diagnostic: the excess is still paid once as actual rent,
and no negative L purchase or transfer to another spending category is invented.
D1's broader cash/noncash reconciliation remains open.
L sales rise despite lower L employment along this single-seed path; the table
reports realized sales, not the mechanical demand deduction. Changed buyer and
lender allocations change subsequent random draws, so these ordered differences
include stochastic path effects. Multi-seed inference is outside this review.
The wider producer proposal is not implemented.

L-sector before/after (iv versus iv+D1), sales in CAD billions, employment in persons:

| arm | quarter | L_sales_bn | L_employment | rent_offset_bn | unoffset_rent_bn |
|---|---|---|---|---|---|
| iv | 1 | 98.796 | 360,120.000 | 0.000 | 0.000 |
| iv | 12 | 91.992 | 360,120.000 | 0.000 | 0.000 |
| d1 | 1 | 98.796 | 360,120.000 | 3.798 | 0.327 |
| d1 | 12 | 118.689 | 342,110.000 | 3.809 | 0.313 |

Saving is `(income − net interest − goods consumption incl. VAT − actual rent) /
(income − net interest)`, before investment and D.8. Positive new financial saving
goes into deposits only when that separate switch is on. None of these runs
recalibrates the initial saving propensity to the extra income or smaller basket.

Paired old-insolvency runs give this **ordered, dynamic** saving decomposition
(iii → +D2 → +D1 → +deposit-only; percentage points):

| component | quarter | before_pct | after_pct | change_pp |
|---|---|---|---|---|
| D2 | 1 | -16.373 | -9.622 | 6.751 |
| D2 | 12 | -14.859 | -9.853 | 5.006 |
| D1 | 1 | -9.622 | -9.725 | -0.103 |
| D1 | 12 | -9.853 | -9.368 | 0.485 |
| deposit-only saving | 1 | -9.725 | -9.725 | 0.000 |
| deposit-only saving | 12 | -9.368 | -7.220 | 2.149 |

The previous candidate's +13.48% / +21.89% figures came from a wider L removal,
an assumed 20% payout, and a saving-propensity recalibration to the smaller basket.
Its national weighted saving propensity was reset to +25.19%, versus about ?9.7%
in the corrected baseline. They should not be treated as the results of these
corrected specifications.
The following static accounting bridge explains those old Q12 rates relative to
−11.9435%; it is **not a causal estimate**. D2 replaces the old unfunded FA receipt
with actual net distributions; the L removal is reconstructed at each region's
original basket share holding its non-L purchases fixed. Deposit-only allocation
has zero direct effect on C/Y; remaining dynamics and the propensity reset are
shown explicitly as a residual. The paired runs above measure its new dynamic effect.

| arm | old_default_saving_pct | D2_direct_pp | D1_removed_bundle_pp | deposit_only_direct_pp | residual_dynamics_and_propensity_pp | final_saving_pct |
|---|---|---|---|---|---|---|
| fixed | -11.944 | 11.205 | 22.938 | 0.000 | -8.718 | 13.481 |
| income | -11.944 | 11.517 | 20.338 | 0.000 | 1.975 | 21.887 |

[Table 36-10-0112](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201)
gives 2022 DI 1,502.340B, consumption 1,511.382B and pension adjustment 40.585B.
Its net saving rate is **2.0996%**; removing D.8 gives the closer cash comparison
**−0.6019%**. This still is not full SNA reconciliation: owner-occupied housing,
housing depreciation/input costs, FISIM, pension accruals and property-income
coverage differ. Matched imputed housing income/consumption cancel in saving's
numerator but change the denominator; adding an income memo alone while retaining
L purchases is not evidence of measured net disposable-income equivalence.
No fit is claimed by comparing the model's cash rate directly with 2.1%.

## GDP and household debt

The old Q12 GDP of 687.693B (fixed C) / 674.708B (income-driven C), versus 710.106B
in its old default, accompanied cash consumption of **309.683B / 276.950B**,
versus **375.792B**: reductions of **66.109B / 98.842B**. The broad L deletion and
changed propensity reduced goods demand, followed by firm production and labour;
the no-input/no-depreciation housing block and external-demand responses partly
offset that decline. Dividends are redistribution, not extra value added. GDP
therefore need not rise when the measured household saving rate rises.
Those historical comparisons also left the quota bug in their default, so they
cannot establish a corrected-model policy conclusion. Current GDP by arm is above.

Debt still falls because principal repayment and write-offs exceed new lending.
For the **old** fixed / income candidate, reconstructed initial debt is 2,830.344B;
new loans are 39.203 / 33.731B, principal 341.846 / 341.864B, and inferred household
write-offs 175.238 / 171.267B, leaving 2,352.462 / 2,350.944B. Initial debt is
reconstructed from Q1, when the three-period D3 rule cannot yet write off debt.
The current simulations record household write-offs directly and satisfy this bridge
(amounts in billions except the final rounding residual, which is in CAD):

| arm | initial_debt_bn | new_credit_bn | principal_bn | household_writeoffs_bn | q12_debt_bn | debt_bridge_error |
|---|---|---|---|---|---|---|
| i | 2,881.902 | 24.923 | 326.234 | 520.471 | 2,060.121 | -0.001 |
| ii | 2,883.063 | 24.913 | 334.838 | 421.807 | 2,151.331 | 0.001 |
| iii | 2,883.063 | 309.897 | 332.068 | 551.732 | 2,309.161 | 0.000 |
| iv | 2,883.063 | 256.179 | 330.756 | 488.848 | 2,319.638 | 0.000 |
| v | 2,883.063 | 292.390 | 367.865 | 178.915 | 2,628.673 | 0.000 |
| d1 | 2,883.063 | 255.313 | 331.635 | 480.832 | 2,325.909 | 0.000 |
| deposit | 2,883.063 | 259.188 | 331.453 | 480.510 | 2,330.288 | -0.000 |

## Verification and provenance

All 12 simulations are finite and passed the regional accounting battery
(cash, wages/benefits/rent, house sales, distributions/taxes, goods settlement,
loan stocks, bank snapshots/equity and explained reserves). Largest relative
identity residual is **8.42e-14**, below 1e-8; national signed cancellation is
not used for acceptance. All run manifests agree for runtime and runner source.
The final country file contains a later three-line `Country.reset` fix clearing
stale D2 state; attribution runs construct fresh simulations and do not call reset.
`postrun_reset_fix.json` verifies this is the only difference (including the
Windows CRLF/git LF hashes). Its regression and all 44 focused tests pass.
Per-arm JSONs retain commit, dirty-tree status, configuration, source SHA-256 and
pickle SHA-256; early HEADs differ because the runner reporting correction and
reset regression were amended into f. The original input pickles were preserved;
the agreed H7 pickle was built under a distinct name.

The full suite uses `serial_test_plugin.py` to set the sampler fixture to one
worker; its test and assertions remain active. The initial partial suite was
stopped after detecting that fixture's default parallelism; only the completed
serial run is used for the final verdict.

Full `tests/` verdict: **381 passed, 30 failed, 2 setup errors, 0 skipped**, in
18m17s. Every one of the 30 failures is exactly
`ValueError: Nan in transactor_total_real_supply`: 29 in `test_simulation.py`
and one in `test_sampler.py`, matching the documented baseline fingerprint.
The two **additional** errors are `TestSectorExoPricesReader.test_read_from_csv`
and `.test_missing_file_returns_none`: Windows denied pytest access to
`AppData/Local/Temp/pytest-of-eizadi`. Both pass in the targeted rerun with
`--basetemp=../.tmp/correction_pytest_temp` (**2 passed**). No model code changed
for that rerun. The original full-suite result and the rerun are both retained;
there are no additional unresolved test failures beyond the known 30.

Full-suite results are in `outputs/household_corrections/full_tests.xml` and
`summary.json`; focused tests passed at every commit as listed above.
Benchmark selections, concepts, dates and hashes are in
[benchmarks/household_corrections/README.md](benchmarks/household_corrections/README.md).
The inherited principal-flow benchmark has no original downloaded snapshot;
that provenance limitation is recorded rather than silently repaired.

Reproduce with the root `../.venv/Scripts/python.exe`, `PYTHONUTF8=1`, this worktree
on `PYTHONPATH`, a short writable `NUMBA_CACHE_DIR`, and read-only `MACROABM_RAW_DATA`.

```text
python dev/io2022/household_prototype/prepare_household_canadianization.py --real --mortgage-method pro_rata --output-dir dev/validation_2022/candidate_agreed
python dev/io2022/household_prototype/prepare_household_consumption.py --real --recipient dev/validation_2022/candidate_agreed/prototype_household.csv --output-dir dev/validation_2022/candidate_agreed
python dev/io2022/build_2022_datawrapper.py --household-csv dev/validation_2022/candidate_agreed/prototype_household_consumption.csv --pickle dev/pkl_files/io2022_household_agreed.pkl --build-only
python dev/validation_2022/run_household_corrections.py --arm iv --quarters 12 --pickle dev/pkl_files/io2022_household_agreed.pkl
python dev/validation_2022/summarise_household_corrections.py
python -m pytest tests/ -q -p dev.validation_2022.serial_test_plugin --basetemp=../.tmp/household_full_suite
```

Use `io2022_phaseA.pkl` for i and the agreed pickle for ii–v/d1/deposit; finish
all 2-quarter arms before 12-quarter arms. Source and results are review material,
not approval of behavioural calibration. Stop here for review.
