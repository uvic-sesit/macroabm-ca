# Four checks before D3 — 22 October 2026, local time

D3 is **on hold**. Substantial write-offs survive the mechanical fixes, but the
diagnostics do not establish that D3 is the appropriate remedy. The initial
consumption/income mismatch, automatic overdrafts, collateral treatment in the
old insolvency rule and invalid bank-capital initialization need separate review.
Phase B and C_dp_005 have not started. Work remains on `feature/validation-2022`;
no push, original-repository edit, ITC/user-cost edit or pickle change.

This report supersedes the earlier recommendation to retain D3 merely because
arm iv had large write-offs. Dollar amounts are CAD billions unless stated.
`b1` denotes the original b1b2960 behaviour with read-only instrumentation;
`fixed` adds the obligation-screen correction only; **`final` adds the liability
bookkeeping correction as well**. The bank reader correction protects future
builds; it does not change the serialized input used in any of these runs.

## Findings and decisions

| Check | Finding | Fix commit | Decision needed |
|---|---|---|---|
| 1: starting income and Q1 cohort | Q1 saving gap is predominantly consumption; most cancelled debt belongs to households already having negative net worth at t0, though nonnegative deposits | No residual income plug; 37cf590 synchronizes household liabilities after cancellation | Consistent initial income/consumption closure and treatment of recoverable collateral |
| 2: new D4 loans | Existing overdraft principal/interest and consumer debt-service capacity were incompletely screened; automatic overdrafts remain outside origination limits | d7a2110, regression tests | Explicit overdraft facility, limit and arrears policy; no blanket prohibition imposed |
| 3: firm payouts and bank capital | Q9 spike is mostly utilities and accommodation/food failures; payout cash cap works; every region starts with a national bank-capital amount, from the wrong financial-account concept | 59a37ef fixes omitted regional multiplier only | Canadian book-equity benchmark/bank boundary and fresh validation input; retained-profit/cash-reserve payout policy |
| 4: sector L | Final seed 0: sales -0.7%, essentially fixed quantity/employment. Final D1 seeds 1/2 fail bank-resolution accounting; original-path decomposition below | Diagnostic instrumentation only | Cross-seed acceptance blocked; keep narrow D1 opt-in, no wider producer boundary |

## Commits and reproducibility

| Commit | Change | Focused validation tests |
|---|---|---:|
| 5ea5807 | Read-only cohort, lending-vintage, firm and bank instrumentation | Exact two-quarter replay of earlier arm iv |
| d7a2110 | Include overdraft principal/interest and consumer service in D4 screens | 49 |
| 59a37ef | Apply regional share to both bank-equity reader return paths | 51 |
| 37cf590 | Refresh household debt and net worth when the old rule cancels loans; trigger unchanged | 52 |
| 94a956b | Domestic L buyer panels, summary/audit tools and isolated baseline replay | Read-only artifact checks |

All household diagnostic simulations were serial, with 13 Canadian regions. Two-quarter iv/v accounting
checks precede the final 12-quarter runs. No calibration or new behavioural cap
was introduced. Each run manifest records source hashes, seed, HEAD, input hash
and accounting error. Exact input SHA256 is
`3b48c0dba90c2d3c837f92bc0477e4b242ba0afa78275b095e26cc52b4fcb313`.
Read-only baseline instrumentation replayed the prior two-quarter GDP/write-offs
to less than one cent. Baseline labels reflect model behaviour, not the manifest
HEAD, which also contains instrumentation.

Individual borrower/cohort records remain local in ignored `micro/` directories.
Their hashes and the aggregate panels appear in
[result_manifest.json](outputs/pre_D3_checks/result_manifest.json). These are
synthetic model records. The panel files, rather than rounded tables, are the
numerical record.

Raw run CSV stocks/flows are CAD for the represented model agents; aggregate
columns ending `_B` are billions. The origination audit's `_per_household_CAD`
columns divide by the regional representation factor. Report tables use billions
unless a per-household or employment unit is stated.

## 1. Household income, spending and the starting cohort

Comparison uses annualized model Q1 cash flows against the mean of the four 2022
seasonally adjusted annual-rate observations in
[36-10-0112](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201),
with property detail from annual
[36-10-0482](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610048201).
The retained extracts/provenance are under `benchmarks/household_corrections/`.
That downloaded vintage is dated 23 October UTC, which was 22 October locally.
The line bridge is an accounting/concept comparison, not a seasonally fitted
simulation or a claim that noncash SNA receipts are available for spending.
Rental income belongs to mixed income in SNA; it is separated here for clarity.
Gaps are model minus benchmark, in $B/year; expense gaps are not sign-reversed.
The following initial snapshot and Q1 use original arm iv as requested.

| line | t0 | Q1 annualized | 2022 benchmark | Q1 gap | table | vector |
|---|---|---|---|---|---|---|
| compensation | 1,386.338 | 1,374.048 | 1,378.529 | -4.481 | 36-10-0112 | v62305952 |
| nonrental mixed income | 0.000 | 96.738 | 97.274 | -0.536 | 36-10-0112 | v62305955 minus v62305958 |
| rental income (cash model / net actual+imputed SNA) | 16.502 | 16.501 | 127.567 | -111.066 | 36-10-0112 | v62305958 |
| deposit interest received | 6.777 | 30.021 | 17.779 | 12.242 | 36-10-0482 | v80013650 |
| other direct interest received | 0.000 | 0.000 | 11.364 | -11.364 | 36-10-0482 | v80013651 |
| pension/insurance/implicit interest received | 0.000 | 0.000 | 87.818 | -87.818 | 36-10-0482 | v80013649 minus v80013650 minus v80013651 |
| dividends | 0.000 | 92.052 | 92.052 | -0.000 | 36-10-0482 | v80013659 |
| foreign/miscellaneous property income | 0.000 | 0.000 | 37.575 | -37.575 | 36-10-0482 | v80013660 plus v80013661 |
| government transfers | 256.324 | 252.408 | 286.670 | -34.262 | 36-10-0112 | v62305967 |
| corporate transfers | 0.000 | 120.911 | 121.500 | -0.589 | 36-10-0112 | v62305966 |
| NPISH/nonresident transfers | 0.000 | 0.000 | 14.354 | -14.354 | 36-10-0112 | v62305965 plus v62305971 |
| personal income taxes | 208.318 | 260.288 | 348.148 | -87.860 | 36-10-0112 | v62305976 |
| government social contributions | 202.916 | 200.980 | 131.280 | 69.700 | 36-10-0112 | v62305978 |
| other current transfers paid | 0.000 | 0.000 | 206.503 | -206.503 | 36-10-0112 | v62305972 minus v62305976 minus v62305978 |
| interest paid | — | 43.242 | 84.211 | -40.969 | 36-10-0112 | v62305961 |
| cash disposable income | — | 1,478.170 | 1,502.340 | -24.170 | 36-10-0112 | v62305981 |
| consumption | 1,485.603 | 1,620.402 | 1,511.382 | 109.020 | 36-10-0112 | v62305982 |

