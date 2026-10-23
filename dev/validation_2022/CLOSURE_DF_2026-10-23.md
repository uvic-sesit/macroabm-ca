# Closure D/F — household timing and D1 gate, 23 October 2026

**Scope: completed steps 1–3 of the hand-over's explicitly permitted staged
pass. F (steps 4–6) is approved for the next pass but is not implemented here.**
No new firm-debt pickle or firm-default rule is claimed. D3 remains diagnostic
only; E, Phase B and C_dp_005 remain on hold. Work is on
`feature/validation-2022`, from `1c1eb8a`; no push.

## Decisions, commits and tests

| Step | Commit | Tests / result |
|---|---|---|
| 1: current receipts in D, exact settlement and senior cash reservation | 54709c9 | 23 focused tests pass, including current net wages with zero opening deposits, payment distress, funded declarations and counterparties |
| 2: narrow D1 on in both candidate arms | 3d54d44 | 6 focused tests pass; candidate flag and existing narrow offset regressions |
| 3: serial gate/seed diagnostics | ed02f71 | 3 gate-boundary/NumPy serialization regressions pass; twelve 2Q/12Q measurements below |
| 4–6: firm debt boundary, payment default and F remeasurement | Not started in this staged pass | No F results or F validation claimed |

An initial diagnostic completed its two quarters but could not serialize a
NumPy boolean in the gate manifest. ed02f71 fixes serialization and tests the
5% boundary. The completed evidence was rerun from the frozen corrected runner.
No calibration or new parameter was used to improve the gate result.

## Settlement choice and exact resources

The implementation budgets against **declared current receipts**, keeping the
existing quarter-end stock histories and booking every flow once. Spendable
resources are opening deposits + net wages + unemployment benefits + other
government transfers + funded D2 receipts + net rental income − rent − interest
− contractual principal − executed house purchases + committed new installment
loans + executed house-sale proceeds. Unused revolving capacity stays zero.
No D4 headroom is used. VAT and capital-formation tax are included in goods cost;
one factor scales planned consumption and investment across all goods.

The original income was not fully knowable before clearing: nominal wages and
transfers used a CPI computed from the purchases being cleared, and D2 could
re-clip a declared payment against post-clearing firm cash. The timing correction
therefore makes these declarations binding:

- Fix the nominal payroll/transfer conversion at the CPI available when the
  payment is declared. Use that *same* index for firm wage debits, household
  receipts and government wage withholding. Realized consumption CPI is still
  computed normally; it does not retrospectively rewrite a nominal payment.
- Declare D2 amounts from the existing payer-by-payer positive-opening-cash cap
  before goods clearing. Those funded payments cannot be revoked after household
  spending. Their firm debit, household credit and taxes are booked once through
  the normal final accounting methods. Subsequent operating deficits remain firm
  obligations; this is a settlement-priority change, not an invented income line.
  The D2 payout ratio, recipient allocation and benchmarks are unchanged.
- Budgeting records a receipt memo, not an extra credit to opening deposits.
  The runner asserts, household by household every quarter, that declared and
  actually booked net receipts agree (rtol 1e-12, atol 1e-5 CAD).
- Optional purchases of other financial assets cannot use cash already needed
  for taxes and senior contractual payments. Redirect only the necessary part
  of newly allocated OFA saving into deposits. Total allocated wealth is unchanged;
  this does not impose deposit-only saving. The redirected amount is reported.

Defaults without D remain unchanged. Both the pre-goods senior shortfall and
actual end-payment overdraft are recorded; the budget cap itself is not a
default trigger. Existing accounting counterparty identities remain active.

## Household gate and benchmark

C's unchanged annual target is **1,511.382B**, or **377.8455B per quarter**.
The gate uses cash consumption including VAT and paid rent; narrow D1 removes
eligible duplicated private-household-landlord rent from renters' sector-L
purchases. The offset is capped at each renter's L budget. Unoffset rent is
retained as a memo in the quarterly panel; no wider housing boundary is changed.
Gate pass means Q1 consumption is at least 95% of the target, not that the
whole household closure is economically validated.
The shortfall column is a percentage of the target.

