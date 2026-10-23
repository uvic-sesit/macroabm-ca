"""Render the review report from frozen measurement panels and test evidence."""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE/'outputs/ABCD'
TARGET = HERE/'HOUSEHOLD_CLOSURE_ABCD_2026-10-23.md'


def md(frame):
    frame = frame.copy().fillna('—')
    lines = ['| ' + ' | '.join(map(str, frame.columns)) + ' |',
             '| ' + ' | '.join(['---']*len(frame.columns)) + ' |']
    lines += ['| ' + ' | '.join(map(str, row)) + ' |' for row in frame.itertuples(index=False, name=None)]
    return '\n'.join(lines)+'\n'


def money(frame, columns):
    frame = frame.copy()
    for col in columns:
        frame[col] = frame[col].div(1e9).round(3)
    return frame


def main():
    s = pd.read_csv(OUT/'summary.csv')
    q = pd.read_csv(OUT/'quarterly.csv')
    s12 = s[(s.quarters==12)&(s.arm!='final_d1')]
    base = s12[s12.seed==0].set_index('arm').loc[['iv-A','iv-AC','iv-ACD','v-ACD']].reset_index()
    text = TARGET.read_text(encoding='utf-8').split('## Implementation decisions')[0].split('## Remaining work')[0]
    text = text.replace('Work in progress from `448a6bb`', 'Implementation and diagnostics from `448a6bb`')
    text += '''## Implementation decisions and focused tests

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

'''
    initial = pd.read_csv(OUT/'initial_bank_capital.csv')
    z = money(initial[['region','loans','equity','reserves','equity_to_loans','resolution_ratio']], ['loans','equity','reserves'])
    for col in ['equity_to_loans','resolution_ratio']:
        z[col] = (100*z[col]).round(3)
    text += md(z.rename(columns={'equity_to_loans':'E/L %','resolution_ratio':'E/(L+R) %'}))
    text += '''
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

'''
    calibration = base[['arm','old_propensity','new_propensity','Q1_consumption','Q1_cash_DI','Q1_cash_saving']].copy()
    for col in ['old_propensity','new_propensity','Q1_cash_saving']:
        calibration[col] = (calibration[col]*100).round(3)
    for col in ['Q1_consumption','Q1_cash_DI']:
        calibration[col] = (calibration[col]*4/1e9).round(3)
    text += md(calibration.rename(columns={'old_propensity':'Old weighted s %','new_propensity':'New weighted s %',
        'Q1_consumption':'Q1 cash C, annual B','Q1_cash_DI':'Q1 cash DI, annual B','Q1_cash_saving':'Q1 cash saving %'}))
    text += '''
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

'''
    cols = ['arm','seed','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation',
            'resolution_events','Q12_GDP','Q12_consumption','Q12_cash_saving']
    z = money(s12[cols], ['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses',
                         'recapitalisation','Q12_GDP','Q12_consumption'])
    z['Q12_cash_saving'] = (100*z.Q12_cash_saving).round(2)
    text += md(z)
    text += '''
Across seeds 0–2, ACD household write-offs are 133.088–135.976B and v-ACD
54.098–54.980B. Bank losses vary much more: ACD 429.784–667.491B and v-ACD
312.028–349.014B. Seed-0 write-offs annualized against initial household debt
are about 1.54% and 0.63%, respectively (gross cancellation, not recovered net
loss). Firm principal plus overdrafts account for roughly 69–80% of ACD bank
losses and 83–85% of v-ACD losses. Household results are stable across seeds;
aggregate bank/firm losses are materially seed-sensitive. The fiscal support
totals are themselves large relative to the corrected 456.221B initial capital.
This is accounting closure, not evidence of realistic bank resolution frequency.

'''
    text += '\n### Seed-0 household write-offs by quarter\n\n'
    qb = q[(q.quarters==12)&(q.seed==0)&(q.arm!='final_d1')]
    for measure, title in [('household_writeoffs',None), ('bank_losses','Seed-0 total bank losses by quarter')]:
        if title:
            text += f'\n### {title}\n\n'
        table = qb.pivot(index='quarter',columns='arm',values=measure)[['iv-A','iv-AC','iv-ACD','v-ACD']]/1e9
        table.loc['Total'] = table.sum()
        text += md(table.round(3).reset_index())
    text += '\n### Quarterly macro, support and constraints (seed 0)\n\n'
    for arm in ['iv-A','iv-AC','iv-ACD','v-ACD']:
        text += f'\n**{arm}**\n\n'
        table = qb[qb.arm==arm][['quarter','gdp','consumption','cash_DI','cash_saving_rate','recapitalisation',
                                'min_capital_ratio','constrained_share','consumption_cut']].copy()
        table = money(table, ['gdp','consumption','cash_DI','recapitalisation','consumption_cut'])
        for col in ['cash_saving_rate','min_capital_ratio','constrained_share']:
            table[col] = (100*table[col]).round(2)
        text += md(table.rename(columns={'cash_saving_rate':'Saving %','min_capital_ratio':'Min E/L %',
                                         'constrained_share':'Constrained %'}))
    text += '''
`outputs/ABCD/quarterly.csv` contains the same per-quarter decomposition and
macro/constraint measures for **every** seed, including minimum pre-resolution
capital and the demography ratio. `resolution_log.csv` is the full bank/quarter
event log with equity absorbed, uncovered loss, recapitalisation and resolution
count. `banks_by_quarter.csv` includes initial, pre-support and post-support
bank equity. `firm_insolvencies_by_industry.csv` gives quarterly industry counts,
principal and overdraft losses for each arm/seed. Counts refer to composite
industry-region agents, not a count of Canadian legal businesses.

### Origination attribution (12-quarter horizon)

'''
    z = s12[['arm','seed','overdraft_share_new_lending','loss_share_new_principal']].copy()
    z[['overdraft_share_new_lending','loss_share_new_principal']] *= 100
    text += md(z.round(2))
    text += '''
These are value shares. The loss numerator tracks the portion of *new principal*
cancelled by the end of the run, after contractual amortization, not total
borrower debt or an ever-defaulted flag. Late originations have shorter exposure.
Quarter-of-origination panels are in `new_lending_vintages.csv`. Borrower-level
diagnostics remain in ignored local `micro/` directories.

## Accounting and failed-D1 regressions

'''
    z = s[['arm','seed','quarters','max_accounting_error']].copy()
    z['max_accounting_error'] = z.max_accounting_error.map(lambda v:f'{v:.2e}')
    text += md(z)
    original = []
    for p in (HERE/'outputs/ABCD_original_d1').glob('*/manifest.json'):
        m = json.loads(p.read_text()); r = pd.read_csv(p.parent/'resolutions.csv')
        original.append(dict(seed=m['seed'], quarters=m['quarters'], error=f"{m['max_accounting_error']:.2e}",
                             events=len(r), recap_B=round(r.recapitalisation.sum()/1e9,3)))
    if original:
        text += '\nThe original failing D1 seeds were also replayed using the protected old input\nwith B enabled, C/D disabled. These are accounting regressions, not candidate\nbank-capital benchmarks:\n\n'+md(pd.DataFrame(original).sort_values('seed'))
    text += '''
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

'''
    debt = pd.read_csv(OUT/'initial_firm_debt_by_industry.csv')
    z = money(debt.nlargest(8,'debt'), ['debt','implied_intercompany','external_instrument_proxy'])
    text += md(z)
    text += '''
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

'''
    test = OUT/'full_test_execution.json'
    if test.exists():
        t = json.loads(test.read_text())
        text += f"Full suite: **{t['passed']} passed, {len(t['failures'])} failed**, {t['tests']} cases. "
        extra = sum(not f['known_nan'] for f in t['failures'])
        text += f"Failures beyond the known transactor-total-real-supply NaN cases: **{extra}**.\n\n"
        text += f"Elapsed {t['seconds']/60:.1f} minutes. The full run used `run_pre_D3_tests.py`; "
        text += f"sampler properties: `{t['sampler_properties']}`. No simulation batch ran concurrently.\n"
    else:
        text += '**Full suite still pending; this report is not yet complete.**\n'
    text += '''
Work remained on `feature/validation-2022`; no push. The original repository,
ITC/user-cost files and accepted pickles were not modified. The new pickle is
local under its distinct name; its SHA256 is in `bankcap_provenance.json`.
Original-input D1 runs are read-only accounting regression controls. Source,
input hashes, seed, quarters and accounting errors accompany each run.
Stop here for review.
'''
    TARGET.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
