# Firm debt and default, then household default - 24 October 2026 UTC

**F is implemented and measured on seeds 0-2. Gate F: FAIL.
Household continuation check: FAIL. E has not started.**
The old household default rule remains in every measured arm. D3 is off.
The buffer-stock rule is a proposal only. Phase B and C_dp_005 remain on hold.
Work starts from f77f0f5 on feature/validation-2022; no push.

## Steps, commits, tests and gate decisions

| Step | Commit / focused tests | Result |
|---|---|---|
| Accepted initial planned household investment | 9a26aeb; planned-gate regression | 60.59825B/q, exactly 36-10-0112 v62305994; Gate 1 passes; realized affordability cuts are not a gate |
| F data boundary and allocation | 12987e6; 2 regression tests | External bank-held proxy 1,281.615B; consolidated claims and scope adjustment explicit; no initial K/O/P/Q/T bank loans |
| F payment default / retained secured contract | 923f107; 4 initial regression tests | Candidate flag on, default off; exact uncovered-principal loss and surviving contract, no fictitious recovery cash |
| Existing overdraft service screen | 43bd9f9; additional regression | Includes overdraft interest |
| Overdraft principal in collateral shortfall | a039998; exact mixed-credit and overdraft-only regressions | Total bank credit shares collateral and losses; explicit non-cash debit relief and by-bank counterparty |
| Diagnostic income / assets / jobs / firms | bd72103, 980c8cd; 2 diagnostic regressions | Fixed initial bins; direct income-restoration counterfactual and separate wage/job/D2 receipt changes |
| F gate | 9a26aeb; gate regression | FAIL; maximum accounting residual 6.66e-15; loss reductions below |
| Household continuation check | 9a26aeb; slope/sign regression | FAIL; Q4-Q12 OLS slopes below; any positive slope stops E |
| E | Not implemented | Required stop after F; no foreclosure, recovery or household-default change |

Twelve focused tests pass. Investment is income-based; 5%/quarter is
depreciation. The earlier realized-investment FAIL entry is superseded by the
review's planned-initial-investment gate. No level is fitted to a gate.

## Execution and evidence

All final measurements are in outputs/FE/serial, with a 2Q accounting run
immediately before each same-seed 12Q run, one validation simulation at a time.
The user clarified that the separate BDA workflow may continue; the earlier
global-serialization approval block is resolved. The historical pilot outside
serial is excluded. Every final run records the input hash, source hashes,
HEAD, seed and normalized accounting error. Stock/counterparty checks use
the 1e-8 battery. The new pickle and all three accepted-input hashes are audited.
The earlier loan-only collateral measurements are retained under
superseded_loan_only_collateral and excluded from every final table.

Amounts below are CAD B for flows/stocks unless ratios or percentages are
labelled. Consumption includes VAT and paid rent; realized investment includes
capital-formation tax. Planned investment is captured before D cuts. Saving
is cash DI minus consumption, divided by cash DI; the -0.6% comparator excludes
D.8. See inherited 36-10-0112 source/vector/date/hashes and benchmarks/IFE/provenance.json.

## Seed comparison and continuation gates


| seed | initial_planned_investment | baseline_firm_losses | firm_losses | firm_loss_reduction | gate_F | constrained_slope_pp_per_quarter | household_check_pass | Q12_constrained_share | Q12_cash_saving |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 60.598 | 352.695 | 205.399 | 41.763 | True | 2.126 | False | 50.523 | 2.937 |
| 1 | 60.598 | 332.277 | 265.003 | 20.246 | False | 2.088 | False | 50.317 | 3.306 |
| 2 | 60.598 | 351.876 | 229.988 | 34.639 | True | 2.061 | False | 49.679 | 3.864 |

Slope is percentage points per quarter, using unrounded Q4-Q12 shares.
Material firm-loss reduction means at least 25%, declared before 12Q outcomes.
Recognition changes and retained overdrafts must be reviewed alongside this gate.

| seed | base_GDP | F_GDP | base_consumption | F_consumption | base_bank_losses | F_bank_losses | base_recap | F_recap | F_Q12_overdraft |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 660.089 | 670.410 | 341.167 | 342.184 | 586.421 | 441.852 | 475.519 | 220.141 | 200.585 |
| 1 | 730.817 | 666.865 | 364.727 | 346.042 | 567.069 | 502.068 | 370.190 | 310.153 | 216.727 |
| 2 | 602.782 | 632.115 | 303.424 | 325.136 | 585.890 | 467.004 | 399.164 | 235.207 | 189.037 |

## Debt boundary and equity bridge

Amounts below are CAD B. Cash and physical firm assets are unchanged.

| Initial stock bridge | B |
|---|---:|
| Original modeled bank firm loans | 2,271.807 |
| NBSA external non-mortgage loans, v62694407 | 925.316 |
| NBSA mortgages, v62694408 | 356.299 |
| New bank-held external-loan proxy | 1,281.615 |
| Explicit consolidation credit to firm equity, v62694409 | +1,164.071 |
| Separate scope/allocation adjustment to equity | -173.879 |
| Net equity increase = old bank debt minus new bank debt | +990.192 |
| Bonds, v62694398, outside modeled bank contracts | 625.741 |
| NBSA total-loans minus listed components, separately unallocated | 2.954 |

The old model stock was already below NBSA total loans (2,448.640B), so simply
subtracting 1,164.071B from it would not yield the requested external-loan
boundary. The explicit scope adjustment reconciles that mismatch; it is not
a simulated payment, bank loss or unexplained accounting plug. Firm-level
before/after equity and both credits are retained in initial_firm_debt.csv.
Bonds are a named boundary outside the model, not added to bank loans.
The per-firm consolidation/scope split is a pro-forma bridge allocated
by old model debt, not an observed distribution of intercompany claims
or evidence of such claims at public producers. Each net equity change
equals its actual old-minus-new bank-debt change. Only the national
intercompany benchmark is observed.

The [NBSA table](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610058001)
is the inherited 2026-10-13 controls snapshot. Full source hash, vectors and
values are in build_provenance.json. No accepted input was overwritten.

Allocation uses observed 2022Q4 non-mortgage loans and overdrafts from
[33-10-0225](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3310022501).
Each published financial-statements group is crosswalked to the model, split
by output within combined groups, and allocated across regions by output.
The same observed industry loan weights proxy mortgage allocation because
the table does not expose mortgage liability amounts separately. This is an
allocation assumption, not an observed mortgage distribution. Utilities
includes the model's electricity/gas and water producers. The educational /
health private-enterprise row is excluded because the model supplies no
cited private-producer share for P/Q. Financial K and household-employer T
are outside the private non-financial corporation boundary. The industry financial-statements weights are a proxy for the NBSA
private-corporation boundary; the IO producers do not separately identify
private/government ownership within every other industry. No capital-share
fallback was needed. Crosswalks, weights and every used vector are in
industry_allocation.csv; source/retrieval/full ZIP/full CSV/extract hashes are
in benchmarks/FE/industry_provenance.json.