**Recorded saving-rate bridge (SNA comparison, percentage points; cash-restatement caveat below)**

| component | rate_or_change_pp |
|---|---|
| 2022 D.8-free rate | -0.602 |
| Disposable-income gap | -1.645 |
| Consumption gap | -7.375 |
| Model Q1 cash rate | -9.622 |

At t0, booked income is 1335.154B/year and consumption
is 1485.603B/year. The booked income includes an unfunded financial-asset
proxy of 87.238B/year; realized D2 mixed income, dividends
and corporate-transfer series are initially zero, although planned D2 payments
are available for subsequent decisions. Initial interest-paid series are NaN
placeholders, so a measured initial cash-DI/saving rate is unavailable. Initial
deposit interest in the table is stock × rate, not a booked cash receipt; initial
taxes are reconstructed from the configured wage/rent rates. This is an
inconsistent initial closure, not evidence for adding every missing SNA line
as a cash transfer.

The source paths also explain why observed aggregates need not be hit: public
benefits are built by `DefaultDataReaders.get_total_benefits_lcu` from OECD public
cash social-expenditure share × World Bank scaled GDP, not directly from the
household-account transfer vector. Coverage/reference-year reconciliation is
needed before replacing that target. Canadian PIT uses 348,148/2,005,348 from
an SNA income base (`macro_data/processing/country_data/tax_data.py`), whereas
the model taxes a smaller/different set of wage/rent/distribution flows. An
observed average rate therefore does not reproduce observed PIT receipts.
Neither difference is repaired by adding an unsourced net-income residual.

Q1 cash disposable income is 1478.170 versus 1,502.340B/year;
consumption is 1620.402 versus 1,511.382B/year. Cash saving is
-9.622% versus -0.602%
excluding D.8 (40.585B/year, v105775422). The exact ordered rate bridge is
-1.645pp from the disposable-income difference and
-7.375pp from consumption. Thus 7.375 of the 9.020
percentage-point gap is spending. This is the residual after using D2 in arm iv;
it does not add the previous ordered D1/D2/deposit-saving effects a second time.

This is an arithmetic bridge to the cited SNA account, **not a fully restated
cash-only benchmark**. Removing D.8 alone does not remove imputed housing,
FISIM and other accruals. The model treats the owner L bundle as a cash market
purchase, while SNA imputed housing is noncash; simply deleting that benchmark
line from one side would be inconsistent. A complete cash restatement needs
the housing and pension/institutional boundary decisions. The rate decomposition
locates the recorded gap without claiming those concept differences are solved.

Large gross scope differences offset: imputed rental income and pension/insurance
investment income lack cash counterparts, while current taxes and transfers paid
are also incomplete. All model employer social contributions go to government;
the SNA government contribution benchmark is a narrower recipient boundary.
Other transfers paid include pension-related flows missing from the model's
institutional structure. Interest paid has a different FISIM/property-income
boundary. The inherited negative saving propensity was initialized on incomplete
income and remains unchanged when D2 raises expected income, increasing desired
consumption. A consistent initialization or revised consumption rule is an option
for approval; fitting a saving propensity or inventing an income residual is not
a mechanical correction and was not done.

The original Q1 pair makes the interaction visible: iii has annualized cash DI
1,308.008B and consumption 1,522.166B (saving -16.373%); iv has 1,478.170B and
1,620.402B (-9.622%). Adding funded D2 receipts raises DI by 170.162B/year and
realized consumption by 98.236B/year. It improves saving by 6.751pp while taking
consumption from 10.784B above the SNA benchmark to 109.020B above. This is a
paired simulation outcome with market rationing, not an estimated marginal
propensity or a calibrated household-account correction.

### Q1 write-off cohort under the old rule

The following is original arm iv. The old trigger is negative net worth **and**
negative deposits at the time of the check. Counts use regional population
scales, with unscaled simulated counts also reported in the CSV. Income deciles
use t0 income per represented household with national population weighting.
Age is the oldest member of the synthetic household, an explicit proxy rather
than the SFS reference person's age. Tenure -1 is assigned social housing,
1 owner, 2 part owner, 3 private renter.

There are 1,228 simulated households, representing
1,035,940, with 171.143B of term debt cancelled.
None met both old-rule conditions at t0. However, 68.10%
of the cohort already had negative net worth; those households account for
93.88% of cancelled debt. A further 29.39% of households had nonnegative net worth
below one quarter's income. The saving/settlement gap pushes this fragile
starting cohort into overdraft; it does not create all of its balance-sheet
insolvency from scratch. Initial deposits are 2.140B,
falling to -4.551B; net worth moves from -53.003
to -58.846B. Real assets rise 1.004B in
aggregate, so an aggregate house-price collapse does not explain the cohort.
The old rule cancels all term debt rather than just the uncovered recovery loss.

**decile**

| group | simulated_count | represented_count | count_share_pct | group_incidence_pct | debt_B | debt_share_pct |
|---|---|---|---|---|---|---|
| 1 | 219 | 219000 | 21.140 | 14.138 | 9.290 | 5.428 |
| 2 | 112 | 91210 | 8.805 | 5.884 | 5.623 | 3.285 |
| 3 | 125 | 91340 | 8.817 | 5.894 | 4.775 | 2.790 |
| 4 | 181 | 140410 | 13.554 | 9.063 | 16.690 | 9.752 |
| 5 | 136 | 127090 | 12.268 | 8.201 | 13.979 | 8.168 |
| 6 | 122 | 107150 | 10.343 | 6.913 | 15.985 | 9.340 |
| 7 | 114 | 99150 | 9.571 | 6.399 | 20.080 | 11.733 |
| 8 | 93 | 73200 | 7.066 | 4.722 | 29.234 | 17.081 |
| 9 | 73 | 57160 | 5.518 | 3.689 | 21.034 | 12.290 |
| 10 | 53 | 30230 | 2.918 | 1.950 | 34.454 | 20.132 |

