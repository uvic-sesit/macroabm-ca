# Firm debt and default, then household default - 24 October 2026 UTC

**F is implemented but not accepted as validated. Final serial measurements and
full-suite testing are pending an execution constraint. E has not started.**
This date is UTC; the host is still 23 October (UTC-7). Branch
feature/validation-2022, starting f77f0f5; no push.

The review's corrected investment gate is accepted: initial *planned*
investment is 60.59825B/quarter, exactly the independent 36-10-0112 v62305994
benchmark. Realized investment can be below it because investment is cut first.
The earlier realized-investment gate in CLOSURE_IFE is superseded. The 5% rate
is depreciation; investment is a propensity times expected income.

## Implementation and current gate status

| Step | Commit / focused regressions | Result |
|---|---|---|
| External firm-loan boundary | 12987e6; two allocation/consolidation/input-validation tests | New input built; external loans 1,281.615B; no private bank debt in K/O/P/Q/T |
| Payment-based continuing-firm default | 923f107; four initial tests | Default off; enabled in candidate; exact partial lender losses and surviving contracts |
| Loss/constraint instrumentation | bd72103; constraint-class test | Read-only household income-restoration counterfactual and firm leverage/default panels |
| Accepted planned-I / continuation gates | 9a26aeb; two gate tests | Planned-I passes; F and household continuation checks pending |
| Existing overdraft interest in service | 43bd9f9; additional regression | Senior service includes overdraft interest; existing overdrafts are not forgiven |
| Employment and firm-receipt diagnosis | 980c8cd; additional job-count regression | Wages, employment and D2 receipts separated; no behavioral change |
| E | Not implemented | Requires F pass and nonpositive constrained-share slope on all seeds |

Eleven focused regressions pass (focused_tests.xml/log). These are unit tests,
not substitute twelve-quarter measurements. The full tests/ suite through
run_pre_D3_tests.py has **not** been run for this candidate. Its last accepted
baseline was 421 passes and 30 known "Nan in transactor_total_real_supply"
failures; no claim about this candidate's full-suite result is made.

## Execution constraint and remaining runs

One preliminary seed-0 2Q run completed with maximum normalized accounting
error 3.91e-15. It preceded discovery that a separate BDA linkage workflow was
active. It is retained as a **pilot**, not a final serial measurement. The
current rule additionally includes overdraft interest in the distress screen;
N=3 means no restructuring event is exercised by a 2Q pilot.

Automatic approval review rejected starting final measurements because the
other workflow remains active and the user's one-simulation-at-a-time
constraint was interpreted globally. The external workflow was neither
modified nor terminated. A clarification is pending on whether that constraint
covers only this validation task. Final evidence is reserved for outputs/FE/serial.

Remaining, sequentially: seeds 0-2, each a 2Q accounting run then 12Q; aggregate
F losses against the same-seed iv-ACDpAI baseline; test the Q4-Q12 constraint
slope; start E only if all continuation checks pass; run the full suite at the
end. run_fe_measurements.py, summarise_fe.py, fe_analysis.py, audit_fe.py and
run_fe_full_tests.py are prepared. The serial runner does not automatically
validate external workflow state; the caller must verify or obtain clarified
scope before launching it.

No new household/firm loss table or seed comparison is available yet. Do not
substitute the pilot or old baseline for the requested final measurements.

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
are outside the private non-financial corporation boundary. No capital-share
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

After N quarters, write down max(0, bank principal - 0.8 * current-price
capital). Allocate the loss pro rata to actual lending banks and book it
through the existing same-quarter loss path. The rest remains a contract;
its principal, interest amounts and installment amounts shrink pro rata.
There is no added maturity extension. The producer retains capital, cash and
its overdraft and continues operating. The distress clock restarts after a
restructuring event. Repeated events are counted as restructuring events,
not distinct legal business insolvencies.

**Retained collateral-covered principal is not recovery cash.** No capital
is sold and no lender cash receipt is invented. Recovery cash is zero in F;
retained-contract and collateral-capacity series are recorded separately.
Overdrafts can therefore continue accumulating: zero recognized losses alone
would not establish healthy firms. Deposits, gross overdrafts, debt/capital
and debt/GOS paths must be reviewed with the loss results.

F's assessment threshold for "material" is at least a 25% reduction in total
firm loan plus overdraft losses on every seed, alongside accounting <=1e-8.
This was declared before 12Q outcomes and does not enter model behavior.

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

## Recommendation at this checkpoint

Do not accept F's loss path, start E, or declare Phase B ready yet. The debt
boundary and unit accounting mechanics are reviewable; loss plausibility,
recapitalisations and the household continuation check require the pending
three-seed runs. D3, the buffer-stock implementation, Phase B and C_dp_005
remain on hold. Canadian loss-order comparisons belong with measured final
losses, not with the unvalidated change in the recognition rule.
