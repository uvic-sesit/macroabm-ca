"""Steps 1–3 report; explicitly distinguish household gate from F validation."""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE/'outputs/DF'


def md(frame):
    rows = [[' | '.join(map(str,frame.columns))], [' | '.join(['---']*len(frame.columns))]]
    lines = ['| '+r[0]+' |' for r in rows]
    lines += ['| '+' | '.join(map(str,row))+' |' for row in frame.itertuples(index=False,name=None)]
    return '\n'.join(lines)+'\n'


def main():
    s = pd.read_csv(OUT/'summary.csv').query('quarters==12').copy()
    q = pd.read_csv(OUT/'quarterly.csv').query('quarters==12').copy()
    names = {'iv-ACDp':'iv-ACD′','v-ACDp':'v-ACD′'}
    for frame in [s,q]:
        frame['arm'] = frame.arm.map(names)
    text = '''# Closure D/F — household timing and D1 gate, 23 October 2026

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

'''
    gate = s[['arm','seed','Q1_consumption','Q1_C_target','Q1_consumption_shortfall','household_gate_passed']].copy()
    gate[['Q1_consumption','Q1_C_target']] = gate[['Q1_consumption','Q1_C_target']].div(1e9).round(3)
    gate['Q1_consumption_shortfall'] = (gate.Q1_consumption_shortfall*100).round(3)
    text += md(gate)
    text += '''
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

'''
    macro = q[q.quarter.isin([1,12])][['arm','seed','quarter','consumption','cash_DI','cash_saving','cash_saving_rate','gdp',
                                      'constrained_share','consumption_cut','rent_offset','saving_redirect']].copy()
    for col in ['consumption','cash_DI','cash_saving','gdp','consumption_cut','rent_offset','saving_redirect']:
        macro[col] = macro[col].div(1e9).round(3)
    for col in ['cash_saving_rate','constrained_share']:
        macro[col] = (macro[col]*100).round(3)
    text += md(macro)
    text += '\n## Household and bank losses: 12-quarter totals / seed comparison\n\n'
    loss = s[['arm','seed','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses',
              'recapitalisation','resolution_events','overdraft_share_new_lending','loss_share_new_principal']].copy()
    for col in ['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation']:
        loss[col] = loss[col].div(1e9).round(3)
    for col in ['overdraft_share_new_lending','loss_share_new_principal']:
        loss[col] = (loss[col]*100).round(3)
    text += md(loss)
    text += '''
Overdraft losses in this table are cancelled **firm** overdrafts; household
overdrafts remain bank claims. Recapitalisation is reported separately from
losses. New-lending shares are by value at origination; new-principal loss shares
track contractual amortization and cancellation through Q12. Later vintages
have shorter exposure. Borrower-level records remain local in ignored micro/.
The firm debt boundary and firm insolvency predicate are **still the old ones**.

## Quarterly loss, support and constraint panels (seed 0)

'''
    for arm in ['iv-ACD′','v-ACD′']:
        text += '\n**'+arm+'**\n\n'
        z = q[(q.arm==arm)&(q.seed==0)][['quarter','household_writeoffs','firm_loan_losses','overdraft_losses',
            'bank_losses','recapitalisation','cash_saving_rate','constrained_share','consumption_cut','rent_offset']].copy()
        for col in ['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','consumption_cut','rent_offset']:
            z[col] = z[col].div(1e9).round(3)
        for col in ['cash_saving_rate','constrained_share']:
            z[col] = (z[col]*100).round(3)
        text += md(z)
    text += '''
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

'''
    checks = pd.read_csv(OUT/'summary.csv')[['arm','seed','quarters','max_accounting_error']].copy()
    checks['max_accounting_error'] = checks.max_accounting_error.map(lambda x:f'{x:.2e}')
    text += md(checks)
    tests = OUT/'full_test_execution.json'
    if tests.exists():
        t = json.loads(tests.read_text())
        text += f"\nFull suite: **{t['passed']} passed, {len(t['failures'])} failed**, {t['tests']} cases. "
        text += f"Beyond known NaN cases: **{sum(not x['known_nan'] for x in t['failures'])}**. "
        text += f"Sampler properties: `{t['sampler_properties']}`; elapsed {t['seconds']/60:.1f} minutes.\n"
    else:
        text += '\n**Full suite pending: this report is not final.**\n'
    text += '''
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
'''
    (HERE/'CLOSURE_DF_2026-10-23.md').write_text(text,encoding='utf-8')


if __name__ == '__main__':
    main()