**tenure**

| group | simulated_count | represented_count | count_share_pct | group_incidence_pct | debt_B | debt_share_pct |
|---|---|---|---|---|---|---|
| -1 | 483 | 379050 | 36.590 | 26.061 | 7.517 | 4.392 |
| 1 | 253 | 214390 | 20.695 | 2.104 | 118.936 | 69.495 |
| 2 | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| 3 | 492 | 442500 | 42.715 | 11.489 | 44.690 | 26.112 |

**age band**

| group | simulated_count | represented_count | count_share_pct | group_incidence_pct | debt_B | debt_share_pct |
|---|---|---|---|---|---|---|
| <35 | 218 | 184340 | 17.794 | 13.469 | 19.511 | 11.400 |
| 35-44 | 347 | 307400 | 29.674 | 7.807 | 52.275 | 30.545 |
| 45-54 | 265 | 235300 | 22.714 | 8.258 | 47.643 | 27.838 |
| 55-64 | 223 | 175480 | 16.939 | 5.795 | 39.335 | 22.984 |
| 65+ | 175 | 133420 | 12.879 | 3.093 | 12.379 | 7.233 |

**deposit band**

| group | simulated_count | represented_count | count_share_pct | group_incidence_pct | debt_B | debt_share_pct |
|---|---|---|---|---|---|---|
| zero | 224 | 194300 | 18.756 | 22.849 | 12.370 | 7.228 |
| 0-1k | 429 | 357720 | 34.531 | 36.461 | 25.255 | 14.756 |
| 1-10k | 532 | 443890 | 42.849 | 12.844 | 70.738 | 41.333 |
| 10-50k | 41 | 38030 | 3.671 | 0.829 | 46.533 | 27.189 |
| 50k+ | 2 | 2000 | 0.193 | 0.036 | 16.247 | 9.493 |

**net worth band**

| group | simulated_count | represented_count | count_share_pct | group_incidence_pct | debt_B | debt_share_pct |
|---|---|---|---|---|---|---|
| negative | 847 | 705430 | 68.096 | 75.761 | 160.673 | 93.882 |
| zero | 50 | 42080 | 4.062 | 97.272 | 0.121 | 0.070 |
| 0-25k | 331 | 288430 | 27.842 | 26.129 | 10.350 | 6.047 |
| 25-100k | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| 100k+ | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |

**main cause**

| group | simulated_count | represented_count | count_share_pct | group_incidence_pct | debt_B | debt_share_pct |
|---|---|---|---|---|---|---|
| debt_service | 89 | 57320 | 5.533 | 16.907 | 37.476 | 21.898 |
| rent | 83 | 54290 | 5.241 | 34.376 | 1.211 | 0.708 |
| spending | 1056 | 924330 | 89.226 | 6.162 | 132.456 | 77.395 |

**t0 state**

| group | simulated_count | represented_count | count_share_pct | group_incidence_pct | debt_B | debt_share_pct |
|---|---|---|---|---|---|---|
| NW>=one quarter income | 26 | 26000 | 2.510 | 0.188 | 0.408 | 0.238 |
| near: 0<=NW<one quarter income | 355 | 304510 | 29.395 | 42.335 | 10.062 | 5.879 |
| negative NW, nonnegative deposits | 847 | 705430 | 68.096 | 75.761 | 160.673 | 93.882 |

Cause attribution uses a three-block Shapley decomposition of the observed
overdraft: goods/investment spending plus VAT, debt service (principal, loan and
overdraft interest), and actual rent. Resources are the exact residual of these
blocks and closing deposits; no arbitrary sequencing chooses the winner.
Classification uses the largest block per household. Aggregate overdraft
attribution is 2.788B spending, 1.395B debt service and 0.368B rent, with zero
other-resource residual. These are cash pressures, not legal insolvency causes.
All group counts, incidence and debt shares are in
[Q1_cohort_groups.csv](outputs/pre_D3_checks/Q1_cohort_groups.csv).

## 2. New lending and the mechanical screen fixes

The original D4 screen omitted overdraft principal from its LTI debt total and
overdraft interest from existing debt service; consumer originations also lacked
the mortgage-style service-cap check. d7a2110 counts these obligations in both
allocators and both loan categories, including same-quarter consumer service
before granting mortgages. Existing scheduled principal is capped by remaining
principal. Overdraft principal enters total debt, while its interest enters
service; no fictional overdraft amortization schedule was added.

37cf590 separately synchronizes household debt/net worth to surviving credit
books immediately after cancellation. Previously the household could carry
forgiven liabilities into later decisions. The old trigger and cancellation
amount for an already selected cohort are unchanged.

Loan tracking follows new principal through contractual amortization and actual
per-bank/per-household cancellations. The loss fraction below is principal
written off divided by new principal originated within this 12-quarter window.
The second measure is original value of vintages with any write-off; neither is
an annual default rate. Later vintages are right-censored.

| run | new_lending_B | new_principal_written_B | loss_pct | orig_value_eventually_written_pct | lent_to_overdrawn_pct | lent_to_negative_NW_pct |
|---|---|---|---|---|---|---|
| b1_iii_q12_s0 | 309.897 | 134.578 | 43.427 | 45.580 | 98.585 | 20.926 |
| b1_iv_q12_s0 | 256.179 | 103.445 | 40.380 | 42.412 | 97.982 | 19.561 |
| final_iii_q12_s0 | 298.479 | 130.192 | 43.618 | 45.786 | 98.201 | 1.453 |
| final_iv_q12_s0 | 247.688 | 100.554 | 40.597 | 42.679 | 97.755 | 1.260 |
| final_v_q12_s0 | 268.623 | 34.904 | 12.994 | 22.158 | 98.213 | 45.985 |

After both fixes, arm iv still loses 40.60% of newly originated principal within the window, and 97.76% of lending goes to borrowers already overdrawn. Its negative-net-worth share falls to 1.26% once forgiven liabilities are synchronized; the original recorded negative-net-worth measure was materially distorted by stale debt. In v, which preserves more collateral-backed liabilities, 45.98% of lending goes to recorded negative-net-worth borrowers. D4 screens income, service and property collateral; it does not impose a separate positive-net-worth or no-overdraft eligibility condition.

