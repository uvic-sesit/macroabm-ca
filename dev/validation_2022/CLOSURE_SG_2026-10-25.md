# Closure SG review - 2026-10-25 UTC

Base `2cdf4d6`, branch `feature/validation-2022`. **Neither FS nor FS_T passes every gate: both also fail the short accounting attempt before Q1 completes. Do not promote either input. F_CFC remains the accepted diagnostic baseline.** All independent source, housing and income-concept checks are completed. Step 2 and all dependent twelve-quarter runs are skipped. No gate threshold or behavioural parameter was changed to obtain a pass. No push, Phase B, C_dp_005, investment expansion or new household allocation build.

## Steps, commits and gates

| Step | Commit / verification | Finding / decision |
|---|---|---|
| Independent GDP income assertion | `2ef7a32`; two focused regressions | Fixes the duplicated output/expenditure assertion. Same np.isclose tolerance; genuinely checks output against income. |
| FS / FS_T source build | `1eadde5`; four source-unit/net-surplus regressions; frozen git inputs | Canonical SUT balances independently. Both arms pass all13 regional GDP identities. FS fails cost gate; FS_T removes above-price exceptions but retains floor/tiny-output margin exceptions. |
| Source bookkeeping audit | `dc68b37`; four focused regressions plus exact build assertions | Explicit VA6 stays unchanged; reader-implied VA falls. ROW import counterpart follows the export removal. Only v3 candidates are retained for gates; earlier v1/v2 pickles remain untouched and excluded. |
| Step2 FSG | No build / no run | Depends on a passing Step1 arm. Neither passes the full gate; no scope rescale or GFCF substitution attempted. |
| Step3 housing | Read-only t0 F_CFC and existing CIS candidate | SNA housing services enter cash goods demand; imputed income remains a noncash memo. Exact imputed-purchase attribution is unavailable in mixed sector L; bounds/proxy below. No closure change. |
| Step4 income concept | Read-only CIS PUMF, existing inputs | Candidate max error13.265% before tax,21.153% after tax; empirical progressive-tax diagnostic12.064%. Allocation and PIT both remain specification issues. |
| Step5 | Full suite / source-stock audit / report | 494 passed, 30 failures, 524 cases; sampler one worker. Stop for review. |

Gate results by arm (max margin deviation is percentage points):

| arm | regional_initialization | independent_income | margin_exceptions | max_margin_gap_pp | above_price_exceptions | inherited_floor_exceptions | passed | accounting_passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FS | True | True | 244 | 100.000 | 6 | 29 | False | False |
| FS_T | True | True | 33 | 100.000 | 0 | 29 | False | False |

The unchanged output/expenditure assertion and the corrected income assertion are both exercised in each region. Cost failures are recorded even where they arise in numerically tiny sectors. No exclusion or tolerance change is used to pass an arm. Accounting is an independent short diagnostic, reported below; its success alone cannot override a cost failure.

New inputs, with SHA256 (accepted pickles unchanged):

| arm | source_pickle | sha256 |
| --- | --- | --- |
| FS | io2022_fs_sg_v3_2026_10_25.pkl | 084920b9bc7ca37636c6597464589c01b5260f2167e2d064541600c64752e23d |
| FS_T | io2022_fs_t_sg_v3_2026_10_25.pkl | 460c07739b7554796f467a46269025c2b254584d850f75a6635a0b3a954a5cfc |

## 1. Source verification and t0 bridge

All IO reads use `git show feature/sut-balance:<file>` at **d847fb2e22fee298c7af31803d3ab6543126dda4**, not the working tree. Old comparison blobs are from479dcb4. Both handoff documents, source schema and all input hashes are cached in benchmarks/SG. The requested compatibility hash **41590fdb19d9eb79758169b51afc0751e6d5c19ce88183bb8fbe330889e689aa** is the CRLF byte representation. Git's LF blob has SHA256 **f0004ad3d40e465cceba3d9735d6dda5b00658fe6ca88af5ffed944917a8adb9**; converting only LF to CRLF reproduces the requested hash exactly. Both are recorded; no economic content changed.

Independent CSV identities, not copied pass flags:

