"""Render the QE review packet from completed measurements, never fitted values."""
import json
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;OUT=HERE/'outputs/QE'


def table(frame,digits=3):
    def fmt(v):
        if pd.isna(v):return ''
        if isinstance(v,(float,np.floating)):
            return f'{v:.3e}' if 0<abs(v)<1e-4 else f'{v:,.{digits}f}'
        return str(v).replace('|','/')
    return '| '+' | '.join(frame.columns)+' |\n| '+' | '.join(['---']*len(frame.columns))+' |\n'+'\n'.join('| '+' | '.join(fmt(v) for v in row)+' |' for row in frame.itertuples(index=False,name=None))+'\n'


def main():
    test_path=OUT/'verification/full_test_execution.json'
    tests=json.loads(test_path.read_text()) if test_path.exists() else None
    q=pd.read_csv(OUT/'quarterly.csv');g=pd.read_csv(OUT/'gates.csv');dist=pd.read_csv(OUT/'consumption_distribution.csv')
    changes=pd.read_csv(OUT/'headline_changes.csv');decomp=pd.read_csv(OUT/'GDP_expenditure_decomposition.csv');e=pd.read_csv(OUT/'E_metrics.csv')
    bridge=pd.read_csv(OUT/'bridge/GDP_bridge.csv');cost=pd.read_csv(OUT/'bridge/firm_bridge.csv');checks=pd.read_csv(OUT/'bridge/unchanged_GDP_checks.csv')
    qg=g[g.arm=='Q'];eg=g[g.arm=='E']
    totals=q.groupby(['arm','seed'])[['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation']].sum().reset_index()
    c=[]
    for p in sorted((OUT/'C_bank_replays').glob('*/bank_components.csv')):
        z=pd.read_csv(p).groupby('seed')[['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation']].sum().reset_index();z['arm']='C';c.append(z)
    totals=pd.concat([totals,*c],ignore_index=True).sort_values(['arm','seed'])
    totals.to_csv(OUT/'bank_loss_totals.csv',index=False)
    paired=q[q.arm=='F_CFC'].merge(q[q.arm=='E'],on=['seed','quarter'],suffixes=('_old','_E'))
    loss=paired[['seed','quarter','household_writeoffs_old','household_writeoffs_E','bank_losses_old','bank_losses_E','recapitalisation_old','recapitalisation_E']].copy()
    loss.to_csv(OUT/'old_vs_E_quarterly.csv',index=False)
    endpoints=dist[dist.quarter.isin([0,12])]
    endpoints.to_csv(OUT/'distribution_endpoints.csv',index=False)
    source=json.loads((HERE/'benchmarks/QE/provenance.json').read_text())
    national=changes.pivot(index=['arm','seed'],columns='metric',values='change_pct').reset_index()
    national=national.rename(columns={'gdp':'nominal_GDP_pct','gdp_PPI_deflated':'PPI_deflated_GDP_pct','C':'national_account_C_pct','I':'investment_pct','employment':'employment_pct','implicit_GDP_PPI':'price_level_pct','GDP_PPI_scope_adjusted_t0_diagnostic':'scope_adjusted_GDP_pct','GDP_PPI_Q1_to_Q12':'Q1_Q12_GDP_pct'})
    summary=national[['arm','seed','nominal_GDP_pct','PPI_deflated_GDP_pct','scope_adjusted_GDP_pct','Q1_Q12_GDP_pct','national_account_C_pct','investment_pct','employment_pct','price_level_pct']]
    summary.to_csv(OUT/'shrinkage_seed_comparison.csv',index=False)
    # Every t0/Q12 raw level remains in the long-form endpoint file.
    endpoint_levels=changes[['arm','seed','metric','Q0','Q12']]
    endpoint_levels.to_csv(OUT/'headline_endpoint_levels.csv',index=False)
    d0=endpoints[(endpoints.seed==0)&(endpoints.scheme=='DHEA_equivalised_DI')].pivot(index=['arm','quarter'],columns='quintile',values='share').reset_index()
    for j in range(1,6):d0[j]*=100
    d0.columns=['arm','quarter','Q1_share_pct','Q2_share_pct','Q3_share_pct','Q4_share_pct','Q5_share_pct']
    s0=endpoints[(endpoints.seed==0)&(endpoints.scheme=='SHS_gross_household_income')].pivot(index=['arm','quarter'],columns='quintile',values='share').reset_index()
    for j in range(1,6):s0[j]*=100
    s0.columns=d0.columns
    wealth=pd.read_csv(OUT/'runs/F_CFC_base_q12_s0/wealth_definition_audit.csv').groupby('definition')[['L','target','gap','hypothetical_kappa_gap']].sum().reset_index()
    wealth['kappa_gap_pct_C']=100*wealth.hypothetical_kappa_gap/3778455e5
    for key in ['L','target','gap','hypothetical_kappa_gap']:wealth[key]/=1e9
    actualbridge=bridge[['region','production_market','income_market','expenditure_market_scope_adjusted','production_income_residual','expenditure_residual']].copy()
    for col in actualbridge.columns[1:]:actualbridge[col]/=1e9
    byindustry=cost[cost.above_price_nonnegative_GOS].groupby('industry').agg(cells=('firm','size'),CFC=('CFC','sum'),IO_GOS=('IO_GOS','sum')).reset_index()
    byindustry.to_csv(OUT/'bridge/above_price_by_industry.csv',index=False)
    a=q[q.arm.isin(['F_CFC','Q','E'])][['arm','seed','quarter','consumption','cash_DI','cash_saving_rate','constrained_share','investment','asset_liquidation','gdp']].copy()
    for key in ['consumption','cash_DI','investment','asset_liquidation','gdp']:a[key]/=1e9
    a['cash_saving_rate']*=100;a['constrained_share']*=100
    a.to_csv(OUT/'household_and_GDP_paths_B_pct.csv',index=False)
    text=[]
    def add(s):text.append(s)
    add('# Household distribution, payment default and GDP bridge — QE review, 2026-10-25 UTC\n')
    add('**Stop for review: Q fails; E is accounting-consistent but fails its empirical loss/arrears gate; FB fails initialization and unit-cost gates. No combined run, B2 retest, Phase B or C_dp_005 port.** F_CFC is adopted as the accepted firm-data baseline, with P off, as instructed. That adoption is a data improvement, not a validation pass.\n')
    add('Money is CAD billions unless specified. Every primary 12-quarter result uses seeds 0–2, run serially. Accepted pickles are unchanged; the FB experiment has a new filename and is not promoted. Report date is UTC; the Windows local date during much of the work was 24 October.\n')
    add('## Steps, commits, tests and gates\n')
    add(table(pd.DataFrame([
        ['1 F_CFC baseline','9cc1563','1 regression','Accepted data baseline; earlier margin gate remains failed'],
        ['2 Q','f0b6aee','3 propensity regressions','Q-G0 fails on all seeds; see full gate table'],
        ['3 E','d23d31e','5 servicing/foreclosure regressions','E empirical gate fails; accounting passes after two mechanical fixes'],
        ['3 rental PIT scope','f0fc613','1 rent-counterparty regression','Public rent excluded from private-landlord PIT base'],
        ['3 foreclosure occupancy','4ef8b68','1 occupancy regression','Third-party tenant cannot be overwritten without an executed move'],
        ['4 GDP bridge','c89ea09','3 valuation regressions','All 13 unchanged GDP checks fail; margin passes; 102 cost exceptions'],
        ['5 combined / B2 retest','none','not run','Dependencies fail; no tuning'],
        ['6 gates / report','final diagnostics commit','1 share-gate regression + full suite','Review packet only'],
    ],columns=['Step','Commit','Tests','Result'])))
    add('## Headline: shrinkage and an initial GDP scope error\n')
    add('The raw Q0→Q12 contraction contains a **64.132B t0 housing-memo addition**. `Economy.from_data` always adds real and imputed rent at initialization; `Country.update_realised_metrics` passes both as zero thereafter when `housing_services_in_household_io=True`. All three accepted inputs carry that flag. The t0 expenditure identity therefore adds housing already inside sector L, while later GDP uses the IO scope. This is a reporting/initialization inconsistency, not an unobserved economic shock. It is recorded, not removed by a cash, inventory or trade plug.\n')
    add('The scope-adjusted column subtracts that identified t0 duplicate **for diagnosis only**; it does not change the model, inputs or gates. PPI-deflated GDP is a proxy, not a chained-volume SNA measure. Consumption uses the model CPI and investment the CFPI. Raw nominal and deflated endpoint levels for every arm are in [headline endpoint levels](outputs/QE/headline_endpoint_levels.csv); employment is expanded persons, price level is nominal GDP divided by the PPI-deflated proxy.\n')
    add(table(summary))
    add('For F_CFC seed 0, raw nominal GDP is 772.215B at Q0 and 654.309B at Q12. The comparable t0 scope diagnostic is 708.084B; the Q1 PPI-deflated level is 704.885B and Q12 is 656.243B. A material contraction remains after allowing for the initialization artifact.\n')
    add('### Expenditure decomposition, Q0→Q12\n')
    dec=decomp.copy();dec['change_B']=dec.change_CAD/1e9
    pivot=dec.pivot(index=['arm','seed'],columns='component',values='change_B').reset_index().rename(columns={'expenditure_unallocated':'initial_housing_scope_change'})
    add(table(pivot))
    add('The table sums exactly to the model expenditure-GDP change. `initial_housing_scope_change` is −64.132B, not a new flow. C and I contract in the accepted firm baseline while G rises. The model also has an existing multi-country GDP routine that balances reported exports/imports against output GDP. Thus this is a descriptive accounting bridge; the X/M changes cannot all be interpreted as independently observed trade-demand responses. No new balancing trade flow was introduced here. Firm CFC changes alter replacement demand, costs and household income jointly; this round does not causally isolate those channels.\n')
    add('## Initial consumption distribution: inherited failure and Q\n')
    add('C, F and F_CFC all inherit the t0 distribution failure without a B2 wealth term. Seed 0 shares below; [all seeds, endpoints and raw annualised levels](outputs/QE/distribution_endpoints.csv) and [all quarters](outputs/QE/consumption_distribution.csv) are retained.\n')
    add('DHEA income-rank comparison, percent of total household consumption:\n\n'+table(d0))
    add('SHS before-tax household-income-rank comparison, percent:\n\n'+table(s0))
    add('Primary benchmark: [StatCan DHEA 36-10-0587-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610058701), 2022 HFCE vectors v116884012/035/058/081/104; disposable-income vectors **v116884005/028/051/074/097**. The source consumption/disposable-income ratios are '+', '.join(f'{v:.6f}' for v in source['ratios'])+'. Q interpolates linearly across household-weighted equivalised-income percentiles .1/.3/.5/.7/.9, clamps outside those midpoints, freezes initial propensities, and applies one national multiplier **1.097931**. Initial account C is 377.8455B/q, matching 36-10-0112 v62305982. F’s consumption function and floors are retained; Q has no B2 wealth term.\n')
    add('DHEA quintiles use OECD-modified equivalised household disposable income, household weights, adult/child factors 1/.5/.3. Model rank income is per-household cash DI divided by those units, with regional expansion factors removed. DHEA DI includes noncash/imputed items missing from the model proxy. Applying source ratios to a different income distribution **does not guarantee source consumption shares**: Q-G0 fails, rather than passing “by construction”. No quintile-specific second rescale or parameter tuning was applied.\n')
    add('DHEA target shares: 13.384/15.924/19.428/21.693/29.571%. Secondary [SHS 11-10-0223-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110022301), 2023 revised 2026-09-18, uses un-equivalised before-tax household-income quintiles and current-consumption mean vectors v54529951/993, v54530035/077/119. Its shares normalise equal-quintile published means (an approximation, because quintile household counts are not published). Owner-imputed rent and other national-account imputations differ from SHS scope; reference year and coverage also differ. Executed imputed housing services cannot be separated from the model L bundle, so no SHS-comparable subtraction is fabricated. Including owner-imputed rent tends to raise upper-quintile shares.\n')
    add('### Q gates, unchanged after measurement\n')
    cols=['seed','Q_G0','Q_G1','Q_G2','Q_G3','constrained_slope_pp','Q12_saving_pct','max_zero_goods_share','max_accounting_error']
    add(table(qg[cols]))
    add('Q-G0 is only the construction check, relative SHARE deviation ≤15%; it is not validation. Q-G1 tests positive-income zero-goods share strictly <2% at t0 and every quarter. Q-G2 tests Q12 relative shares. Q-G3 retains Gate B: constrained-share Q4–Q12 OLS slope ≤.25 percentage point/q, saving [−5.6%,4.4%], Q1 C≥95% of benchmark, accounting ≤1e−8. All gate details remain in [gates.csv](outputs/QE/gates.csv).\n')
    add('### Deposits-only sensitivity, read-only at t0\n')
    add(table(wealth))
    add('An SFS deposits-only buffer **is available**: recompute the same weighted decile/age medians using PWASTDEP alone, retaining survey weights, PEFATINC income, PAGEMIEG age and the existing family-to-household mapping. The broad definition uses the unchanged BE reference. At κ=.01/q, the aggregate hypothetical wealth term is 14.834% of C with deposits+nonpension OFA, versus 5.038% with deposits and its own SFS median buffer; holding the broad buffer fixed gives 3.726%. These are t0 sensitivity audits; neither wealth term enters Q. [SFS source/hash/method](benchmarks/QE/sfs_deposit_provenance.json).\n')
    add('## E: cash payments, arrears and foreclosure\n')
    add('E replaces the net-worth trigger and D3 only when selected. Scheduled payments are cash-constrained using deposits, current funded receipts, net deposit interest, new credit, executed property proceeds and existing non-pension assets, after rent/property obligations. Interest is paid first and principal second, pro rata by contract. Unpaid principal stays in the loan book; unpaid interest is a non-accrual memo, not bank income or capitalised credit. Uncured arrears persist. Monthly 30/60/90+ buckets are inferred from equally spaced due dates and cash available first within a quarter; the model does not observe monthly receipts. Negative net worth alone never defaults.\n')
    add('N=3 consecutive distressed quarters is the **unchanged, labelled assumption shared with firms** (roughly 7–9 months from first missed due date under the buckets). The 20% stress-sale discount is also a labelled assumption, with 10–30% illustrative uncertainty; it is not an estimated legal fee or Canadian foreclosure-cost rate. Neither was tuned. Existing non-pension financial assets fund service before residual unsecured principal is written off. Pensions stay protected. Initial arrears are unobserved and set to zero, so a zero Q1 write-off is partly a construction consequence, not independent validation.\n')
    add('Mortgaged properties enter the existing housing market at market value less the stated discount. **Only executed sales** repay principal; only the remaining shortfall after pooled collateral is disposed of is written off; surplus remains with the household. The property-to-loan link is missing, so mortgages use a pooled household collateral assumption. A dispossessed owner becomes a renter through the existing public-housing fallback. No buyer/vacant possession: retain the encumbering bank mortgage claim in a foreclosure queue, without REO cash or hypothetical recovery. Existing third-party tenants keep their homes until an executable move allows vacant possession. This holding treatment delays loss realization and is an explicit limitation. Mortgage insurance/guarantor claims are not added.\n')
    add('### E gates and benchmark scope\n')
    eg_table=eg[['seed','E_G1','E_G2','E_G3','annual_writeoff_pct','Q12_60plus_pct','Q12_90plus_pct','Q1_writeoffs','Q4_Q12_mean_writeoffs']].copy()
    for col in ['Q1_writeoffs','Q4_Q12_mean_writeoffs']:eg_table[col]/=1e9
    add(table(eg_table))
    add('E-G1 compares each reported Q1–Q12 arrears observation with factor-two bands and the 12-quarter annualised principal-loss ratio with [0.05%,0.28%]. No hidden warm-up is dropped. Arrears use pooled mortgage-borrower counts, whereas source account counts can include multiple mortgages per household. Annualised write-offs are total losses/3 divided by mean formal household debt over Q0–Q12. These scope limits prevent a claim of exact household-portfolio validation. E-G2 compares Q1 losses with twice Q4–Q12 mean; E-G3 is accounting.\n')
    add('| Benchmark | Verified value / scope | Source and provenance |\n|---|---|---|\n| TransUnion | Q3 2024 mortgage account 60+ DPD **0.25%**; not 90+ | [Mortgage Loan Summary, p12](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q3_24_ciir_report.pdf); direct PDF download returned 403, so the cached factual extract—not inaccessible PDF bytes—is hashed |\n| CBA | December 2022 **0.15%**, 7,740/5,106,262 mortgages; three or more months overdue | [Canada historical table](https://cba.ca/Assets/CanadianBankersAssociation/Documents/Articles/Statistics/stat-mortgages-arrears-november-2025-en.pdf), PDF p3; full PDF hash recorded |\n| RBC | 2022 **0.10%**, 2023 **0.14%** annual net write-off ratio, **consolidated all loans**, not household-only | [RBC 2023 annual report](https://www.rbc.com/investor-relations/_assets-custom/pdf/ar_2023_e.pdf), Table78; retained verified extraction/full PDF hash |\n')
    add('All source dates, vectors (or not-applicable labels), hashes, parameter assumptions and limitations: [credit benchmarks](benchmarks/QE/credit_benchmarks.json), [DHEA extraction](benchmarks/QE/provenance.json), and inherited [DHEA/SHS definitions](benchmarks/B2/distribution_provenance.json). The requested RBC range is retained as an imperfect order-of-magnitude gate; it is not falsely relabelled a household-only benchmark.\n')
    add('### Old rule versus E, by quarter\n')
    pretty=loss.copy()
    for col in pretty.columns[2:]:pretty[col]/=1e9
    add(table(pretty))
    add('### Bank-loss composition and recapitalisation totals, 12 quarters\n')
    pretty=totals.copy()
    for col in ['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation']:pretty[col]/=1e9
    add(table(pretty))
    add('C’s bank decomposition is a read-only serial replay, required to match its original macro paths and consumption distributions exactly; accounting is independently checked. Full quarterly components, capital ratios and resolution events are in the primary run folders and [quarterly.csv](outputs/QE/quarterly.csv); C’s components are in [C_bank_replays](outputs/QE/C_bank_replays). New E losses go through the same by-bank capital/resolution paths as the old rule.\n')
    add('Detailed E defaults, 30/60/90+ arrears, executed-sale recoveries, pending foreclosures, mortgage/unsecured losses and non-accrual interest are in [E_metrics.csv](outputs/QE/E_metrics.csv). Counts are expanded households; “foreclosure_sales” counts borrowers with a positive executed collateral repayment, not individual dwellings. Firm-default counts in the raw panels are model province/industry agents, not observed Canadian business insolvency counts.\n')
    add('### Rejected accounting attempt and mechanical corrections\n')
    add('The first E seed-0 12-quarter attempt is retained and **rejected** (maximum relative battery residual 1.4296e−4; rent-counterparty residual up to 5.762M). Foreclosure exposed two mechanical defects: public-housing rent was taxed as private-landlord rent when the household became tenure-status 3; sales could overwrite third-party tenants’ occupancy. The two isolated fixes above leave N/haircut unchanged. New `E_cashfix` inputs/configurations pass 2- and 4-quarter diagnostics before the accepted 12-quarter measurements. Old failed diagnostics are not spliced into the accepted results.\n')
    add('## Independent FB GDP/tax/output bridge\n')
    add('Accepted source: F_CFC. New experimental input: `io2022_household_f_cfc_qe_bridge_2026_10_25.pkl`; its SHA-256 and unchanged source hash are in [provenance](outputs/QE/bridge/provenance.json). Preserve financial stocks, debt, capital stocks and initial capital purchases. Zero-source producers are marked inactive holders; **no debt is forgiven**. The source is the cached provincial 2022 detailed SUT mapped to OECD50, with PRM100000–PRM800000 vectors and concordance/file hashes recorded.\n')
    add('National annual signed other-production taxes are **100.504B**, input-product taxes **26.546B**, and the cost-side row/column adjustment **48.338B**. Production at the source basic-price valuation equals cost-side output less basic intermediate use and the input-product valuation; income is compensation + GOS/mixed income + signed other production taxes. Final product taxes then give market-price GDP. Housing already inside L is excluded from an additional producer block in the SNA-scope diagnostic. The remaining expenditure excess is **74.883B/year**, decomposing into the row/column adjustment plus input-product valuation (rounding retained). It is not absorbed by a fictitious buyer, inventory or cash transfer.\n')
    add(table(actualbridge,digits=6))
    add('The bridge’s production/income residual is at most 0.000239B/q (source/mapping rounding), retained visibly. [Unchanged model initializer checks](outputs/QE/bridge/unchanged_GDP_checks.csv) fail in **all 13 regions**: Newfoundland output/expenditure ratio is 0.990609, improved from the older 0.929 prototype by preserving capital purchases and fiscal initial conditions, but still not one. The initializer also contains a pre-existing repeated output/expenditure assertion where its message says output/income; independent income ratios are therefore recorded rather than trusting that second check. No assertion or tolerance was changed.\n')
    add('Gross-margin residual passes at 0.000978 percentage point, but **102 active region/industry cells** have cost above price despite non-negative source GOS. GOS is gross of CFC: positive GOS alone does not guarantee a positive surplus after CFC and financing. The requested gate is applied unchanged; no depreciation or cost is removed to force it. [Cell-level bridge](outputs/QE/bridge/firm_bridge.csv) and [industry exceptions](outputs/QE/bridge/above_price_by_industry.csv) are retained. FB is unaccepted and not iterated; its accounting/dynamic gates cannot be passed. The consistent read-only GDP bridge does not manufacture a balanced runnable data set.\n')
    add('## Verification, limitations and recommendation\n')
    if tests is not None:
        add(f'Full `tests/` via `run_pre_D3_tests.py`: **{tests["passed"]} passed, {len(tests["failures"])} known failures, {tests["tests"]} cases**. The sampler uses one worker. Exact failure IDs are compared with the known 30 “Nan in transactor_total_real_supply” cases; no additional failures are accepted. [Full execution](outputs/QE/verification/full_test_execution.json). Focused regressions cover baseline selection, rank interpolation, share gates, cash servicing, foreclosure cash/occupancy, rental PIT and GDP valuation.\n')
    else:add('**DRAFT: the full suite is still running. No final pass/failure count is claimed.** Measurement/source/stock prechecks have passed; the final test audit remains pending.\n')
    add('**Not ready for Phase B.** Keep F_CFC as the accepted data baseline, retain Q and E as opt-in unvalidated candidates, and do not combine them. E removes the false net-worth default mechanism and initial loss spike, but its loss and arrears levels remain too high to call Canadian orders of magnitude plausible. Large firm losses, public recapitalisations and the failed IO/tax/cost reconciliation remain unresolved; reduced losses alone are not validation.\n')
    add('Next review decisions concern: reconciling cash versus DHEA imputed income before another distribution rule; applying the existing IO-housing scope consistently to GDP initialization/income reporting; resolving the observed IO row/column/product-valuation gap without a plug; specifying the treatment of genuinely negative net operating surplus versus the gross-GOS cost gate; and validating payment/default/foreclosure timing and pooled collateral against loan-level data. The default constant-propensity income feedback and remaining asset exhaustion still need attention; no buffer-stock parameter was tuned here. Initial bank funding/reserve boundaries and unmodelled mortgage insurance remain limitations.\n')
    add('All household consumption, disposable income, saving (against −0.6%), constraints, investment, asset drawdown and GDP paths: [household/GDP quarterly table](outputs/QE/household_and_GDP_paths_B_pct.csv). Gates, seeds, complete source hashes, protected-input checks and excluded attempts are in the evidence folder and final audit. No push; stop for review.\n')
    destination=HERE/('CLOSURE_QE_2026-10-25.md' if tests is not None else 'CLOSURE_QE_DRAFT_2026-10-25.md');destination.write_text('\n'.join(text),encoding='utf-8')
    if tests is None:
        print('Wrote draft; full tests still running',destination)
        return
    register=HERE/'ISSUE_REGISTER.md';old=register.read_text(encoding='utf-8');marker='<!-- QE-2026-10-25 -->'
    addition=f'''\n\n{marker}\n## QE review — 2026-10-25 UTC\n\n- Adopt F_CFC on accepted FE F lineage (9cc1563), P off; data improvement, not a margin-validation pass.\n- Q (f0b6aee) fails the DHEA-share construction gate on every seed. One common rescale and source C/DI ratios cannot reproduce DHEA shares on the different cash-income proxy. No tuning.\n- E (d23d31e), with rental-PIT fix f0fc613 and occupancy fix 4ef8b68, is accounting-consistent in the new measurements but fails empirical arrears/loss gate. Old net-worth rule remains selectable. Failed pre-fix attempt retained/excluded.\n- FB data experiment (c89ea09) fails all 13 unchanged GDP initialization checks and has 102 above-price/nonnegative-GOS cells, despite a 0.000978 pp gross-margin residual. No FB dynamics or combined Q+E+B2 run.\n- New GDP diagnostic: t0 adds 64.132B of rent memos already in household IO; dynamic GDP omits that block. Both raw Q0 changes and scope-adjusted/Q1 diagnostics are reported. No GDP/cash plug or initializer tolerance change.\n- Phase B and C_dp_005 stay on hold. Full suite: {tests['passed']} passed, {len(tests['failures'])} known failures; exact IDs audited.\n- [QE report](CLOSURE_QE_2026-10-25.md), [gates](outputs/QE/gates.csv), [audit](outputs/QE/audit.json).\n'''
    if marker in old:old=old[:old.index(marker)].rstrip()
    register.write_text(old+addition,encoding='utf-8')
    print('Wrote',destination)

if __name__=='__main__':main()
