"""Render the gated F report from final evidence; E is conditional, never assumed."""
import json
import subprocess
from pathlib import Path
import pandas as pd
from render_afe_report import table

HERE=Path(__file__).resolve().parent
OUT=HERE/'outputs/FE'
REPORT=HERE/'CLOSURE_FE_2026-10-24.md'


def main():
    gates=json.loads((OUT/'continuation.json').read_text())
    if gates['start_E']:
        raise RuntimeError('All continuation checks pass: E must be completed before rendering a stopped-at-F report')
    # A stable specification source makes repeated renders idempotent.
    old=subprocess.check_output(['git','show',
        '0e64a05:dev/validation_2022/CLOSURE_FE_2026-10-24.md'],cwd=HERE.parents[1]).decode('utf-8')
    initial=old[old.index('## Debt boundary and equity bridge'):old.index('## Household check and buffer-stock option')]
    initial=initial.replace('Bonds are a named boundary outside the model, not added to bank loans.',
        'Bonds are a named boundary outside the model, not added to bank loans.\n'
        'The per-firm consolidation/scope split is a pro-forma bridge allocated\n'
        'by old model debt, not an observed distribution of intercompany claims\n'
        'or evidence of such claims at public producers. Each net equity change\n'
        'equals its actual old-minus-new bank-debt change. Only the national\n'
        'intercompany benchmark is observed.')
    initial=initial.replace('No capital-share\nfallback was needed.',
        'The industry financial-statements weights are a proxy for the NBSA\n'
        'private-corporation boundary; the IO producers do not separately identify\n'
        'private/government ownership within every other industry. No capital-share\n'
        'fallback was needed.')
    a=initial.index('After N quarters, write down')
    b=initial.index("F's assessment threshold",a)
    initial=initial[:a]+'''After N quarters, total bank credit is formal loan principal plus the
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

'''+initial[b:]
    proposal=old[old.index('## Household check and buffer-stock option'):old.index('## Recommendation')]
    q=pd.read_csv(OUT/'quarterly.csv').query('quarters==12').sort_values(['seed','quarter'])
    s=pd.read_csv(OUT/'summary.csv').query('quarters==12').sort_values('seed')
    g=pd.read_csv(OUT/'gates_and_comparison.csv').sort_values('seed')
    plans=pd.read_csv(OUT/'planned_household_spending.csv')
    q=q.merge(plans,on=['seed','quarter'],validate='one_to_one')
    lev=pd.read_csv(OUT/'leverage_national.csv')
    q=q.merge(lev[['seed','quarter','debt','capital','GOS','deposits','overdraft','debt_to_capital','debt_to_annualised_GOS',
                  'total_bank_credit','credit_to_capital','credit_to_annualised_GOS']],
        on=['seed','quarter'],validate='one_to_one')
    detail=pd.read_csv(OUT/'firm_defaults_detail.csv')
    events=pd.read_csv(OUT/'resolution_log.csv').query('quarters==12')
    oldq=pd.read_csv(HERE/'outputs/IFE/quarterly.csv').query('quarters==12')
    oldsummary=pd.read_csv(HERE/'outputs/IFE/summary.csv').query('quarters==12').set_index('seed')
    tests=json.loads((OUT/'full_test_execution.json').read_text()) if (OUT/'full_test_execution.json').exists() else None
    audit=json.loads((OUT/'audit.json').read_text()) if (OUT/'audit.json').exists() else None
    maxerr=g.max_accounting_error.max()
    fresult='PASS' if gates['gate_F_pass'] else 'FAIL'
    household='PASS' if gates['household_check_pass'] else 'FAIL'
    parts=[f'''# Firm debt and default, then household default - 24 October 2026 UTC

**F is implemented and measured on seeds 0-2. Gate F: {fresult}.
Household continuation check: {household}. E has not started.**
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
| F gate | 9a26aeb; gate regression | {fresult}; maximum accounting residual {maxerr:.3g}; loss reductions below |
| Household continuation check | 9a26aeb; slope/sign regression | {household}; Q4-Q12 OLS slopes below; any positive slope stops E |
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

''']
    parts.append(table(g,['seed','initial_planned_investment','baseline_firm_losses','firm_losses','firm_loss_reduction',
        'gate_F','constrained_slope_pp_per_quarter','household_check_pass','Q12_constrained_share','Q12_cash_saving'],
        money=['initial_planned_investment','baseline_firm_losses','firm_losses'],
        percent=['firm_loss_reduction','Q12_constrained_share','Q12_cash_saving']))
    parts.append('Slope is percentage points per quarter, using unrounded Q4-Q12 shares.\n'
        'Material firm-loss reduction means at least 25%, declared before 12Q outcomes.\n'
        'Recognition changes and retained overdrafts must be reviewed alongside this gate.\n')
    compare=[]
    for r in s.itertuples():
        b=oldsummary.loc[r.seed]
        end=q[q.seed==r.seed].iloc[-1]
        compare.append(dict(seed=r.seed,base_GDP=b.Q12_GDP,F_GDP=r.Q12_GDP,
            base_consumption=b.Q12_consumption,F_consumption=r.Q12_consumption,
            base_bank_losses=b.bank_losses,F_bank_losses=r.bank_losses,
            base_recap=b.recapitalisation,F_recap=r.recapitalisation,
            F_Q12_overdraft=end.overdraft))
    parts.append(table(pd.DataFrame(compare),list(compare[0]),money=[k for k in compare[0] if k!='seed']))
    parts.append(initial)
    parts.append('## Quarterly household and bank losses, support and capital\n\n'
        'Loan write-offs and overdraft losses are distinct components. Capital ratio is\n'
        'equity/loans; minimum before resolution is also retained in quarterly.csv.\n')
    for seed in range(3):
        z=q[q.seed==seed].copy()
        parts.append(f'### Seed {seed}\n\n')
        parts.append(table(z,['quarter','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses',
            'recapitalisation','min_capital_ratio_before_resolution','min_capital_ratio','min_resolution_ratio'],
            money=['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation'],
            percent=['min_capital_ratio_before_resolution','min_capital_ratio','min_resolution_ratio']))
    parts.append('### Twelve-quarter totals\n\n')
    parts.append(table(s,['seed','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses',
        'recapitalisation','resolution_events','min_capital_before_resolution','min_capital_ratio'],
        money=['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation'],
        percent=['min_capital_before_resolution','min_capital_ratio']))
    parts.append('## Resolution log\n\n')
    if len(events):
        parts.append(table(events,['seed','region','bank','quarter','equity_before','losses_absorbed_by_equity',
            'uncovered_loss','recapitalisation','equity_after'],money=['equity_before','losses_absorbed_by_equity',
            'uncovered_loss','recapitalisation','equity_after']))
    else:parts.append('No resolution events in the final 12Q runs.\n')
    parts.append('## Quarterly macro, household investment and constraints\n\n')
    for seed in range(3):
        parts.append(f'### Seed {seed}\n\n')
        parts.append(table(q[q.seed==seed],['quarter','gdp','consumption','cash_DI','cash_saving_rate',
            'planned_investment','investment','investment_cut','consumption_cut','asset_liquidation','constrained_share','consumption_constrained_share'],
            money=['gdp','consumption','cash_DI','planned_investment','investment','investment_cut','consumption_cut','asset_liquidation'],
            percent=['cash_saving_rate','constrained_share','consumption_constrained_share']))
    parts.append('## Firm defaults, collateral coverage and leverage\n\n'
        'Every nonzero quarter/industry cell is in outputs/FE/firm_defaults_detail.csv;\n'
        'industry leverage paths are in leverage_industry.csv. Defaults count composite\n'
        'producer restructuring events, including repeat events, not legal insolvencies.\n'
        'recovery_cash is zero: collateral stays with the producer and secures the\n'
        'retained contract. It is not sold and does not repay the lender in cash.\n\n')
    if len(detail):
        codes=json.loads((HERE/'outputs/pre_D3_checks/industry_mapping.json').read_text())
        industry=detail.groupby(['seed','industry'])[['defaults','loan_debt','overdraft_cancelled','retained_contract','recovery_cash']].sum().reset_index()
        industry['industry_code']=industry.industry.astype(str).map(codes)
        parts.append(table(industry,['seed','industry_code','defaults','loan_debt','overdraft_cancelled','retained_contract','recovery_cash'],
            money=['loan_debt','overdraft_cancelled','retained_contract','recovery_cash']))
        totals=detail.groupby(['seed','quarter'])[['defaults','loan_debt','overdraft_cancelled','retained_contract','retained_loan','retained_overdraft','recovery_cash']].sum().reset_index()
        parts.append(table(totals,list(totals.columns),money=['loan_debt','overdraft_cancelled','retained_contract','retained_loan','retained_overdraft','recovery_cash']))
    else:parts.append('No firm defaults occurred.\n')
    parts.append(table(q,['seed','quarter','debt','overdraft','total_bank_credit','credit_to_capital','credit_to_annualised_GOS'],
        money=['debt','overdraft','total_bank_credit']))
    parts.append('### Why the firm-loss gate is not robust on seed 1\n\n'
        'The 25% materiality assessment is a conservative analysis threshold chosen\n'
        'before the runs, not a number specified by the user or a model calibration.\n'
        'Seed 1 still has lower firm losses, but only by 20.2%. The independent\n'
        'household check stops E regardless of that materiality interpretation.\n\n')
    mechanisms=pd.read_csv(OUT/'firm_loss_mechanisms.csv')
    mechanisms['negative_profit_loss_pct']=100*mechanisms.losses_while_negative_profit/mechanisms.firm_losses
    parts.append(table(mechanisms,['seed','firm_losses','default_events','negative_profit_loss_pct',
        'losses_while_positive_equity','payout_at_loss_events','payouts_while_negative_profit','payouts_while_end_cash_short'],
        money=['firm_losses','losses_while_positive_equity','payout_at_loss_events','payouts_while_negative_profit','payouts_while_end_cash_short']))
    drivers=pd.read_csv(OUT/'firm_loss_industry_diagnosis.csv').sort_values(['seed','losses'],ascending=[True,False]).groupby('seed',sort=False).head(6)
    parts.append(table(drivers,['seed','industry_code','losses','formal_losses','overdraft_losses','initial_debt_capital'],
        money=['losses','formal_losses','overdraft_losses']))
    parts.append('Accommodation/food services is a persistent loss source across seeds.\n'
        'Seed 1 additionally has large food-manufacturing and refining losses. The\n'
        'industry allocation raises initial credit in those manufacturing industries\n'
        'relative to physical capital; this is visible in the independent initial\n'
        'debt/capital table. Continued operating deficits then rebuild overdrafts\n'
        'between restructurings. Most loss occurs with negative current profit;\n'
        'the largest events pay no distributions in that event quarter. Earlier\n'
        'payouts and lost demand can still affect cash, so this is not a causal\n'
        'claim that D2 has no effect. Revaluation alone does not fire the trigger.\n'
        'The debt boundary and default rule changed together: their separate\n'
        'contributions are not identified by this one-arm comparison.\n\n'
        'Proposals for decision, not implemented: review firm cash budgets and\n'
        'investment finance before repeated overdrafts; require a funded retained-\n'
        'profit/current-cash buffer for discretionary payouts; validate recoverable\n'
        'assets (including the treatment of inventory/receivables) against loan\n'
        'collateral concepts; specify recovery or workout finance for continuing\n'
        'producers. Do not alter N, haircut or income targets to conceal the losses.\n'
        'Largest firm events and reconciled sector totals are retained in\n'
        'largest_firm_loss_events.csv and firm_loss_industry_diagnosis.csv.\n\n')
    industry_paths=pd.read_csv(OUT/'leverage_industry.csv')
    public=industry_paths.query('quarter==12 and industry in [44,45,46]').groupby('seed')[['debt','overdraft']].sum().reset_index()
    parts.append('### Government-producer financing boundary\n\n'
        'Initial O/P/Q formal loans are zero, as required by the data correction.\n'
        'The inherited cash settlement can still create operating overdrafts later.\n'
        'These are reported and included in F losses, rather than hidden by the\n'
        'formal-loan boundary. A strict no-private-credit boundary for ongoing public\n'
        'producer operations requires a specified government working-capital cash\n'
        'counterparty; proposal only, not an invented fiscal transfer in this run.\n\n')
    parts.append(table(public,['seed','debt','overdraft'],money=['debt','overdraft']))
    parts.append('## Household constraint diagnosis\n\n'
        'Fixed initial income deciles and non-pension asset bands; household counts\n'
        'are represented counts. The restoration test holds current plans, resources\n'
        'other than income, and senior payments fixed; it is not a causal decomposition.\n'
        'The mutually exclusive classes and overlapping income/job/asset indicators\n'
        'are all retained, so simultaneous mechanisms are visible.\n\n')
    mechanism=pd.read_csv(OUT/'constraint_mechanism.csv').query('quarter==12')
    parts.append(table(mechanism,['seed','diagnosis','households','constrained','income_change','wage_change',
        'firm_receipts_change','other_income_change','employment_change','consumption_cut','investment_cut'],
        money=['income_change','wage_change','firm_receipts_change','other_income_change','consumption_cut','investment_cut']))
    interpret=[]
    asset_classes=pd.read_csv(OUT/'constraint_assets.csv').query('quarter==12')
    for seed in range(3):
        z=mechanism[mechanism.seed==seed];n=z.constrained.sum()
        by=z.set_index('diagnosis')
        other=asset_classes[(asset_classes.seed==seed)&(asset_classes.diagnosis=='other_or_combined')&
                            (asset_classes.asset_band=='zero')]
        interpret.append(dict(seed=seed,
            income_restoration_pct_constrained=100*by.loc['income_restoration_sufficient','constrained']/n if 'income_restoration_sufficient' in by.index else 0.,
            persistent_gap_assets_down_pct_constrained=100*by.loc['persistent_spending_gap_assets_down','constrained']/n if 'persistent_spending_gap_assets_down' in by.index else 0.,
            other_zero_initial_assets_households=other.households.sum(),
            other_zero_assets_plan_above_income=other.plan_above_income.sum(),
            other_zero_assets_income_down=other.income_down.sum()))
    parts.append(table(pd.DataFrame(interpret),list(interpret[0])))
    parts.append('The residual class is not silently attributed to income losses: its\n'
        'large zero-initial-liquid-asset subgroup is shown separately above. A\n'
        'household starting with no liquid assets cannot have assets run down\n'
        'from Q1, but can remain constrained because its plan exceeds income\n'
        'or because senior debt service/rent absorbs available resources. Wage,\n'
        'job and firm-receipt decline indicators below overlap these classes.\n\n')
    for field in ('decile','assets'):
        z=pd.read_csv(OUT/f'constraint_{field}.csv').query('quarter==12')
        group='decile' if field=='decile' else 'asset_band'
        values=[k for k in z.select_dtypes('number') if k not in ['seed','quarter','decile']]
        z=z.groupby(['seed',group])[values].sum().reset_index()
        z['constrained_pct']=100*z.constrained/z.households
        parts.append(table(z,['seed',group,'households','constrained_pct','income_down','wages_down',
            'employment_down','firm_receipts_down','assets_down','plan_above_income','income_change',
            'wage_change','firm_receipts_change','employment_change'],money=['income_change','wage_change','firm_receipts_change']))
    parts.append(proposal)
    parts.append('## Canadian orders of magnitude and recommendation\n\n'
        'The independent initial bank book-equity benchmark is 456.221B from\n'
        '[36-10-0580](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610058001),\n'
        'v62696428 and v62696533, 2022Q4. Model recapitalisations are fiscal\n'
        'support flows, not ordinary bank provisions. Large repeated injections\n'
        'relative to that initial stock would remain economically problematic.\n\n'
        '[RBC 2023 annual report](https://www.rbc.com/investor-relations/_assets-custom/pdf/ar_2023_e.pdf)\n'
        'reports consolidated retail net write-offs of 0.604B in 2022 and 0.881B\n'
        'in 2023. This is one bank, includes international exposures, and is not\n'
        'a national household total. [TransUnion Q4 2024](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q4-24-ciir-report.pdf)\n'
        'shows 60+ day mortgage delinquency of 0.25% of accounts and 0.23% of\n'
        'balances; these are stocks, not charge-off flows. [OSB](https://ised-isde.canada.ca/site/office-superintendent-bankruptcy/en/statistics-and-research/insolvency-statistics/annual-reports/annual-2024)\n'
        'reports 4,810/6,188 business insolvencies in 2023/2024. Composite model\n'
        'restructuring counts cannot be compared one-for-one with legal filings.\n'
        'Source dates, table/page references and hashes remain in benchmarks/ABCD.\n'
        'None of these levels is fitted.\n\n')
    parts.append('For firms and the whole bank book, RBC reports wholesale net write-offs\n'
        'of 0.136B/0.293B in 2022/2023 and overall net write-off ratios of\n'
        '0.10%/0.14% of average loans. Total provisions were 0.484B/2.468B.\n'
        'These consolidated one-bank measures are not national totals or fiscal\n'
        'recapitalisations. See benchmarks/FE/rbc_credit_quality_2022_2023.json\n'
        'for pages, verification date and the full original PDF hash.\n\n')
    # Conclusions use directly measured loss/support/overdraft ranges; they do
    # not turn the recognition-only gate into an economic validation claim.
    parts.append(f'F recognized firm losses fall by {100*g.firm_loss_reduction.min():.2f}%'
        f' to {100*g.firm_loss_reduction.max():.2f}% across seeds. Household write-offs'
        f' remain {s.household_writeoffs.min()/1e9:.3f}-{s.household_writeoffs.max()/1e9:.3f}B over 12Q;'
        f' recapitalisations are {s.recapitalisation.min()/1e9:.3f}-{s.recapitalisation.max()/1e9:.3f}B.'
        f' Firm gross overdrafts at Q12 are {q.query("quarter==12").overdraft.min()/1e9:.3f}-'
        f'{q.query("quarter==12").overdraft.max()/1e9:.3f}B.\n\n')
    parts.append('Recognized firm losses alone do not establish plausible credit risk: F\n'
        'retains the collateral-covered portion of overdrafts and contracts, whereas\n'
        'the old rule cancelled them fully. Review continuing exposures with losses.\n'
        'The old household net-worth rule also remains unvalidated.\n\n')
    rates=[]
    initial_banks=pd.read_csv(OUT/'initial_banks.csv')
    for row in g.itertuples():
        rates.append(dict(seed=row.seed,
            annual_firm_loss_pct_initial_external_credit=100*row.firm_losses/(3*1281615e6),
            annual_bank_loss_pct_initial_joint_loans=100*row.bank_losses/(3*initial_banks.loans.sum()),
            recap_pct_initial_bank_equity=100*row.recapitalisation/456221e6))
    parts.append(table(pd.DataFrame(rates),list(rates[0])))
    parts.append('These are annualized cumulative model losses over three years divided\n'
        'by fixed initial books, not RBC average-book net charge-off ratios. They\n'
        'are an order-of-magnitude diagnostic with explicit denominator limits.\n'
        'Given the remaining loss rates and fiscal support, firm losses and bank\n'
        'recapitalisations are not accepted as plausible Canadian normal-year\n'
        'magnitudes. Better accounting and a lower loan boundary do not settle\n'
        'firm operating deficits, the overdraft channel or collateral realization.\n\n')
    if not gates['household_check_pass']:
        parts.append('The household check fails, so stop before E as instructed. A liquid-wealth\n'
            'response is a justified next candidate for decision; the current results\n'
            'do not identify its Canadian coefficients or warrant fitting them to\n'
            'these gates. Keep the buffer-stock option unimplemented pending approval.\n')
    parts.append('The model is not ready for Phase B. E, buffer-stock behavior and C_dp_005\n'
        'do not start from this report. No claim of plausible household losses or\n'
        'bank recapitalisations follows merely from an accounting pass.\n\n## Full suite and reproducibility\n\n')
    if tests:
        parts.append(f'Full tests/ suite via run_pre_D3_tests.py: {tests["tests"]} cases, '
            f'{tests["passed"]} passed, {len(tests["failures"])} failed; '
            f'{sum(not f["known_nan"] for f in tests["failures"])} beyond the known NaN cases. '
            'Sampler n_cores=1. See full_test_execution.json, full_tests.xml and log.\n')
    else:parts.append('Full suite still running; this report is not final until its result is recorded.\n')
    if audit:parts.append('audit.json verifies all accepted inputs, new input, source hashes, paired\n'
        '2Q/12Q prefixes and exact baseline failure IDs. Micro ledgers remain local;\n'
        'micro_hashes.json and artifact_manifest.json make evidence traceable.\n')
    REPORT.write_text('\n'.join(parts),encoding='utf-8')
    print('Rendered stopped-at-F report')


if __name__=='__main__':main()