Each origination's bank, household, quarter, principal, deposits, overdraft,
net worth, total installment debt and existing service are retained in each
run's `micro/originations.csv`. `micro/origination_audit.csv` joins the population
scale and supplies each amount in CAD per represented household. Original
`b1` net worth is the state actually seen by the decision, which can contain
the now-fixed stale liabilities; it must not be read as independently recomputed
economic net worth. The final runs use synchronized balances.

Automatic settlement overdrafts remain possible even if new installment credit
is denied. Passing these screens does not mean a household has enough cash to
cover its consumption plan or all future obligations. An approved overdraft
facility with a limit and arrears treatment is a separate architectural choice;
no such limit has been silently imposed.

## Revised iv/v write-offs after both model fixes

Arm iv = H7 + D4 + D2, old insolvency. Arm v adds D3 only. D1 and deposit-only
saving are off in both. Bank losses include firm term debt and cancelled firm
overdrafts as well as household term debt. The following seed-0 table is the
final comparison, not the intermediate `fixed` run.

| quarter | iv HH | v HH | iv bank | v bank |
|---|---|---|---|---|
| 1 | 171.129 | 0.000 | 171.129 | 0.000 |
| 2 | 50.642 | 0.000 | 50.970 | 0.328 |
| 3 | 25.422 | 75.322 | 79.153 | 129.044 |
| 4 | 28.473 | 15.519 | 66.646 | 53.692 |
| 5 | 22.119 | 8.178 | 144.311 | 46.159 |
| 6 | 21.182 | 20.029 | 42.708 | 44.389 |
| 7 | 24.102 | 9.106 | 29.017 | 26.578 |
| 8 | 25.157 | 11.014 | 79.561 | 35.940 |
| 9 | 27.505 | 13.172 | 57.577 | 97.219 |
| 10 | 28.245 | 5.483 | 54.507 | 33.847 |
| 11 | 30.965 | 11.033 | 97.418 | 18.078 |
| 12 | 30.086 | 8.076 | 53.144 | 49.352 |
| Total | 485.027 | 176.932 | 926.139 | 534.627 |

Two-quarter accounting runs:

| run | total_HH_writeoffs_B | total_bank_losses_B | accounting_error |
|---|---|---|---|
| final_iv_q2_s0 | 221.771 | 222.099 | 0.000 |
| final_v_q2_s0 | 0.000 | 0.328 | 0.000 |

## 3. D2 firm payouts, the Q9 spike and bank capital

Original arms iii/iv are preserved to diagnose the reported 701B versus 648B
Q12 GDP and Q9 spike, rather than attributing a changed path to the old event.
Each quarterly row below includes failed-firm loan principal and cancelled
overdraft; industry counts and all firm observations are in
[firm_quarterly.csv](outputs/pre_D3_checks/firm_quarterly.csv) and the run's
`firms.csv`. Firm IDs are model industry-region representatives, not identified
Canadian companies. The industry mapping is retained in `industry_mapping.json`.

**b1_iii_q12_s0**

| quarter | insolvencies | firm_debt_B | overdraft_loss_B | requested_dividends_B | paid_dividends_B | cash_before_payout_B | cash_after_payout_B |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 2 | 5 | 0.310 | 0.018 | 0.000 | 0.000 | 0.000 | 0.000 |
| 3 | 10 | 28.776 | 11.617 | 0.000 | 0.000 | 0.000 | 0.000 |
| 4 | 7 | 6.471 | 5.889 | 0.000 | 0.000 | 0.000 | 0.000 |
| 5 | 25 | 16.596 | 13.412 | 0.000 | 0.000 | 0.000 | 0.000 |
| 6 | 21 | 14.687 | 9.708 | 0.000 | 0.000 | 0.000 | 0.000 |
| 7 | 24 | 7.453 | 36.244 | 0.000 | 0.000 | 0.000 | 0.000 |
| 8 | 21 | 11.715 | 11.035 | 0.000 | 0.000 | 0.000 | 0.000 |
| 9 | 27 | 29.239 | 28.667 | 0.000 | 0.000 | 0.000 | 0.000 |
| 10 | 23 | 20.661 | 16.952 | 0.000 | 0.000 | 0.000 | 0.000 |
| 11 | 29 | 34.031 | 45.712 | 0.000 | 0.000 | 0.000 | 0.000 |
| 12 | 36 | 8.376 | 36.612 | 0.000 | 0.000 | 0.000 | 0.000 |

**b1_iv_q12_s0**

| quarter | insolvencies | firm_debt_B | overdraft_loss_B | requested_dividends_B | paid_dividends_B | cash_before_payout_B | cash_after_payout_B |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 0.000 | 0.000 | 17.958 | 17.958 | 806.559 | 739.502 |
| 2 | 5 | 0.310 | 0.018 | 18.693 | 18.689 | 860.463 | 795.717 |
| 3 | 14 | 38.297 | 15.426 | 18.852 | 18.846 | 918.290 | 854.510 |
| 4 | 9 | 9.854 | 6.348 | 18.756 | 18.614 | 991.855 | 929.513 |
| 5 | 28 | 44.004 | 14.269 | 18.581 | 18.463 | 1,055.528 | 996.244 |
| 6 | 31 | 23.767 | 11.779 | 18.104 | 17.942 | 1,129.288 | 1,072.287 |
| 7 | 13 | 2.447 | 2.697 | 17.960 | 17.809 | 1,201.979 | 1,146.252 |
| 8 | 20 | 19.624 | 16.516 | 18.445 | 18.285 | 1,264.019 | 1,208.024 |
| 9 | 24 | 133.399 | 60.446 | 18.290 | 18.165 | 1,337.162 | 1,282.869 |
| 10 | 14 | 8.583 | 7.397 | 17.863 | 17.558 | 1,456.112 | 1,404.027 |
| 11 | 22 | 4.668 | 5.902 | 17.888 | 17.618 | 1,521.337 | 1,469.091 |
| 12 | 28 | 4.525 | 17.404 | 18.127 | 17.850 | 1,585.376 | 1,533.997 |

**final_iii_q12_s0**