- Imported re-exports excluded48.431914B/year, exactly matching the international-export reduction within1.1e-13B. Domestic margin services remain exported (0.661880B including CE; the handoff's approximately0.65B is the13-region scope). Imports in use do not change.
- The canonical output_basic correction is **+26.545927B**, exactly its previously omitted net product taxes on intermediate inputs. The new column already includes these taxes; applying the older FB helper's additional product-tax addend would count them twice. This build uses the reader/source IO sales, not that stale helper.
- Every Canadian region-industry canonical row equals its column: maximum error **0.000004369M**. Production/income/expenditure GDP at basic prices agree regionally, maximum error **0.000005214M**. Recomputed from Z, FD and VA primitives, including CE.
- Observed VA components are byte-equivalent numerically;13-region basic-price GDP remains **2674.182570B**. Compatibility-view reader-implied VA is still **0.122411B below VA6**, the CE boundary; it is reported, not filled.

Compatibility before/after, annual B:

| vintage | reader_sales_B | reader_VA_B | international_exports_B | international_imports_B |
| --- | --- | --- | --- | --- |
| main | 5104.244 | 2722.492 | 965.801 | 902.465 |
| balanced | 5055.812 | 2674.060 | 917.369 | 902.465 |

The explicit industry-vector VA6 field and the firm's residual implied VA are distinct. The former is unchanged, apart from preserved inherited empty-sector floors. The latter falls48.431914B as the fictitious sales disappear. This removes an inflated starting level; it is not evidence of a dynamic no-shock contraction improving. Canonical GDP staying unchanged and model reader-implied GDP falling are consistent statements about different starting accounts.

The new DataWrapper instances clone F_CFC to retain exactly its household/member/job records, employer payroll, deposits, loans, bank capital, installed capital, initial purchases and observed CFC. IO output/export deltas are applied through the50-code concordance, preserving the existing empty-sector floor amounts. Input-productivity and depreciation coefficients are re-expressed in the new output units so physical inputs and CFC amounts stay fixed. International sourcing weights and ROW import counterparts use the new source flow. No population is resampled, new household income created or financial stock rebuilt. Zero-source producers remain contract holders, not forgiven debtors.

FS retains producer-tax amounts. FS_T adds signed D29/D39, **100.503564B/year**, with corresponding government production-tax receipts, the legacy GDP valuation aggregate and corporate-tax/revenue changes. Corporate tax changes follow initial profits; they are not offset with a revenue plug. Exact fiscal deltas are in FS_T_fiscal_bridge.csv.

Province t0 accounts, annual B (explicit VA6 and residual implied VA shown separately):

| arm | region | output_change | old_VA | new_VA | old_implied_VA | new_implied_VA | old_GOS | new_GOS | export_change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FS | CAN_AB | -6.640 | 456.440 | 456.440 | 463.080 | 456.439 | 282.569 | 275.929 | -6.640 |
| FS | CAN_BC | -3.820 | 372.204 | 372.204 | 376.023 | 372.203 | 186.751 | 182.931 | -3.820 |
| FS | CAN_MB | -1.223 | 81.893 | 81.893 | 83.116 | 81.893 | 41.883 | 40.660 | -1.223 |
| FS | CAN_NB | -0.693 | 40.418 | 40.418 | 41.111 | 40.418 | 18.008 | 17.315 | -0.693 |
| FS | CAN_NL | -0.421 | 39.103 | 39.103 | 39.524 | 39.103 | 23.925 | 23.504 | -0.421 |
| FS | CAN_NS | -0.761 | 50.954 | 50.954 | 51.715 | 50.954 | 22.754 | 21.993 | -0.761 |
| FS | CAN_NT | -0.070 | 5.125 | 5.125 | 5.195 | 5.125 | 2.394 | 2.324 | -0.070 |
| FS | CAN_NU | -0.005 | 4.322 | 4.322 | 4.327 | 4.322 | 2.012 | 2.007 | -0.005 |
| FS | CAN_ON | -23.808 | 987.791 | 987.791 | 1011.477 | 987.669 | 450.206 | 426.398 | -23.808 |
| FS | CAN_PE | -0.108 | 8.605 | 8.605 | 8.713 | 8.605 | 4.181 | 4.074 | -0.108 |
| FS | CAN_QC | -9.626 | 512.824 | 512.824 | 522.449 | 512.823 | 223.912 | 214.287 | -9.626 |
| FS | CAN_SK | -1.231 | 110.791 | 110.791 | 112.022 | 110.791 | 75.950 | 74.719 | -1.231 |
| FS | CAN_YT | -0.026 | 3.743 | 3.743 | 3.770 | 3.743 | 1.636 | 1.610 | -0.026 |
| FS_T | CAN_AB | -6.640 | 456.440 | 456.440 | 463.080 | 456.439 | 282.569 | 265.333 | -6.640 |
| FS_T | CAN_BC | -3.820 | 372.204 | 372.204 | 376.023 | 372.203 | 186.751 | 168.680 | -3.820 |
| FS_T | CAN_MB | -1.223 | 81.893 | 81.893 | 83.116 | 81.893 | 41.883 | 37.520 | -1.223 |
| FS_T | CAN_NB | -0.693 | 40.418 | 40.418 | 41.111 | 40.418 | 18.008 | 15.927 | -0.693 |
| FS_T | CAN_NL | -0.421 | 39.103 | 39.103 | 39.524 | 39.103 | 23.925 | 22.974 | -0.421 |
| FS_T | CAN_NS | -0.761 | 50.954 | 50.954 | 51.715 | 50.954 | 22.754 | 20.536 | -0.761 |
| FS_T | CAN_NT | -0.070 | 5.125 | 5.125 | 5.195 | 5.125 | 2.394 | 2.233 | -0.070 |
| FS_T | CAN_NU | -0.005 | 4.322 | 4.322 | 4.327 | 4.322 | 2.012 | 1.983 | -0.005 |
| FS_T | CAN_ON | -23.808 | 987.791 | 987.791 | 1011.477 | 987.669 | 450.206 | 381.579 | -23.808 |
| FS_T | CAN_PE | -0.108 | 8.605 | 8.605 | 8.713 | 8.605 | 4.181 | 3.992 | -0.108 |
| FS_T | CAN_QC | -9.626 | 512.824 | 512.824 | 522.449 | 512.823 | 223.912 | 192.198 | -9.626 |
| FS_T | CAN_SK | -1.231 | 110.791 | 110.791 | 112.022 | 110.791 | 75.950 | 72.730 | -1.231 |
| FS_T | CAN_YT | -0.026 | 3.743 | 3.743 | 3.770 | 3.743 | 1.636 | 1.565 | -0.026 |

Largest affected industries, FS_T annual B; full50-industry and650 region-industry tables are retained:

| industry | output_change | old_implied_VA | new_implied_VA | old_GOS | new_GOS | export_change |
| --- | --- | --- | --- | --- | --- | --- |
| C29 | -9.807 | 24.756 | 14.949 | 12.448 | 2.217 | -9.807 |
| C28 | -7.584 | 28.381 | 20.797 | 14.957 | 7.106 | -7.584 |
| C26 | -5.545 | 13.836 | 8.290 | 8.262 | 2.621 | -5.545 |
| C302T309 | -4.779 | 14.436 | 9.657 | 7.046 | 2.064 | -4.779 |
| C21 | -3.228 | 10.073 | 6.846 | 6.318 | 2.858 | -3.228 |
| C31T33 | -2.632 | 13.987 | 11.355 | 5.053 | 2.299 | -2.632 |
| C20 | -2.507 | 20.603 | 18.096 | 13.513 | 9.947 | -2.507 |
| C27 | -2.324 | 6.897 | 4.573 | 3.295 | 0.887 | -2.324 |
| C25 | -2.083 | 21.729 | 19.646 | 7.798 | 5.494 | -2.083 |
| C13T15 | -1.690 | 4.566 | 2.876 | 2.574 | 0.842 | -1.690 |
| C19 | -1.247 | 24.586 | 23.339 | 21.814 | 20.248 | -1.247 |
| C10T12 | -1.003 | 44.199 | 43.196 | 20.066 | 18.279 | -1.003 |

Earlier F_CFC loss industries, **historical seeds0-2 mean over12 quarters**, alongside FS_T t0 changes (B; not new loss outcomes):

| industry_code | historic_loss_B | output_change | old_GOS | new_GOS |
| --- | --- | --- | --- | --- |
| G | 24.604 | -0.253 | 101.758 | 97.443 |
| F | 22.295 | -0.001 | 76.289 | 65.216 |
| C10T12 | 8.260 | -1.003 | 20.066 | 18.279 |
| C19 | 7.528 | -1.247 | 21.814 | 20.248 |
| J62_63 | 6.515 | 0.000 | 15.373 | 14.288 |
| H51 | 4.975 | 0.000 | 2.026 | 1.910 |
| J58T60 | 4.069 | -0.070 | 5.123 | 7.616 |
| C31T33 | 3.765 | -2.632 | 5.053 | 2.299 |
| A02 | 3.571 | -0.003 | 3.309 | 3.233 |
| I | 3.566 | 0.000 | 12.240 | 13.303 |
| C25 | 2.932 | -2.083 | 7.798 | 5.494 |
| C24B | 2.637 | -0.581 | 8.006 | 6.423 |

The export correction most strongly reduces C29/C28/C26/C302T309/C21, whereas historical losses are concentrated in G/F and several manufacturing/services sectors. G/F output hardly changes; FS_T's signed producer taxes still change their margins. Utilities and other previously flagged revaluation losses cannot be declared cured from this static bridge.

### Unchanged regional GDP checks and net-surplus failures

GDP levels B/quarter; residuals CAD/quarter:

| arm | region | passed | output | expenditure | income | expenditure_gap | income_gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FS | CAN_NL | True | 10.100 | 10.100 | 10.100 | 0.000 | 0.000 |
| FS | CAN_PE | True | 2.251 | 2.251 | 2.251 | 0.000 | 0.000 |
| FS | CAN_NS | True | 13.356 | 13.356 | 13.356 | 0.000 | -0.000 |
| FS | CAN_NB | True | 10.616 | 10.616 | 10.616 | 0.000 | -0.000 |
| FS | CAN_QC | True | 133.099 | 133.099 | 133.099 | -0.000 | 0.000 |
| FS | CAN_ON | True | 256.950 | 256.950 | 256.950 | 0.000 | -0.000 |
| FS | CAN_MB | True | 21.565 | 21.565 | 21.565 | 0.000 | -0.000 |
| FS | CAN_SK | True | 28.901 | 28.901 | 28.901 | 0.000 | -0.000 |
| FS | CAN_AB | True | 117.705 | 117.705 | 117.705 | 0.000 | 0.000 |
| FS | CAN_BC | True | 97.999 | 97.999 | 97.999 | 0.000 | 0.000 |
| FS | CAN_YT | True | 0.980 | 0.980 | 0.980 | 0.001 | 0.000 |
| FS | CAN_NT | True | 1.337 | 1.337 | 1.337 | 0.000 | 0.000 |
| FS | CAN_NU | True | 1.118 | 1.118 | 1.118 | 0.001 | 0.000 |
| FS_T | CAN_NL | True | 10.100 | 10.100 | 10.100 | 0.000 | 0.000 |
| FS_T | CAN_PE | True | 2.251 | 2.251 | 2.251 | 0.000 | 0.000 |
| FS_T | CAN_NS | True | 13.356 | 13.356 | 13.356 | 0.000 | -0.000 |
| FS_T | CAN_NB | True | 10.616 | 10.616 | 10.616 | 0.000 | -0.000 |
| FS_T | CAN_QC | True | 133.099 | 133.099 | 133.099 | -0.000 | 0.000 |
| FS_T | CAN_ON | True | 256.950 | 256.950 | 256.950 | 0.000 | -0.000 |
| FS_T | CAN_MB | True | 21.565 | 21.565 | 21.565 | 0.000 | -0.000 |
| FS_T | CAN_SK | True | 28.901 | 28.901 | 28.901 | 0.000 | -0.000 |
| FS_T | CAN_AB | True | 117.705 | 117.705 | 117.705 | 0.000 | 0.000 |
| FS_T | CAN_BC | True | 97.999 | 97.999 | 97.999 | 0.000 | 0.000 |
| FS_T | CAN_YT | True | 0.980 | 0.980 | 0.980 | 0.001 | 0.000 |
| FS_T | CAN_NT | True | 1.337 | 1.337 | 1.337 | 0.000 | 0.000 |
| FS_T | CAN_NU | True | 1.118 | 1.118 | 1.118 | 0.001 | 0.000 |

FS has244 margin exceptions and6 above-price/nonnegative-observed-NOS exceptions. FS_T has33 margin exceptions and **zero** above-price exceptions. Of its33,29 are inherited1M/year empty-sector floors with zero observed GOS. The other four are source-zero cells carrying only floating-point remnants (CAD/quarter):

| region | industry | new_output | margin_gap_pp |
| --- | --- | --- | --- |
| CAN_NL | C19 | 0.025 | 100.000 |
| CAN_NB | C24A | 0.010 | 100.000 |
| CAN_NT | C25 | 0.001 | 100.000 |
| CAN_NU | C29 | 0.001 | 100.000 |

These are not economically large margin errors, but the stated universal gate still fails. On non-floor cells with more than1M/quarter output, FS_T's maximum error is 0.077804pp. That is an additional diagnostic, **not a replacement threshold**. A future decision must specify the accounting/holding treatment of source-zero producer records and their inherited floor output. No new basket, fictitious buyer, deleted debt, zero-sector override or threshold adjustment was introduced here.

The old FB expenditure bridge's74.883B/year imbalance is removed at the model initialization level: IO sales and exports now change together, and both regional GDP tests pass. Observed/source income still differs at the documented CE/floor boundaries. Thus the broad GDP bridge is repaired, but the full adoption gate is not passed.

### Short accounting gate

Two-quarter seed0 diagnostics only, run after the one-worker suite, one at a time. These do not authorize twelve-quarter runs:

| arm | exit_code | passed | max_accounting_error | seconds |
| --- | --- | --- | --- | --- |
| FS | 1 | False | None | 50.640 |
| FS_T | 1 | False | None | 30.740 |

**Both fail before Q1 completes**, with `Household cash budget requires finite settled cash and senior payments`; the1e-8 accounting battery is not reached. These failures are separate from the30 known full-suite test failures. Two additional seed0 read-only failure replays preserve the same failure and do not change economic values.

The completed first-failure probe identifies **CAN_NL C21** (industry14): balanced-SUT output is zero after removal of6.694M/year of imported re-export sales. Its initial labour-productivity baseline becomes zero while the legacy job/contract holder remains. Runtime labour_productivity_factor, labour_productivity, labour_inputs and production become nonfinite; current employee income is nonfinite for one model individual at that firm, and the wages component of settled receipts is nonfinite for one model household. Other stored household income components and D2 plans remain finite. `labour_productivity.py:149` divides the production target by raw labour input times industry productivity without a zero-denominator branch; `firms.py:780-794` propagates that factor into labour and production. This is a zero-activity runtime boundary exposed by the data correction, not evidence that the household budget needs a higher limit. Exact aggregate traces are in first_nonfinite_budget_probe_complete.json. No cash replacement, positive productivity floor or producer restructuring is applied after failure. A defined zero-activity holder path/zero-over-zero convention, regression-tested with contracts preserved, is needed before another adoption attempt.

Exact traces and attempted commands are preserved. No failed run is labelled an accounting pass. Neither an accounting failure nor a cost failure is repaired by parameter tuning.

## 2. GFCF dependency

No FSG pickle or twelve-quarter run was created. A passing Step1 input is required. The future split must preserve the balanced IO product column and distinguish business, government, NPISH and residential/household GFCF;36-10-0096 supplies investing-industry shares, not a second incompatible regional total. The legacy reader also folds inventory change into fixed capital formation, which must be kept separate from a concept-matched gross-fixed-investment target. No full IO GFCF total is silently relabelled business investment here. Lambda/gamma and the expansion rule are unchanged.

## 3. Housing cash/SNA consistency - read-only

Code trace:

| Link | File:line | Consequence |
|---|---|---|
| Provincial L HFCE not reduced for imputed housing | macro_data/readers/default_readers.py:515 | Unlike the global ICIO path, paid and imputed housing services remain in L household IO demand. |
| Imputed-rent total and owner allocation | macro_data/processing/synthetic_country.py:314; macro_data/configuration/can_2022_constants.py:3 | Initial memo235.938B/year comes from36-10-0124 imputed housing; owners receive the memo, not a cash receipt. |
| SNA HFCE consumption calibration | macromodel/country/household_closure.py:378; macromodel/configurations/household_closure_configuration.py:50 | Consumption target1511.382B/year is36-10-0112 v62305982 and includes noncash services. |
| Goods demand, all sectors including L | macromodel/agents/households/households.py:673; macromodel/agents/households/func/consumption.py:184 | Income/propensity generates a goods basket without a separate owner-imputed-rent exclusion. D caps this basket as cash spending. |
| D1 narrow rent offset | macromodel/country/household_closure.py:12 | Removes only renters' L demand up to actual household-landlord rent, without removing all L or owner imputed housing. |
| Cash income and landlord receipts | macromodel/agents/households/households.py:532 and619 | Rental cash income is actual non-owner-occupied rent after PIT. Owner-imputed memo is absent from cash income. |
| Memo calculation | macromodel/agents/households/households.py:977 | Owners' rent_imputed tracked separately; no self-payment. |
| Cash debit on realized goods purchases | macromodel/agents/households/households.py:1241 and1330 | Realized L purchases join nominal_amount_spent_in_lcu and reduce financial resources; imputed memo itself is not an additional debit. |
| IH GDP scope | macromodel/economy/economy_ts.py:201 and282; macromodel/country/country.py:431 | Prevents re-adding paid/imputed memo rents on top of IO housing in initial GDP. It does not repair the household cash basket. |

Goods-market L purchases are cash sales to sector L firms; those firms bear their usual inputs/costs. Actual private rent is a separate household-to-household cash flow. Imputed rent is neither paid to landlords nor booked as an owner cash income. Planned and realized L quantities have no subcategory identifying housing versus other real-estate services, nor an owner-specific noncash purchase. Consequently **the exact imputed rent inside any household's L purchase is not identifiable** from current model state.

[StatCan's income-account guide](https://www150.statcan.gc.ca/n1/pub/13-606-g/2016001/article/14620-eng.htm) includes implicit owner housing income in the rental component of mixed income; its [rental-income methodology](https://www150.statcan.gc.ca/n1/pub/13-017-x/2008001/themes/ch05/5213352-eng.htm) distinguishes gross rental output and net rental income. This supports a missing noncash counterpart, but does not establish that the full127.6B mixed-income gap equals gross imputed rent. Operating expenses, CFC and housing scope must be bridged. No235.938B cash receipt is invented to close that gap.

Annual B and percentage shares at t0:

| arm | C | DI | gap | imputed_memo | owner_L | memo_proxy | gap_after_memo_proxy | gap_after_all_owner_L_removed | C_dissaver_share | C_memo_proxy_dissaver_share | C_all_owner_L_removed_dissaver_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_CFC | 1564.269 | 1468.386 | 95.884 | 235.938 | 254.400 | 157.046 | -61.163 | -158.516 | 71.941 | 42.054 | 37.724 |
| CIS_candidate | 1555.905 | 1468.386 | 87.519 | 235.938 | 247.597 | 162.121 | -74.602 | -160.078 | 70.100 | 38.556 | 34.348 |

The88B figure belongs to the unaccepted CIS candidate (gap87.519B,70.10% planned dissavers); accepted F_CFC has95.884B and71.94%. The gross235.938B imputed memo is larger than either gap, but is not a measured amount charged to these households as cash. Owner L demand provides an upper bound. The explicit attribution proxy removes **min(owner L planned cash, owner imputed memo)**; it is a read-only bound/proxy, not a fitted allocation or implemented closure. In the candidate it removes162.121B, changes the aggregate gap to **-74.602B**, and reduces planned dissavers to **38.56%** (31.54pp reduction). Even the extreme removal of all owner L leaves34.35% as planned dissavers. A substantial non-housing income/spending issue therefore remains. Renters also buy the mixed L bundle; these diagnostics do not identify imputed housing inside their purchases.

Tenure and after-tax CIS-income decile detail, annual B and percentages:

| arm | decile | tenure | households | C | DI | gap | planned_L | imputed_memo | memo_proxy_removed | dissaver_pct | proxy_dissaver_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F_CFC | 1 | owner | 673000.000 | 17.827 | 8.415 | 9.412 | 3.879 | 13.151 | 3.876 | 99.703 | 97.771 |
| F_CFC | 1 | renter_or_other | 876000.000 | 23.897 | 10.919 | 12.978 | 4.057 | 0.000 | 0.000 | 100.000 | 100.000 |
| F_CFC | 2 | owner | 961280.000 | 29.385 | 18.874 | 10.511 | 6.418 | 20.010 | 6.398 | 94.070 | 69.164 |
| F_CFC | 2 | renter_or_other | 588560.000 | 18.544 | 11.767 | 6.777 | 2.883 | 0.000 | 0.000 | 98.129 | 98.129 |
| F_CFC | 3 | owner | 979200.000 | 35.243 | 27.372 | 7.871 | 7.773 | 20.576 | 7.741 | 83.116 | 40.228 |
| F_CFC | 3 | renter_or_other | 570190.000 | 20.336 | 16.600 | 3.736 | 3.311 | 0.000 | 0.000 | 87.183 | 87.183 |
| F_CFC | 4 | owner | 935970.000 | 41.119 | 36.249 | 4.870 | 8.929 | 20.406 | 8.858 | 71.270 | 17.776 |
| F_CFC | 4 | renter_or_other | 614690.000 | 27.184 | 24.527 | 2.657 | 4.089 | 0.000 | 0.000 | 68.454 | 68.454 |
| F_CFC | 5 | owner | 984200.000 | 55.183 | 51.854 | 3.329 | 11.957 | 20.374 | 11.537 | 63.047 | 6.916 |
| F_CFC | 5 | renter_or_other | 564650.000 | 31.614 | 30.250 | 1.365 | 4.826 | 0.000 | 0.000 | 53.554 | 53.554 |
| F_CFC | 6 | owner | 963760.000 | 70.986 | 66.960 | 4.025 | 15.459 | 19.656 | 14.121 | 67.366 | 8.825 |
| F_CFC | 6 | renter_or_other | 586590.000 | 43.104 | 41.576 | 1.528 | 7.179 | 0.000 | 0.000 | 57.284 | 57.284 |
| F_CFC | 7 | owner | 1046790.000 | 100.676 | 96.207 | 4.469 | 21.815 | 23.330 | 17.582 | 66.109 | 10.892 |
| F_CFC | 7 | renter_or_other | 502810.000 | 47.925 | 46.217 | 1.708 | 8.472 | 0.000 | 0.000 | 55.291 | 55.291 |
| F_CFC | 8 | owner | 1145740.000 | 145.841 | 139.995 | 5.846 | 31.750 | 27.189 | 22.050 | 67.992 | 14.140 |
| F_CFC | 8 | renter_or_other | 403610.000 | 50.631 | 49.764 | 0.868 | 9.281 | 0.000 | 0.000 | 50.546 | 50.546 |
| F_CFC | 9 | owner | 1216520.000 | 215.282 | 207.783 | 7.499 | 47.387 | 30.185 | 26.833 | 68.393 | 16.358 |
| F_CFC | 9 | renter_or_other | 334010.000 | 58.318 | 57.380 | 0.938 | 11.271 | 0.000 | 0.000 | 50.304 | 50.304 |
| F_CFC | 10 | owner | 1283940.000 | 446.716 | 440.466 | 6.250 | 99.033 | 41.060 | 38.051 | 57.951 | 17.914 |
| F_CFC | 10 | renter_or_other | 265810.000 | 84.460 | 85.211 | -0.751 | 16.996 | 0.000 | 0.000 | 43.640 | 43.640 |
| CIS_candidate | 1 | owner | 790850.000 | 20.192 | 11.374 | 8.818 | 4.323 | 18.394 | 4.319 | 93.924 | 79.996 |
| CIS_candidate | 1 | renter_or_other | 758070.000 | 19.929 | 10.779 | 9.150 | 3.629 | 0.000 | 0.000 | 99.207 | 99.207 |
| CIS_candidate | 2 | owner | 884960.000 | 32.535 | 24.147 | 8.388 | 7.130 | 16.831 | 7.072 | 86.082 | 51.558 |
| CIS_candidate | 2 | renter_or_other | 665420.000 | 24.361 | 18.598 | 5.762 | 4.141 | 0.000 | 0.000 | 91.846 | 91.846 |
| CIS_candidate | 3 | owner | 910190.000 | 41.433 | 34.792 | 6.641 | 8.995 | 18.994 | 8.899 | 78.851 | 27.377 |
| CIS_candidate | 3 | renter_or_other | 639170.000 | 28.656 | 24.861 | 3.794 | 4.560 | 0.000 | 0.000 | 78.000 | 78.000 |
| CIS_candidate | 4 | owner | 953480.000 | 52.114 | 46.904 | 5.210 | 11.288 | 19.603 | 10.944 | 70.339 | 14.801 |
| CIS_candidate | 4 | renter_or_other | 596600.000 | 32.763 | 30.005 | 2.758 | 5.143 | 0.000 | 0.000 | 63.969 | 63.969 |
| CIS_candidate | 5 | owner | 1007740.000 | 66.893 | 62.168 | 4.725 | 14.618 | 20.659 | 13.644 | 67.321 | 9.237 |
| CIS_candidate | 5 | renter_or_other | 541490.000 | 35.773 | 34.173 | 1.600 | 5.804 | 0.000 | 0.000 | 57.473 | 57.473 |
| CIS_candidate | 6 | owner | 1017870.000 | 82.020 | 77.941 | 4.080 | 17.897 | 22.968 | 15.952 | 66.728 | 7.762 |
| CIS_candidate | 6 | renter_or_other | 531560.000 | 42.775 | 41.124 | 1.651 | 7.531 | 0.000 | 0.000 | 58.912 | 58.912 |
| CIS_candidate | 7 | owner | 1063030.000 | 105.238 | 100.994 | 4.244 | 23.050 | 23.712 | 18.408 | 65.107 | 10.163 |
| CIS_candidate | 7 | renter_or_other | 487160.000 | 48.104 | 46.791 | 1.313 | 8.620 | 0.000 | 0.000 | 52.350 | 52.350 |
| CIS_candidate | 8 | owner | 1111380.000 | 138.776 | 133.201 | 5.575 | 30.428 | 26.795 | 21.326 | 65.150 | 15.749 |
| CIS_candidate | 8 | renter_or_other | 438110.000 | 54.328 | 53.196 | 1.132 | 9.915 | 0.000 | 0.000 | 53.188 | 53.188 |
| CIS_candidate | 9 | owner | 1179940.000 | 195.849 | 189.897 | 5.952 | 43.153 | 29.285 | 25.560 | 66.191 | 15.001 |
| CIS_candidate | 9 | renter_or_other | 369780.000 | 60.614 | 60.275 | 0.339 | 11.485 | 0.000 | 0.000 | 47.866 | 47.866 |
| CIS_candidate | 10 | owner | 1270960.000 | 393.060 | 386.387 | 6.674 | 86.716 | 38.696 | 35.997 | 60.034 | 16.602 |
| CIS_candidate | 10 | renter_or_other | 279560.000 | 80.492 | 80.778 | -0.286 | 16.317 | 0.000 | 0.000 | 42.925 | 42.925 |

The model currently has tenure1 for owners,3 for renters and-1 for other/social households; the probe follows the runtime owner category. Planned dissaving holds t0 income and the rule fixed; it is not a longitudinal insolvency estimate. Realized consumption is rationed/market-cleared; no new realized path is inferred from this static exercise.

The exact accepted imputed-rent vintage is independently recovered from cached36-10-0124 DBnomics series1.1.1.18:2022 quarterly values57441/58553/59397/60547M sum to235938M. The cache was indexed2026-09-30; source/extract hashes and dimensions are frozen. This series ID is not a native StatCan v-number. The native vector is absent from the legacy cache; attempts to retrieve the official bulk file failed (closed connection / timeout), so native-vector provenance remains explicitly unavailable. No number or identifier was guessed, and no later vintage substituted.

Options, for approval only:

1. **Cash-consistent closure (recommended for the declared cash model).** Identify the housing-service part of L and allocate own-use services to actual owners. Remove that component from both the cash purchase basket and the cash consumption benchmark; retain matched noncash income/use memos and the correct producer/input/CFC accounts. Simple national scope arithmetic gives1511.382-235.938=1275.444B/year before further cash/VAT/rent-boundary reconciliation; that is not a new calibrated target. Paid rent and other L services stay cash. Do not delete the whole L sector or add a costless housing producer.
2. **Matched noncash SNA layer.** Separate owner own-use production/consumption and its income counterpart with net cash zero. Keep it outside deposit budgets, bank receipts, credit screens, PIT and the cash-saving statistic. Record intermediate costs/CFC and ownership consistently. Merely adding cash income or a memo to the current cash goods purchases would not solve the problem.

Neither option is implemented. The housing specification should precede a buffer-stock spending rule or a claim that the propensity itself is the main error.

## 4. CIS before-tax comparison and progressive PIT - read-only

Same CIS2022 PUMF household units as HI: unique EFID family income summed once into PUMFID, household FWEIGHT, unequivalised households, nominal2022 CAD. Before-tax total income is EFATINC+EFINCTX, ranked anew by before-tax income. After-tax ranks are separate; the frozen HI after-tax benchmark is retained exactly to avoid floating-point tied-record differences at decile cutoffs. These custom tabulations have no published vector IDs; source PUMF SHA is in household_provenance.json. Territory/coverage and model income-concept limitations remain.

Model before-tax income adds actual public transfers to reconstructed gross wages and grossed-up funded mixed/property/private-pension/corporate receipts. Employee CPP/EI is separately added back for the CIS after-tax bridge, as in HI; loan interest is excluded from the CIS comparison. Public transfers are not all subject to the model's flat PIT. **Flat PIT therefore does not make model before- and after-tax shares identical**, even though it lacks the observed progressive compression. No receipts are changed.

[StatCan's2022 CIS release](https://www150.statcan.gc.ca/n1/daily-quotidien/240426/dq240426a-eng.htm) defines after-tax income from market income and public transfers less income tax. The [CIS PUMF catalogue](https://www150.statcan.gc.ca/n1/en/catalogue/72M0003X) is the primary source. The empirical diagnostic uses its observed combined income taxes EFINCTX divided by total household income within each gross-income decile. This captures combined federal/provincial incidence, not statutory brackets or a provincial tax-return microsimulation. Applying those rates by model gross-income rank is an explicit descriptive assumption, not a fitted schedule. It includes the source population's credits/composition; this uncertainty is material.

Summary (share gaps are relative%, not differences in dollar levels):

| arm | concept | max_absolute_relative_gap_pct | top_share_pct | CIS_top_share_pct | top_relative_gap_pct |
| --- | --- | --- | --- | --- | --- |
| CIS_candidate | after_tax | 21.153 | 31.754 | 26.210 | 21.153 |
| CIS_candidate | before_tax | 13.265 | 32.481 | 28.994 | 12.024 |
| CIS_candidate | empirical_progressive_read_only | 12.064 | 29.346 | 26.210 | 11.965 |
| F_CFC | after_tax | 41.486 | 35.630 | 26.210 | 35.939 |
| F_CFC | before_tax | 38.731 | 36.269 | 28.994 | 25.090 |
| F_CFC | empirical_progressive_read_only | 37.250 | 33.059 | 26.210 | 26.130 |

Effective rates applied, fractions:

| decile | effective_PIT |
| --- | --- |
| 1 | 0.016 |
| 2 | 0.042 |
| 3 | 0.070 |
| 4 | 0.095 |
| 5 | 0.113 |
| 6 | 0.132 |
| 7 | 0.149 |
| 8 | 0.163 |
| 9 | 0.186 |
| 10 | 0.261 |

For the CIS candidate, comparing before tax reduces the maximum discrepancy from21.153% to13.265%, but still fails10%. Empirical progression reduces the after-tax maximum to12.064% (9.089 percentage points, about43% of the original maximum); the top-share error falls from21.153% to11.965%. It does not pass the unchanged HI gate or cure the remaining household/member/employer support mismatch. For F_CFC, maximum error remains37.250% after the counterfactual. The diagnostic is not a new accepted tax rule.

Counterfactual national annual flows, B; no rescale to preserve taxes or DI:

| arm | flat_PIT | counterfactual_PIT | before_tax_income | counterfactual_after_tax_income |
| --- | --- | --- | --- | --- |
| F_CFC | 262.278 | 334.225 | 1786.056 | 1451.832 |
| CIS_candidate | 262.278 | 320.713 | 1786.056 | 1465.344 |

All decile raw annual levels and shares, separately ranked, are in CIS_concepts.csv. No new household build or progressive PIT implementation. A proper proposal must specify federal and provincial schedules, taxable components, credits/refunds, benefit interactions and fiscal counterparties using household/member records; income-decile rates alone are not such a specification.

## 5. Dynamic comparison, tests and next priorities

No arm passed all Step1 gates, hence no new seeds0-2 twelve-quarter results or FSG comparison exist. Demand spiral, constrained-share paths, investment, losses and recapitalisations cannot be declared improved. Historical IH F_CFC numbers below are **references only**, not new runs:

| seed | GDP_Q0_Q12_pct | GDP_Q1_Q12_pct | household_loss_B | firm_loss_B | overdraft_loss_B | bank_loss_B | recapitalisation_B | Q12_constrained_pct | Q12_HH_investment_B | Q12_firm_investment_B | Q12_employment |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | -7.594 | -6.562 | 233.541 | 54.106 | 30.266 | 317.913 | 165.205 | 50.374 | 29.219 | 88.881 | 18206890.000 |
| 1 | -8.907 | -9.794 | 233.594 | 102.062 | 36.791 | 372.446 | 199.720 | 50.072 | 32.133 | 85.133 | 17839920.000 |
| 2 | -17.400 | -16.074 | 233.240 | 66.091 | 25.289 | 324.620 | 99.958 | 49.647 | 27.313 | 72.144 | 16946630.000 |

Full suite through run_pre_D3_tests.py: **494 passed, 30 failures, 524 cases; sampler one worker**. Exact failure IDs match HI's known30 NaN cases; additional failures **zero**. Four source/cost regressions and two independent GDP regressions pass focused checks; the strengthened explicit-VA assertion is separately rerun after source bookkeeping completion. Accepted input hashes, final v3 build stock/flow checks, source git blobs and run ordering are audited. Earlier v1/v2 data builds are excluded (ROW counterpart / explicit VA6 bookkeeping), retained under their original names, and never iterated.

Recommended order for the next decision: specify a cash/noncash housing split first; finish a traceable household rebuild retaining original household/member/donor IDs; specify progressive PIT alongside that rebuild and test both gross and net concepts; resolve the tiny/source-zero producer holding convention before adopting FS_T. Only after these account boundaries pass should an investment expansion specification be selected. A future desired-capital term must confront the capacity-censored demand signal, not simply raise an accelerator weight. Buffer-stock consumption remains deferred; it cannot substitute for correctly identified cash resources. Phase B remains on hold. Stop for review.