| arm | seed | Q1_consumption | Q1_C_target | Q1_consumption_shortfall | household_gate_passed |
| --- | --- | --- | --- | --- | --- |
| iv-ACD′ | 0 | 365.233 | 377.846 | 3.338 | True |
| iv-ACD′ | 1 | 365.753 | 377.846 | 3.2 | True |
| iv-ACD′ | 2 | 363.364 | 377.846 | 3.833 | True |
| v-ACD′ | 0 | 365.233 | 377.846 | 3.338 | True |
| v-ACD′ | 1 | 365.753 | 377.846 | 3.2 | True |
| v-ACD′ | 2 | 363.364 | 377.846 | 3.833 | True |

All dollar amounts below are CAD billions; flows are quarterly unless marked
12-quarter totals. Saving rates, constrained shares and lending/loss shares
are percentages. StatCan 36-10-0112, 2022 mean of quarterly SAAR observations:
consumption v62305982 = 1,511.382B/year; disposable income v62305981 =
1,502.340B/year. Excluding D.8 gives a saving comparison of **−0.602%**.
This is the same comparison as the accepted report, not a complete restatement
of the model cash account to all noncash SNA entries. No target is refitted.
Source date and full CSV/zip hashes:
`benchmarks/household_corrections/36100112_provenance.json` (retrieved 2026-10-23).

## Q1 and Q12 consumption, disposable income, saving and GDP

| arm | seed | quarter | consumption | cash_DI | cash_saving | cash_saving_rate | gdp | constrained_share | consumption_cut | rent_offset | saving_redirect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| iv-ACD′ | 0 | 1 | 365.233 | 371.908 | 6.675 | 1.795 | 701.118 | 29.003 | 22.699 | 3.768 | 7.262 |
| iv-ACD′ | 0 | 12 | 287.489 | 330.974 | 43.484 | 13.138 | 607.142 | 58.492 | 59.03 | 3.737 | 24.055 |
| iv-ACD′ | 1 | 1 | 365.753 | 371.141 | 5.389 | 1.452 | 715.529 | 29.25 | 23.16 | 3.767 | 7.317 |
| iv-ACD′ | 1 | 12 | 339.556 | 388.989 | 49.433 | 12.708 | 715.707 | 59.131 | 66.603 | 3.783 | 26.424 |
| iv-ACD′ | 2 | 1 | 363.364 | 370.753 | 7.388 | 1.993 | 697.757 | 28.881 | 22.409 | 3.763 | 7.413 |
| iv-ACD′ | 2 | 12 | 269.554 | 317.601 | 48.048 | 15.128 | 579.55 | 58.372 | 59.881 | 3.717 | 23.382 |
| v-ACD′ | 0 | 1 | 365.233 | 371.908 | 6.675 | 1.795 | 701.118 | 29.003 | 22.699 | 3.768 | 7.262 |
| v-ACD′ | 0 | 12 | 286.201 | 331.507 | 45.306 | 13.667 | 632.42 | 58.604 | 62.601 | 3.746 | 26.96 |
| v-ACD′ | 1 | 1 | 365.753 | 371.141 | 5.389 | 1.452 | 715.529 | 29.25 | 23.16 | 3.767 | 7.317 |
| v-ACD′ | 1 | 12 | 297.485 | 352.165 | 54.68 | 15.527 | 639.455 | 59.102 | 64.777 | 3.753 | 26.202 |
| v-ACD′ | 2 | 1 | 363.364 | 370.753 | 7.388 | 1.993 | 697.757 | 28.881 | 22.409 | 3.763 | 7.413 |
| v-ACD′ | 2 | 12 | 264.387 | 309.888 | 45.501 | 14.683 | 590.691 | 58.366 | 61.069 | 3.699 | 25.132 |

## Household and bank losses: 12-quarter totals / seed comparison

| arm | seed | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | resolution_events | overdraft_share_new_lending | loss_share_new_principal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| iv-ACD′ | 0 | 214.476 | 152.961 | 148.49 | 515.926 | 341.274 | 19 | 18.536 | 26.461 |
| iv-ACD′ | 1 | 212.829 | 159.847 | 191.34 | 564.016 | 460.563 | 17 | 15.777 | 24.349 |
| iv-ACD′ | 2 | 218.691 | 168.087 | 125.004 | 511.782 | 282.346 | 16 | 8.146 | 32.551 |
| v-ACD′ | 0 | 38.394 | 159.897 | 166.088 | 364.379 | 200.778 | 12 | 11.23 | 0.7 |
| v-ACD′ | 1 | 36.587 | 231.535 | 213.771 | 481.893 | 353.071 | 15 | 12.984 | 0.392 |
| v-ACD′ | 2 | 38.854 | 206.004 | 138.023 | 382.881 | 295.058 | 11 | 10.317 | 0.319 |