| quarter | insolvencies | firm_debt_B | overdraft_loss_B | requested_dividends_B | paid_dividends_B | cash_before_payout_B | cash_after_payout_B |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 2 | 5 | 0.310 | 0.018 | 0.000 | 0.000 | 0.000 | 0.000 |
| 3 | 10 | 28.776 | 11.617 | 0.000 | 0.000 | 0.000 | 0.000 |
| 4 | 8 | 5.832 | 5.823 | 0.000 | 0.000 | 0.000 | 0.000 |
| 5 | 21 | 32.308 | 18.228 | 0.000 | 0.000 | 0.000 | 0.000 |
| 6 | 18 | 5.486 | 8.749 | 0.000 | 0.000 | 0.000 | 0.000 |
| 7 | 12 | 3.167 | 27.610 | 0.000 | 0.000 | 0.000 | 0.000 |
| 8 | 30 | 25.892 | 17.839 | 0.000 | 0.000 | 0.000 | 0.000 |
| 9 | 25 | 4.574 | 12.614 | 0.000 | 0.000 | 0.000 | 0.000 |
| 10 | 17 | 0.403 | 10.683 | 0.000 | 0.000 | 0.000 | 0.000 |
| 11 | 27 | 1.925 | 30.896 | 0.000 | 0.000 | 0.000 | 0.000 |
| 12 | 28 | 38.692 | 38.953 | 0.000 | 0.000 | 0.000 | 0.000 |

**final_iv_q12_s0**

| quarter | insolvencies | firm_debt_B | overdraft_loss_B | requested_dividends_B | paid_dividends_B | cash_before_payout_B | cash_after_payout_B |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 0.000 | 0.000 | 17.958 | 17.958 | 806.559 | 739.502 |
| 2 | 5 | 0.310 | 0.018 | 18.693 | 18.689 | 860.463 | 795.717 |
| 3 | 14 | 38.297 | 15.434 | 18.852 | 18.846 | 918.303 | 854.523 |
| 4 | 14 | 32.399 | 5.773 | 18.751 | 18.609 | 989.253 | 927.059 |
| 5 | 26 | 107.283 | 14.909 | 18.538 | 18.381 | 1,050.239 | 989.526 |
| 6 | 16 | 15.117 | 6.409 | 18.119 | 17.954 | 1,126.726 | 1,069.502 |
| 7 | 23 | 1.992 | 2.924 | 18.379 | 18.281 | 1,198.095 | 1,141.130 |
| 8 | 24 | 24.380 | 30.024 | 18.905 | 18.835 | 1,266.177 | 1,208.488 |
| 9 | 22 | 8.883 | 21.188 | 18.865 | 18.695 | 1,362.599 | 1,307.470 |
| 10 | 30 | 12.309 | 13.953 | 18.397 | 18.094 | 1,452.113 | 1,399.037 |
| 11 | 24 | 34.923 | 31.530 | 18.012 | 17.667 | 1,536.264 | 1,484.655 |
| 12 | 18 | 3.808 | 19.250 | 18.174 | 17.749 | 1,639.372 | 1,587.595 |

**All original arm-iv Q9 failures ($B)**

| region | firm | industry_name | loan_debt | overdraft_cancelled | equity | deposits | profits | paid_dividends |
|---|---|---|---|---|---|---|---|---|
| CAN_NL | 35 | H53 | 0.125 | 0.329 | -0.004 | -0.329 | -0.048 | 0.000 |
| CAN_NL | 43 | N | 0.000 | 0.390 | -0.060 | -0.390 | -0.105 | 0.000 |
| CAN_PE | 17 | C24A | 0.000 | 0.001 | -0.000 | -0.001 | -0.000 | 0.000 |
| CAN_PE | 21 | C27 | 0.004 | 0.012 | -0.000 | -0.012 | -0.002 | 0.000 |
| CAN_PE | 24 | C301 | 0.000 | 0.003 | -0.000 | -0.003 | -0.001 | 0.000 |
| CAN_PE | 32 | H50 | 0.000 | 0.011 | -0.002 | -0.011 | -0.002 | 0.000 |
| CAN_PE | 37 | J58T60 | 0.000 | 0.021 | -0.001 | -0.021 | -0.004 | 0.000 |
| CAN_NS | 39 | J62_63 | 0.487 | 0.453 | -0.049 | -0.453 | -0.086 | 0.000 |
| CAN_NB | 21 | C27 | 0.005 | 0.011 | -0.002 | -0.011 | -0.004 | 0.000 |
| CAN_QC | 48 | S | 0.856 | 2.142 | -0.207 | -2.142 | -0.295 | 0.000 |
| CAN_ON | 0 | A01 | 14.685 | 4.755 | -0.995 | -4.755 | -0.103 | 0.000 |
| CAN_ON | 27 | D | 82.165 | 6.077 | -3.494 | -6.077 | 0.417 | 0.000 |
| CAN_ON | 36 | I | 0.000 | 19.878 | -3.355 | -19.878 | -3.126 | 0.000 |
| CAN_MB | 9 | C13T15 | 0.036 | 0.089 | -0.015 | -0.089 | -0.018 | 0.000 |
| CAN_SK | 35 | H53 | 0.444 | 0.622 | -0.056 | -0.622 | -0.079 | 0.000 |
| CAN_AB | 36 | I | 2.583 | 6.063 | -0.113 | -6.063 | -0.794 | 0.000 |
| CAN_BC | 0 | A01 | 2.957 | 2.038 | -0.268 | -2.038 | -0.250 | 0.000 |
| CAN_BC | 27 | D | 29.044 | 8.226 | -0.163 | -8.226 | -0.254 | 0.000 |
| CAN_BC | 36 | I | 0.000 | 9.226 | -1.285 | -9.226 | -1.563 | 0.000 |
| CAN_YT | 43 | N | 0.000 | 0.028 | -0.004 | -0.028 | -0.007 | 0.000 |
| CAN_NT | 37 | J58T60 | 0.003 | 0.009 | -0.001 | -0.009 | -0.001 | 0.000 |
| CAN_NT | 43 | N | 0.007 | 0.031 | -0.003 | -0.031 | -0.006 | 0.000 |
| CAN_NU | 37 | J58T60 | 0.000 | 0.003 | -0.000 | -0.003 | -0.000 | 0.000 |
| CAN_NU | 48 | S | 0.000 | 0.027 | -0.010 | -0.027 | -0.027 | 0.000 |

Original arm iv: payouts to firms with negative current profit, summed over 12 quarters:

| payment | paid_B |
|---|---|
| paid_mixed | 23.884 |
| paid_transfers | 26.926 |
| paid_dividends | 0.899 |

