"""Render BE decisions from audited, unrounded measurement tables."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
OUT=HERE/'outputs/BE'


def table(frame,cols=None,billions=()):
    x=frame.copy() if cols is None else frame[cols].copy()
    for c in billions:
        if c in x:x[c]=x[c]/1e9
    def cell(v):
        if isinstance(v,(float,np.floating)):return f'{v:.3f}'
        return str(v).replace('|','/').replace('\n',' ')
    rows=['| '+' | '.join(map(str,x.columns))+' |','| '+' | '.join(['---']*len(x.columns))+' |']
    rows += ['| '+' | '.join(cell(v) for v in row)+' |' for row in x.itertuples(index=False,name=None)]
    return '\n'.join(rows)+'\n'


def main():
    s=pd.read_csv(OUT/'summary.csv');q=pd.read_csv(OUT/'quarterly.csv');cost=pd.read_csv(OUT/'industry_costs.csv')
    base=s[(s.arm=='iv-ACDpAIFB')&(s.variant=='base')]
    prudent=s[s.arm=='iv-ACDpAIFBP']
    sensitivity=s[(s.arm=='iv-ACDpAIFB')&(s.variant!='base')]
    text=['''# Buffer-stock consumption and firm payouts - 24 October 2026 UTC

**Gate B fails on all three seeds. E has not started. Phase B and C_dp_005 remain on hold.**
The approved buffer-stock rule is implemented as an opt-in candidate, and the
firm cost diagnostic and prudent dividend rule have been evaluated separately.
The old household insolvency rule remains in every measured arm; D3 is off.
No parameter was changed to improve a gate result. Work continues from e386f4e
on feature/validation-2022; no push or changes to protected inputs.

## Decisions and implementation

| Step | Commit / regression | Result |
|---|---|---|
| B spending rule and fixed SFS buffers | 2948b08; above/below wealth target, nonnegative spending, exact D and cash flow | Default off; kappa .10, smoothing .25; IO basket and consumption-before-investment preserved |
| B initial debt service | 47e6002; initial contract service regression | Initial interest TS is unset; initialize from scheduled contractual principal/interest and opening overdraft interest |
| Cost/price diagnostic | 6a973a6; exact multiplicative price decomposition | Read-only, no additional random draws; t0 and every quarter, all industries |
| B gate and audits | 1e83c42; percentage-point boundary regression | Gate B fails; no E or foreclosure implementation |
| Prudent discretionary firm payout | PAYOUT_COMMIT; retained-profit/cash/reserve and declaration-settlement regressions | Candidate flag only; mixed income and corporate transfers retain their existing treatment |
| Pricing and producer adjustment | Proposal below | Not implemented |

Amounts in tables are CAD B unless percentages or other units are labelled.
Consumption includes VAT and paid rent. Investment includes capital-formation
tax. Cash DI is net household income less interest paid; saving excludes D.8,
principal payments and capital purchases. Financial saving is separately shown
in the group ledger evidence; cash saving is not a deposit-accumulation rate.

## Buffer-stock specification and initial level

The unanchored rule is max(0, Yperm + kappa*(L - target)). L is positive deposits
plus existing non-pension OFA; overdrafts and unsecured debt are reported as
separate liabilities rather than negative assets. Yperm is smoothed net cash
receipts after principal, interest and rent, using weight .25. Initial service
comes from the loan contracts because interest-paid TS values are unset at t0.
The receipts declaration and final settlement still agree household by household.
The D cap still covers house transactions and other senior obligations, with
zero unused consumer-credit capacity. Investment is cut before consumption.

The fixed target is b*Yperm for positive Yperm. For nonpositive Yperm it is the
initial cell weighted-median liquid-asset level, preventing a negative buffer.
b is the SFS weighted median of L/(annual after-tax income/4), by weighted
income decile and age of the major income recipient. The SFS source is the
[2023 economic-family PUMF, catalogue 13M0006X](https://www150.statcan.gc.ca/n1/en/catalogue/13M0006X).
Liquid variables are PWASTDEP, PWASTMUI, PWASTSTK, PWASTBND, PWASTOIN and PWATFS;
pensions are excluded. PWEIGHT is unchanged. The 80 reference cells include a
pooled-age fallback for each income decile. Model age uses the initial
highest-income linked individual's age as a major-recipient proxy; it is not a
new observation of Canadian household age. Group membership and buffers stay fixed.

Uncertainty: SFS economic families differ from model households; wealth is from
2023, and the model's senior-payment-adjusted income differs from the SFS
after-tax denominator. The model retains its member-age skeleton. These are
reported mapping assumptions, not calibration targets. Source/extract hashes,
variable names, date and cell estimates are in benchmarks/BE/buffer_provenance.json
and sfs_liquid_buffers.csv.

The national level is anchored once to
[36-10-0112](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201),
v62305982: 1,511.382B/year, or 377.8455B/quarter. The implemented anchor is a
single fixed CAD-per-represented-household additive intercept inside max(0,...),
solved by bisection including D1's actual private-rent offset and paid rent.
It leaves kappa, b and smoothing unchanged and is not recalibrated during a run.
Every sensitivity gets its own t0 level anchor to the same target.
The payout arm also initializes C and planned investment to the same national
targets using its own declared D2 receipts; its household-level starting plans
can therefore differ. This standard t0 initialization is part of the reported
comparison, not a refit of response coefficients to outcomes.
This distributional choice matters: an aggregate level match is not evidence
that individual consumption levels are plausible.
The calibrated rule is explicitly max(0, Yperm + kappa*(L-target) + level).
Consequently the intercept shifts the effective wealth-gap threshold by
-level/kappa. The above/below-target regression checks establish the raw
wealth response at level zero; they do not validate the distribution after
anchoring. This distinction and the resulting zero-consumption incidence
are central to the failed candidate, not concealed by the aggregate match.

''']
    calibrations=[]
    for p in sorted(OUT.glob('*/manifest.json')):
        m=json.loads(p.read_text())
        if m['quarters']!=12:continue
        c=pd.read_csv(p.parent/'buffer_calibration.csv')
        calibrations.append(dict(arm=m['arm'],variant=m['variant'],seed=m['seed'],
            level_CAD_per_household=c.level_per_household.iloc[0],
            initial_account_C=c.initial_account_consumption.sum(),initial_Yperm=c.initial_permanent_income.sum()))
    text += [table(pd.DataFrame(calibrations),billions=['initial_account_C','initial_Yperm']),
             '\nThe cash-saving benchmark is -0.601861%, using v62305980 disposable income\n'
             'and v62305982 consumption, excluding v105775422 pension entitlements.\n'
             'Published v62305984 saving includes that adjustment and is 2.1% in 2022.\n'
             'The selected vectors, retrieval date, full-source and extract hashes are\n'
             'in benchmarks/BE/benchmark_index.json and household_targets_2022.csv.\n\n',
             '## Gate B and four requested sensitivities\n\n',
             table(pd.concat([base,sensitivity]),['arm','variant','seed','constrained_slope_pp','Q12_constrained_pct','Q12_saving_pct','gate_passed']),
             '\nGate: accounting <=1e-8, Q4-Q12 OLS slope <=.25 percentage points/q,\n'
             'and Q12 cash saving in [-5.6%,4.4%], on every base seed. Sensitivities\n'
             'are seed 0 only as requested; they do not qualify E independently.\n\n']
    text += ['![Consumption, saving and constrained-share paths](outputs/BE/buffer_gate_paths.png)\n\n']
    zero=pd.read_csv(OUT/'household_zero_consumption_diagnosis.csv')
    national=zero.groupby(['arm','variant','seed','quarter']).sum(numeric_only=True).reset_index()
    national['zero_goods_pct']=100*national.zero_goods_households/national.households
    national['positive_income_zero_goods_pct']=100*national.income_positive_zero_goods/national.households
    text += ['## Household diagnosis\n\n',
             table(national[(national.arm=='iv-ACDpAIFB')&(national.variant=='base')],
                   ['seed','quarter','zero_goods_pct','positive_income_zero_goods_pct','cash_DI','consumption_with_rent'],billions=['cash_DI','consumption_with_rent']),
             '\nA zero goods purchase does not imply zero paid rent. Low constrained\n'
             'shares cannot validate a rule that itself plans very little consumption.\n'
             'The large negative common intercept clips many positive-income households\n'
             'to zero goods demand. Initial aggregate consumption is concentrated in\n'
             'wealth-rich households, then falls as their assets are drawn down.\n'
             'This is a failure of this anchored candidate, not evidence that Canadian\n'
             'households choose these consumption levels. No gate-oriented refit was made.\n\n']
    diagnosis=pd.read_csv(OUT/'constraint_diagnosis.csv')
    final=diagnosis[(diagnosis.arm=='iv-ACDpAIFB')&(diagnosis.variant=='base')&(diagnosis.quarter==12)]
    cl=final.groupby(['seed','diagnosis'])[['households','constrained','income_down','wages_down','firm_receipts_down','employment_down','assets_down']].sum().reset_index()
    text += [table(cl), '\nClasses match FE: income-restoration sufficient, persistent spending gap\n'
             'with assets down, and other/combined. Restoring Q1 receipts is an\n'
             'accounting counterfactual, not a causal employment estimate. Fixed\n'
             'decile x initial OFA-band details are in constraint_diagnosis.csv;\n'
             'the zero-consumption and saving panel is household_zero_consumption_diagnosis.csv.\n\n']
    for col in ['decile','asset_band']:
        z=zero[(zero.arm=='iv-ACDpAIFB')&(zero.variant=='base')&(zero.quarter==12)].groupby(['seed',col]).sum(numeric_only=True).reset_index()
        z['zero_goods_pct']=100*z.zero_goods_households/z.households
        text += [table(z,['seed',col,'households','zero_goods_pct','cash_saving','consumption_with_rent'],billions=['cash_saving','consumption_with_rent'])]
    text += ['\nDecision needed before reopening E: review the distributional t0 anchor and\n'
             'the SFS/model liquidity and income mapping. One option is household-specific\n'
             'initial level offsets that preserve an independently validated consumption\n'
             'distribution while retaining fixed wealth responses; another is a\n'
             'structural target-wealth rule with heterogeneity and precautionary motives.\n'
             'An additional data-mapping option is an independently specified SFS\n'
             'within-cell wealth-rank matching rule, rather than treating one cell\n'
             'median as every wealth-rich household\'s desired buffer. Observed\n'
             'wealth is not itself an estimated desired wealth target. Small SFS\n'
             'cells (minimum eight records) and the family/household boundary add\n'
             'uncertainty. These possibilities need a specification before rerunning.\n'
             'Both change the specification and need review. Neither is implemented,\n'
             'and no coefficient is selected using this gate.\n\n',
             '## Quarterly macro outcomes and loss attribution\n\n']
    for arm in ['iv-ACDpAIFB','iv-ACDpAIFBP']:
        for seed in range(3):
            z=q[(q.arm==arm)&(q.variant=='base')&(q.seed==seed)]
            if not len(z):continue
            text += [f'### {arm}, seed {seed}\n\n',table(z,['quarter','constrained_pct','cash_saving_pct','consumption','C_target_gap_pct','planned_investment','investment','asset_liquidation','gdp'],
                billions=['consumption','planned_investment','investment','asset_liquidation','gdp']),
                table(z,['quarter','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','min_capital_ratio','min_resolution_ratio'],
                billions=['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation'])]
    text += ['\n### Twelve-quarter totals and final levels\n\n',table(pd.concat([base,prudent]),
        ['arm','seed','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','Q12_GDP','Q12_consumption','Q12_saving_pct'],
        billions=['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','Q12_GDP','Q12_consumption']),
        '\nThe full quarterly sensitivity outputs, OFA boundary flows, debt/overdrafts,\n'
        'bank stocks and named fiscal recapitalisations remain in outputs/BE.\n'
        'The OFA liquidation path is still explicitly without issuer; no offsetting\n'
        'issuer is invented. Retained F collateral is not a cash recovery.\n\n',
        '## Firm starting costs, pricing and demand\n\n',
        'All industry-quarter observations, all three base seeds and payout reruns\n'
        'are in industry_costs.csv; firm_costs.csv in each run retains regional\n'
        'firm observations and exact price decomposition. Industry unit costs are\n'
        'output-weighted. Components are intermediate inputs, wages, taxes and\n'
        'depreciation per unit; interest is additional in profit.\n\n']
    initial=cost[(cost.arm=='iv-ACDpAIFB')&(cost.variant=='base')&(cost.seed==0)&(cost.quarter==0)].copy()
    initial['t0_class']=np.where(initial.profit<0,'initial loss','initial profit/nonnegative')
    text += [table(initial,['industry_code','price','intermediates_per_unit','wages_per_unit','taxes_per_unit','depreciation_per_unit','unit_cost','GOS','IO_GOS','profit','t0_class'],billions=['GOS','IO_GOS','profit']),
        '\nThe reconstructed and stored t0 unit costs agree numerically. Sector I,\n'
        'H53 and A02 already have costs above price. Their gross surplus is positive,\n'
        'but the existing depreciation burden makes net profit negative. The\n'
        'industry IO benchmark is the accepted input residual VA minus employee\n'
        'compensation and production taxes, not a net-profit target. Current\n'
        'depreciation comes from the inherited GFCF/investment-calibrated capital\n'
        'consumption matrix (icio_sea_matching.py and icio_reader.py), rather than\n'
        'industry observed CFC. This is an existing conceptual proxy requiring\n'
        'an empirical CFC bridge; it is not proof of a mechanical scaling error.\n'
        'No t0 firm input is changed in this round.\n\n'
        'The price rule uses expected PPI inflation with speed 1, demand-pull and\n'
        'cost-push speeds 0, and firm noise standard deviation .05. Thus there is\n'
        'no direct correction toward an individual producer cost-plus price.\n'
        'The diagnostic records the deterministic expected-inflation price and\n'
        'recovers the multiplicative noise from the actual draw, without drawing\n'
        'another random number. Price-floor observations are flagged as censored.\n'
        'Subsequent demand loss, capacity use and cost/price gaps are descriptive\n'
        'joint outcomes; the decomposition alone does not identify causation.\n\n']
    paths=pd.read_csv(OUT/'price_path_decomposition.csv')
    paths=paths[(paths.arm=='iv-ACDpAIFB')&(paths.variant=='base')&(paths.quarter==12)&paths.industry_code.isin(['I','C10T12','C19','H53','F','A02'])]
    text += ['Cumulative price paths below use fixed t0 output weights; actual price\n'
             'index = expected-inflation index times noise residual index. The\n'
             'residual aggregates the realized firm noise and any censored floors.\n\n',
             table(paths,['seed','industry_code','actual_price_index','expected_inflation_index','noise_residual_index'])]
    focus=cost[(cost.arm=='iv-ACDpAIFB')&(cost.variant=='base')&cost.industry_code.isin(['I','C10T12','C19','H53','F','A02'])]
    for seed in range(3):
        z=focus[(focus.seed==seed)&focus.quarter.isin([0,12])]
        text += [f'### Focus industries, seed {seed}, t0 and Q12\n\n',table(z,['quarter','industry_code','price','unit_cost','profit','capacity_use','demand','output','expected_price','realised_noise_price_effect'],billions=['profit','demand','output'])]
    text += ['\nInitial losses are a starting cost/IO-calibration issue. Newly loss-making\n'
        'industries are classified jointly by relative price/cost and demand/output\n'
        'changes in industry_loss_classification.csv. C10T12, C19 and F begin\n'
        'profitable nationally, so their later losses cannot all be attributed to\n'
        'initial negative profit. Losses within a profitable national industry may\n'
        'still be concentrated in particular regional firms.\n\n',
        '## Approved prudent payout rule\n\n'
        'Only discretionary firm dividends are screened. Mixed income and corporate\n'
        'transfers retain the existing D2 requests, cash cap, tax and household\n'
        'allocation. Released dividend capacity is not reassigned to those flows.\n'
        'The discretionary dividend is capped by positive retained profit and cash\n'
        'above declared mixed/transfers plus a reserve for next-quarter scheduled\n'
        'principal, interest (including overdraft interest), and the latest nominal\n'
        'wage bill. The latest observed wages are the no-new-parameter forecast.\n'
        'Opening distributable retained profit is one initial quarter of positive\n'
        'after-tax profit, explicitly a proxy because a historical retained-earnings\n'
        'ledger is not available. Thereafter the ledger carries realized after-tax\n'
        'profits less all firm distributions; negative balances carry forward.\n'
        'Current asset revaluations do not create distributable profit.\n\n'
        'The screen runs before the irrevocable D2 declaration used in household\n'
        'budgets. End-quarter payment settles that declaration exactly. Later\n'
        'operating losses can still reduce cash; this is not a guarantee of positive\n'
        'end-quarter deposits. Non-discretionary transfers can themselves breach the\n'
        'reserve. No payout is retrospectively cancelled after households spend it.\n\n']
    classified=pd.read_csv(OUT/'industry_loss_classification.csv')
    classified=classified[(classified.arm=='iv-ACDpAIFB')&(classified.variant=='base')&classified.Q12_lossmaking]
    text += ['All nationally loss-making Q12 industries, with overlapping diagnostic\n'
             'flags (demand down does not rule out pricing/cost effects):\n\n',
             table(classified,['seed','industry_code','profit','classification','demand_down','noise_sufficient_for_cost_crossing','cost_above_no_noise_price'],billions=['profit'])]
    comparison=base.merge(prudent,on='seed',suffixes=('_B','_P'))
    records=[]
    for r in comparison.itertuples():
        records.append(dict(seed=r.seed,firm_loss_B=r.firm_loan_losses_B+r.overdraft_losses_B,
            firm_loss_P=r.firm_loan_losses_P+r.overdraft_losses_P,payout_B=r.firm_payouts_B,payout_P=r.firm_payouts_P,
            Q12_GDP_B=r.Q12_GDP_B,Q12_GDP_P=r.Q12_GDP_P,Q12_income_B=r.Q12_household_income_B,Q12_income_P=r.Q12_household_income_P))
    text += [table(pd.DataFrame(records),billions=['firm_loss_B','firm_loss_P','payout_B','payout_P','Q12_GDP_B','Q12_GDP_P','Q12_income_B','Q12_income_P']),
        '\nFirm losses fall on seeds 0 and 2 but rise on seed 1. The payout rule\n'
        'therefore does not provide a robust firm-loss reduction. Discretionary\n'
        'and non-discretionary flows must be separated because altered prices,\n'
        'profits and cash positions can increase total distributions even when\n'
        'dividends are restricted. Twelve-quarter components:\n\n',
        table(pd.concat([base,prudent]),['arm','seed','paid_mixed','paid_transfers','paid_dividends'],billions=['paid_mixed','paid_transfers','paid_dividends']),
        '\nDetailed retained-profit, reserve and declared/paid dividend observations\n'
        'are in each payout run payout_log.csv. Quarterly payouts and household\n'
        'income are in quarterly.csv; event-by-event fiscal support is in\n'
        'resolution_log.csv. The payout arm is a separate comparison, not a\n'
        'replacement for the original Gate B measurement.\n\n',
        '## Firm-behaviour proposals only\n\n'
        '1. Replace unanchored price noise with a cost/markup target: form expected\n'
        '   unit intermediate, wage and tax costs and separately validated CFC;\n'
        '   target price = expected unit cost/(1 - target operating margin).\n'
        '   Anchor industry margins to concept-matched IO/QFSE observations, with\n'
        '   partial adjustment and a floor covering variable cost. Estimate the\n'
        '   adjustment speed independently; do not choose it to remove defaults.\n'
        '   A limited idiosyncratic shock, if retained, should mean-revert around\n'
        '   the target. Separate financing costs from operating margins and avoid\n'
        '   using the initial investment proxy as observed depreciation.\n'
        '2. For persistent operating losses, specify either capacity contraction\n'
        '   with worker reallocation and asset transfers or explicit exit/entry.\n'
        '   Entry requires start-up equity, working capital, product supply and\n'
        '   worker matching; exit needs creditor recoveries and an asset buyer.\n'
        '   Public O/P/Q producers need a government financing counterparty.\n'
        '   Duration thresholds, scrapping/recovery and entry rates need sourced\n'
        '   Canadian evidence or labelled sensitivities. Do not delete continuing\n'
        '   overdrafts, forgive debt, or create production capacity without funding.\n\n'
        'Neither proposal is implemented. The approved payout restriction alone\n'
        'does not repair structurally negative operating margins or capital-cost\n'
        'measurement.\n\n'
        '## Plausibility and review recommendation\n\n'
        'Household losses still use the old rule. Aggregate reductions under B\n'
        'coincide with implausibly weak consumption, so they do not validate the\n'
        'household default mechanism. E remains necessary to evaluate payment\n'
        'failure and collateral recovery, but its explicit gate has not passed.\n\n'
        'For scale, [RBC 2023 annual report](https://www.rbc.com/investor-relations/_assets-custom/pdf/ar_2023_e.pdf)\n'
        'has retail net write-offs .604B/.881B in 2022/2023 and wholesale\n'
        '.136B/.293B; total write-off ratios .10%/.14% of average loans. These\n'
        'are one consolidated bank, not national household totals.\n'
        '[TransUnion Q4 2024](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q4-24-ciir-report.pdf)\n'
        'reports 60+ day mortgage delinquency .25% of accounts and .23% of\n'
        'balances, stocks rather than loss flows. [OSB 2024](https://ised-isde.canada.ca/site/office-superintendent-bankruptcy/en/statistics-and-research/insolvency-statistics/annual-reports/annual-2024)\n'
        'reports 4,810/6,188 business insolvencies in 2023/2024; composite model\n'
        'restructurings do not equal legal filings. Original dates, tables/pages\n'
        'and hashes remain in benchmarks/ABCD and benchmarks/FE; BE benchmark_index\n'
        'links their exact provenance hashes. No levels are fitted to these figures.\n\n'
        'Firm losses and repeated recapitalisations remain too large to accept as\n'
        'normal Canadian baseline magnitudes. They combine an inherited starting\n'
        'capital-cost proxy and producer/pricing behaviour. They can be stated as\n'
        'limitations in exploratory runs, but should not be presented as a validated\n'
        'firm closure. In this round Phase B is not ready regardless: Gate B fails,\n'
        'and the required household default step has not run. Review the household\n'
        'level/mapping issue first; decide separately which firm limitations are\n'
        'acceptable for a future conditional Phase B.\n\n'
        '## Verification and evidence\n\n']
    auditpath=OUT/'audit.json'
    if auditpath.exists():
        a=json.loads(auditpath.read_text());text += [f"Full suite: {a['passed']} passed, {a['known_failures']} known failures, {a['extra_failures']} extra failures, {a['tests']} cases. "
            f"Maximum accounting residual across {len(a['runs'])} runs: {a['max_accounting_error']:.3g}.\n\n"]
    text += ['The full suite uses run_pre_D3_tests.py, sampler n_cores=1. The exact\n'
        '30 pre-existing Nan in transactor_total_real_supply failure IDs are\n'
        'compared with FE. All final base/payout 2Q prefixes match their 12Q\n'
        'counterparts. Protected pickle hashes, source revisions and all run\n'
        'metadata are audited. Local household micro ledgers are not committed;\n'
        'their hashes and aggregate group panels are retained.\n\n'
        'Evidence: [quarterly](outputs/BE/quarterly.csv), [summary](outputs/BE/summary.csv),\n'
        '[all-industry costs](outputs/BE/industry_costs.csv), [constraints](outputs/BE/constraint_diagnosis.csv),\n'
        '[resolution log](outputs/BE/resolution_log.csv), [audit](outputs/BE/audit.json).\n'
        'Reproduce with run_be_measurements.py, summarise_be.py,\n'
        'be_household_diagnosis.py, run_be_full_tests.py, audit_be.py and this renderer.\n'
        'Stop here for review. No Phase B or C_dp_005 work has started.\n']
    report=''.join(text)
    debt=pd.read_csv(OUT/'initial_household_debt.csv').debt.sum()
    shares=pd.concat([base,prudent])[['arm','seed','household_writeoffs','recapitalisation']].copy()
    shares['annualised_HH_loss_initial_debt_pct']=100*shares.household_writeoffs/(3*debt)
    shares['recap_initial_bank_equity_pct']=100*shares.recapitalisation/456.221e9
    scale='Initial household debt is '+f'{debt/1e9:,.3f}'+'B. Annualised model losses below\n'
    scale+='are 12Q write-offs / 3 / initial debt; this is not an average-loan net\n'
    scale+='charge-off rate. The initial bank-equity denominator is 456.221B\n'
    scale+='(36-10-0580 v62696428 + v62696533, 2022Q4; inherited bank-capital provenance).\n\n'
    scale+=table(shares,['arm','seed','annualised_HH_loss_initial_debt_pct','recap_initial_bank_equity_pct'])+'\n'
    report=report.replace('For scale, [RBC 2023 annual report]',scale+'For scale, [RBC 2023 annual report]')
    payout=HERE/'outputs/BE/payout_commit.txt'
    report=report.replace('PAYOUT_COMMIT',payout.read_text().strip() if payout.exists() else 'pending')
    (HERE/'CLOSURE_BE_2026-10-24.md').write_text(report,encoding='utf-8')
    marker='## Buffer-stock B and prudent payouts - 24 October 2026 UTC'
    issues=(HERE/'ISSUE_REGISTER.md').read_text(encoding='utf-8').split(marker)[0].rstrip()
    section='\n\n'+marker+'\n\n'
    section+='Supersedes the FE proposal-only status for B. F remains an accepted candidate.\n'
    section+='Gate B fails on all seeds; E, Phase B and C_dp_005 have not started.\n\n'
    section+='| Check / decision | Commit / evidence | Finding / decision needed |\n|---|---|---|\n'
    section+='| Fixed SFS buffer response | 2948b08, 47e6002; 5 regressions | Default off, candidate on; kappa .10, smoothing .25, fixed SFS decile/age buffers; initial contractual service replaces unset interest TS. |\n'
    section+='| t0 consumption level | buffer_calibration.csv | Matches 377.8455B/q exactly. Common level is -83,544.52 CAD/household/q. It shifts the effective buffer threshold and clips widespread positive-income goods demand to zero; review this distributional anchor before accepting the candidate. |\n'
    section+='| Gate B | 1e83c42; 2 diagnostic/gate regressions | Saving fails in every base seed and all four one-factor sensitivities. No coefficient or SFS cell was refitted to the gate. |\n'
    section+='| Firm t0 costs | 6a973a6; industry_costs.csv | I cost/price=1.323, H53=1.295, A02=1.082 at t0. Positive GOS is outweighed by inherited investment-proxy depreciation. No proven mechanical t0 data error; empirical CFC bridge remains needed. |\n'
    section+='| Prudent discretionary dividends | 95cf3e6; 3 regressions and exact payout ledger audit | Positive retained profit plus cash above next service/wage reserve. Mixed income and corporate transfers retain treatment. Firm-loss effect differs across seeds. |\n'
    section+='| E / pricing / entry | not implemented | E held by Gate B; pricing and producer adjustment remain specified proposals only. |\n\n'
    section+=table(base,['seed','constrained_slope_pp','Q12_constrained_pct','Q12_saving_pct','gate_passed'])+'\n'
    section+=table(pd.DataFrame(records),billions=['firm_loss_B','firm_loss_P','payout_B','payout_P','Q12_GDP_B','Q12_GDP_P','Q12_income_B','Q12_income_P'])+'\n'
    if auditpath.exists():
        section+=f"All {len(a['runs'])} serial runs pass accounting (max {a['max_accounting_error']:.3g}); protected inputs and paired prefixes match. "
        section+=f"Full suite: {a['passed']} passed / {a['known_failures']} known failures / {a['extra_failures']} extra failures, {a['tests']} cases; sampler one worker.\n\n"
    else:section+='Full suite and final artifact audit pending.\n\n'
    section+='Recommendation: do not accept this anchored B candidate or declare household losses plausible. Firm losses combine a starting capital-cost proxy with price/demand/continuation behaviour; they can be disclosed in exploratory work, not treated as a validated closure. Phase B remains gated.\n\n'
    section+='[CLOSURE_BE_2026-10-24.md](CLOSURE_BE_2026-10-24.md) contains the full quarterly, sensitivity, industry and seed evidence. Stop for review.\n'
    (HERE/'ISSUE_REGISTER.md').write_text(issues+section,encoding='utf-8')


if __name__=='__main__':main()