[33-10-0014](https://www150.statcan.gc.ca/n1/en/catalogue/3310001401) provides
business-credit supplier detail, including banks and other lenders. Its
borrower coverage includes finance and unincorporated enterprises, so it is
not a matching NFPC-instrument holder matrix. The cached 2022 H2 observations
and review are in benchmarks/FE/holder_review.json. Until an exact matching
cross-tab is established, all 1,281.615B external loans are treated as bank-held:
this is an explicit upper-bound assumption, not a verified bank-only total.

New input: dev/pkl_files/io2022_household_agreed_bankcap_firmdebt.pkl.
SHA256: 0abf12059d02f3bbcce09bee5d504325c740d3b7505f5f6c6a75e2c871bb130d.
initial_audit.json verifies all three accepted pickle hashes remain unchanged.

## Industry debt and leverage before / after

Debt levels are B; debt/capital uses the unchanged current-price physical
capital stock; debt/GOS uses four times initial quarterly GOS. The initial
GOS denominator is read from the pilot's t0 state, before any default rule.
A nonpositive GOS, if present, is not an economically meaningful leverage
denominator. Full precision and consolidation credits are in
outputs/FE/initial_industry_bridge.csv.

| industry_code | debt_before | debt_after | debt_capital_before | debt_capital_after | debt_annualised_GOS_before | debt_annualised_GOS_after |
| --- | --- | --- | --- | --- | --- | --- |
| A01 | 47.456 | 72.323 | 0.780 | 1.189 | 1.345 | 2.050 |
| A02 | 2.602 | 10.867 | 0.818 | 3.415 | 0.786 | 3.284 |
| A03 | 1.137 | 3.941 | 0.773 | 2.677 | 0.460 | 1.594 |
| B05 | 5.794 | 4.603 | 0.766 | 0.609 | 0.732 | 0.581 |
| B06 | 309.382 | 66.575 | 0.533 | 0.115 | 1.966 | 0.423 |
| B07 | 36.818 | 13.852 | 0.810 | 0.305 | 2.118 | 0.797 |
| B08 | 17.333 | 9.206 | 0.637 | 0.338 | 1.034 | 0.549 |
| B09 | 22.536 | 6.837 | 0.675 | 0.205 | 2.689 | 0.816 |
| C10T12 | 20.816 | 38.041 | 0.865 | 1.580 | 1.037 | 1.896 |
| C13T15 | 1.450 | 3.351 | 0.939 | 2.171 | 0.563 | 1.302 |
| C16 | 6.797 | 6.338 | 0.810 | 0.755 | 0.593 | 0.553 |
| C17_18 | 9.824 | 5.238 | 0.860 | 0.458 | 1.781 | 0.950 |
| C19 | 11.236 | 32.132 | 0.725 | 2.073 | 0.515 | 1.473 |
| C20 | 16.762 | 2.993 | 0.759 | 0.136 | 1.240 | 0.221 |
| C21 | 5.592 | 7.110 | 0.960 | 1.220 | 0.885 | 1.125 |
| C22 | 5.241 | 5.148 | 0.918 | 0.902 | 1.047 | 1.029 |
| C23 | 5.549 | 3.582 | 0.871 | 0.563 | 1.417 | 0.915 |
| C24A | 4.240 | 4.633 | 0.897 | 0.980 | 0.996 | 1.089 |
| C24B | 14.763 | 11.309 | 0.814 | 0.624 | 1.844 | 1.413 |
| C25 | 5.667 | 8.455 | 0.893 | 1.332 | 0.727 | 1.084 |
| C26 | 5.310 | 5.275 | 0.938 | 0.932 | 0.643 | 0.638 |
| C27 | 2.330 | 2.509 | 0.938 | 1.010 | 0.707 | 0.761 |
| C28 | 5.929 | 9.273 | 0.861 | 1.347 | 0.396 | 0.620 |
| C29 | 18.426 | 9.682 | 1.006 | 0.528 | 1.480 | 0.778 |
| C301 | 0.713 | 0.793 | 0.841 | 0.936 | 1.658 | 1.846 |
| C302T309 | 6.912 | 7.471 | 0.932 | 1.007 | 0.981 | 1.060 |
| C31T33 | 3.641 | 13.838 | 0.906 | 3.444 | 0.721 | 2.739 |
| D | 263.967 | 47.226 | 0.823 | 0.147 | 6.833 | 1.222 |
| E | 62.865 | 12.499 | 0.828 | 0.165 | 13.700 | 2.724 |
| F | 34.219 | 103.664 | 0.819 | 2.480 | 0.449 | 1.359 |
| G | 90.463 | 213.575 | 0.850 | 2.007 | 0.889 | 2.099 |
| H49 | 132.433 | 101.215 | 0.759 | 0.580 | 3.990 | 3.049 |
| H50 | 5.731 | 3.792 | 0.839 | 0.555 | 8.658 | 5.728 |
| H51 | 24.652 | 19.485 | 0.792 | 0.626 | 12.170 | 9.619 |
| H52 | 55.194 | 41.980 | 0.844 | 0.642 | 5.639 | 4.289 |
| H53 | 24.190 | 19.472 | 0.844 | 0.679 | 4.787 | 3.854 |
| I | 30.758 | 22.814 | 0.840 | 0.623 | 2.513 | 1.864 |
| J58T60 | 18.683 | 11.128 | 0.921 | 0.549 | 3.647 | 2.172 |
| J61 | 23.416 | 22.973 | 0.823 | 0.807 | 0.860 | 0.843 |
| J62_63 | 41.629 | 24.773 | 0.911 | 0.542 | 2.708 | 1.611 |
| K | 46.320 | 0.000 | 0.901 | 0.000 | 0.627 | 0.000 |
| L | 70.885 | 164.086 | 0.874 | 2.024 | 0.245 | 0.568 |
| M | 33.785 | 58.997 | 0.891 | 1.556 | 0.732 | 1.279 |
| N | 36.481 | 30.763 | 0.871 | 0.735 | 1.165 | 0.982 |
| O | 407.555 | 0.000 | 0.838 | 0.000 | 6.651 | 0.000 |
| P | 156.748 | 0.000 | 0.860 | 0.000 | 5.491 | 0.000 |
| Q | 92.905 | 0.000 | 0.862 | 0.000 | 1.941 | 0.000 |
| R | 19.452 | 7.738 | 0.868 | 0.345 | 2.619 | 1.042 |
| S | 5.210 | 10.057 | 0.831 | 1.604 | 0.637 | 1.230 |
| T | 0.009 | 0.000 | 0.678 | 0.000 | -78,897,380,656,263.422 | -0.000 |

## Bank reserves and initial capital

National reserves: -1,978.554B before, -988.361B after. Negative reserves
are the model's central-bank borrowing position, not customer deposits.
National bank equity remains 456.221B and is reallocated across the 13 regions
by final firm-plus-household initial loans. R = D_f + D_h + E - L.
The last two columns below are percentages. The existing resolution threshold
is 5% of loans plus the reserve/deposit stock used by DefaultBankDemography;
all banks start above it (minimum 11.685%).

| region | reserves_before | reserves_after | equity_to_loans | resolution_ratio |
| --- | --- | --- | --- | --- |
| CAN_NL | -28.163 | -10.996 | 10.955 | 13.328 |
| CAN_PE | -4.134 | -0.812 | 10.955 | 11.685 |
| CAN_NS | -60.398 | -38.545 | 10.955 | 16.815 |
| CAN_NB | -42.489 | -29.517 | 10.955 | 15.136 |
| CAN_QC | -377.523 | -179.895 | 10.955 | 13.704 |
| CAN_ON | -723.389 | -349.418 | 10.955 | 14.207 |
| CAN_MB | -52.502 | -26.098 | 10.955 | 13.548 |
| CAN_SK | -97.019 | -62.900 | 10.955 | 17.841 |
| CAN_AB | -306.161 | -149.058 | 10.955 | 14.873 |
| CAN_BC | -279.461 | -139.187 | 10.955 | 14.472 |
| CAN_YT | -2.467 | -0.738 | 10.955 | 13.098 |
| CAN_NT | -2.879 | -0.877 | 10.955 | 13.450 |
| CAN_NU | -1.968 | -0.321 | 10.955 | 12.419 |

## Firm distress specification and limits

Candidate-only flag: household_closure.firm_payment_default_enabled. Default
False. Provisional firm_distress_periods=3 and firm_collateral_haircut=0.20
are labelled assumptions, not sourced Canadian recovery estimates. E must
use the same N if it is eventually authorized by the household gate.

At quarter-end, after operating cash flows and the existing settlement,
senior debt service is loan principal plus loan interest plus overdraft
interest. Cash before service is reconstructed by adding this service back
to end deposits. If that cash cannot cover service, the distress clock rises;
a met payment resets it. Existing settlement funds shortages with overdrafts;
this rule identifies service not met *from cash*, rather than introducing
new unpaid-arrears contracts. Equity revaluation never enters the trigger.

After N quarters, total bank credit is formal loan principal plus the
negative deposit balance (overdraft). Write down only max(0, total bank credit
- 0.8 * current-price capital). Allocate this uncovered loss pro rata across
formal loans and overdrafts. Formal losses are assigned to actual loan-book
lenders; overdraft losses to the deposit-account bank. Both enter the same
quarter's by-bank loss queue. Formal principal write-offs enter the loan-stock
counter; overdraft relief is a separate named term in the cash/reserve battery.

Surviving formal principal, contractual interest and installments scale pro
rata. Covered overdrafts remain debit balances owed at their existing terms.
No maturity extension is added. The producer retains physical capital and
continues operating; equity rises by the exact liability relief. Relief cannot
create positive cash. The distress clock restarts after restructuring; event
counts and retained balances can therefore include repeated restructurings.

**Collateral coverage is not recovery cash.** No capital is sold and no lender
cash receipt is invented. Recovery cash is zero in F; retained formal contracts
and retained overdrafts are recorded separately. Covered overdrafts can still
accumulate between events. Review total credit/capital and gross overdrafts,
not just the smaller formal principal book or recognized losses.

F's assessment threshold for "material" is at least a 25% reduction in total
firm loan plus overdraft losses on every seed, alongside accounting <=1e-8.
This was declared before 12Q outcomes and does not enter model behavior.


## Quarterly household and bank losses, support and capital

Loan write-offs and overdraft losses are distinct components. Capital ratio is
equity/loans; minimum before resolution is also retained in quarterly.csv.

### Seed 0


| quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | min_capital_ratio_before_resolution | min_capital_ratio | min_resolution_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 72.697 | 0.000 | 0.000 | 72.697 | 0.000 | 5.335 | 5.335 | 7.637 |
| 2 | 62.299 | 0.000 | 0.000 | 62.299 | 0.000 | 5.029 | 5.029 | 7.217 |
| 3 | 35.742 | 0.103 | 0.029 | 35.874 | 0.690 | 3.010 | 4.825 | 6.904 |
| 4 | 27.140 | 14.596 | 14.432 | 56.168 | 6.077 | 2.057 | 4.889 | 6.298 |
| 5 | 12.233 | 9.302 | 2.816 | 24.350 | 28.146 | 3.356 | 4.625 | 5.100 |
| 6 | 9.478 | 2.056 | 0.809 | 12.342 | 2.611 | 4.158 | 4.449 | 5.378 |
| 7 | 5.225 | 17.467 | 31.595 | 54.287 | 68.629 | 1.897 | 4.185 | 5.201 |
| 8 | 2.630 | 8.702 | 5.321 | 16.653 | 62.488 | 3.517 | 3.517 | 5.327 |
| 9 | 2.681 | 12.315 | 4.071 | 19.067 | 5.471 | 3.099 | 3.935 | 5.080 |
| 10 | 2.276 | 12.694 | 41.361 | 56.331 | 45.687 | -9.085 | 6.131 | 5.651 |
| 11 | 2.212 | 6.611 | 8.375 | 17.199 | 0.299 | 5.657 | 5.657 | 5.447 |
| 12 | 1.840 | 7.290 | 5.455 | 14.584 | 0.042 | 5.670 | 5.670 | 5.009 |

### Seed 1


| quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | min_capital_ratio_before_resolution | min_capital_ratio | min_resolution_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 77.158 | 0.000 | 0.000 | 77.158 | 0.000 | 5.782 | 5.782 | 8.255 |
| 2 | 52.223 | 0.000 | 0.000 | 52.223 | 0.674 | 3.223 | 4.428 | 5.043 |
| 3 | 34.905 | 0.124 | 0.053 | 35.082 | 7.946 | 3.395 | 6.048 | 8.040 |
| 4 | 31.368 | 22.144 | 16.433 | 69.945 | 30.128 | 2.436 | 5.525 | 6.857 |
| 5 | 14.442 | 4.114 | 2.096 | 20.652 | 0.000 | 4.982 | 4.982 | 5.466 |
| 6 | 7.919 | 8.197 | 3.602 | 19.718 | 23.542 | 4.142 | 4.605 | 5.584 |
| 7 | 5.862 | 33.835 | 42.918 | 82.615 | 136.320 | -6.117 | 5.437 | 5.709 |
| 8 | 2.727 | 6.277 | 4.062 | 13.066 | 5.020 | 3.107 | 4.691 | 5.178 |
| 9 | 3.326 | 8.502 | 6.170 | 17.999 | 1.351 | 4.538 | 4.538 | 5.073 |
| 10 | 3.229 | 18.008 | 53.238 | 74.474 | 35.641 | 0.529 | 5.324 | 5.277 |
| 11 | 2.027 | 3.998 | 6.174 | 12.199 | 8.240 | 1.879 | 5.105 | 5.409 |
| 12 | 1.880 | 9.813 | 15.245 | 26.938 | 61.291 | 3.858 | 5.820 | 5.280 |

### Seed 2


| quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | min_capital_ratio_before_resolution | min_capital_ratio | min_resolution_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 75.383 | 0.000 | 0.000 | 75.383 | 0.000 | 5.645 | 5.645 | 8.069 |
| 2 | 58.728 | 0.000 | 0.000 | 58.728 | 0.681 | 3.159 | 5.634 | 7.427 |
| 3 | 39.615 | 0.146 | 0.069 | 39.830 | 0.000 | 4.606 | 4.606 | 6.604 |
| 4 | 23.917 | 20.600 | 14.186 | 58.703 | 6.522 | -1.298 | 3.841 | 5.124 |
| 5 | 10.289 | 7.989 | 4.738 | 23.017 | 55.020 | 3.245 | 4.602 | 5.607 |
| 6 | 7.421 | 7.720 | 4.264 | 19.406 | 0.000 | 4.400 | 4.400 | 5.293 |
| 7 | 5.869 | 14.417 | 31.159 | 51.445 | 49.113 | -6.037 | 4.474 | 5.035 |
| 8 | 5.466 | 4.637 | 7.725 | 17.828 | 6.169 | 3.558 | 4.387 | 5.194 |
| 9 | 3.906 | 17.041 | 9.865 | 30.811 | 72.453 | 3.661 | 5.048 | 5.168 |
| 10 | 1.938 | 10.247 | 48.367 | 60.553 | 43.415 | -3.155 | 4.567 | 5.530 |
| 11 | 2.537 | 3.067 | 8.836 | 14.440 | 0.472 | 4.239 | 4.239 | 5.263 |
| 12 | 1.945 | 4.062 | 10.854 | 16.860 | 1.361 | 1.619 | 4.246 | 5.477 |

### Twelve-quarter totals


| seed | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | resolution_events | min_capital_before_resolution | min_capital_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 236.453 | 91.135 | 114.264 | 441.852 | 220.141 | 20 | -9.085 | 3.517 |
| 1 | 237.065 | 115.013 | 149.990 | 502.068 | 310.153 | 25 | -6.117 | 4.428 |
| 2 | 237.015 | 89.926 | 140.063 | 467.004 | 235.207 | 25 | -6.037 | 3.841 |

## Resolution log


| seed | region | bank | quarter | equity_before | losses_absorbed_by_equity | uncovered_loss | recapitalisation | equity_after |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | CAN_PE | 0 | 3 | 0.347 | 0.712 | 0.000 | 0.690 | 1.037 |
| 0 | CAN_NB | 0 | 4 | 2.715 | 1.926 | 0.000 | 5.681 | 8.396 |
| 0 | CAN_YT | 0 | 4 | 0.134 | 0.157 | 0.000 | 0.228 | 0.362 |
| 0 | CAN_NU | 0 | 4 | 0.050 | 0.224 | 0.000 | 0.168 | 0.218 |
| 0 | CAN_BC | 0 | 5 | 16.733 | 8.213 | 0.000 | 28.146 | 44.879 |
| 0 | CAN_NL | 0 | 6 | 2.243 | 0.515 | 0.000 | 2.611 | 4.854 |
| 0 | CAN_PE | 0 | 7 | 0.564 | 0.269 | 0.000 | 0.397 | 0.961 |
| 0 | CAN_QC | 0 | 7 | 18.703 | 15.835 | 0.000 | 49.823 | 68.525 |
| 0 | CAN_AB | 0 | 7 | 25.115 | 1.400 | 0.000 | 18.249 | 43.364 |
| 0 | CAN_NU | 0 | 7 | 0.043 | 0.163 | 0.000 | 0.161 | 0.204 |
| 0 | CAN_ON | 0 | 8 | 53.857 | 3.042 | 0.000 | 62.488 | 116.345 |
| 0 | CAN_NS | 0 | 9 | 2.873 | 0.441 | 0.000 | 5.471 | 8.344 |
| 0 | CAN_NL | 0 | 10 | 2.201 | 1.233 | 0.000 | 2.369 | 4.569 |
| 0 | CAN_MB | 0 | 10 | 4.126 | 1.106 | 0.000 | 5.994 | 10.120 |
| 0 | CAN_AB | 0 | 10 | 24.859 | 3.838 | 0.000 | 15.460 | 40.319 |
| 0 | CAN_BC | 0 | 10 | 20.248 | 9.088 | 0.000 | 21.103 | 41.351 |
| 0 | CAN_YT | 0 | 10 | -0.060 | 0.145 | 0.060 | 0.385 | 0.324 |
| 0 | CAN_NU | 0 | 10 | -0.178 | 0.175 | 0.178 | 0.377 | 0.199 |
| 0 | CAN_PE | 0 | 11 | 0.606 | 0.091 | 0.000 | 0.299 | 0.905 |
| 0 | CAN_NU | 0 | 12 | 0.164 | 0.030 | 0.000 | 0.042 | 0.206 |
| 1 | CAN_PE | 0 | 2 | 0.376 | 0.688 | 0.000 | 0.674 | 1.051 |
| 1 | CAN_NL | 0 | 3 | 2.386 | 0.085 | 0.000 | 2.608 | 4.994 |
| 1 | CAN_NB | 0 | 3 | 3.234 | 2.313 | 0.000 | 5.338 | 8.572 |
| 1 | CAN_BC | 0 | 4 | 15.766 | 15.769 | 0.000 | 29.720 | 45.486 |
| 1 | CAN_YT | 0 | 4 | 0.098 | 0.171 | 0.000 | 0.264 | 0.361 |
| 1 | CAN_NU | 0 | 4 | 0.073 | 0.169 | 0.000 | 0.145 | 0.218 |
| 1 | CAN_AB | 0 | 6 | 20.074 | 6.351 | 0.000 | 23.542 | 43.616 |
| 1 | CAN_QC | 0 | 7 | 13.936 | 21.873 | 0.000 | 54.107 | 68.042 |
| 1 | CAN_ON | 0 | 7 | 41.526 | 36.019 | 0.000 | 76.003 | 117.529 |
| 1 | CAN_MB | 0 | 7 | 5.003 | 1.318 | 0.000 | 5.548 | 10.551 |
| 1 | CAN_YT | 0 | 7 | 0.013 | 0.277 | 0.000 | 0.325 | 0.338 |
| 1 | CAN_NU | 0 | 7 | -0.128 | 0.193 | 0.128 | 0.337 | 0.209 |
| 1 | CAN_NB | 0 | 8 | 2.647 | 2.576 | 0.000 | 5.020 | 7.666 |
| 1 | CAN_NL | 0 | 9 | 3.267 | 0.062 | 0.000 | 1.294 | 4.561 |
| 1 | CAN_NU | 0 | 9 | 0.192 | 0.006 | 0.000 | 0.057 | 0.249 |
| 1 | CAN_PE | 0 | 10 | 0.443 | 0.139 | 0.000 | 0.480 | 0.924 |
| 1 | CAN_NS | 0 | 10 | 3.349 | 0.919 | 0.000 | 4.951 | 8.300 |
| 1 | CAN_SK | 0 | 10 | 7.265 | 3.000 | 0.000 | 5.189 | 12.454 |
| 1 | CAN_BC | 0 | 10 | 16.703 | 10.113 | 0.000 | 24.523 | 41.226 |
| 1 | CAN_YT | 0 | 10 | 0.019 | 0.276 | 0.000 | 0.302 | 0.321 |
| 1 | CAN_NU | 0 | 10 | 0.085 | 0.164 | 0.000 | 0.196 | 0.281 |
| 1 | CAN_AB | 0 | 11 | 32.179 | 1.039 | 0.000 | 7.974 | 40.153 |
| 1 | CAN_NT | 0 | 11 | 0.070 | 0.207 | 0.000 | 0.266 | 0.337 |
| 1 | CAN_ON | 0 | 12 | 45.953 | 16.245 | 0.000 | 61.233 | 107.185 |
| 1 | CAN_NU | 0 | 12 | 0.271 | 0.008 | 0.000 | 0.058 | 0.329 |
| 2 | CAN_PE | 0 | 2 | 0.368 | 0.688 | 0.000 | 0.681 | 1.050 |
| 2 | CAN_NB | 0 | 4 | 2.334 | 2.086 | 0.000 | 6.053 | 8.387 |
| 2 | CAN_YT | 0 | 4 | 0.135 | 0.160 | 0.000 | 0.228 | 0.363 |
| 2 | CAN_NU | 0 | 4 | -0.030 | 0.254 | 0.030 | 0.241 | 0.211 |
| 2 | CAN_NL | 0 | 5 | 2.687 | 0.072 | 0.000 | 2.238 | 4.925 |
| 2 | CAN_AB | 0 | 5 | 20.416 | 8.342 | 0.000 | 24.092 | 44.508 |
| 2 | CAN_BC | 0 | 5 | 16.175 | 3.225 | 0.000 | 28.690 | 44.865 |
| 2 | CAN_NL | 0 | 7 | 2.487 | 2.192 | 0.000 | 2.150 | 4.637 |
| 2 | CAN_QC | 0 | 7 | 22.199 | 11.938 | 0.000 | 46.366 | 68.565 |
| 2 | CAN_YT | 0 | 7 | 0.049 | 0.284 | 0.000 | 0.294 | 0.343 |
| 2 | CAN_NU | 0 | 7 | -0.122 | 0.166 | 0.122 | 0.303 | 0.182 |
| 2 | CAN_PE | 0 | 8 | 0.369 | 0.334 | 0.000 | 0.564 | 0.934 |
| 2 | CAN_MB | 0 | 8 | 4.730 | 0.656 | 0.000 | 5.604 | 10.334 |
| 2 | CAN_NB | 0 | 9 | 3.319 | 3.042 | 0.000 | 4.270 | 7.589 |
| 2 | CAN_ON | 0 | 9 | 46.682 | 10.191 | 0.000 | 68.092 | 114.774 |
| 2 | CAN_NT | 0 | 9 | 0.271 | 0.027 | 0.000 | 0.091 | 0.362 |
| 2 | CAN_AB | 0 | 10 | 22.404 | 5.303 | 0.000 | 18.324 | 40.729 |
| 2 | CAN_BC | 0 | 10 | 16.543 | 10.390 | 0.000 | 24.503 | 41.046 |
| 2 | CAN_YT | 0 | 10 | -0.113 | 0.266 | 0.113 | 0.434 | 0.321 |
| 2 | CAN_NU | 0 | 10 | 0.016 | 0.117 | 0.000 | 0.154 | 0.170 |
| 2 | CAN_PE | 0 | 11 | 0.498 | 0.264 | 0.000 | 0.385 | 0.884 |
| 2 | CAN_NT | 0 | 11 | 0.314 | 0.028 | 0.000 | 0.087 | 0.401 |
| 2 | CAN_NL | 0 | 12 | 3.494 | 0.124 | 0.000 | 0.904 | 4.398 |
| 2 | CAN_PE | 0 | 12 | 0.547 | 0.340 | 0.000 | 0.307 | 0.854 |
| 2 | CAN_NU | 0 | 12 | 0.029 | 0.133 | 0.000 | 0.151 | 0.180 |

## Quarterly macro, household investment and constraints


### Seed 0


| quarter | gdp | consumption | cash_DI | cash_saving_rate | planned_investment | investment | investment_cut | consumption_cut | asset_liquidation | constrained_share | consumption_constrained_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 700.194 | 378.859 | 371.908 | -1.869 | 60.850 | 50.916 | 8.494 | 5.404 | 11.027 | 18.631 | 12.026 |
| 2 | 693.301 | 370.187 | 366.518 | -1.001 | 59.816 | 46.496 | 12.519 | 10.427 | 19.935 | 24.752 | 18.099 |
| 3 | 690.172 | 360.159 | 361.116 | 0.265 | 58.742 | 43.605 | 15.096 | 15.121 | 23.173 | 29.481 | 22.625 |
| 4 | 696.450 | 353.685 | 358.580 | 1.365 | 58.454 | 40.903 | 17.426 | 18.057 | 23.954 | 33.326 | 26.326 |
| 5 | 693.015 | 354.295 | 360.103 | 1.613 | 59.060 | 39.477 | 19.513 | 21.001 | 24.995 | 36.395 | 29.789 |
| 6 | 685.890 | 351.336 | 357.213 | 1.645 | 58.405 | 37.639 | 20.738 | 21.612 | 25.426 | 39.103 | 30.758 |
| 7 | 682.802 | 346.417 | 353.891 | 2.112 | 57.817 | 35.410 | 22.322 | 23.535 | 24.696 | 41.526 | 33.024 |
| 8 | 689.678 | 343.655 | 353.981 | 2.917 | 57.979 | 34.035 | 23.731 | 25.685 | 24.316 | 43.530 | 34.706 |
| 9 | 677.072 | 347.094 | 357.083 | 2.798 | 58.292 | 33.648 | 24.537 | 25.744 | 24.703 | 45.636 | 35.501 |
| 10 | 680.509 | 340.708 | 353.427 | 3.599 | 57.226 | 32.133 | 25.052 | 25.663 | 23.426 | 47.362 | 36.651 |
| 11 | 673.038 | 339.222 | 351.442 | 3.477 | 57.572 | 30.514 | 26.685 | 28.076 | 23.030 | 49.101 | 39.575 |
| 12 | 670.410 | 342.184 | 352.538 | 2.937 | 57.995 | 30.113 | 27.862 | 29.574 | 24.088 | 50.523 | 44.185 |

### Seed 1


| quarter | gdp | consumption | cash_DI | cash_saving_rate | planned_investment | investment | investment_cut | consumption_cut | asset_liquidation | constrained_share | consumption_constrained_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 714.585 | 382.888 | 371.141 | -3.165 | 60.935 | 49.775 | 8.661 | 5.579 | 11.618 | 18.762 | 12.414 |
| 2 | 709.956 | 372.912 | 370.588 | -0.627 | 60.581 | 47.286 | 12.987 | 10.910 | 19.893 | 25.070 | 18.584 |
| 3 | 703.832 | 365.885 | 366.867 | 0.268 | 59.970 | 44.079 | 15.617 | 14.511 | 23.133 | 29.793 | 22.602 |
| 4 | 690.366 | 362.853 | 367.323 | 1.217 | 60.080 | 41.845 | 17.926 | 17.797 | 24.759 | 33.515 | 26.462 |
| 5 | 681.167 | 351.114 | 361.586 | 2.896 | 58.828 | 39.272 | 19.115 | 19.443 | 23.541 | 36.294 | 28.350 |
| 6 | 690.680 | 346.583 | 352.980 | 1.812 | 57.412 | 37.282 | 20.032 | 20.267 | 26.080 | 39.080 | 29.178 |
| 7 | 688.669 | 346.127 | 357.051 | 3.059 | 58.437 | 35.604 | 22.575 | 23.597 | 23.796 | 41.503 | 33.536 |
| 8 | 689.913 | 342.329 | 358.652 | 4.551 | 58.664 | 35.313 | 23.288 | 23.958 | 22.706 | 43.435 | 34.291 |
| 9 | 681.522 | 353.219 | 361.192 | 2.207 | 58.968 | 35.072 | 23.645 | 23.072 | 27.479 | 45.328 | 32.873 |
| 10 | 670.565 | 350.005 | 362.599 | 3.473 | 59.231 | 33.180 | 25.961 | 26.922 | 23.647 | 47.234 | 37.480 |
| 11 | 678.855 | 339.199 | 353.918 | 4.159 | 57.575 | 31.761 | 25.592 | 27.070 | 22.534 | 48.941 | 37.947 |
| 12 | 666.865 | 346.042 | 357.872 | 3.306 | 58.666 | 31.194 | 27.325 | 28.614 | 23.811 | 50.317 | 43.151 |

### Seed 2


| quarter | gdp | consumption | cash_DI | cash_saving_rate | planned_investment | investment | investment_cut | consumption_cut | asset_liquidation | constrained_share | consumption_constrained_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 696.683 | 378.706 | 370.753 | -2.145 | 60.458 | 49.380 | 8.339 | 5.390 | 11.410 | 18.561 | 11.626 |
| 2 | 686.512 | 367.015 | 363.336 | -1.013 | 59.067 | 44.730 | 12.222 | 10.293 | 19.511 | 24.624 | 17.952 |
| 3 | 674.532 | 353.193 | 356.492 | 0.925 | 57.967 | 42.739 | 14.807 | 15.575 | 22.046 | 29.334 | 24.176 |
| 4 | 669.293 | 346.610 | 352.039 | 1.542 | 56.820 | 40.371 | 16.369 | 17.609 | 24.627 | 32.999 | 25.096 |
| 5 | 667.864 | 342.382 | 351.041 | 2.467 | 56.630 | 38.272 | 18.238 | 19.994 | 23.712 | 35.887 | 28.149 |
| 6 | 659.086 | 340.590 | 349.981 | 2.684 | 56.784 | 36.311 | 20.082 | 20.519 | 23.499 | 38.673 | 30.327 |
| 7 | 652.437 | 331.692 | 345.058 | 3.874 | 56.225 | 34.655 | 21.162 | 22.060 | 22.740 | 41.051 | 32.716 |
| 8 | 644.189 | 327.948 | 342.374 | 4.213 | 55.934 | 33.912 | 21.557 | 23.579 | 24.227 | 42.744 | 32.104 |
| 9 | 642.080 | 331.315 | 337.347 | 1.788 | 55.183 | 32.601 | 22.555 | 23.734 | 27.039 | 44.773 | 34.306 |
| 10 | 635.072 | 319.760 | 337.582 | 5.279 | 55.124 | 30.538 | 24.244 | 27.144 | 21.342 | 46.821 | 37.948 |
| 11 | 637.323 | 323.942 | 335.023 | 3.308 | 54.545 | 30.474 | 23.762 | 25.513 | 24.366 | 48.199 | 36.201 |
| 12 | 632.115 | 325.136 | 338.204 | 3.864 | 55.542 | 29.112 | 25.985 | 29.344 | 22.694 | 49.679 | 41.273 |

## Firm defaults, collateral coverage and leverage

Every nonzero quarter/industry cell is in outputs/FE/firm_defaults_detail.csv;
industry leverage paths are in leverage_industry.csv. Defaults count composite
producer restructuring events, including repeat events, not legal insolvencies.
recovery_cash is zero: collateral stays with the producer and secures the
retained contract. It is not sold and does not repay the lender in cash.


| seed | industry_code | defaults | loan_debt | overdraft_cancelled | retained_contract | recovery_cash |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | A01 | 21 | 5.543 | 2.181 | 57.999 | 0.000 |
| 0 | A02 | 22 | 6.334 | 3.684 | 5.755 | 0.000 |
| 0 | A03 | 22 | 1.011 | 0.451 | 0.857 | 0.000 |
| 0 | B05 | 36 | 0.001 | 0.003 | 0.085 | 0.000 |
| 0 | B06 | 18 | 0.000 | 0.000 | 0.018 | 0.000 |
| 0 | B07 | 17 | 1.075 | 2.705 | 7.407 | 0.000 |
| 0 | B08 | 28 | 0.286 | 0.641 | 12.067 | 0.000 |
| 0 | B09 | 21 | 0.031 | 0.175 | 12.847 | 0.000 |
| 0 | C10T12 | 9 | 0.559 | 0.419 | 1.858 | 0.000 |
| 0 | C13T15 | 7 | 1.652 | 0.429 | 2.759 | 0.000 |
| 0 | C16 | 19 | 0.710 | 0.541 | 4.635 | 0.000 |
| 0 | C17_18 | 29 | 0.806 | 2.069 | 13.378 | 0.000 |
| 0 | C19 | 20 | 5.030 | 3.764 | 4.102 | 0.000 |
| 0 | C20 | 8 | 0.001 | 0.009 | 0.641 | 0.000 |
| 0 | C21 | 14 | 0.723 | 0.252 | 2.991 | 0.000 |
| 0 | C22 | 24 | 0.944 | 2.927 | 4.436 | 0.000 |
| 0 | C23 | 31 | 1.136 | 1.964 | 7.271 | 0.000 |
| 0 | C24A | 20 | 0.378 | 0.581 | 3.987 | 0.000 |
| 0 | C24B | 14 | 3.258 | 1.557 | 9.482 | 0.000 |
| 0 | C25 | 16 | 0.839 | 0.369 | 2.081 | 0.000 |
| 0 | C26 | 19 | 0.244 | 0.190 | 0.601 | 0.000 |
| 0 | C27 | 19 | 0.677 | 0.812 | 2.056 | 0.000 |
| 0 | C28 | 5 | 0.657 | 0.250 | 2.861 | 0.000 |
| 0 | C29 | 4 | 0.002 | 0.000 | 9.107 | 0.000 |
| 0 | C301 | 28 | 0.466 | 0.661 | 2.133 | 0.000 |
| 0 | C302T309 | 11 | 0.284 | 0.409 | 0.502 | 0.000 |
| 0 | C31T33 | 15 | 6.280 | 1.640 | 2.973 | 0.000 |
| 0 | D | 17 | 0.000 | 0.000 | 39.073 | 0.000 |
| 0 | E | 38 | 0.000 | 0.000 | 44.090 | 0.000 |
| 0 | F | 3 | 10.926 | 2.178 | 12.761 | 0.000 |
| 0 | G | 1 | 0.020 | 0.002 | 0.089 | 0.000 |
| 0 | H49 | 11 | 0.264 | 0.157 | 3.705 | 0.000 |
| 0 | H50 | 41 | 0.659 | 0.592 | 14.277 | 0.000 |
| 0 | H51 | 39 | 5.200 | 4.130 | 68.010 | 0.000 |
| 0 | H52 | 20 | 2.477 | 0.948 | 34.686 | 0.000 |
| 0 | H53 | 42 | 7.505 | 7.616 | 65.930 | 0.000 |
| 0 | I | 37 | 16.036 | 55.534 | 88.419 | 0.000 |
| 0 | J58T60 | 35 | 0.960 | 2.075 | 16.944 | 0.000 |
| 0 | J61 | 11 | 0.660 | 0.187 | 4.412 | 0.000 |
| 0 | J62_63 | 24 | 2.214 | 2.827 | 40.171 | 0.000 |
| 0 | K | 3 | 0.000 | 0.014 | 0.025 | 0.000 |
| 0 | M | 4 | 0.043 | 0.013 | 0.025 | 0.000 |
| 0 | N | 16 | 0.228 | 0.602 | 11.506 | 0.000 |
| 0 | P | 7 | 0.000 | 0.000 | 0.724 | 0.000 |
| 0 | Q | 3 | 0.000 | 0.000 | 0.277 | 0.000 |
| 0 | R | 39 | 1.801 | 5.772 | 48.471 | 0.000 |
| 0 | S | 27 | 3.215 | 2.932 | 5.809 | 0.000 |
| 0 | T | 39 | 0.000 | 0.000 | 0.887 | 0.000 |
| 1 | A01 | 18 | 3.208 | 1.932 | 40.690 | 0.000 |
| 1 | A02 | 25 | 6.962 | 4.651 | 5.587 | 0.000 |
| 1 | A03 | 21 | 1.051 | 0.535 | 0.780 | 0.000 |
| 1 | B05 | 36 | 0.000 | 0.000 | 0.075 | 0.000 |
| 1 | B06 | 19 | 0.000 | 0.000 | 0.031 | 0.000 |
| 1 | B07 | 17 | 0.319 | 0.236 | 6.733 | 0.000 |
| 1 | B08 | 28 | 0.321 | 0.644 | 11.723 | 0.000 |
| 1 | B09 | 26 | 0.145 | 1.097 | 17.216 | 0.000 |
| 1 | C10T12 | 13 | 16.888 | 20.957 | 23.723 | 0.000 |
| 1 | C13T15 | 9 | 1.932 | 0.887 | 2.759 | 0.000 |
| 1 | C16 | 21 | 1.438 | 1.820 | 6.586 | 0.000 |
| 1 | C17_18 | 30 | 0.288 | 0.896 | 11.941 | 0.000 |
| 1 | C19 | 19 | 13.340 | 7.267 | 7.309 | 0.000 |
| 1 | C20 | 20 | 0.040 | 0.291 | 3.431 | 0.000 |
| 1 | C21 | 13 | 0.426 | 0.668 | 1.663 | 0.000 |
| 1 | C22 | 25 | 0.920 | 3.592 | 3.533 | 0.000 |
| 1 | C23 | 35 | 1.019 | 1.289 | 11.069 | 0.000 |
| 1 | C24A | 21 | 0.250 | 0.518 | 2.970 | 0.000 |
| 1 | C24B | 16 | 0.070 | 0.190 | 4.052 | 0.000 |
| 1 | C25 | 17 | 2.251 | 2.469 | 4.838 | 0.000 |
| 1 | C26 | 17 | 0.115 | 0.131 | 0.367 | 0.000 |
| 1 | C27 | 17 | 1.271 | 2.107 | 4.054 | 0.000 |
| 1 | C28 | 5 | 1.139 | 1.214 | 2.643 | 0.000 |
| 1 | C29 | 3 | 0.002 | 0.000 | 0.000 | 0.000 |
| 1 | C301 | 26 | 0.463 | 0.970 | 1.589 | 0.000 |
| 1 | C302T309 | 10 | 0.542 | 0.060 | 1.718 | 0.000 |
| 1 | C31T33 | 25 | 9.952 | 4.989 | 5.373 | 0.000 |
| 1 | D | 17 | 0.000 | 0.000 | 27.683 | 0.000 |
| 1 | E | 40 | 0.000 | 0.000 | 52.642 | 0.000 |
| 1 | F | 3 | 0.301 | 0.131 | 0.129 | 0.000 |
| 1 | H49 | 12 | 0.496 | 0.094 | 4.098 | 0.000 |
| 1 | H50 | 42 | 0.757 | 1.001 | 15.123 | 0.000 |
| 1 | H51 | 39 | 6.940 | 7.059 | 66.590 | 0.000 |
| 1 | H52 | 22 | 4.593 | 2.378 | 66.561 | 0.000 |
| 1 | H53 | 41 | 8.110 | 8.626 | 63.048 | 0.000 |
| 1 | I | 33 | 15.921 | 51.278 | 87.221 | 0.000 |
| 1 | J58T60 | 37 | 2.107 | 3.912 | 19.824 | 0.000 |
| 1 | J61 | 12 | 2.664 | 1.300 | 18.392 | 0.000 |
| 1 | J62_63 | 20 | 0.001 | 0.011 | 9.132 | 0.000 |
| 1 | K | 5 | 0.000 | 0.017 | 0.061 | 0.000 |
| 1 | M | 7 | 0.062 | 0.033 | 0.124 | 0.000 |
| 1 | N | 19 | 0.772 | 0.592 | 35.952 | 0.000 |
| 1 | P | 7 | 0.000 | 0.000 | 0.877 | 0.000 |
| 1 | Q | 3 | 0.000 | 0.000 | 0.314 | 0.000 |
| 1 | R | 38 | 1.741 | 5.406 | 42.724 | 0.000 |
| 1 | S | 31 | 6.197 | 8.743 | 11.918 | 0.000 |
| 1 | T | 39 | 0.000 | 0.000 | 0.887 | 0.000 |
| 2 | A01 | 17 | 2.262 | 1.049 | 11.566 | 0.000 |
| 2 | A02 | 23 | 6.817 | 6.184 | 4.865 | 0.000 |
| 2 | A03 | 24 | 1.105 | 0.533 | 0.625 | 0.000 |
| 2 | B05 | 36 | 0.000 | 0.000 | 0.078 | 0.000 |
| 2 | B06 | 21 | 0.000 | 0.000 | 0.754 | 0.000 |
| 2 | B07 | 19 | 0.454 | 0.349 | 6.378 | 0.000 |
| 2 | B08 | 29 | 0.386 | 0.955 | 12.080 | 0.000 |
| 2 | B09 | 23 | 0.000 | 0.000 | 13.620 | 0.000 |
| 2 | C10T12 | 14 | 6.730 | 11.271 | 8.077 | 0.000 |
| 2 | C13T15 | 6 | 0.933 | 0.152 | 1.321 | 0.000 |
| 2 | C16 | 22 | 0.616 | 1.069 | 2.152 | 0.000 |
| 2 | C17_18 | 23 | 1.144 | 2.884 | 13.486 | 0.000 |
| 2 | C19 | 12 | 2.582 | 0.818 | 3.150 | 0.000 |
| 2 | C20 | 16 | 0.021 | 0.154 | 1.211 | 0.000 |
| 2 | C21 | 14 | 1.533 | 1.001 | 4.208 | 0.000 |
| 2 | C22 | 16 | 0.415 | 1.243 | 1.425 | 0.000 |
| 2 | C23 | 31 | 0.502 | 0.585 | 4.330 | 0.000 |
| 2 | C24A | 17 | 0.430 | 0.639 | 2.941 | 0.000 |
| 2 | C24B | 19 | 0.238 | 0.663 | 4.096 | 0.000 |
| 2 | C25 | 15 | 3.813 | 8.048 | 8.596 | 0.000 |
| 2 | C26 | 13 | 0.194 | 0.172 | 0.485 | 0.000 |
| 2 | C27 | 15 | 0.838 | 2.186 | 2.199 | 0.000 |
| 2 | C28 | 3 | 0.004 | 0.000 | 0.000 | 0.000 |
| 2 | C29 | 4 | 0.033 | 0.034 | 13.636 | 0.000 |
| 2 | C301 | 25 | 0.380 | 0.671 | 1.241 | 0.000 |
| 2 | C302T309 | 12 | 0.685 | 0.286 | 5.586 | 0.000 |
| 2 | C31T33 | 18 | 4.825 | 1.937 | 3.872 | 0.000 |
| 2 | D | 21 | 0.000 | 0.000 | 29.403 | 0.000 |
| 2 | E | 38 | 0.000 | 0.000 | 47.242 | 0.000 |
| 2 | F | 5 | 12.378 | 1.697 | 12.264 | 0.000 |
| 2 | G | 2 | 0.016 | 0.002 | 0.206 | 0.000 |
| 2 | H49 | 11 | 0.551 | 0.075 | 31.039 | 0.000 |
| 2 | H50 | 45 | 0.641 | 0.712 | 14.415 | 0.000 |
| 2 | H51 | 38 | 5.280 | 4.779 | 61.550 | 0.000 |
| 2 | H52 | 29 | 0.431 | 0.139 | 68.159 | 0.000 |
| 2 | H53 | 41 | 7.169 | 6.804 | 62.664 | 0.000 |
| 2 | I | 36 | 16.626 | 57.885 | 84.457 | 0.000 |
| 2 | J58T60 | 32 | 1.257 | 3.024 | 17.983 | 0.000 |
| 2 | J61 | 10 | 0.023 | 0.045 | 0.606 | 0.000 |
| 2 | J62_63 | 17 | 0.001 | 0.007 | 12.181 | 0.000 |
| 2 | K | 3 | 0.000 | 0.015 | 0.025 | 0.000 |
| 2 | M | 5 | 0.052 | 0.050 | 0.045 | 0.000 |
| 2 | N | 20 | 0.434 | 0.646 | 36.713 | 0.000 |
| 2 | O | 1 | 0.000 | 0.000 | 3.192 | 0.000 |
| 2 | P | 6 | 0.000 | 0.000 | 0.294 | 0.000 |
| 2 | Q | 3 | 0.000 | 0.000 | 0.253 | 0.000 |
| 2 | R | 38 | 3.473 | 13.334 | 48.419 | 0.000 |
| 2 | S | 27 | 4.653 | 7.968 | 7.879 | 0.000 |
| 2 | T | 39 | 0.000 | 0.000 | 0.800 | 0.000 |

| seed | quarter | defaults | loan_debt | overdraft_cancelled | retained_contract | retained_loan | retained_overdraft | recovery_cash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 3 | 41 | 0.103 | 0.029 | 0.402 | 0.287 | 0.115 | 0.000 |
| 0 | 4 | 121 | 14.596 | 14.432 | 98.063 | 59.910 | 38.153 | 0.000 |
| 0 | 5 | 59 | 9.302 | 2.816 | 46.315 | 37.165 | 9.150 | 0.000 |
| 0 | 6 | 77 | 2.056 | 0.809 | 14.232 | 10.864 | 3.368 | 0.000 |
| 0 | 7 | 149 | 17.467 | 31.595 | 149.567 | 73.445 | 76.122 | 0.000 |
| 0 | 8 | 90 | 8.702 | 5.321 | 61.606 | 41.426 | 20.180 | 0.000 |
| 0 | 9 | 94 | 12.315 | 4.071 | 27.615 | 18.267 | 9.349 | 0.000 |
| 0 | 10 | 155 | 12.694 | 41.361 | 175.123 | 69.674 | 105.450 | 0.000 |
| 0 | 11 | 76 | 6.611 | 8.375 | 61.691 | 32.079 | 29.612 | 0.000 |
| 0 | 12 | 92 | 7.290 | 5.455 | 40.567 | 25.691 | 14.876 | 0.000 |
| 1 | 3 | 47 | 0.124 | 0.053 | 2.257 | 1.189 | 1.068 | 0.000 |
| 1 | 4 | 130 | 22.144 | 16.433 | 99.925 | 61.775 | 38.150 | 0.000 |
| 1 | 5 | 53 | 4.114 | 2.096 | 27.460 | 21.705 | 5.756 | 0.000 |
| 1 | 6 | 80 | 8.197 | 3.602 | 20.306 | 13.229 | 7.077 | 0.000 |
| 1 | 7 | 162 | 33.835 | 42.918 | 161.851 | 83.399 | 78.453 | 0.000 |
| 1 | 8 | 79 | 6.277 | 4.062 | 72.407 | 54.399 | 18.008 | 0.000 |
| 1 | 9 | 105 | 8.502 | 6.170 | 34.483 | 18.675 | 15.808 | 0.000 |
| 1 | 10 | 169 | 18.008 | 53.238 | 163.752 | 61.734 | 102.018 | 0.000 |
| 1 | 11 | 74 | 3.998 | 6.174 | 76.680 | 50.719 | 25.962 | 0.000 |
| 1 | 12 | 100 | 9.813 | 15.245 | 46.630 | 21.934 | 24.697 | 0.000 |
| 2 | 3 | 41 | 0.146 | 0.069 | 0.250 | 0.153 | 0.097 | 0.000 |
| 2 | 4 | 119 | 20.600 | 14.186 | 93.735 | 59.044 | 34.692 | 0.000 |
| 2 | 5 | 61 | 7.989 | 4.738 | 23.976 | 17.764 | 6.213 | 0.000 |
| 2 | 6 | 75 | 7.720 | 4.264 | 23.109 | 16.802 | 6.306 | 0.000 |
| 2 | 7 | 142 | 14.417 | 31.159 | 137.705 | 74.448 | 63.257 | 0.000 |
| 2 | 8 | 93 | 4.637 | 7.725 | 50.878 | 36.459 | 14.419 | 0.000 |
| 2 | 9 | 93 | 17.041 | 9.865 | 49.199 | 35.143 | 14.056 | 0.000 |
| 2 | 10 | 150 | 10.247 | 48.367 | 153.583 | 69.247 | 84.336 | 0.000 |
| 2 | 11 | 82 | 3.067 | 8.836 | 65.306 | 42.848 | 22.458 | 0.000 |
| 2 | 12 | 98 | 4.062 | 10.854 | 74.029 | 42.662 | 31.367 | 0.000 |

| seed | quarter | debt | overdraft | total_bank_credit | credit_to_capital | credit_to_annualised_GOS |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 1260.255 | 0.304 | 1260.559 | 0.428 | 0.961 |
| 0 | 2 | 1238.895 | 13.987 | 1252.882 | 0.427 | 0.962 |
| 0 | 3 | 1217.432 | 35.808 | 1253.240 | 0.432 | 0.959 |
| 0 | 4 | 1181.477 | 46.619 | 1228.096 | 0.420 | 0.915 |
| 0 | 5 | 1151.077 | 72.454 | 1223.531 | 0.411 | 0.920 |
| 0 | 6 | 1128.093 | 102.229 | 1230.322 | 0.414 | 0.940 |
| 0 | 7 | 1089.735 | 103.009 | 1192.744 | 0.402 | 0.911 |
| 0 | 8 | 1060.473 | 130.565 | 1191.037 | 0.396 | 0.890 |
| 0 | 9 | 1027.764 | 158.443 | 1186.207 | 0.396 | 0.931 |
| 0 | 10 | 994.918 | 149.526 | 1144.444 | 0.388 | 0.877 |
| 0 | 11 | 968.408 | 173.080 | 1141.489 | 0.387 | 0.888 |
| 0 | 12 | 941.355 | 200.585 | 1141.940 | 0.386 | 0.896 |
| 1 | 1 | 1260.255 | 0.327 | 1260.582 | 0.428 | 0.921 |
| 1 | 2 | 1238.895 | 14.714 | 1253.608 | 0.423 | 0.931 |
| 1 | 3 | 1217.411 | 38.044 | 1255.454 | 0.424 | 0.943 |
| 1 | 4 | 1173.908 | 46.977 | 1220.886 | 0.421 | 0.951 |
| 1 | 5 | 1148.831 | 76.176 | 1225.007 | 0.425 | 0.965 |
| 1 | 6 | 1119.746 | 111.349 | 1231.096 | 0.413 | 0.921 |
| 1 | 7 | 1065.175 | 107.187 | 1172.362 | 0.383 | 0.888 |
| 1 | 8 | 1038.800 | 139.513 | 1178.313 | 0.389 | 0.892 |
| 1 | 9 | 1010.321 | 168.095 | 1178.416 | 0.395 | 0.921 |
| 1 | 10 | 972.503 | 152.748 | 1125.251 | 0.373 | 0.910 |
| 1 | 11 | 949.055 | 188.423 | 1137.479 | 0.371 | 0.872 |
| 1 | 12 | 919.873 | 216.727 | 1136.601 | 0.364 | 0.911 |
| 2 | 1 | 1260.255 | 0.283 | 1260.537 | 0.445 | 0.971 |
| 2 | 2 | 1238.895 | 12.518 | 1251.412 | 0.456 | 0.976 |
| 2 | 3 | 1217.388 | 33.741 | 1251.129 | 0.455 | 0.994 |
| 2 | 4 | 1175.430 | 43.296 | 1218.726 | 0.442 | 0.967 |
| 2 | 5 | 1146.451 | 65.869 | 1212.320 | 0.436 | 0.958 |
| 2 | 6 | 1117.886 | 91.139 | 1209.026 | 0.430 | 0.975 |
| 2 | 7 | 1082.768 | 92.068 | 1174.836 | 0.416 | 0.950 |
| 2 | 8 | 1057.702 | 117.522 | 1175.224 | 0.418 | 0.967 |
| 2 | 9 | 1020.321 | 144.042 | 1164.364 | 0.412 | 0.948 |
| 2 | 10 | 990.068 | 132.617 | 1122.684 | 0.394 | 0.933 |
| 2 | 11 | 967.199 | 160.984 | 1128.182 | 0.394 | 0.921 |
| 2 | 12 | 943.398 | 189.037 | 1132.435 | 0.394 | 0.948 |

### Why the firm-loss gate is not robust on seed 1

The 25% materiality assessment is a conservative analysis threshold chosen
before the runs, not a number specified by the user or a model calibration.
Seed 1 still has lower firm losses, but only by 20.2%. The independent
household check stops E regardless of that materiality interpretation.


| seed | firm_losses | default_events | negative_profit_loss_pct | losses_while_positive_equity | payout_at_loss_events | payouts_while_negative_profit | payouts_while_end_cash_short |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 205.399 | 954 | 98.711 | 119.260 | 0.000 | 49.468 | 7.960 |
| 1 | 265.003 | 999 | 98.825 | 142.544 | 0.000 | 52.833 | 8.019 |
| 2 | 229.988 | 954 | 97.888 | 121.138 | 0.000 | 54.025 | 6.307 |

| seed | industry_code | losses | formal_losses | overdraft_losses | initial_debt_capital |
| --- | --- | --- | --- | --- | --- |
| 0 | I | 71.570 | 16.036 | 55.534 | 0.623 |
| 0 | H53 | 15.121 | 7.505 | 7.616 | 0.679 |
| 0 | F | 13.104 | 10.926 | 2.178 | 2.480 |
| 0 | A02 | 10.017 | 6.334 | 3.684 | 3.415 |
| 0 | H51 | 9.329 | 5.200 | 4.130 | 0.626 |
| 0 | C19 | 8.794 | 5.030 | 3.764 | 2.073 |
| 1 | I | 67.199 | 15.921 | 51.278 | 0.623 |
| 1 | C10T12 | 37.845 | 16.888 | 20.957 | 1.580 |
| 1 | C19 | 20.607 | 13.340 | 7.267 | 2.073 |
| 1 | H53 | 16.737 | 8.110 | 8.626 | 0.679 |
| 1 | C31T33 | 14.941 | 9.952 | 4.989 | 3.444 |
| 1 | S | 14.940 | 6.197 | 8.743 | 1.604 |
| 2 | I | 74.510 | 16.626 | 57.885 | 0.623 |
| 2 | C10T12 | 18.001 | 6.730 | 11.271 | 1.580 |
| 2 | R | 16.806 | 3.473 | 13.334 | 0.345 |
| 2 | F | 14.076 | 12.378 | 1.697 | 2.480 |
| 2 | H53 | 13.973 | 7.169 | 6.804 | 0.679 |
| 2 | A02 | 13.001 | 6.817 | 6.184 | 3.415 |

Accommodation/food services is a persistent loss source across seeds.
Seed 1 additionally has large food-manufacturing and refining losses. The
industry allocation raises initial credit in those manufacturing industries
relative to physical capital; this is visible in the independent initial
debt/capital table. Continued operating deficits then rebuild overdrafts
between restructurings. Most loss occurs with negative current profit;
the largest events pay no distributions in that event quarter. Earlier
payouts and lost demand can still affect cash, so this is not a causal
claim that D2 has no effect. Revaluation alone does not fire the trigger.
The debt boundary and default rule changed together: their separate
contributions are not identified by this one-arm comparison.

Proposals for decision, not implemented: review firm cash budgets and
investment finance before repeated overdrafts; require a funded retained-
profit/current-cash buffer for discretionary payouts; validate recoverable
assets (including the treatment of inventory/receivables) against loan
collateral concepts; specify recovery or workout finance for continuing
producers. Do not alter N, haircut or income targets to conceal the losses.
Largest firm events and reconciled sector totals are retained in
largest_firm_loss_events.csv and firm_loss_industry_diagnosis.csv.


### Government-producer financing boundary

Initial O/P/Q formal loans are zero, as required by the data correction.
The inherited cash settlement can still create operating overdrafts later.
These are reported and included in F losses, rather than hidden by the
formal-loan boundary. A strict no-private-credit boundary for ongoing public
producer operations requires a specified government working-capital cash
counterparty; proposal only, not an invented fiscal transfer in this run.


| seed | debt | overdraft |
| --- | --- | --- |
| 0 | 0.000 | 0.911 |
| 1 | 0.000 | 2.267 |
| 2 | 0.000 | 3.516 |

## Household constraint diagnosis

Fixed initial income deciles and non-pension asset bands; household counts
are represented counts. The restoration test holds current plans, resources
other than income, and senior payments fixed; it is not a causal decomposition.
The mutually exclusive classes and overlapping income/job/asset indicators
are all retained, so simultaneous mechanisms are visible.


| seed | diagnosis | households | constrained | income_change | wage_change | firm_receipts_change | other_income_change | employment_change | consumption_cut | investment_cut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | income_restoration_sufficient | 466510 | 466510 | -5.575 | -5.867 | -1.027 | 1.319 | -421170.000 | 0.968 | 1.542 |
| 0 | other_or_combined | 4080230 | 4080230 | 0.216 | 0.457 | -1.201 | 0.960 | -117050.000 | 12.139 | 12.494 |
| 0 | persistent_spending_gap_assets_down | 3283000 | 3283000 | -1.262 | -0.285 | -2.040 | 1.063 | -173000.000 | 16.467 | 13.826 |
| 0 | unconstrained | 7667580 | 0 | -12.512 | -4.995 | -10.452 | 2.935 | -623820.000 | 0.000 | 0.000 |
| 1 | income_restoration_sufficient | 534620 | 534620 | -7.651 | -8.133 | -1.209 | 1.690 | -480370.000 | 1.208 | 1.705 |
| 1 | other_or_combined | 4063050 | 4063050 | 2.645 | 1.866 | -1.158 | 1.937 | -112010.000 | 11.600 | 12.253 |
| 1 | persistent_spending_gap_assets_down | 3200160 | 3200160 | 1.099 | 1.370 | -1.952 | 1.682 | -171030.000 | 15.806 | 13.367 |
| 1 | unconstrained | 7699490 | 0 | -9.124 | -3.755 | -10.355 | 4.986 | -574360.000 | 0.000 | 0.000 |
| 2 | income_restoration_sufficient | 716500 | 716500 | -9.921 | -10.339 | -1.638 | 2.056 | -610260.000 | 1.747 | 2.337 |
| 2 | other_or_combined | 3984190 | 3984190 | -1.055 | -0.893 | -1.197 | 1.035 | -122010.000 | 12.147 | 11.697 |
| 2 | persistent_spending_gap_assets_down | 2998250 | 2998250 | -2.547 | -1.595 | -1.923 | 0.971 | -153020.000 | 15.450 | 11.951 |
| 2 | unconstrained | 7798380 | 0 | -18.854 | -9.991 | -12.118 | 3.256 | -688650.000 | 0.000 | 0.000 |

| seed | income_restoration_pct_constrained | persistent_gap_assets_down_pct_constrained | other_zero_initial_assets_households | other_zero_assets_plan_above_income | other_zero_assets_income_down |
| --- | --- | --- | --- | --- | --- |
| 0 | 5.958 | 41.930 | 3969830 | 3942500 | 1355010 |
| 1 | 6.856 | 41.039 | 3940730 | 3910410 | 1368120 |
| 2 | 9.306 | 38.944 | 3836840 | 3810540 | 2152100 |

The residual class is not silently attributed to income losses: its
large zero-initial-liquid-asset subgroup is shown separately above. A
household starting with no liquid assets cannot have assets run down
from Q1, but can remain constrained because its plan exceeds income
or because senior debt service/rent absorbs available resources. Wage,
job and firm-receipt decline indicators below overlap these classes.


| seed | decile | households | constrained_pct | income_down | wages_down | employment_down | firm_receipts_down | assets_down | plan_above_income | income_change | wage_change | firm_receipts_change | employment_change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 1549000 | 68.819 | 462000 | 115000 | 22000 | 1471000 | 355000 | 1549000 | -0.137 | -0.196 | -0.227 | -22000.000 |
| 0 | 2 | 1550190 | 43.456 | 1103630 | 134500 | 28020 | 1514080 | 456500 | 1547180 | -0.738 | -0.189 | -0.852 | -27020.000 |
| 0 | 3 | 1549700 | 40.529 | 956620 | 273630 | 66040 | 1522500 | 458380 | 1541080 | -1.087 | -0.323 | -1.156 | -54040.000 |
| 0 | 4 | 1549280 | 49.919 | 798410 | 477220 | 123100 | 1520020 | 506270 | 1520850 | -1.033 | -0.507 | -1.081 | -107090.000 |
| 0 | 5 | 1549740 | 54.319 | 760180 | 572530 | 151140 | 1498680 | 586670 | 1515030 | -1.256 | -0.872 | -1.047 | -136110.000 |
| 0 | 6 | 1549880 | 55.857 | 814020 | 704560 | 203060 | 1521830 | 652650 | 1522430 | -1.737 | -1.493 | -1.062 | -197030.000 |
| 0 | 7 | 1549340 | 55.366 | 919340 | 721000 | 195160 | 1536250 | 694590 | 1526450 | -2.191 | -1.645 | -1.364 | -194100.000 |
| 0 | 8 | 1550180 | 51.789 | 979320 | 685910 | 199140 | 1545130 | 728680 | 1538510 | -2.498 | -1.597 | -1.720 | -199120.000 |
| 0 | 9 | 1549460 | 47.305 | 1091420 | 750710 | 195200 | 1546370 | 841780 | 1537890 | -3.301 | -1.855 | -2.238 | -195190.000 |
| 0 | 10 | 1550550 | 37.891 | 1223370 | 754270 | 196370 | 1549480 | 824700 | 1526040 | -5.154 | -2.014 | -3.973 | -203340.000 |
| 1 | 1 | 1549000 | 68.560 | 556000 | 124000 | 28000 | 1404000 | 355000 | 1549000 | 0.048 | -0.225 | -0.225 | -29000.000 |
| 1 | 2 | 1550190 | 43.391 | 875090 | 167020 | 36020 | 1415080 | 455500 | 1547180 | -0.424 | -0.218 | -0.919 | -37020.000 |
| 1 | 3 | 1549700 | 40.659 | 894670 | 302060 | 77050 | 1295500 | 453380 | 1543080 | -0.654 | -0.371 | -1.154 | -63060.000 |
| 1 | 4 | 1549280 | 49.918 | 768080 | 471090 | 107180 | 1361020 | 500280 | 1523780 | -0.582 | -0.355 | -1.094 | -87190.000 |
| 1 | 5 | 1549740 | 54.383 | 761890 | 590300 | 140090 | 1335680 | 589710 | 1518960 | -0.806 | -0.753 | -1.061 | -128080.000 |
| 1 | 6 | 1549880 | 55.662 | 690900 | 544340 | 166090 | 1391830 | 645650 | 1528400 | -0.617 | -0.669 | -1.011 | -152040.000 |
| 1 | 7 | 1549340 | 54.657 | 755930 | 599540 | 183130 | 1398250 | 688590 | 1528450 | -1.623 | -1.347 | -1.428 | -187100.000 |
| 1 | 8 | 1550180 | 51.079 | 794090 | 576470 | 190220 | 1379130 | 718690 | 1539500 | -1.637 | -1.176 | -1.678 | -192170.000 |
| 1 | 9 | 1549460 | 47.761 | 797410 | 539630 | 221320 | 1392370 | 837820 | 1536870 | -2.706 | -1.836 | -2.275 | -234290.000 |
| 1 | 10 | 1550550 | 37.119 | 800830 | 450780 | 222850 | 1318480 | 810770 | 1527050 | -4.030 | -1.703 | -3.831 | -227820.000 |
| 2 | 1 | 1549000 | 68.496 | 869000 | 85000 | 34000 | 1471000 | 351000 | 1549000 | -0.319 | -0.382 | -0.276 | -36000.000 |
| 2 | 2 | 1550190 | 43.520 | 941180 | 118360 | 30020 | 1514080 | 452500 | 1547180 | -0.956 | -0.433 | -0.952 | -32020.000 |
| 2 | 3 | 1549700 | 40.593 | 1133270 | 259440 | 65060 | 1521250 | 451370 | 1543050 | -1.592 | -0.686 | -1.273 | -59060.000 |
| 2 | 4 | 1549280 | 49.788 | 1032320 | 414760 | 131170 | 1519370 | 494320 | 1523580 | -1.897 | -1.220 | -1.255 | -112160.000 |
| 2 | 5 | 1549740 | 53.222 | 1057340 | 526010 | 180120 | 1498480 | 566710 | 1513110 | -2.614 | -2.110 | -1.248 | -173100.000 |
| 2 | 6 | 1549880 | 54.631 | 1047370 | 612130 | 198150 | 1521470 | 637640 | 1525380 | -2.909 | -2.546 | -1.233 | -198080.000 |
| 2 | 7 | 1549340 | 53.819 | 1066480 | 582430 | 195200 | 1535950 | 669610 | 1525460 | -3.400 | -2.677 | -1.597 | -201120.000 |
| 2 | 8 | 1550180 | 49.985 | 1155400 | 673420 | 223270 | 1544800 | 714730 | 1536520 | -4.564 | -3.454 | -2.015 | -225210.000 |
| 2 | 9 | 1549460 | 46.536 | 1173130 | 660030 | 246330 | 1546100 | 820820 | 1537880 | -5.494 | -4.020 | -2.554 | -255300.000 |
| 2 | 10 | 1550550 | 36.219 | 1311250 | 772820 | 275900 | 1549120 | 797800 | 1528060 | -8.632 | -5.291 | -4.474 | -281890.000 |

| seed | asset_band | households | constrained_pct | income_down | wages_down | employment_down | firm_receipts_down | assets_down | plan_above_income | income_change | wage_change | firm_receipts_change | employment_change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0-10k | 1882380 | 83.375 | 877930 | 686880 | 184160 | 1882380 | 1497360 | 1855690 | -1.706 | -1.604 | -0.967 | -190130.000 |
| 0 | 10-100k | 3917340 | 48.378 | 2352760 | 1433920 | 378350 | 3917340 | 2798590 | 3869170 | -4.446 | -3.029 | -3.096 | -367300.000 |
| 0 | 100k+ | 4568410 | 3.264 | 3788310 | 1459620 | 403340 | 4568410 | 1809270 | 4520300 | -9.957 | -3.018 | -8.751 | -384300.000 |
| 0 | zero | 5129190 | 82.197 | 2089310 | 1608910 | 413380 | 4857210 | 0 | 5079300 | -3.024 | -3.040 | -1.906 | -393310.000 |
| 1 | 0-10k | 1882380 | 83.376 | 779360 | 559000 | 191240 | 1687380 | 1475420 | 1860670 | -0.821 | -1.209 | -0.955 | -192190.000 |
| 1 | 10-100k | 3917340 | 47.895 | 1867890 | 1134570 | 362540 | 3531340 | 2784630 | 3880200 | -3.033 | -2.559 | -3.144 | -362490.000 |
| 1 | 100k+ | 4568410 | 3.198 | 2994890 | 1266170 | 381450 | 4094410 | 1795340 | 4518100 | -8.031 | -2.371 | -8.642 | -370430.000 |
| 1 | zero | 5129190 | 82.002 | 2052750 | 1405490 | 436720 | 4378210 | 0 | 5083300 | -1.146 | -2.514 | -1.934 | -412660.000 |
| 2 | 0-10k | 1882380 | 82.633 | 1198240 | 686300 | 208250 | 1881930 | 1439450 | 1857660 | -3.277 | -3.125 | -1.089 | -211200.000 |
| 2 | 10-100k | 3917340 | 46.543 | 2692020 | 1286680 | 431600 | 3916650 | 2749670 | 3872170 | -8.071 | -6.517 | -3.499 | -431540.000 |
| 2 | 100k+ | 4568410 | 2.936 | 3787310 | 1265290 | 442700 | 4567830 | 1767380 | 4524080 | -14.416 | -6.369 | -10.120 | -434680.000 |
| 2 | zero | 5129190 | 81.614 | 3109170 | 1466130 | 496670 | 4855210 | 0 | 5075310 | -6.614 | -6.808 | -2.169 | -496520.000 |

## Household check and buffer-stock option - proposal only

For each seed, compute the OLS slope of constrained share on quarters 4-12,
using unrounded shares. Any positive slope stops E. Planned investment and
consumption, realized purchases, cuts, asset liquidation, cash income/saving,
GDP, firm losses, bank losses/support and capital ratios remain reportable
regardless of the sign. The cash-saving comparator stays -0.6%, excluding D.8,
with provenance inherited from benchmarks/household_corrections/36100112.

The diagnostic fixes income deciles and non-pension asset bands at t0. It
restores Q1 receipts while holding today's plans, assets, deposits and senior
payments fixed. A constraint relieved by that restoration is classified as
"income restoration sufficient." A remaining constraint with planned spending
above current income and assets below Q1 is a "persistent spending gap with
assets down." The residual is "other or combined." These are accounting
counterfactuals, not exclusive causal estimates. Wages, employed members,
D2 mixed/dividend/corporate receipts and remaining income are separately
compared with Q1, including overlapping incidence indicators.

A specified option for decision, not implementation:
C_plan[h,t] = max(0, Yperm[h,t] + kappa * (L[h,t] - b[h] * Yperm[h,t])).
L is deposits plus non-pension liquid financial assets, with existing
unsecured/overdraft liabilities reported separately. Yperm is a smoothed
cash income after senior obligations; the existing exact D resource cap and
investment-after-consumption priority still apply. Preserve the IO basket.
Use a provisional quarterly income-smoothing weight 0.25 and kappa 0.10;
these are explicitly unestimated assumptions, with +/-50% sensitivity proposed.
Set b[h] from fixed initial SFS-based liquid-wealth/income ratios within income
and age groups, rather than tuning b or kappa to pass this simulation gate.
Nonpositive-income households require an explicit fallback buffer in levels.
A full optimizing version could replace this approximation later.

[Carroll's buffer-stock theory](https://www.econ2.jhu.edu/people/ccarroll/papers/BufferStockTheory/BufferStockTheory.html)
supports a consumption response to cash-on-hand and a target wealth/income
ratio; it does not supply Canadian estimates for these proposed coefficients.
The [Bank of Canada coholding study](https://www.bankofcanada.ca/wp-content/uploads/2024/05/swp2024-16.pdf)
shows why gross liquid assets and liquid debt should be retained separately;
its empirical application is US-based, not a Canadian parameter benchmark.
Both originals, retrieval dates and hashes are in benchmarks/FE/proposal_sources.json.
The buffer-stock rule remains deferred for the user's decision.


## Canadian orders of magnitude and recommendation

The independent initial bank book-equity benchmark is 456.221B from
[36-10-0580](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610058001),
v62696428 and v62696533, 2022Q4. Model recapitalisations are fiscal
support flows, not ordinary bank provisions. Large repeated injections
relative to that initial stock would remain economically problematic.

[RBC 2023 annual report](https://www.rbc.com/investor-relations/_assets-custom/pdf/ar_2023_e.pdf)
reports consolidated retail net write-offs of 0.604B in 2022 and 0.881B
in 2023. This is one bank, includes international exposures, and is not
a national household total. [TransUnion Q4 2024](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q4-24-ciir-report.pdf)
shows 60+ day mortgage delinquency of 0.25% of accounts and 0.23% of
balances; these are stocks, not charge-off flows. [OSB](https://ised-isde.canada.ca/site/office-superintendent-bankruptcy/en/statistics-and-research/insolvency-statistics/annual-reports/annual-2024)
reports 4,810/6,188 business insolvencies in 2023/2024. Composite model
restructuring counts cannot be compared one-for-one with legal filings.
Source dates, table/page references and hashes remain in benchmarks/ABCD.
None of these levels is fitted.


For firms and the whole bank book, RBC reports wholesale net write-offs
of 0.136B/0.293B in 2022/2023 and overall net write-off ratios of
0.10%/0.14% of average loans. Total provisions were 0.484B/2.468B.
These consolidated one-bank measures are not national totals or fiscal
recapitalisations. See benchmarks/FE/rbc_credit_quality_2022_2023.json
for pages, verification date and the full original PDF hash.


F recognized firm losses fall by 20.25% to 41.76% across seeds. Household write-offs remain 236.453-237.065B over 12Q; recapitalisations are 220.141-310.153B. Firm gross overdrafts at Q12 are 189.037-216.727B.


Recognized firm losses alone do not establish plausible credit risk: F
retains the collateral-covered portion of overdrafts and contracts, whereas
the old rule cancelled them fully. Review continuing exposures with losses.
The old household net-worth rule also remains unvalidated.


| seed | annual_firm_loss_pct_initial_external_credit | annual_bank_loss_pct_initial_joint_loans | recap_pct_initial_bank_equity |
| --- | --- | --- | --- |
| 0 | 5.342 | 3.537 | 48.253 |
| 1 | 6.892 | 4.018 | 67.983 |
| 2 | 5.982 | 3.738 | 51.556 |

These are annualized cumulative model losses over three years divided
by fixed initial books, not RBC average-book net charge-off ratios. They
are an order-of-magnitude diagnostic with explicit denominator limits.
Given the remaining loss rates and fiscal support, firm losses and bank
recapitalisations are not accepted as plausible Canadian normal-year
magnitudes. Better accounting and a lower loan boundary do not settle
firm operating deficits, the overdraft channel or collateral realization.


The household check fails, so stop before E as instructed. A liquid-wealth
response is a justified next candidate for decision; the current results
do not identify its Canadian coefficients or warrant fitting them to
these gates. Keep the buffer-stock option unimplemented pending approval.

The model is not ready for Phase B. E, buffer-stock behavior and C_dp_005
do not start from this report. No claim of plausible household losses or
bank recapitalisations follows merely from an accounting pass.

## Full suite and reproducibility


Full tests/ suite via run_pre_D3_tests.py: 463 cases, 433 passed, 30 failed; 0 beyond the known NaN cases. Sampler n_cores=1. See full_test_execution.json, full_tests.xml and log.

audit.json verifies all accepted inputs, new input, source hashes, paired
2Q/12Q prefixes and exact baseline failure IDs. Micro ledgers remain local;
micro_hashes.json and artifact_manifest.json make evidence traceable.
