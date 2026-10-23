# Household closure A–D: implementation and diagnostic record

Implementation and diagnostics from `448a6bb`, on `feature/validation-2022`. D3 remains
unaccepted; Phase B and C_dp_005 are on hold. No push.

## Approved overdraft proxy and sensitivity search

The household file exposes outstanding card and credit-line balances, not
contractual limits. The main D arm uses **zero unused capacity**, as explicitly
selected by the user. Discretionary purchases require positive settled cash
after senior payments. Senior payments can still create payment distress.
Do not substitute D4 underwriting headroom.

The user additionally requested one sensitivity using separate published
Canadian card and line-of-credit utilisation rates, and authorized omission if
no defensible source was found quickly. The quick search did not establish
suitable rates for both products, so **the sensitivity is omitted**:

- [TransUnion Canada Q4 2024 report](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q4-24-ciir-report.pdf),
  copyright 2025, pp. 9, 12 and 17, provides balances and credit lines but
  explicitly warns that their ratio is not its utilisation measure: balances
  include closed accounts, while limits exclude them. These ratios are not
  substituted for published utilisation rates.
- [Bank of Canada HELOC statistics](https://www.bankofcanada.ca/rates/banking-and-financial-statistics/chartered-banks-home-equity-lines-of-credit-helocs/)
  cover secured home-equity facilities at chartered banks. A HELOC rate would
  not identify utilisation of the household file's general credit-line balance.

Neither source is used as a numeric model benchmark; no utilisation parameter
or inferred limit is added. This search decision does not imply that suitable
data could never be obtained with further research.

## A: bank-capital initialization

StatCan 36-10-0580, 2022 Q4 liability-side book equity: chartered banks
`v62696428` = 405.572B; quasi-banks `v62696533` = 50.649B; total 456.221B.
The cached source's date, SHA256 and selectors are recorded in
`outputs/ABCD/bankcap_provenance.json`. No national-accounts input is fitted.

Allocate national equity in proportion to each regional bank's initial firm
plus household loan balance, normalizing jointly across the 13 banks.
Customer deposits and borrower contracts remain unchanged. The counterpart is
the reserve plug, R = D_f + D_h + E - L. Initial bank deposit-interest income,
profit, tax and liabilities are recomputed by the existing preprocessing
methods. The national ratio E/L is 8.8503%. `initial_bank_capital.csv` reports
all bank stocks and the demography ratio E/(L+R), against its 5% threshold.

The fresh-build path uses the same loan allocation. The Canadian 2022 bank
reader bypasses asset-side F5 and supplies the NBSA book amount provisionally;
the joint final-loan allocation supersedes its regional VA shares.

New output: `dev/pkl_files/io2022_household_agreed_bankcap.pkl`.
The two accepted input pickles are not overwritten.

Focused A regressions: four passed (book-equity selector, joint loan allocation,
contract preservation, reserve identity and regional reconciliation).

## Implementation decisions and focused tests

| Decision | Commit | Focused regression run | Result |
|---|---|---|---|
| A: NBSA book capital and loan-share allocation | f8e9854 | 4 tests | Pass; all 13 initial ratios exceed 5% |
| B: same-agent bridge bank and fiscal counterparty | c977e16 | 6 tests, including two forced resolutions | Pass; borrower contracts preserved |
| C: initial saving propensity with funded D2 receipts | c2c0120 | 6 tests | Pass; D2-off calibration retained |
| D: zero unused capacity, proportional goods cap | 788f84f | 13 tests | Pass; flag defaults off |
| Read-only serial measurement runner | 3054d2e | Four 2-quarter accounting arms, then 12-quarter and seed runs | See batteries below |

Focused counts include relevant existing regressions, not just newly added tests.
One focused run hit Windows' long Numba-cache path; rerunning with the existing
short `NUMBA_CACHE_DIR` passed all 13. No model parameter was changed for this.

## B: resolution accounting and interpretation

The same bank agent becomes the bridge bank; its resolution count increments.
All principal, rates, installments and customer deposits survive resolution.
Borrower and overdraft losses are charged by bank before support, in the same
quarter. A negative equity hole is covered, not erased by setting equity to
zero. At a regulatory-threshold intervention with positive residual equity,
no additional asset loss is invented merely to force that balance to zero.
The event log records credit losses absorbed by pre-existing equity separately
from the uncovered hole and fiscal injection.

The post-support target is the larger of (8% loan-capital minimum + a 1 percentage
point buffer) times loans, and the equity needed for a 6% demography ratio.
The latter solves E/(D+E)=6%, because the reserve plug changes with the transfer.
The 1-point buffer is an explicit model resolution policy, not a fitted Canadian
coefficient. These unweighted model ratios are not Canadian CET1/RWA ratios.
Banks can remain below 8% E/L between interventions because the unchanged
demography trigger is 5% E/(L+R). Both ratios are reported; they are not conflated.

Government books the injection as a named fiscal transfer, increasing deficit
and debt. The receiving bank books the same amount in equity and reserves.
The accounting battery includes a recapitalisation counterparty identity and
adds support once to the fiscal cash boundary, not again as an unexplained
reserve term. Other bank losses continue through the existing by-bank path.

### Initial banks (CAD billions)

| region | loans | equity | reserves | E/L % | E/(L+R) % |
| --- | --- | --- | --- | --- | --- |
| CAN_NL | 79.156 | 7.006 | -28.163 | 8.85 | 13.738 |
| CAN_PE | 16.323 | 1.445 | -4.134 | 8.85 | 11.852 |
| CAN_NS | 132.021 | 11.684 | -60.398 | 8.85 | 16.314 |
| CAN_NB | 118.613 | 10.498 | -42.489 | 8.85 | 13.79 |
| CAN_QC | 1092.744 | 96.711 | -377.523 | 8.85 | 13.522 |
| CAN_ON | 1901.19 | 168.261 | -723.389 | 8.85 | 14.286 |
| CAN_MB | 162.14 | 14.35 | -52.502 | 8.85 | 13.088 |
| CAN_SK | 196.63 | 17.402 | -97.019 | 8.85 | 17.47 |
| CAN_AB | 725.099 | 64.173 | -306.161 | 8.85 | 15.318 |
| CAN_BC | 713.371 | 63.135 | -279.461 | 8.85 | 14.55 |
| CAN_YT | 6.304 | 0.558 | -2.467 | 8.85 | 14.54 |
| CAN_NT | 6.813 | 0.603 | -2.879 | 8.85 | 15.329 |
| CAN_NU | 4.467 | 0.395 | -1.968 | 8.85 | 15.817 |

Negative reserves are net borrowing at the reserve plug, not household or firm
deposit cancellation. The allocation is national across the 13 banks, not
13 copies of the national amount. Each initial demography ratio is above 5%.

## C: saving calibration and benchmark boundary

Use the existing income-weighted constant-propensity method, C=(1-s)Y, with
initial net income excluding the unfunded financial-income proxy and including
funded planned mixed income, dividends and corporate transfers. Regional
consumption shares are retained. The specified national target is 1,511.382B/yr
at purchasers' prices, table 36-10-0112, v62305982. No ex-post run is fitted.
The target applies to the model's IO goods-consumption boundary, which already
contains sector-L services. Cash consumption below also includes separately
paid rent; D1 is off in all four attribution arms. This remaining boundary
duplication is disclosed rather than removed through another propensity fit.

| arm | Old weighted s % | New weighted s % | Q1 cash C, annual B | Q1 cash DI, annual B | Q1 cash saving % |
| --- | --- | --- | --- | --- | --- |
| iv-A | -9.726 | -9.726 | 1620.402 | 1478.17 | -9.622 |
| iv-AC | -9.726 | -0.439 | 1543.835 | 1477.062 | -4.521 |
| iv-ACD | -9.726 | -0.439 | 906.015 | 1469.091 | 38.328 |
| v-ACD | -9.726 | -0.439 | 906.015 | 1469.091 | 38.328 |

The 2022 comparison is consumption 1,511.382B, disposable income 1,502.340B
(v62305981), and saving excluding D.8 of -0.602%. The model cash account omits
some noncash household-account entries (including D.8); the displayed cash
comparison is not a complete SNA restatement. D2-on initial expected income is
1,504.780B/yr and the C calibration exactly targets 1,511.382B/yr of goods
consumption. Q1 realized receipts, price/quantity clearing, additional paid rent
and interest produce the remaining difference; they are not filled with income.
The source CSV, retrieval date and full zip/CSV hashes remain in
`benchmarks/household_corrections/36100112_provenance.json`.

## D: cash available at goods clearing

Zero **unused** capacity does not cancel existing credit-card/line balances or
installment loans. The budget uses deposits already available before goods
clearing, plus committed new installment loans and executed house-sale proceeds,
minus rent, interest, principal service and executed house purchases. VAT and
capital-formation tax enter the purchase cost. One factor scales every planned
consumption and investment good. Wage and transfer withholding is already net
in income; it is not charged again to this stock budget.

Current-quarter wages/distributions settle later in this model's ordering and
are not forecast as spendable deposits by this conservative proxy. This timing
restriction, and the exclusion of OFA liquidation from the budget, make it a
strict cash-in-hand diagnostic. It is not an estimated Canadian revolving-credit
facility. Senior payments remain due even if they exceed resources; the pre-
receipt shortfall and the actual end-payment overdraft are recorded separately.
The latter is `payment_distress` before insolvency processing. The cap itself
does not change either the old rule or D3. Portfolio saving behavior is unchanged.

The resulting large consumption cut and high saving rate are material costs of
this bound. They must not be interpreted as validation of the facility choice.
No D4 headroom, arbitrary multiplier, or utilisation parameter is introduced.

## Twelve-quarter results

Amounts are CAD billions, flows per quarter unless marked total. Household
write-offs are cancelled loan principal. Bank losses split into household
principal, firm principal and cancelled **firm** overdrafts. Household overdrafts
remain claims in these specifications. Government support is not netted against
losses. Cash C includes VAT and paid rent; GDP is the model output measure.

### Totals and final-quarter macro outcomes

| arm | seed | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | resolution_events | Q12_GDP | Q12_consumption | Q12_cash_saving |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| iv-A | 0 | 452.964 | 162.47 | 145.666 | 761.1 | 594.024 | 27 | 714.379 | 400.22 | -8.94 |
| iv-AC | 0 | 384.235 | 195.178 | 219.673 | 799.086 | 615.831 | 28 | 743.639 | 386.82 | -1.81 |
| iv-ACD | 0 | 133.439 | 207.109 | 89.237 | 429.784 | 309.603 | 9 | 536.906 | 219.325 | 30.64 |
| iv-ACD | 1 | 133.088 | 207.146 | 134.807 | 475.041 | 288.712 | 12 | 525.78 | 213.362 | 30.25 |
| iv-ACD | 2 | 135.976 | 395.907 | 135.607 | 667.491 | 552.902 | 12 | 479.842 | 200.477 | 29.95 |
| v-ACD | 0 | 54.098 | 159.75 | 135.166 | 349.014 | 224.273 | 6 | 533.803 | 212.005 | 30.86 |
| v-ACD | 1 | 54.439 | 137.432 | 120.157 | 312.028 | 173.895 | 7 | 575.345 | 222.517 | 31.87 |
| v-ACD | 2 | 54.98 | 157.491 | 107.205 | 319.676 | 195.222 | 8 | 513.558 | 206.461 | 31.14 |

Across seeds 0–2, ACD household write-offs are 133.088–135.976B and v-ACD
54.098–54.980B. Bank losses vary much more: ACD 429.784–667.491B and v-ACD
312.028–349.014B. Seed-0 write-offs annualized against initial household debt
are about 1.54% and 0.63%, respectively (gross cancellation, not recovered net
loss). Firm principal plus overdrafts account for roughly 69–80% of ACD bank
losses and 83–85% of v-ACD losses. Household results are stable across seeds;
aggregate bank/firm losses are materially seed-sensitive. The fiscal support
totals are themselves large relative to the corrected 456.221B initial capital.
This is accounting closure, not evidence of realistic bank resolution frequency.


### Seed-0 household write-offs by quarter

| quarter | iv-A | iv-AC | iv-ACD | v-ACD |
| --- | --- | --- | --- | --- |
| 1 | 171.129 | 167.837 | 75.345 | 0.0 |
| 2 | 45.919 | 42.179 | 26.119 | 0.0 |
| 3 | 22.916 | 21.238 | 6.602 | 32.712 |
| 4 | 26.551 | 22.573 | 16.433 | 9.236 |
| 5 | 25.932 | 12.766 | 2.908 | 2.145 |
| 6 | 16.55 | 15.579 | 1.774 | 6.254 |
| 7 | 20.236 | 11.156 | 1.762 | 1.378 |
| 8 | 14.251 | 17.081 | 0.45 | 0.665 |
| 9 | 22.683 | 13.095 | 1.013 | 0.897 |
| 10 | 27.937 | 13.65 | 0.205 | 0.184 |
| 11 | 29.757 | 24.921 | 0.539 | 0.322 |
| 12 | 29.103 | 22.159 | 0.289 | 0.306 |
| Total | 452.964 | 384.235 | 133.439 | 54.098 |

### Seed-0 total bank losses by quarter

| quarter | iv-A | iv-AC | iv-ACD | v-ACD |
| --- | --- | --- | --- | --- |
| 1 | 171.129 | 167.837 | 75.345 | 0.0 |
| 2 | 46.247 | 42.507 | 26.451 | 0.333 |
| 3 | 76.645 | 74.954 | 16.381 | 42.491 |
| 4 | 44.515 | 40.579 | 92.251 | 61.77 |
| 5 | 60.647 | 39.786 | 25.543 | 19.483 |
| 6 | 37.473 | 21.915 | 122.627 | 33.715 |
| 7 | 58.339 | 45.089 | 4.653 | 18.645 |
| 8 | 44.751 | 62.423 | 3.386 | 23.424 |
| 9 | 75.064 | 35.001 | 15.82 | 42.104 |
| 10 | 64.267 | 58.715 | 20.856 | 17.912 |
| 11 | 38.337 | 106.281 | 11.924 | 76.226 |
| 12 | 43.689 | 103.998 | 14.547 | 12.912 |
| Total | 761.1 | 799.086 | 429.784 | 349.014 |

### Quarterly macro, support and constraints (seed 0)


**iv-A**

| quarter | gdp | consumption | cash_DI | Saving % | recapitalisation | Min E/L % | Constrained % | consumption_cut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 701.874 | 405.101 | 369.543 | -9.62 | 1.016 | 3.49 | 0.0 | 0.0 |
| 2 | 697.369 | 399.488 | 363.726 | -9.83 | 6.084 | 3.13 | 0.0 | 0.0 |
| 3 | 696.251 | 400.323 | 361.923 | -10.61 | 122.011 | 3.4 | 0.0 | 0.0 |
| 4 | 692.719 | 397.285 | 360.113 | -10.32 | 121.185 | 3.6 | 0.0 | 0.0 |
| 5 | 692.325 | 394.425 | 359.806 | -9.62 | 0.43 | 3.46 | 0.0 | 0.0 |
| 6 | 694.699 | 395.51 | 359.872 | -9.9 | 46.071 | 4.59 | 0.0 | 0.0 |
| 7 | 690.896 | 390.892 | 357.797 | -9.25 | 2.996 | 3.46 | 0.0 | 0.0 |
| 8 | 685.346 | 386.823 | 351.764 | -9.97 | 46.673 | 3.79 | 0.0 | 0.0 |
| 9 | 700.413 | 387.144 | 357.677 | -8.24 | 132.649 | 3.48 | 0.0 | 0.0 |
| 10 | 707.841 | 392.371 | 359.822 | -9.05 | 72.807 | 4.67 | 0.0 | 0.0 |
| 11 | 706.91 | 394.005 | 361.62 | -8.96 | 42.102 | 4.72 | 0.0 | 0.0 |
| 12 | 714.379 | 400.22 | 367.38 | -8.94 | 0.0 | 4.23 | 0.0 | 0.0 |

**iv-AC**

| quarter | gdp | consumption | cash_DI | Saving % | recapitalisation | Min E/L % | Constrained % | consumption_cut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 701.334 | 385.959 | 369.266 | -4.52 | 1.011 | 3.49 | 0.0 | 0.0 |
| 2 | 695.775 | 378.673 | 363.347 | -4.22 | 5.524 | 3.22 | 0.0 | 0.0 |
| 3 | 695.669 | 374.157 | 361.613 | -3.47 | 119.097 | 3.44 | 0.0 | 0.0 |
| 4 | 700.852 | 373.488 | 361.976 | -3.18 | 61.66 | 3.35 | 0.0 | 0.0 |
| 5 | 707.025 | 376.54 | 364.445 | -3.32 | 60.024 | 3.35 | 0.0 | 0.0 |
| 6 | 704.797 | 372.305 | 363.609 | -2.39 | 9.49 | 3.84 | 0.0 | 0.0 |
| 7 | 714.082 | 376.673 | 368.198 | -2.3 | 36.232 | 4.85 | 0.0 | 0.0 |
| 8 | 727.483 | 385.142 | 375.814 | -2.48 | 0.0 | 3.93 | 0.0 | 0.0 |
| 9 | 735.806 | 396.461 | 381.154 | -4.02 | 36.686 | 3.62 | 0.0 | 0.0 |
| 10 | 740.585 | 401.368 | 383.475 | -4.67 | 79.661 | 3.45 | 0.0 | 0.0 |
| 11 | 737.508 | 395.08 | 376.354 | -4.98 | 152.814 | 3.89 | 0.0 | 0.0 |
| 12 | 743.639 | 386.82 | 379.932 | -1.81 | 53.633 | 5.69 | 0.0 | 0.0 |

**iv-ACD**

| quarter | gdp | consumption | cash_DI | Saving % | recapitalisation | Min E/L % | Constrained % | consumption_cut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 693.236 | 226.504 | 367.273 | 38.33 | 0.97 | 3.96 | 52.19 | 165.842 |
| 2 | 612.853 | 229.816 | 344.253 | 33.24 | 0.0 | 3.98 | 53.45 | 137.228 |
| 3 | 578.126 | 230.51 | 329.816 | 30.11 | 1.07 | 4.01 | 54.46 | 119.592 |
| 4 | 558.777 | 229.985 | 321.528 | 28.47 | 7.126 | 3.28 | 55.65 | 112.881 |
| 5 | 543.937 | 227.374 | 315.689 | 27.98 | 0.0 | 3.12 | 56.84 | 109.989 |
| 6 | 535.249 | 224.289 | 310.607 | 27.79 | 191.741 | 3.81 | 57.93 | 107.526 |
| 7 | 537.049 | 221.033 | 310.111 | 28.72 | 0.0 | 3.49 | 59.15 | 107.011 |
| 8 | 542.459 | 221.139 | 314.928 | 29.78 | 0.368 | 3.41 | 60.46 | 112.675 |
| 9 | 545.074 | 221.086 | 318.051 | 30.49 | 42.471 | 2.72 | 61.54 | 116.102 |
| 10 | 542.619 | 221.705 | 316.915 | 30.04 | 0.0 | 2.75 | 62.44 | 118.419 |
| 11 | 540.623 | 219.68 | 314.916 | 30.24 | 57.166 | 2.03 | 63.38 | 118.484 |
| 12 | 536.906 | 219.325 | 316.225 | 30.64 | 8.692 | 1.88 | 64.53 | 118.982 |

**v-ACD**

| quarter | gdp | consumption | cash_DI | Saving % | recapitalisation | Min E/L % | Constrained % | consumption_cut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 693.236 | 226.504 | 367.273 | 38.33 | 0.0 | 8.82 | 52.19 | 165.842 |
| 2 | 612.857 | 229.924 | 343.847 | 33.13 | 0.0 | 7.06 | 53.45 | 137.12 |
| 3 | 578.187 | 230.586 | 329.279 | 29.97 | 1.452 | 6.87 | 54.42 | 119.665 |
| 4 | 561.496 | 228.876 | 322.304 | 28.99 | 0.0 | 5.95 | 55.52 | 112.215 |
| 5 | 549.539 | 226.356 | 315.589 | 28.28 | 0.0 | 5.99 | 56.71 | 109.306 |
| 6 | 535.898 | 224.466 | 310.546 | 27.72 | 0.0 | 4.84 | 58.12 | 109.985 |
| 7 | 530.534 | 221.522 | 310.612 | 28.68 | 0.0 | 3.68 | 59.28 | 111.408 |
| 8 | 530.618 | 219.164 | 309.936 | 29.29 | 0.381 | 3.24 | 60.52 | 112.666 |
| 9 | 527.396 | 217.635 | 309.865 | 29.76 | 54.284 | 3.63 | 61.65 | 115.369 |
| 10 | 530.32 | 216.338 | 309.002 | 29.99 | 40.442 | 3.67 | 62.59 | 116.505 |
| 11 | 528.224 | 214.32 | 307.134 | 30.22 | 127.715 | 4.62 | 63.51 | 116.528 |
| 12 | 533.803 | 212.005 | 306.613 | 30.86 | 0.0 | 4.7 | 64.45 | 118.862 |

`outputs/ABCD/quarterly.csv` contains the same per-quarter decomposition and
macro/constraint measures for **every** seed, including minimum pre-resolution
capital and the demography ratio. `resolution_log.csv` is the full bank/quarter
event log with equity absorbed, uncovered loss, recapitalisation and resolution
count. `banks_by_quarter.csv` includes initial, pre-support and post-support
bank equity. `firm_insolvencies_by_industry.csv` gives quarterly industry counts,
principal and overdraft losses for each arm/seed. Counts refer to composite
industry-region agents, not a count of Canadian legal businesses.

### Origination attribution (12-quarter horizon)

| arm | seed | overdraft_share_new_lending | loss_share_new_principal |
| --- | --- | --- | --- |
| iv-A | 0 | 97.9 | 48.23 |
| iv-AC | 0 | 98.43 | 43.76 |
| iv-ACD | 0 | 2.64 | 0.91 |
| iv-ACD | 1 | 3.26 | 2.05 |
| iv-ACD | 2 | 3.4 | 2.74 |
| v-ACD | 0 | 5.99 | 1.26 |
| v-ACD | 1 | 7.67 | 3.16 |
| v-ACD | 2 | 2.53 | 0.9 |

These are value shares. The loss numerator tracks the portion of *new principal*
cancelled by the end of the run, after contractual amortization, not total
borrower debt or an ever-defaulted flag. Late originations have shorter exposure.
Quarter-of-origination panels are in `new_lending_vintages.csv`. Borrower-level
diagnostics remain in ignored local `micro/` directories.

## Accounting and failed-D1 regressions

| arm | seed | quarters | max_accounting_error |
| --- | --- | --- | --- |
| final_d1 | 1 | 12 | 6.64e-15 |
| final_d1 | 2 | 12 | 1.11e-14 |
| iv-A | 0 | 12 | 7.59e-15 |
| iv-A | 0 | 2 | 5.07e-15 |
| iv-AC | 0 | 12 | 7.50e-15 |
| iv-AC | 0 | 2 | 7.50e-15 |
| iv-ACD | 0 | 12 | 1.11e-14 |
| iv-ACD | 1 | 12 | 1.17e-14 |
| iv-ACD | 2 | 12 | 9.08e-15 |
| iv-ACD | 0 | 2 | 6.08e-15 |
| v-ACD | 0 | 12 | 9.76e-15 |
| v-ACD | 1 | 12 | 1.81e-14 |
| v-ACD | 2 | 12 | 9.98e-15 |
| v-ACD | 0 | 2 | 6.05e-15 |

The original failing D1 seeds were also replayed using the protected old input
with B enabled, C/D disabled. These are accounting regressions, not candidate
bank-capital benchmarks:

| seed | quarters | error | events | recap_B |
| --- | --- | --- | --- | --- |
| 1 | 12 | 6.79e-14 | 1 | 68.737 |
| 2 | 12 | 5.23e-14 | 1 | 78.174 |

## Canadian orders of magnitude and provenance

- RBC's 2023 annual report, printed allowance table p.178, reports consolidated
  retail net write-offs in 2022 of 24M mortgages, 248M personal and 332M cards;
  in 2023: 17M, 404M and 460M. Thus 0.604B and 0.881B per year across these
  products at one large Canadian bank. Coverage includes international business;
  these are **not** Canadian national totals. Recoveries reduce net write-offs,
  unlike the model's gross principal cancellation. [RBC report](https://www.rbc.com/investor-relations/_assets-custom/pdf/ar_2023_e.pdf).
- TransUnion's Q4 2024 mortgage summary reports 0.25% of accounts and 0.23% of
  balances at 60+ days past due. Arrears are a stock, not a write-off flow;
  do not equate these figures with model loss rates. [TransUnion report](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q4-24-ciir-report.pdf).
- OSB reports 4,810 business BIA insolvencies in 2023 and 6,188 in 2024.
  The model's 650 composite producer agents cannot be compared one-for-one
  with those legal-business counts. [OSB annual 2024](https://ised-isde.canada.ca/site/office-superintendent-bankruptcy/en/statistics-and-research/insolvency-statistics/annual-reports/annual-2024).

These sources indicate low ordinary mortgage loss/arrears, not the wholesale
erasure of mortgage principal on a negative-net-worth trigger. They do not
provide an exact like-for-like national charge-off target. No level is fitted.
`benchmarks/ABCD/order_benchmarks_snapshot.json` records table/page, reference
date, scope and figures; `provenance.json` records its SHA256 and retrieval date.
That snapshot hash covers the selected figures checked through primary-source
web extraction. Separate full-source hashes and UTC retrieval timestamps are
recorded for the downloaded RBC report, OSB page and OSFI B-20 page. TransUnion's
full PDF download returned HTTP 403; its figures use the checked snapshot rather
than claiming a full-PDF hash.
Bank-capital and firm-instrument benchmarks have the full cached StatCan source
hash, date and vectors in their respective provenance files. Saving benchmarks
retain their original StatCan CSV and zip hashes. No utilisation number is used.

## E: proposal only — payment default and recoveries

Do not activate or accept D3 on the strength of lower write-offs. Replace the
net-worth predicate with a payment ledger: senior amounts due, cash actually
paid, arrears principal/interest, age of arrears, and cure. Rationed discretionary
goods purchases do not constitute a failed contractual payment. Negative net
worth is a vulnerability measure, not by itself a cancellation instruction.

At default, preserve secured mortgage claims in a workout/foreclosure book.
Specify whether payments continue, whether a loan cures and whether foreclosure
is initiated. Sell collateral to an explicit buyer: buyer deposits fund the
recovery credited to the lender, and title changes. Principal paid from that
cash reduces the loan; only the uncovered balance is a by-bank loss. Never
forgive the full loan and let the borrower keep the collateral. If impairment
is recognized before sale, add a provision/contra-asset and recovery receivable
ledger so that later sale does not recognize the same loss twice.

For unsecured claims, distribute legally available recovery cash by stated
priority. Do not treat a valuation haircut as a cash inflow. Mortgage insurance
requires an explicit insurer counterparty and coverage state; a high survey LTV
alone does not establish insurance coverage.

| Parameter | Source or proposed treatment | Uncertainty |
|---|---|---|
| Arrears/default clock | Observable past-due measures; TransUnion distinguishes 60+ mortgage arrears and 90+ card arrears. Define a contractual quarterly clock before choosing the trigger | D3's three quarters are nine months, not a 90-day definition; no timing fit proposed |
| Collateral eligibility and value | OSFI B-20 requires enforceable collateral and prudent valuation and recognizes realization costs | Underwriting rules are not realized LGD estimates |
| Haircut / sale costs | Retain the existing 20% only as an explicitly unestimated scenario for review; obtain Canadian realized foreclosure/recovery costs before accepting a central value | No defensible single national estimate supplied here; do not tune it to match aggregate losses |
| Recovery lag and cure | Require loan/workout or insurer claims data and an explicit sale mechanism | Not identified by aggregate arrears or net write-offs |
| Insurance / recourse | Explicit contract status and counterparty needed | Household input lacks enough information to infer coverage from LTV alone |

[OSFI B-20, 2017 guideline](https://www.osfi-bsif.gc.ca/en/guidance/guidance-library/residential-mortgage-underwriting-practices-procedures-guideline-2017)
supports the valuation/enforceability requirements, not the candidate's 20%
haircut. E is a specification for approval; no arrears, recovery or foreclosure
behavior has been implemented.

## F: proposal only — instrument and industry boundary

| industry | industry_code | debt | implied_intercompany | external_instrument_proxy |
| --- | --- | --- | --- | --- |
| 44 | O | 407.555 | 193.749 | 213.805 |
| 4 | B06 | 309.382 | 147.078 | 162.303 |
| 27 | D | 263.967 | 125.489 | 138.479 |
| 45 | P | 156.748 | 74.517 | 82.231 |
| 31 | H49 | 132.433 | 62.958 | 69.475 |
| 46 | Q | 92.905 | 44.167 | 48.739 |
| 30 | G | 90.463 | 43.005 | 47.457 |
| 41 | L | 70.885 | 33.698 | 37.186 |

The 2,271.807B initial model balance is entirely placed with banks. NBSA
36-10-0580, private non-financial corporations, market value, 2022 Q4, records
2,448.640B total loan liabilities, including 1,164.071B corporate claims/loans
and advances, 925.316B non-mortgage loans and 356.299B mortgages. An unallocated
2.954B difference remains between the total and these detail rows in the cached
vintage; it is not silently assigned to banks. The same vintage has 625.741B
bonds, which are a separate instrument, not part of the loan total. The earlier
firm audit's bond benchmark used another vintage; it is not substituted here.

Under the initial build's broad loan concept, a pro-rata bridge attributes
1,080.006B of model debt to intercompany claims, leaving 1,191.802B in the
external-instrument proxy **including the unallocated residual**. The latter is
not identifiable as bank-only from borrower instrument totals: other lenders
also hold loans. The industry split above is an illustrative allocation of the
national concept error using existing model debt shares, not observed industry
creditor holdings. The full 50-industry and regional-firm panels are in
`initial_firm_debt_by_industry.csv` and `initial_firm_debt_by_firm.csv`.

Public administration, education and health carry 657.208B (28.93%) despite the
private-corporation benchmark boundary. Ontario's single utilities agent starts
with 96.665B, of which the illustrative intercompany component is 45.954B.
Its 82.165B exposure in the prior Q9 failure follows amortization; it is not a
separate 82B observed utility borrower.

The trigger is `equity < 0 and deposits < 0`. Equity revalues finished goods,
materials and capital at current prices before subtracting debt. Consequently,
asset price changes can combine with an overdraft to cancel all loan principal,
even with positive current operating profit. In the prior Ontario utilities Q9
case, residual noncash assets fell 9.022B while current profit was positive and
that firm's D2 payout was zero. The residual combines price and stock-volume
changes; it is not a measured pure price loss. The code's current-price formula
establishes the revaluation sensitivity independently of that decomposition.

Proposed corrections, **not implemented**: distinguish bank, intercompany,
bond and other-lender claims; either represent intercompany creditors and
assets explicitly or consolidate both sides consistently. Allocate bank credit
using industry/sector creditor data, with a separate treatment of government
producers. Do not simply delete debt and leave the opposite balance sheet
unadjusted. Replace balance-sheet-driven blanket forgiveness with a payment/
workout rule, separate revaluation from cash default, and retain explicit recovery
and restructuring paths. Industry-region agent failures are restructurings of
composite producers, not literal business exits.

## Recommendation

Write-offs are **not yet validated as plausible**. C addresses the initialization
consistency, but the zero-capacity D bound achieves much of its loss reduction
by sharply rationing consumption; saving remains far above the household-account
comparison. Large Q1 principal cancellations persist under the old rule, and
D3 reduces/delays losses without supplying collateral recoveries. E is still
needed as a properly specified payment/default/recovery option for review.
Firm principal and overdraft losses are now the dominant bank-loss component in
the ACD arms; F's creditor boundary and revaluation/workout mechanisms are the
next substantive issues. Neither E nor F is implemented or calibrated here.
D3 remains on hold, and Phase B/C_dp_005 have not started.

## Full suite and scope check

Full suite: **398 passed, 30 failed**, 428 cases. Failures beyond the known transactor-total-real-supply NaN cases: **0**.

Elapsed 20.3 minutes. The full run used `run_pre_D3_tests.py`; sampler properties: `[{'name': 'sampler_n_cores', 'value': '1'}]`. No simulation batch ran concurrently.

Work remained on `feature/validation-2022`; no push. The original repository,
ITC/user-cost files and accepted pickles were not modified. The new pickle is
local under its distinct name; its SHA256 is in `bankcap_provenance.json`.
Original-input D1 runs are read-only accounting regression controls. Source,
input hashes, seed, quarters and accounting errors accompany each run.
Stop here for review.