Original Q9 bank losses total 222.785B: 28.940B household loans, 133.399B firm
loans and 60.446B cancelled firm overdrafts. Utilities (D) in Ontario and British
Columbia account for 111.209B of failed loan principal; accommodation/food (I)
also contributes large overdrafts. Failure follows the model's balance-sheet
trigger, not simply negative current profit: Ontario utilities still has positive
current profit but negative equity and deposits. This identifies the spike's
balance-sheet source; it does not establish that dividends alone caused every
failure. Source-scope problems in firm debt and missing production taxes remain
in the prior firm audit.

Both utilities representatives were already overdrawn in Q7 and paid **zero**
mixed income, transfers or dividends in Q7–Q9. Ontario's Q8→Q9 equity moves
5.220→-3.494B: deposits -4.773→-6.077B, debt 83.777→82.165B, and the noncash
asset residual (equity + debt - deposits) 93.770→84.749B. The 9.022B decline in
that asset-value/stock residual dominates the equity deterioration; current
profit is +0.417B. BC's equivalent residual falls 38.276→37.107B and deposits
-7.400→-8.226B, taking equity 1.263→-0.163B while debt amortizes. These are
balance-sheet decompositions, not a claim that the entire residual change is
pure price revaluation: the saved panel does not split asset prices from
quantities/depreciation. Earlier D2 payments and general-equilibrium paths can
still affect later buffers. These six observations are retained in
`Q9_utilities_balance_bridge.csv`.

The payout algorithm uses lagged positive profit and two available-cash caps.
No observed payout turns nonnegative cash into overdraft, and cash-short firms
pay zero. Negative cash after payout occurs when cash was already negative.
Payouts may nevertheless be made while current-quarter profits are negative,
and consume cash buffers needed in future periods. The retained panel includes
requested versus actual mixed-income/corporate-transfer payments as well as
dividends; current-loss-maker dividends, cash-short payouts and overdraft-created
counts are explicit columns. A possible rule is dividends bounded by positive
current retained earnings and cash after near-term obligations plus a liquidity
reserve. This changes behaviour and needs approval. Mixed income and pension
transfers need their own institutional treatment rather than blindly adopting
the corporate-dividend restriction.

### Bank capital is not validated

Every provincial bank starts with **506.210B**, giving 6,580.730B nationally.
No recorded bank equity turns negative in the original or final runs; this is partly a
consequence of excessive starting capital, not evidence that Canadian banks
could absorb these losses. The quarterly bank-level panel includes initial,
before-rescue and end-of-quarter observations, equity and equity/loan ratio:
`b1_iii_q12_s0/banks.csv`, `b1_iv_q12_s0/banks.csv` and final equivalents.

| run | total_bank_losses_B | min_bank_equity_B | negative_bank_observations |
|---|---|---|---|
| b1_iii_q12_s0 | 945.914 | 142.537 | 0 |
| b1_iv_q12_s0 | 936.527 | 111.250 | 0 |
| final_iii_q12_s0 | 878.634 | 195.380 | 0 |
| final_iv_q12_s0 | 926.139 | 140.801 | 0 |
| final_v_q12_s0 | 534.627 | 308.342 | 0 |

**Failed diagnostic: final D1, seed 1.** Ontario reaches a bank-resolution
trigger in Q11 while book equity is still positive (50.139B; equity/loans 3.796%).
`DefaultBankDemography` uses equity/(loans + bank deposits), not the equity/loans
ratio reported in the bank panel. Resolution calls `remove_loans_by_bank`,
cancelling 1,320.852B of loans. That call increments the aggregate write-off
counter without a by-bank loss attribution, after the quarter's ordinary bank
loss recognition and stock calculation. The bank stock is not refreshed until
Q12. The loan identity consequently has +1,320.852B in Q11 and -1,320.852B in Q12;
the run's maximum normalized accounting error is 2.939. It is retained as a
failed diagnostic, not an accepted accounting path. The cancelled bank portfolio
is outside the household-only write-off measure and the origination loss tracker
around household insolvency, so that run's loan-loss percentages understate
all cancellation routes. Its Q12 seed comparison is descriptive only.

Final D1 seed 2 also fails through this route: Ontario cancels a 1,356.011B
portfolio in Q10, with the opposite loan-stock residual in Q11 and another
14.131B cancellation in Q12. Its maximum normalized accounting error is 3.073.
Both requested D1 seed runs were completed and retained, but neither is an
accepted accounting path. The paired iv runs pass.

Repairing the full resolution transaction requires choosing whether loans
transfer, borrowers receive forgiveness, and which equity/deposit/fiscal claims
absorb the loss. That is an architectural decision, not an authorized choice
for this diagnostic. No resolution change or bailout was invented. No negative
*recorded* equity therefore does not imply solvency after recognizing all losses.

For review, the preferred resolution design is to preserve borrower contracts
and transfer the loan book to a successor/bridge bank while specifying the
equity/deposit/fiscal loss waterfall. An alternative is explicit debt forgiveness,
with simultaneous borrower liability cancellation, bank asset/loss recognition
and a funded recapitalization transaction. These are proposals only.

The reader computed a regional ratio and omitted it from both return paths;
59a37ef fixes that mechanical error, including own-observation and proxy-country
regressions. Separately, its selector uses **ASS/F5** for S122_S123, meaning banks'
holdings of equity assets, not their own book capital. Merely applying the ratio
does not resolve that concept error. The agreed pickle is unchanged, so all
results here retain the inherited bad capital stock.

