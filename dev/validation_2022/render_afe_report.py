"""Render the gated step-A report from measured evidence; no fitted parameters."""
import json
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent
OUT=HERE/'outputs/AFE'


def table(frame,columns,money=(),percent=()):
    x=frame[list(columns)].copy()
    for c in money:x[c]=x[c]/1e9
    for c in percent:x[c]=x[c]*100
    def fmt(v):
        if isinstance(v,(bool,str,int)):return str(v)
        try:return f'{v:.3f}'
        except (ValueError,TypeError):return str(v)
    lines=['| '+' | '.join(x.columns)+' |','| '+' | '.join(['---']*len(x.columns))+' |']
    lines.extend('| '+' | '.join(fmt(v) for v in row)+' |' for row in x.itertuples(index=False,name=None))
    return '\n'.join(lines)+'\n'


def main():
    q=pd.read_csv(OUT/'quarterly.csv').query('quarters==12')
    s=pd.read_csv(OUT/'summary.csv').query('quarters==12')
    gates=pd.DataFrame(json.loads((OUT/'step_A_gates.json').read_text()))
    if gates.gate_pass.any():
        raise RuntimeError('Stopped-at-A report requires all gates failed; inspect results')
    d=pd.read_csv(OUT/'saving_by_decile.csv')
    a=pd.read_csv(OUT/'saving_by_assets.csv')
    tests=json.loads((OUT/'full_test_execution.json').read_text()) if (OUT/'full_test_execution.json').exists() else None
    parts=['''# Closure A/F/E — financial-asset budget gate, 23 October 2026

**Step 1 is implemented and measured. Both parts of its gate fail on every seed.
Steps 2 (F) and 3 (E) therefore did not start, as instructed.** D3 is off in
all runs; the old household and firm rules remain. Phase B and C_dp_005 remain
on hold. Work starts from 3248706 on feature/validation-2022; no push.

## Steps, commits and decision

| Step | Commit / tests | Gate and result |
|---|---|---|
| 1: cash, then non-pension OFA, then proportional cuts | 393bff8; 16 focused checks pass across asset, budget, income and gate tests | Accounting passes; economic gate fails on seeds 0–2 |
| Diagnostic household grouping correction | f140ae2; 9 focused checks pass including new regional-total reconciliation regression | All six final runs repeated from this source; superseded evidence excluded |
| 2: firm debt boundary and payment default (F) | Not started; no F tests or new firm-debt pickle | Blocked by step 1 gate; no change to firm instruments, allocation or default |
| 3: household payment default and foreclosure (E) | Not started; no E tests | Same gate; no new N, haircut or recovery parameter chosen |

## What changed and how it books

The financial_asset_drawdown switch is off by default and on only in iv-ACD′A.
Accepted D timing, C calibration, D2, H7/D4, bank capital/resolution and narrow
D1 remain. Unused credit capacity is zero; no propensity, benchmark, credit
headroom or multiplier changes.

The budget uses opening deposits plus declared current receipts, committed
loans and executed sale proceeds, less rent, interest, principal and executed
house purchases. It then includes existing non-pension OFA before applying the
common consumption/investment cut. At settlement it uses cash first and
liquidates only the remaining shortfall from actual spending and senior
payments; unfilled purchases cause no liquidation. Optional new OFA saving
cannot divert senior-payment cash. Excess senior shortfalls remain payment
distress, not a new default trigger.

The protected pension component is input Voluntary Pension multiplied by
population scale, matching OFA units. It stays protected; there is no separate
pension revaluation path. Remaining non-pension OFA includes later saving.
initial_financial_assets.csv checks original component sums/units in every
region. No input record or pickle changes.

Liquidation uses the existing OFA usage/deposit calculation: OFA falls by L,
and deposit resources rise by L. It is not income or new credit. The reserve
boundary **OFA without issuer** remains −ΔOFA: gross liquidation less new OFA
accumulation. Net boundary and gross liquidation are both reported; no issuer
is invented. Cash, loan, equity, reserve and recapitalisation identities stay
active.

## Gate and seed comparison

Before runs, “must not trend upward over Q4–Q12” was defined as an OLS slope
of population-constrained share ≤0 across those nine quarters. Q4/Q12 endpoints
are also reported. Q12 cash saving must be within ±5 percentage points of the
unchanged −0.602% benchmark. Both conditions must pass on every seed. step_A_gates.json is authoritative
for this gate. The inherited run-manifest field household_gate_passed refers
only to the earlier Q1 consumption check, which passes; it does not indicate
that the present Q4?Q12/saving gate passed. The summary renames that legacy
field to avoid confusing the two.

Amounts in all tables are CAD billions; flows quarterly unless marked 12Q.
Shares/rates are percentages, slopes percentage points/quarter. Cuts are
planned VAT-inclusive consumption cuts before goods-market rationing.
''']
    parts.append(table(gates,['seed','constrained_Q4','constrained_Q12','constrained_slope_per_quarter','Q12_saving_rate','saving_gap_pp','trend_pass','saving_pass'],percent=['constrained_Q4','constrained_Q12','constrained_slope_per_quarter','Q12_saving_rate']))
    parts.append('## Quarterly household budget, liquidation and macro outcomes\n')
    cols=['quarter','constrained_share','consumption_cut','asset_liquidation','ofa_without_issuer','consumption','cash_DI','cash_saving','cash_saving_rate','gdp']
    for seed in range(3):
        parts.append(f'### Seed {seed}\n')
        parts.append(table(q[q.seed==seed],cols,money=[c for c in cols if c not in ['quarter','constrained_share','cash_saving_rate']],percent=['constrained_share','cash_saving_rate']))
    parts.append('## Accepted D timing/D1 base comparison\n\nAll other flags/input match. This is a dynamic comparison, not a fixed-income causal decomposition. Q12 GDP rises against the accepted base in seeds 0 and 2, but falls in seed 1; no seed-independent GDP stabilisation is claimed. Consumption still falls 16.2?18.4% from Q1 to Q12 in the new runs.\n')
    old=pd.read_csv(HERE/'outputs/DF/quarterly.csv').query("quarters==12 and arm=='iv-ACDp'")
    cmp=pd.concat([old.assign(version='accepted base'),q.assign(version='+ asset drawdown')])
    cmp=cmp[cmp.quarter.isin([1,12])].sort_values(['seed','quarter','version'])
    parts.append(table(cmp,['seed','quarter','version','constrained_share','consumption','cash_saving_rate','gdp'],money=['consumption','gdp'],percent=['constrained_share','cash_saving_rate']))
    parts.append('''## Who drives saving and rising constraints

Deciles are fixed t0 national income ranks, population weighted. Asset bins
are t0 non-pension OFA per represented household, kept fixed as assets run down.
Positive saving and dissaving are summed separately. Assets are captured before
the old insolvency handler. Full Q1–Q12 panels by decile, assets, and both are
in saving_by_decile.csv, saving_by_assets.csv and saving_by_decile_assets.csv.

Across seeds, the 45.24% of households starting with zero or at most 10,000
CAD of non-pension OFA account for 73.99?74.36% of Q12 constraints and
59.94?64.98% of net cash saving. Households starting above 100,000 CAD hold
97.51?97.59% of remaining non-pension assets at Q12; only 3.09?3.29% are
constrained. This is not an aggregate shortage of OFA.

Income deciles 6?10 contribute 80.31?83.67% of Q12 net saving. Their low-asset
subgroup is 18.11% of all households but contributes 43.79?45.02% of saving.
The bottom two deciles together dissave 0.58?1.75B in Q12. The income/asset
cross-panel therefore matters: higher income does not imply a liquid buffer.

### Income deciles at Q12, all seeds
''')
    parts.append(table(d[d.quarter==12],['seed','decile','households','constrained_share','cash_DI','consumption','cash_saving','positive_saving','dissaving','opening_assets'],money=['cash_DI','consumption','cash_saving','positive_saving','dissaving','opening_assets'],percent=['constrained_share']))
    parts.append('### Initial non-pension assets at Q12, all seeds\n')
    parts.append(table(a[a.quarter==12],['seed','asset_bin','households','constrained_share','cash_saving','positive_saving','dissaving','opening_assets','liquidation'],money=['cash_saving','positive_saving','dissaving','opening_assets','liquidation'],percent=['constrained_share']))
    changes=[]
    for seed in range(3):
        for col,frame,group in [('asset_bin',a,'asset'),('decile',d,'income')]:
            start=frame[(frame.seed==seed)&(frame.quarter==4)].set_index(col)
            end=frame[(frame.seed==seed)&(frame.quarter==12)].set_index(col)
            for key in start.index:
                changes.append(dict(seed=seed,group=group,bin=str(key),extra_constrained=end.loc[key,'constrained']-start.loc[key,'constrained'],saving_change=end.loc[key,'cash_saving']-start.loc[key,'cash_saving']))
    changes=pd.DataFrame(changes)
    changes.to_csv(OUT/'Q4_Q12_group_changes.csv',index=False)
    parts.append('### Q4–Q12 change in constraints and saving\n')
    parts.append(table(changes,['seed','group','bin','extra_constrained','saving_change'],money=['saving_change']))
    parts.append('''### Cash saving versus financial-asset accumulation

Cash saving is cash DI minus consumption (VAT and paid rent included). It does
not subtract principal or household capital purchases. A constrained borrower
can therefore record positive cash saving while repaying principal, buying
capital goods and losing financial assets. The exact battery bridge is:

S_cash = Δdeposits + ΔOFA + principal − new loans + net house purchases
         + household investment including CF tax.

“Implied investment including CF tax” is the residual from this identity,
not an independently observed estimate. House sales cancel nationally to
floating-point precision. This bridge changes neither definition nor gate.
It cannot identify principal/investment by decile; a household-level ledger
would resolve that attribution.
''')
    parts.append(table(q[q.quarter==12],['seed','cash_saving','deposit_change','net_OFA_accumulation','principal_repayment','new_loans','house_sales_net','investment_including_CF_tax_implied'],money=['cash_saving','deposit_change','net_OFA_accumulation','principal_repayment','new_loans','house_sales_net','investment_including_CF_tax_implied']))
    parts.append('''## Household/firm losses and bank support

Combined firm principal/overdraft losses are about 58?67% of total bank losses across seeds. These retain legacy default rules and the legacy firm-debt boundary. They
are not F/E validation results. Principal losses, firm overdraft losses and
recapitalisations are separate flows.

### Twelve-quarter totals
''')
    cols=['seed','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','resolution_events','min_capital_ratio']
    parts.append(table(s,cols,money=cols[1:6],percent=['min_capital_ratio']))
    parts.append('### Quarterly losses/support, all seeds\n')
    cols=['seed','quarter','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','min_capital_ratio']
    parts.append(table(q,cols,money=cols[2:7],percent=['min_capital_ratio']))
    parts.append('''Resolution_log.csv and banks_by_quarter.csv retain events and before/after
rescue capital. Minimum ratios above are end-quarter equity/loans, not
CET1/RWA. Firm loss allocation is in firm_insolvencies_by_industry.csv;
origination overdrafts and principal losses are in new_lending_vintages.csv.

### Firm debt before/after

| Item | Before | After this step |
|---|---:|---|
| Initial firm loan debt | 2,271.807B, accepted model audit | Unchanged |
| External-loan/mortgage boundary, intercompany consolidation, bonds and O/P/Q | Legacy boundary | F not implemented: gate fails |
| Industry allocation/default | Legacy | Unchanged |
| io2022_household_agreed_bankcap_firmdebt.pkl | Not built by this task | Not built |

An F industry before/after table or F loss comparison would imply work that
did not occur. F/E remain pending behind the gate; neither is validated here.

## Diagnosis and options for review

Asset drawdown improves consumption/constraint levels but does not stabilise
the trajectory. Wealth is concentrated: unused assets elsewhere cannot fund
another household without a transfer or credit, neither authorized here.
Low-asset groups can be constrained and still contribute positive cash saving
because principal/capital purchases use resources outside consumption. The
initial uniform income-weighted propensity remains unchanged. Liquidity
permission alone does not create a buffer-stock consumption rule. Goods
rationing and legacy firm failures also remain in the dynamic feedback;
these runs do not separately identify their causal effects.

Options, **not implemented**:

1. Audit desired/filled consumption, investment and principal at household
   level. Consider consumption priority over discretionary capital purchases,
   rather than scaling both together. That changes the proportional rule and
   needs review; do not choose it merely to force the gate to pass.
2. Specify heterogeneous spending/saving with independently sourced income
   and liquid-wealth evidence and an explicit asset-buffer objective. Source
   parameters and sensitivities; no quarterly national consumption rescaling.
3. Review contractual burdens and E workouts alongside that ledger. Principal
   is not consumption; liquidity distress is not negative net worth. F/E stay
   gated; no silent change to debt service, benchmark or default clock.

Recommendation: retain the asset option as a diagnostic and resolve the
spending/investment/payment ledger before accepting closure. Household/firm
losses and recapitalisations remain too large to claim plausible orders of
magnitude. Phase B is **not ready**. F may explain part of the feedback, but
the user's gate prevents starting it here.

## Provenance and execution

Unchanged saving comparison: StatCan 36-10-0112, 2022 mean of quarterly SAAR;
C v62305982 = 1,511.382B/year; cash-comparison DI v62305981 = 1,502.340B/year;
excluding D.8 gives −0.601861%. This remains an approximate model cash/SNA
comparison, not a complete boundary bridge.
[Source](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201).
Retrieved 2026-10-23; ZIP SHA256
b577daa453e1527602f55000d301624143bdaf3dba87bfbd458f44d6ab797d1e;
CSV SHA256 5cfe7a3c5a9cd3610faa2d7fd19b591b1cfed01750d0c493568f0c1f25cc7d97.
Original provenance: benchmarks/household_corrections/36100112_provenance.json.

No new benchmark/parameter is introduced. Earlier RBC net write-offs,
TransUnion arrears and OSB insolvency figures retain sources, scopes, dates
and hashes in benchmarks/ABCD/ and the accepted ABCD report. One bank's net
losses, national arrears stocks and legal-business counts are not equated
to model gross cancellations or 650 composite producers. Accepted figures
are RBC consolidated retail net write-offs 0.604B/0.881B in 2022/2023;
TransUnion Q4 2024 mortgage 60+ arrears 0.25% of accounts; OSB business BIA
insolvencies 4,810/6,188 in 2023/2024. These are not matching denominators.
[RBC](https://www.rbc.com/investor-relations/_assets-custom/pdf/ar_2023_e.pdf),
[TransUnion](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q4-24-ciir-report.pdf),
[OSB](https://ised-isde.canada.ca/site/office-superintendent-bankruptcy/en/statistics-and-research/insolvency-statistics/annual-reports/annual-2024).
Snapshot provenance and full-source hashes where available remain in
benchmarks/ABCD/order_benchmarks_snapshot.json and provenance.json; the
TransUnion full PDF was unavailable and uses its checked snapshot. The accepted
2,271.807B is the initial model debt audit, not a new bank-holder estimate.

For each seed 0–2 a 2Q accounting run immediately preceded its 12Q measurement,
serially. Final source is f140ae2-compatible; manifests retain exact source
and input hashes/seed. Every budgeted receipt reconciles household by household
to booked income. All accounting errors are below 1e-8. Short runs reproduce
the first two quarters of long runs. Group income, consumption, constraints
and liquidation reconcile to outcomes; liquidation never exceeds available
non-pension OFA. Initial components, protected pickles and opening cash funding
of D2 declarations are independently checked.

The initial 393bff8 2Q/partial 12Q runs were superseded because group consumption
broadcast a regional total. National flows/accounting were unaffected. Those
runs were stopped and retained locally under AFE_superseded_393bff8; all final
runs repeat after f140ae2's individual-series reconciliation and regression.
No superseded number enters this report. See superseded_run_note.json.
''')
    if tests:
        parts.append(f"Full tests/ through run_pre_D3_tests.py: **{tests['passed']} passed, {len(tests['failures'])} known NaN failures**, no new failures/errors. Sampler n_cores=1; failed identities checked against DF. Logs, JUnit, execution metadata and final audit are under outputs/AFE/.\n")
    else:parts.append('Full suite pending; draft.\n')
    parts.append('No original repository, ITC/user-cost file or accepted pickle modified. No new pickle built. Nothing pushed. Stop for review.\n')
    (HERE/'CLOSURE_AFE_2026-10-23.md').write_text('\n'.join(parts),encoding='utf-8')


if __name__=='__main__':
    main()