Overdraft losses in this table are cancelled **firm** overdrafts; household
overdrafts remain bank claims. Recapitalisation is reported separately from
losses. New-lending shares are by value at origination; new-principal loss shares
track contractual amortization and cancellation through Q12. Later vintages
have shorter exposure. Borrower-level records remain local in ignored micro/.
The firm debt boundary and firm insolvency predicate are **still the old ones**.

## Quarterly loss, support and constraint panels (seed 0)


**iv-ACD′**

| quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | cash_saving_rate | constrained_share | consumption_cut | rent_offset |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 82.63 | 0.0 | 0.0 | 82.63 | 0.0 | 1.795 | 29.003 | 22.699 | 3.768 |
| 2 | 68.243 | 0.31 | 0.038 | 68.591 | 1.281 | 5.237 | 35.183 | 34.405 | 3.762 |
| 3 | 19.417 | 38.296 | 17.368 | 75.081 | 0.781 | 7.323 | 39.779 | 40.609 | 3.755 |
| 4 | 22.607 | 7.95 | 4.181 | 34.737 | 7.412 | 8.715 | 43.694 | 45.039 | 3.75 |
| 5 | 6.525 | 36.957 | 11.733 | 55.216 | 194.235 | 9.614 | 46.823 | 49.115 | 3.745 |
| 6 | 7.578 | 15.578 | 13.849 | 37.005 | 56.29 | 10.694 | 49.053 | 50.087 | 3.739 |
| 7 | 1.539 | 13.04 | 10.117 | 24.696 | 0.288 | 11.52 | 51.083 | 51.816 | 3.737 |
| 8 | 1.534 | 23.528 | 27.109 | 52.171 | 0.0 | 11.279 | 52.841 | 56.169 | 3.742 |
| 9 | 1.883 | 0.708 | 25.504 | 28.095 | 8.481 | 13.108 | 54.47 | 57.337 | 3.739 |
| 10 | 0.914 | 5.669 | 6.648 | 13.231 | 35.406 | 12.707 | 56.195 | 59.472 | 3.74 |
| 11 | 1.259 | 6.826 | 10.617 | 18.702 | 29.973 | 13.852 | 57.327 | 58.162 | 3.734 |
| 12 | 0.348 | 4.098 | 21.325 | 25.771 | 7.128 | 13.138 | 58.492 | 59.03 | 3.737 |

**v-ACD′**

| quarter | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | cash_saving_rate | constrained_share | consumption_cut | rent_offset |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.795 | 29.003 | 22.699 | 3.768 |
| 2 | 0.0 | 0.31 | 0.038 | 0.348 | 0.0 | 5.046 | 35.131 | 34.153 | 3.762 |
| 3 | 16.172 | 38.296 | 17.372 | 71.841 | 1.318 | 7.061 | 39.773 | 40.564 | 3.758 |
| 4 | 12.91 | 36.768 | 7.141 | 56.818 | 0.0 | 8.736 | 43.76 | 46.378 | 3.758 |
| 5 | 2.525 | 14.598 | 15.868 | 32.991 | 0.0 | 10.166 | 46.702 | 49.368 | 3.753 |
| 6 | 4.243 | 4.348 | 4.997 | 13.589 | 0.0 | 11.442 | 49.159 | 54.578 | 3.756 |
| 7 | 0.464 | 5.205 | 5.542 | 11.211 | 0.247 | 11.889 | 51.331 | 56.912 | 3.752 |
| 8 | 0.257 | 15.797 | 18.873 | 34.927 | 99.032 | 12.559 | 52.895 | 58.689 | 3.753 |
| 9 | 1.129 | 26.535 | 33.859 | 61.523 | 0.0 | 13.061 | 54.441 | 59.322 | 3.75 |
| 10 | 0.129 | 2.986 | 19.433 | 22.549 | 85.059 | 13.45 | 56.231 | 62.197 | 3.746 |
| 11 | 0.237 | 13.083 | 21.844 | 35.163 | 11.377 | 13.545 | 57.466 | 61.604 | 3.745 |
| 12 | 0.328 | 1.97 | 21.123 | 23.42 | 3.745 | 13.667 | 58.604 | 62.601 | 3.746 |