This interpretation follows the selected asset-side instrument and
[Eurostat financial-account definitions](https://ec.europa.eu/eurostat/cache/metadata/en/nasq_10_f_esms.htm);
it is a source-concept diagnosis, not a newly estimated bank-capital target.

For a Canadian benchmark,
[36-10-0580](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610058001)
2022 Q4 liability-side **Book value / Equity** reports chartered banks 405.572B
(v62696428), quasi-banks 50.649B (v62696533), total 456.221B (v62696323).
The model total is 14.4 times that combined benchmark. Sector coverage must be
chosen explicitly; neither regulatory CET1 nor banks' equity asset holdings is
the same concept. Model equity/loans is not a risk-weighted regulatory capital
ratio. Benchmark extract and raw-source SHA are in
`benchmarks/pre_D3_checks/36100580_bank_equity_2022Q4.csv` and
`bank_equity_provenance.json`, from the inherited 13 October controls snapshot.

**Decision:** choose Canadian bank sector/book-equity coverage, regional
allocation and balance-sheet counterpart, then authorize a new validation input
and reruns. No rescaling of existing pickles or automatic capital injection was
used to make losses appear sustainable.

## 4. Sector L: prices, quantities, buyers and seeds

Each paired run changes only narrow D1 relative to iv. Seeds 1 and 2 were run
for 12 quarters per arm, serially; seed 0 is also retained. This is a paired-seed
comparison, not a guarantee of identical later random draws: changed allocation
branches can consume different numbers of draws. National P is total L sales
divided by total L real sales. The exact symmetric decomposition is
Δsales = ΔP × mean(Q) + ΔQ × mean(P). Inventory is in base-value quantity units.

**Original reported anomaly: exact b1b2960-source replay, seed 0**

| quarter | base_sales_B | D1_sales_B | price_base | price_D1 | price_effect_B | quantity_effect_B | inventory_base_B_units | inventory_D1_B_units |
|---|---|---|---|---|---|---|---|---|
| 1 | 98.796 | 98.796 | 0.976 | 0.976 | 0.000 | 0.000 | 0.000 | 0.000 |
| 2 | 95.802 | 95.802 | 0.946 | 0.946 | 0.000 | 0.000 | 0.000 | 0.000 |
| 3 | 96.352 | 96.352 | 0.952 | 0.952 | -0.000 | 0.000 | 0.000 | 0.000 |
| 4 | 96.755 | 102.328 | 0.956 | 1.011 | 5.573 | 0.000 | 0.000 | 0.000 |
| 5 | 94.433 | 105.746 | 0.933 | 1.045 | 11.313 | 0.000 | 0.000 | 0.000 |
| 6 | 95.402 | 111.749 | 0.942 | 1.108 | 16.724 | -0.377 | 0.000 | 0.367 |
| 7 | 97.525 | 113.760 | 0.963 | 1.140 | 17.744 | -1.510 | 0.000 | 1.436 |
| 8 | 94.805 | 112.797 | 0.937 | 1.114 | 17.992 | -0.000 | 0.000 | 0.000 |
| 9 | 90.591 | 112.231 | 0.895 | 1.111 | 21.900 | -0.260 | 0.000 | 0.260 |
| 10 | 91.641 | 114.389 | 0.905 | 1.185 | 27.636 | -4.888 | 0.000 | 4.678 |
| 11 | 89.694 | 117.306 | 0.886 | 1.213 | 32.365 | -4.753 | 0.000 | 4.529 |
| 12 | 91.992 | 118.689 | 0.909 | 1.212 | 30.219 | -3.522 | 0.000 | 3.321 |

The reported Q12 increase of 26.697B decomposes into 30.219B from the national unit-value price and -3.522B from quantity. The national unit value includes regional mix. Summing province-level decompositions instead gives 30.745B price and -4.048B quantity, also price-led. Employment falls from 360,120 to 342,110; inventory accumulates to 3.321B base-value quantity units. Higher nominal sales therefore do not indicate a real L expansion.

The replay uses an isolated `git archive b1b2960 macromodel` source snapshot, read-only input and the same diagnostic wrappers. Its manifest records the native source commit and archive hash. No branch checkout or original-repository edit was performed. `replay_pre_D3_original.py` reproduces this operation. Buyer, inventory and employment observations are retained in `b1_d1_q12_s0/L.csv`.

**Final Q12 pairs: seeds 1 and 2 have failed D1 accounting and are descriptive only**

| seed | base_sales_B | D1_sales_B | delta_sales_B | delta_pct | price_effect_B | quantity_effect_B | price_base | price_D1 |
|---|---|---|---|---|---|---|---|---|
| 0 | 95.393 | 94.722 | -0.671 | -0.703 | -0.671 | -0.000 | 0.942 | 0.936 |
| 1 | 121.165 | 97.660 | -23.505 | -19.400 | -23.505 | -0.000 | 1.197 | 0.965 |
| 2 | 107.398 | 92.610 | -14.787 | -13.769 | -14.787 | 0.000 | 1.061 | 0.915 |

**Intermediate obligation-screen-only pairs (before the stale-liability fix), all pass accounting**

| seed | base_sales_B | D1_sales_B | delta_pct | price_effect_B | quantity_effect_B |
|---|---|---|---|---|---|
| 0 | 101.142 | 102.688 | 1.529 | 1.547 | -0.000 |
| 1 | 104.615 | 110.366 | 5.497 | 5.751 | -0.000 |
| 2 | 105.173 | 94.207 | -10.427 | -10.967 | 0.000 |

The intermediate sign changes across seeds. The final seed-0 quantities and employment are essentially unchanged, with a small nominal sales decline; the final cross-seed comparison cannot be accepted until bank resolution is repaired. The reported original sales increase must therefore not be treated as a robust D1 response.

**Quarterly price × quantity decomposition, seed 0**

| quarter | base_sales_B | D1_sales_B | price_base | price_D1 | price_effect_B | quantity_effect_B | inventory_base_B_units | inventory_D1_B_units |
|---|---|---|---|---|---|---|---|---|
| 1 | 98.796 | 98.796 | 0.976 | 0.976 | 0.000 | 0.000 | 0.000 | 0.000 |
| 2 | 95.802 | 95.802 | 0.946 | 0.946 | 0.000 | 0.000 | 0.000 | 0.000 |
| 3 | 96.352 | 96.352 | 0.952 | 0.952 | -0.000 | 0.000 | 0.000 | 0.000 |
| 4 | 91.387 | 95.819 | 0.903 | 0.947 | 4.432 | -0.000 | 0.000 | 0.000 |
| 5 | 89.086 | 94.650 | 0.880 | 0.935 | 5.564 | -0.000 | 0.000 | 0.000 |
| 6 | 92.806 | 95.272 | 0.917 | 0.941 | 2.466 | -0.000 | 0.000 | 0.000 |
| 7 | 94.602 | 96.366 | 0.935 | 0.952 | 1.763 | -0.000 | 0.000 | 0.000 |
| 8 | 93.395 | 94.149 | 0.923 | 0.930 | 0.754 | -0.000 | 0.000 | 0.000 |
| 9 | 90.461 | 92.860 | 0.894 | 0.917 | 2.399 | -0.000 | 0.000 | 0.000 |
| 10 | 87.910 | 94.252 | 0.868 | 0.931 | 6.342 | -0.000 | 0.000 | 0.000 |
| 11 | 90.994 | 94.040 | 0.899 | 0.929 | 3.046 | -0.000 | 0.000 | 0.000 |
| 12 | 95.393 | 94.722 | 0.942 | 0.936 | -0.671 | -0.000 | 0.000 | 0.000 |

**final_iv_q12_s0: buyers of Canadian L output**

| quarter | quantity | sales | HH_L_domestic | firms_L_domestic | government_L_domestic | ROW_L_sales | buyer_residual_B | employment | rent_offset |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 101.232 | 98.796 | 79.000 | 19.032 | 0.764 | 0.000 | 0.000 | 360,120.000 | 0.000 |
| 2 | 101.232 | 95.802 | 77.048 | 18.384 | 0.370 | 0.000 | 0.000 | 360,120.000 | 0.000 |
| 3 | 101.232 | 96.352 | 76.971 | 18.469 | 0.912 | 0.000 | -0.000 | 360,120.000 | 0.000 |
| 4 | 101.232 | 91.387 | 72.926 | 17.405 | 1.056 | 0.001 | -0.000 | 360,120.000 | 0.000 |
| 5 | 101.232 | 89.086 | 71.268 | 16.953 | 0.864 | 0.001 | -0.000 | 360,120.000 | 0.000 |
| 6 | 101.232 | 92.806 | 74.493 | 17.664 | 0.646 | 0.004 | -0.000 | 360,120.000 | 0.000 |
| 7 | 101.232 | 94.602 | 76.118 | 18.036 | 0.443 | 0.005 | -0.000 | 360,120.000 | 0.000 |
| 8 | 101.232 | 93.395 | 75.457 | 17.742 | 0.194 | 0.002 | -0.000 | 360,120.000 | 0.000 |
| 9 | 101.232 | 90.461 | 72.979 | 17.233 | 0.249 | 0.000 | 0.000 | 360,120.000 | 0.000 |
| 10 | 101.232 | 87.910 | 71.073 | 16.602 | 0.234 | 0.001 | 0.000 | 360,120.000 | 0.000 |
| 11 | 101.232 | 90.994 | 73.427 | 17.233 | 0.330 | 0.003 | -0.000 | 360,120.000 | 0.000 |
| 12 | 101.232 | 95.393 | 76.485 | 18.156 | 0.737 | 0.015 | -0.000 | 360,120.000 | 0.000 |

**final_d1_q12_s0: buyers of Canadian L output**

| quarter | quantity | sales | HH_L_domestic | firms_L_domestic | government_L_domestic | ROW_L_sales | buyer_residual_B | employment | rent_offset |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 101.232 | 98.796 | 79.587 | 19.032 | 0.177 | 0.000 | 0.000 | 360,120.000 | 3.798 |
| 2 | 101.232 | 95.802 | 76.855 | 18.384 | 0.563 | 0.000 | -0.000 | 360,120.000 | 3.793 |
| 3 | 101.232 | 96.352 | 77.687 | 18.469 | 0.195 | 0.000 | 0.000 | 360,120.000 | 3.790 |
| 4 | 101.232 | 95.819 | 76.793 | 18.284 | 0.735 | 0.007 | 0.000 | 360,120.000 | 3.791 |
| 5 | 101.232 | 94.650 | 76.573 | 18.027 | 0.047 | 0.002 | -0.000 | 360,120.000 | 3.791 |
| 6 | 101.232 | 95.272 | 77.105 | 18.045 | 0.118 | 0.003 | -0.000 | 360,120.000 | 3.787 |
| 7 | 101.232 | 96.366 | 77.410 | 18.216 | 0.715 | 0.025 | 0.000 | 360,120.000 | 3.787 |
| 8 | 101.232 | 94.149 | 75.718 | 17.730 | 0.681 | 0.020 | -0.000 | 360,120.000 | 3.792 |
| 9 | 101.232 | 92.860 | 74.780 | 17.403 | 0.645 | 0.031 | 0.000 | 360,120.000 | 3.792 |
| 10 | 101.232 | 94.252 | 75.485 | 17.639 | 1.081 | 0.047 | -0.000 | 360,120.000 | 3.789 |
| 11 | 101.232 | 94.040 | 76.172 | 17.592 | 0.227 | 0.050 | -0.000 | 360,120.000 | 3.799 |
| 12 | 101.232 | 94.722 | 76.231 | 17.691 | 0.762 | 0.038 | 0.000 | 360,120.000 | 3.803 |

National buyer flows reconcile to Canadian L sales; regional buyer expenditure
alone need not equal that region's seller revenue because purchases cross
provincial borders. `HH_L`/`firms_L` include imports; the `_domestic` columns above
exclude imports and include all Canadian origins. Buyer splits can shift despite
the reduced renter budget when supply constraints ration realized purchases.
The full L panel retains regional minimum/maximum prices, inventories, production,
employment and all quarters/seeds. These paths must be read with the inherited
noise-driven price rule documented in the firm audit.

## Recommendation and review boundary

Do not accept D3 yet. Its smaller write-off totals establish a scenario difference,
not a Canadian arrears, foreclosure or recovery mechanism. First resolve the
initial income/consumption boundary, automatic overdrafts and Canadian bank
capital; then choose a collateral/recovery specification with an explicit cash
and balance-sheet path. The old rule also remains unsuitable as a validated
Canadian default process. D2 and narrow D1 remain opt-in candidates. H7 and the
quota correction are unchanged. No Phase B or C_dp_005 work was started.

8 of 10 final runs pass the 1e-8 accounting threshold; 2 fail and are retained explicitly. Focused tests: 52 passed.

| run | accounting_error |
|---|---|
| final_d1_q12_s1 | 2.939 |
| final_d1_q12_s2 | 3.073 |

Full suite: 391 passed, 30 failures, 0 setup/runtime errors. 30 failures match the known `Nan in transactor_total_real_supply` cases; 0 additional failures. Raw XML/log and case classifications are retained.

Sampler rerun: workers=1, failures=1, errors=0; all failures match the known NaN: True. Worker count is verified from the JUnit property.

Test-harness exception: pytest was serial, but its existing sampler test
internally defaults to cpu_count()/2 workers. This was discovered after that
test finished; its workers had exited. The household diagnostic runs remained
serial. The sampler is rerun with `run_pre_D3_tests.py`, which sets only its
worker count to one and records that setting in JUnit; no test is skipped.
Use this wrapper for future full suites under the one-simulation constraint.
The initial full-suite result and the serial sampler rerun are retained separately.
