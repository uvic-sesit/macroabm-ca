# Household closure A–D: implementation and diagnostic record

Work in progress from `448a6bb`, on `feature/validation-2022`. D3 remains
unaccepted; Phase B and C_dp_005 are on hold. No push.

## Approved overdraft proxy and sensitivity search

The household file exposes outstanding card and credit-line balances, not
contractual limits. The main D arm uses **zero unused capacity**, as explicitly
selected by the user. Households without positive deposits cannot fund
discretionary purchases. Senior payments can still create payment distress.
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

## Remaining work

B, C, D implementation and regression tests, accounting runs, twelve-quarter
and seed comparisons, proposals E/F, and final full-suite verification remain
pending. This file does not assert acceptance of the candidate.