The corresponding **all-seed quarterly** metrics, including Q1/Q12 and all
intermediate GDP/consumption/income, rent offsets, senior shortfalls, savings
redirects and minimum bank capital ratios, are in `outputs/DF/quarterly.csv`.
The rent offset is the VAT-inclusive planned L-demand reduction before D's
budget scaling and goods rationing. The consumption cut is D's planned
VAT-inclusive consumption reduction; neither is a realized-sales counterfactual.
Constrained shares weight households by their represented regional population.
`resolution_log.csv` contains every bank/quarter resolution, equity absorbed,
uncovered loss and government recapitalisation. `new_lending_vintages.csv` gives
quarter-of-origination attribution; `banks_by_quarter.csv` retains pre- and
post-resolution equity. Firm counts/debt by industry and quarter are retained
in `firm_insolvencies_by_industry.csv` for diagnostics, not as F-trigger results.

`funding_declarations.csv` verifies each firm's declared payout against opening
cash. Raw `firms.csv` still uses the historical name `cash_before_payout` for
end-operating cash before the deferred cash-booking call; that is **not** the
earlier declaration-date cash under the corrected settlement ordering.

## Accounting, scope and tests

| arm | seed | quarters | max_accounting_error |
| --- | --- | --- | --- |
| iv-ACDp | 0 | 12 | 1.01e-14 |
| iv-ACDp | 1 | 12 | 6.63e-15 |
| iv-ACDp | 2 | 12 | 6.43e-15 |
| iv-ACDp | 0 | 2 | 6.77e-15 |
| iv-ACDp | 1 | 2 | 3.11e-15 |
| iv-ACDp | 2 | 2 | 3.42e-15 |
| v-ACDp | 0 | 12 | 8.34e-15 |
| v-ACDp | 1 | 12 | 5.85e-15 |
| v-ACDp | 2 | 12 | 1.12e-14 |
| v-ACDp | 0 | 2 | 8.34e-15 |
| v-ACDp | 1 | 2 | 5.85e-15 |
| v-ACDp | 2 | 2 | 3.50e-15 |

Full suite: **407 passed, 30 failed**, 437 cases. Beyond known NaN cases: **0**. Sampler properties: `[{'name': 'sampler_n_cores', 'value': '1'}]`; elapsed 18.4 minutes.

Input remains the accepted `io2022_household_agreed_bankcap.pkl`, SHA256
`d7b39868a569ea52d749aced375247ed6824c8ff2c9e9493100a43645b0de228`.
No accepted pickle, original-repository file, ITC/user-cost input or pickle was
modified. Source/input hashes and the accounting/gate result accompany each
fresh run. Every 12-quarter arm/seed was preceded by its own 2-quarter run;
simulations and the final one-worker-sampler test suite ran serially.

## Recommendation and next pass

The timing defect is corrected; the gate outcome above is distinct from
validation of write-offs. Residual saving and loan losses must be judged from
these corrected panels rather than the invalid opening-cash-only ACD results.
Large cancellations under the net-worth rule and D3's missing collateral sale/
recovery path still prevent acceptance of household losses as realistic. E is
still needed; D3 remains on hold rather than being accepted from lower totals.

Firm losses and bank recapitalisations are **not validated** in this staged pass:
they still use the intercompany/public-producer debt boundary and valuation-
sensitive firm rule documented in the prior A–D report. The approved F data
correction, new firm-debt pickle, payment-based firm trigger and F remeasurement
are next-pass work, not results claimed by this document. No F haircut or
default-duration parameter was introduced here.

Existing order-of-magnitude comparisons retain their provenance in
`benchmarks/ABCD/`: RBC retail net write-offs (0.604B in 2022 and 0.881B in 2023,
one consolidated bank, including international exposures), TransUnion Q4 2024
mortgage 60+ day arrears (0.25% of accounts), and OSB business insolvencies
(4,810 in 2023; 6,188 in 2024). These differ from national gross model principal
cancellation and composite-producer counts; no level is fitted. Their scope
limitations and full-source/snapshot hashes are in the prior report and source
provenance. Stop here for review under the hand-over's staged-pass option.

Primary sources: [RBC annual report 2023](https://www.rbc.com/investor-relations/_assets-custom/pdf/ar_2023_e.pdf),
[TransUnion Q4 2024](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q4-24-ciir-report.pdf),
[OSB annual 2024](https://ised-isde.canada.ca/site/office-superintendent-bankruptcy/en/statistics-and-research/insolvency-statistics/annual-reports/annual-2024).
