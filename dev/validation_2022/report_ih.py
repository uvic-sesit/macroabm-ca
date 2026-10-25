"""Build the IH review report and a read-only IO pipeline handoff."""
from pathlib import Path
import json
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;OUT=HERE/'outputs/IH';DATE='2026-10-25'
def table(f):
    def cell(x):
        if isinstance(x,(float,np.floating)):return f'{x:.3f}' if np.isfinite(x) else ''
        return str(x).replace('|','/')
    return '| '+' | '.join(map(str,f.columns))+' |\n| '+' | '.join(['---']*len(f.columns))+' |\n'+'\n'.join('| '+' | '.join(cell(x) for x in r)+' |' for r in f.itertuples(index=False,name=None))
def load(n):return pd.read_csv(OUT/(n+'.csv'))
def main():
    q=load('quarterly');h=load('headline');ch=load('changes');g=load('gates');inv=load('investment_national');di=load('DHEA_DI_comparison');bridge=load('DHEA_component_bridge');cost=load('unit_cost_gates')
    final=OUT/'verification_final/full_test_execution.json';prior=OUT/'verification/full_test_execution.json';test=json.loads((final if final.exists() else prior).read_text())
    assert len(g)==33 and g[g.gate.isin(['H-G1','H-G2','E-G2','E-G3'])].passed.all()
    seed=ch[ch.metric=='gdp'][['arm','seed','Q0','Q1','Q12','Q0_Q12_pct','Q1_Q12_pct']].copy();seed[['Q0','Q1','Q12']]/=1e9
    real=ch[ch.metric=='gdp_PPI_deflated'][['arm','seed','Q0_Q12_pct','Q1_Q12_pct']].rename(columns={'Q0_Q12_pct':'PPI_proxy_Q0_Q12_pct','Q1_Q12_pct':'PPI_proxy_Q1_Q12_pct'});seed=seed.merge(real,on=['arm','seed'])
    totals=q.groupby(['arm','seed'])[['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation']].sum().div(1e9).reset_index().rename(columns={'overdraft_losses':'firm_overdraft_losses'})
    e=g[g.gate=='E-G1'][['arm','seed','value','Q12_60plus_pct','Q12_90plus_pct','passed']].rename(columns={'value':'annual_HH_writeoff_pct'})
    cure=[]
    for (arm,s),z in h[h.arm.isin(['E','E2'])].groupby(['arm','seed']):
        def ratio(a,b):return 100*z[a].sum()/z[b].sum() if z[b].sum() else np.nan
        cure.append(dict(arm=arm,seed=s,mortgage_cure_pct=ratio('mortgage_cures','mortgage_prior_arrears'),consumer_cure_pct=ratio('consumer_cures','consumer_prior_arrears'),roll_30_60_pct=ratio('mortgage_30_to_60','mortgage_30_exposed'),roll_60_90_pct=ratio('mortgage_60_to_90','mortgage_60_exposed'),partial_catchup_household_quarters=z.get('partial_catchup',pd.Series(dtype=float)).sum(),restructurings=0))
    pd.DataFrame(cure).to_csv(OUT/'cure_and_roll_rates.csv',index=False)
    endpoints=q[(q.arm=='F_CFC')&q.quarter.isin([1,12])][['seed','quarter','consumption','cash_DI','cash_saving_rate','constrained_share','investment','asset_liquidation','investment_cut','consumption_cut']].copy();money=['consumption','cash_DI','investment','asset_liquidation','investment_cut','consumption_cut'];endpoints[money]/=1e9;endpoints[['cash_saving_rate','constrained_share']]*=100
    dq=di[(di.seed==0)&(di.quarter==0)].copy();dq[['model_DI_share','DHEA_DI_share','nonpositive_DI_share','negative_DI_share']]*=100
    b=bridge[(bridge.seed==0)&(bridge.quarter==0)&(bridge.quintile==1)][['model_line','model_annual_B','DHEA_annual_B','gap_B','vector']]
    plan=inv[(inv.arm=='F_CFC')&(inv.seed==0)][['quarter','replacement_planned','stock_adjustment_and_clipping','credit_cut','realised','CFC','net_investment','hold_initial_net_accounting']].copy();plan.iloc[:,1:]/=1e9
    fyear=load('observed_investment_totals_MCAD_annual') if False else pd.read_csv(OUT/'observed_investment_totals_MCAD_annual.csv');fyear.iloc[:,1:]/=1000
    compare=load('initial_investment_observed_comparison');compare=compare.groupby('industry_code')[['allocated_observed_investment','allocated_observed_CFC','model_initial_investment','new_CFC','observed_mapped_net_investment','initial_model_net']].sum().mul(4/1e9).reset_index()
    compare.to_csv(OUT/'initial_investment_industry_annual_B.csv',index=False)
    contraction=load('GDP_decomposition');contraction=contraction[contraction.arm=='F_CFC'].copy();contraction.delta_CAD/=1e9;contraction.share_GDP_change*=100
    # Exact descriptive cash-C bridge and observed wage/employment changes.
    inc=load('income_quintiles');consumption=[];wage_rows=[]
    for (arm,seedno),z in inc.groupby(['arm','seed']):
        a=z.groupby('quarter').sum(numeric_only=True)
        for t,r in a.iterrows():
            row=dict(arm=arm,seed=seedno,quarter=t,DI=r.DI,C=r.consumption,cash_saving=r.DI-r.consumption,wages_net=r.wages_net,mixed_net=r.mixed_net,property_net=r.dividends_net+r.rent_net,transfers=r.government_transfers+r.corporate_transfers_net,net_interest=r.net_interest)
            row['DI_residual']=row['DI']-(row['wages_net']+row['mixed_net']+row['property_net']+row['transfers']-row['net_interest'])
            consumption.append(row)
        hi=h[(h.arm==arm)&(h.seed==seedno)].set_index('quarter');fi=inv[(inv.arm==arm)&(inv.seed==seedno)].set_index('quarter')
        for t in range(13):
            W=fi.loc[t,'wages'];W0=fi.loc[0,'wages'];E=hi.loc[t,'employment'];E0=hi.loc[0,'employment']
            wage_rows.append(dict(arm=arm,seed=seedno,quarter=t,firm_compensation=W,employment=E,workers_effect=(E-E0)*W0/E0,wage_composition_effect=E*(W/E-W0/E0),GDP_C_price_effect=hi.loc[t,'C']-hi.loc[t,'C_CPI_deflated'],GDP_C_quantity_effect=hi.loc[t,'C_CPI_deflated']-hi.loc[0,'C']))
    pd.DataFrame(consumption).to_csv(OUT/'consumption_cash_bridge.csv',index=False);pd.DataFrame(wage_rows).to_csv(OUT/'wage_employment_price_bridge.csv',index=False)
    wc=pd.DataFrame(wage_rows);wc=wc[(wc.arm=='F_CFC')&wc.quarter.isin([0,12])].copy();wc[['firm_compensation','workers_effect','wage_composition_effect','GDP_C_price_effect','GDP_C_quantity_effect']]/=1e9;wc.employment/=1e6
    national_income=bridge[(bridge.seed==0)&(bridge.quarter==0)].groupby('model_line')[['model_annual_B','DHEA_annual_B','gap_B']].sum().reset_index()
    national_income.to_csv(OUT/'DHEA_national_cash_bridge_B.csv',index=False)
    bottom_shares=b[['model_line','model_annual_B','DHEA_annual_B']].merge(national_income,on='model_line',suffixes=('_bottom','_national'))
    bottom_shares['model_bottom_share_pct']=100*bottom_shares.model_annual_B_bottom/bottom_shares.model_annual_B_national;bottom_shares['DHEA_bottom_share_pct']=100*bottom_shares.DHEA_annual_B_bottom/bottom_shares.DHEA_annual_B_national
    entrants=pd.read_csv(OUT/'arrears_entrants_corrected.csv')
    entrant_summary=entrants.groupby(['seed','trigger']).households.sum().unstack(fill_value=0).reset_index();entrant_summary['confirmed_rate_reset']=0
    entrant_decile=entrants[(entrants.seed==0)&(entrants.kind=='mortgage')].groupby(['decile','tenure']).households.sum().unstack(fill_value=0).reset_index()
    losses=pd.read_csv(OUT/'E2_loss_quarterly.csv')[['seed','quarter','mortgage_writeoffs','formal_unsecured_writeoffs','household_overdraft_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','min_capital_ratio']].copy()
    for key in ['mortgage_writeoffs','formal_unsecured_writeoffs','household_overdraft_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation']:losses[key]/=1e9
    report=f'''# Household closure IH review — {DATE} (UTC)

Review baseline: `51f0615`; accepted configuration remains **F_CFC**. Q and E/E2 are opt-in. No investment or household-income rule was changed. No accepted pickle, original model repository, ITC experiment, or IO pipeline was modified; no push. Phase B and C_dp_005 remain on hold.

## Decisions and gates

| Step | Change / finding | Commit / validation | Gate / decision |
|---|---|---|---|
| 1 Housing GDP | Remove duplicate IO-contained real/imputed rent at t0; scope public rental income and debug addends consistently; retain cash rent memos | `c1712b7`, `3557989`; two housing regression tests; three F_CFC and three E exact-path comparisons | H-G1/H-G2 pass on all applicable seeds. Initial GDP decreases 64.131664B. |
| 2 Investment | Read-only ledger identifies replacement-only dynamics **and an inherited investment allocation proxy**, rather than an observed-GFCF initial anchor | `04fb61e`, `57f16c9`; per-industry/province investment ledger and exact decomposition | Specification decision required; no rule change. Independent steps completed. |
| 3 Income distribution | Cash DI is substantially more concentrated than DHEA, with income concepts and allocation both contributing | `04fb61e`, `57f16c9`; exact income reconstruction, benchmark vectors in companion CSV | No fix; decide the income bridge and allocation before fitting consumption shares. |
| 4 E2 cure | Full cure already existed; partial catch-up now freezes the bucket and distress clock when current service is covered and old arrears shrink | `15fcb37`; two cure regressions, 2Q then 12Q seeds 0–2, N=3 and discount=20% unchanged | E-G1 fails every seed; E-G2 and accounting pass. E2 remains opt-in and unvalidated. |
| 5 Net-surplus cost gate | F_CFC fails; unaccepted FB passes the revised cost criterion | `04fb61e`; net-surplus regression, exception CSVs | FB's separate GDP/SUT failure remains; do not promote it. |
| 6 Review | All independent work completed; no tuning | Full one-worker suite below; protected hashes and run manifests audited | Stop for review. |

Diagnostic scripts and gates live in `ih_diagnostics.py`, `prepare_ih.py`, `ih_observed_investment.py`, `summarise_ih.py`; measurement implementation was committed separately from model changes. The subsequent arrears-attribution correction is read-only, regression tested, and replayed against the original E economic paths.

## 1. Housing scope and corrected contraction

IO-contained housing contributes **zero additional rent** to each GDP approach at t0 and dynamically. Rent paid, imputed rent and rent received remain intact in cash/market ledgers. Paid and imputed rents have explicitly named report memo columns. No trade, inventory or cash entry was introduced. The residual in expenditure component changes is below one dollar nationally; the Q0 to Q12 decomposition contains no `initial_housing_scope_change` term.

A code search found no agent behaviour reading the GDP, national C or national I reporting series. Growth expectations use historic **gross-output growth** and exogenous observations (`economy/economy.py:439–448`), rather than GDP; firm targets use firm-specific demand/production histories. Household propensity calibration uses household incomes and its explicit benchmark, rather than economy-level t0 C. Initial economy C/I continue to precede closure reanchoring; that surviving timing distinction is documented, not silently reanchored. Exact `outcomes.csv`, non-GDP headline series and Q1–Q12 GDP match the previous F_CFC/E runs on every seed (`behaviour_comparison.csv`). The changes in GDP growth reporting denominators are intentional reporting effects.

Nominal levels in B; PPI-deflated GDP is an indicative proxy, **not** SNA chained real GDP:

{table(seed)}

The reporting correction removes an exaggerated initial contraction. It does not eliminate the model's no-shock contraction or explain seed divergence.

## 2. Investment diagnosis — no rule change

For firm i and capital input j, the active rule is:

- Expected demand extrapolates smoothed previous demand with macro and firm growth expectations (`agents/firms/func/demand_estimator.py:120` onward). Desired output adds inventory-buffer adjustments (`func/target_production.py:267`).
- Capital-plan reference output q^K is clamped toward available labour, intermediate inputs and capital capacity (`firms.py:709–738`; `func/target_production.py:364–379`). The shipped capital-capacity weight is 1; fully utilised initial capacity and capacity-capped excess demand are the previously documented F-S1/F-S3 lock.
- Raw replacement R_ij = q^K_i × delta_ji (`func/target_capital_inputs.py:339`). Unconstrained purchases U_ij = max(0, R_ij - lambda × (K_ij - Kref_ij)) (`:371–386`). The accepted lambda is **0**, so there is no independent expansion or positive net-investment term. The default base-year reference is K0 × q_previous/q0; forward-looking and rolling alternatives exist but are off (`:104–207`). ITC/user-cost switches are inactive and untouched.
- Finance-adjusted plan T_ij = max(0, U_ij - gamma × (credit_target - credit_received)/[(1+expected_inflation) × lagged_price_j]) (`:438–444`). Gamma is **0** in the accepted configuration. This particular financing cut is zero, even where requested credit is unmet; financing can still affect other targets and payment distress. The ledger keeps requested/received long credit separately.
- Actual capital goods are allocated from executed goods purchases (`firms.py:1369–1377`), then valued and assigned actual nominal expenditure (`:1390–1434`). Therefore plan less nominal actual is a **clearing/price residual**, not all credit rationing. Realised CFC is valued on actual output; replacement planning uses reference output and lagged prices.

**Correction to the starting hypothesis:** initial firm purchases were explicitly frozen from the previous used-capital/depreciation proxy by `build_firm_cfc_b2.py:83–86`. They are not an independently observed 2022 GFCF series. Their annual total is **398.886B**, while the observed-CFC charge is **377.244B**. The resulting t0 model net investment of **21.642B/year** cannot be treated as an observed growth target.

Observed annual 2022 current-price non-residential capital flows, StatCan **36-10-0096-01**, including the business residual that excludes government and NPISH:

{table(fyear)}

Direct Canada vectors: total investment/CFC **v90968052/v90968082**; government **v90970252/v90970282**; NPISH **v90970012/v90970042**. The business residual is derived from those three source series, with no independent invented vector.

The national model includes O/P/Q and financial/other producers, so it is not a private-business-only GFCF series. Its t0 O/P/Q purchases are only **29.084B/year**, versus CFC **95.548B/year**; other model industries purchase **369.802B/year**, versus CFC **281.696B/year**. Those groupings do not exactly equal institutional government/business sectors. They show that a close national aggregate conceals a large allocation discrepancy. No part of this discrepancy was repaired or rescaled.

The read-only provincial/industry concordance reuses the accepted CFC source grouping and fixed output shares. It maps investment to **412.999B/year**, **1.658B above** the direct Canada total; provincial/national fallback and concordance differences remain visible. This diagnostic mapping is not a balanced new investment calibration. Its row-level vectors and fallback labels are in `observed_investment_concordance.csv`; the direct Canada totals above are the primary benchmark. Mapped observed net investment uses mapped **source CFC**, separately from CFC actually charged by the model. Before/after concept comparisons are in `initial_investment_observed_comparison.csv` (industry × province) and `initial_investment_industry_annual_B.csv`.

Seed 0, B/quarter. At Q0 the “stock adjustment” column is the inherited acquisition-minus-CFC difference, not an executed behavioural expansion calculation:

{table(plan)}

All seeds have zero active stock-gap expansion and zero direct credit-plan cut. Their Q12 firm purchases are **88.881/85.133/72.144B**, compared with 99.721B at t0. Household investment falls as well and must not be folded into the firm-rule attribution. All industry × province × quarter observations, prices/clearing residuals and financing quantities are retained in `investment_industry_province.csv`.

The counterfactual column holds **each cell's initial nominal net investment**, including negative values: I_accounting(t)=CFC_actual(t)+(I0-CFC0). This is an accounting replacement of one line; actual output, prices, wages, financing and clearing are held at their observed run values. It is **not** a feasible investment policy, causal GDP simulation, or forecast; negative cell values are not clipped to conceal scope problems.

### Consumption and descriptive GDP attribution

Household-account C includes VAT and actual rent; GDP's IO C has its own housing scope. At Q1/Q12, B/quarter and percentages:

{table(endpoints)}

The wage/price bridge (compensation and contributions in B; employment in millions):

{table(wc[['seed','quarter','firm_compensation','employment','workers_effect','wage_composition_effect','GDP_C_price_effect','GDP_C_quantity_effect']])}

The wage-bill change splits exactly into a worker-count term at the initial average bill and a wage/composition term at current workers. The nominal GDP-C change splits into its CPI-deflated quantity change and price term at the regional indices; these are diagnostic index calculations. `consumption_cash_bridge.csv` gives every quarter's exact identity C = net wages + mixed income + property receipts + transfers - net interest - cash saving. It separates the transfer and saving contributions without treating them as an identified investment multiplier.

`income_quintiles.csv` contains every quarter's wage income, transfers, mixed/property receipts, taxes, net interest, C and financial assets. Together with `headline.csv` employment and CPI and `quarterly.csv` spending cuts, it decomposes nominal income/spending changes without claiming an identified causal multiplier. Planned consumption can exceed receipts while assets run down; binding budgets and falling earned income then reduce realised C. CPI-deflated C and employment are in `changes.csv`; prices are separated from nominal expenditure. Transfers include automatic benefits and firm-funded D2 receipts, so they cannot all be interpreted as exogenous stabilisers.

Signed contribution to Q0 to Q12 nominal GDP change, B and percent of that change (negative percentages offset the contraction):

{table(contraction[['seed','component','delta_CAD','share_GDP_change']])}

Direct total investment decline accounts descriptively for **70.3%, 61.3%, 45.8%** of the GDP decline; C accounts for **86.4%, 59.8%, 54.7%**, with the other components offsetting or adding to them. These shares are not an estimate that investment *caused* the consumption fall. Establishing that feedback requires an approved structural counterfactual. The legacy GDP routine balances reported X/M to output GDP; those trade entries are not independently identified feedback effects.

**Investment options for decision (none implemented):** (1) reconcile observed GFCF by industry/province and institution, explicitly distinguishing source CFC from net additions, then decide a transitional or exogenous net-additions path; this fixes the data anchor but does not create an endogenous expansion mechanism. (2) introduce a growth/expectations-consistent desired-capital term, tied to *unclamped* demand and a defensible utilisation target, alongside correcting the F-S1/F-S3 censored-demand lock. Merely raising a stock-gap weight with capacity-clamped demand cannot reliably unlock growth; the existing forward-looking/rolling-reference options must be tested jointly with the signal. (3) use a stock-adjustment plan around desired capacity with explicit order/backlog expectations and financing, replacing the output-proportional replacement shortcut. Options 2/3 need stability and shock-response checks; no parameters should be chosen to make these gates pass.

## 3. Household income distribution vs DHEA — no fix

Rank is national, household-weighted cash DI per actual household divided by OECD-modified units (1 for first adult, .5 additional age 14+, .3 under 14), exactly the G3 ranking. Quintile totals and shares are **unequivalised household DI** after ranking, and per-household annual amounts use expanded household counts. This is a cash proxy, whereas DHEA allocates SNA DI, including noncash concepts. It is not the SHS before-tax-income ranking.

DHEA table **36-10-0587-01**, 2022 DI vectors **v116884005/028/051/074/097**. Seed 0 initial levels (shares in %, per-HH in CAD/year):

{table(dq[['quintile','model_DI_share','DHEA_DI_share','model_per_HH','DHEA_per_HH','nonpositive_DI_share','negative_DI_share']])}

Other seeds and Q12 are in `DHEA_DI_comparison.csv`. The model represents **15.49732M households**, while DHEA's published totals/per-household means imply about **16.24M** (rounded source means). That denominator gap matters for levels; it cannot explain the large share differences. Only about **0.387% of bottom-quintile households** have nonpositive initial cash DI; the rest of the initial quintiles have none. The bottom shortfall is broader than zero-income records. The optional weighted mean of per-household equivalised DI is retained only as a model statistic; it is **not** compared to DHEA “value per consumption unit,” which divides the aggregate by aggregate units (metadata footnote 10).

Bottom-quintile component bridge, B/year. Gross wages exclude employer contributions; property receipts exclude deposit interest, which is netted in the interest-paid line. Taxes/contributions are the model PIT and employee SSC. Those scope differences are explicit:

{table(b)}

The model lines reconstruct DI exactly (rounding residual under one cent at quintile level). Current transfers combine government benefits/pensions and grossed-up corporate transfers, with the benchmark counted once. Separate government transfers are **40.099B**, against DHEA's broader current receipts **83.095B**; corporate receipts add **5.586B**. Thus combined transfers have the largest negative bottom-quintile line gap (**37.410B**), followed by labour (**24.211B**) and mixed income (**16.237B**). Lower model taxes/contributions and net interest offset part of those gaps. This is a concept-aware decomposition, not proof that every gap is an error to be filled with cash.

National component totals, B/year:

{table(national_income)}

Bottom quintile's shares of each national component:

{table(bottom_shares[['model_line','model_bottom_share_pct','DHEA_bottom_share_pct']])}

National cash DI is 1,468.386B versus DHEA 1,502.343B, a 2.26% shortfall, while bottom DI is 45% short. Large gross receipt and deduction concept gaps offset nationally; the disproportionate bottom gaps in wages, mixed income and transfers establish an allocation problem in addition to missing concepts. Adding the national gross-income gaps as cash while omitting their pension/tax/noncash counterparts would be an unjustified closure change.

Mapping: model gross wages correspond to part of DHEA compensation, without employer pension/social contributions; nonrental mixed income corresponds to only part of DHEA net mixed income, which includes owner-occupied dwelling services; cash dividends/rent and net deposit interest correspond to portions of DHEA property receipts/payments, without the full pension/insurance/imputed attribution; government and corporate transfers correspond to current transfers, with different pension and institutional coverage. DHEA taxes/social contributions include noncash and employer-related entries absent from the model's cash deduction. STiK is **not** added to DI (it belongs to adjusted DI). The initial financial-asset-income proxy is removed in favour of funded D2 receipts, as in the accepted configuration.

Source allocation is also material: the adapter first uses CIS-decile income shares (`macro_data/readers/population_data/canadianized_household_adapter.py:96–106`); pension/social-transfer weights are subsequently fitted and nationally rescaled (`synthetic_population/hfcs_synthetic_population.py:705–723`); matched individual jobs determine wages; D2 distributions depend on its allocation weights. None is a DHEA component-by-component allocation. Since the mismatch exists at t0, it cannot be attributed to subsequent firm failures alone. The gross wage/transfer gaps require an allocation/data-boundary audit; missing imputed housing and pension concepts require a conceptual bridge, not an invented payment.

**Income options:** build matched cash/SNA accounts first, including employer/pension contributions and imputed housing as noncash memo counterparts; then audit CIS/benefit/job allocation against a consistent after-tax household-income distribution. Alternatively retain a deliberately cash-only household model and use cash-comparable distribution targets after documented exclusions. Do not infer spending propensities from unmatched DHEA C/DI ratios or add transfers just to reproduce consumption shares. No income or spending specification was changed here.

## 4. E2 cure and remaining defaults

E already returned a household to current when the entire scheduled service plus old arrears was paid. The premise that cure was impossible was therefore incorrect. E2 adds one opt-in assumption: when the current schedule is fully covered and outstanding old arrears decline, preserve the current bucket and consecutive-distress clock; full settlement resets both; otherwise age as before. There is no forgiveness, no new term extension, and **zero restructurings**. Full current payment without positive catch-up does not freeze ageing. N=3 and the 20% foreclosure discount are unchanged. Household overdraft relief keeps its existing negative-deposit distress rule; the added 30/60/90 catch-up treatment concerns formal loan arrears.

Canadian [CMHC mortgage guidance](https://www.cmhc-schl.gc.ca/professionals/industry-innovation-and-leadership/industry-expertise/resources-for-mortgage-professionals/i-cant-pay-my-mortgage) discusses alternative payment arrangements; [FCAC debt guidance](https://www.canada.ca/en/financial-consumer-agency/services/debt/paying-debt.html) discusses repayment schedules and past-due accounts. These support considering cure/workouts, **not** the numerical quarterly bucket-freeze assumption. Source dates, factual-extract hashes and the direct CMHC 403 limitation are recorded in `benchmarks/IH/cure_assumption.json`; no full-webpage hash is claimed. The rule is a labelled diagnostic assumption, not a fitted Canadian cure estimate.

The initial entrant classification incorrectly treated a rising stock interest/principal ratio as a rate reset. Amortisation can raise that ratio with no reset; the current loan implementation does not reset existing contracts. That diagnostic was rejected and replaced with a tested classification and exact-path E replays (`entrant_replay_proof.json`). Main entrant counts use those corrected replays. No model payment rule changed for this correction. Trigger labels are a descriptive priority hierarchy: unable to cover initial senior service from initial deposits/receipts/liquid assets; then current DI below initial DI; then initially planned C above DI; then other. Separate overlapping flags are retained. An income decline flag does not prove that the decline alone caused failure; any-decline classification is stated explicitly. Confirmed existing-contract reset entrants are zero; changing new-loan mix is not a reset.

`arrears_entrants_corrected.csv` reports entrants by seed, quarter, formal debt type, initial equivalised-DI decile and tenure; these are loan-type entry events, **not unique people over 12 quarters**. Mortgage/consumer co-entry can count a household twice. Initial-data inability, persistent planned dissaving and income losses must therefore not be compared as independent causal experiments.

Corrected entrant events over 12 quarters (expanded household counts):

{table(entrant_summary)}

Seed 0 mortgage entrants by initial equivalised-income decile and tenure code (1 owner, 3 renter; other codes retained as observed housing states). Other seeds and debt types are in the companion CSV:

{table(entrant_decile)}

Arrears/write-off benchmark gate:

{table(e)}

Frozen benchmark sources: [RBC Annual Report 2023](https://www.rbc.com/investor-relations/_assets-custom/pdf/ar_2023_e.pdf), [TransUnion Q3 2024](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q3_24_ciir_report.pdf), and [CBA monthly arrears table](https://cba.ca/Assets/CanadianBankersAssociation/Documents/Articles/Statistics/stat-mortgages-arrears-november-2025-en.pdf).

The annual household net-write-off diagnostic divides total 12-quarter household losses by three and by average formal debt plus household overdrafts (13 stock dates). RBC's 0.10–0.14% is **all consolidated bank loans**, not household-only Canadian losses; its factor-two band is .05–.28%. [TransUnion Q3 2024](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q3_24_ciir_report.pdf)'s mortgage account 60+ Q3 2024 benchmark is .25% (band .125–.50%); [CBA December 2022](https://cba.ca/Assets/CanadianBankersAssociation/Documents/Articles/Statistics/stat-mortgages-arrears-november-2025-en.pdf) 90+ is .15% (band .075–.30%). These different dates and scopes remain limitations, not calibration targets. E-G1 applies the inherited quarterly arrears bounds and annual loss band; all seeds fail. Initial arrears start at zero, so Q1 has no write-off by construction under N=3; passing E-G2 is not validation of initial arrears prevalence.

Cash cures and mortgage roll rates, summed event exposures over 12 quarters:

{table(pd.DataFrame(cure))}

Cure numerators are captured immediately after servicing, **before** default/foreclosure can zero an arrears record. Thus write-off is not miscounted as cure. The buckets infer monthly due dates from quarterly cash and can jump directly beyond 90; 30 to 60 and 60 to 90 report crossing of the threshold at the next quarterly observation, not a monthly transition probability. Partial-catch-up counts are household × loan-type × quarter events.

### Household and bank loss composition

B over 12 quarters; household losses include formal unsecured, mortgage shortfalls and household overdrafts. The separate firm-overdraft column is **not** an extra household loss:

{table(totals)}

E2 quarterly composition, B (the `overdraft_losses` column below is firm OD; household OD is separate):

{table(losses)}

`E2_loss_quarterly.csv` contains every quarter and seed's mortgage loss, formal unsecured loss, household OD relief, firm loan/OD loss, bank total, recapitalisation, recoveries, defaults and foreclosure sales. `resolution_log.csv` retains each bank/quarter event and recapitalisation; `quarterly.csv` and raw bank files retain minimum capital ratios. Household unsecured figures in the raw headline include OD relief; the derived file subtracts it to report formal unsecured losses separately. No loan-vintage loss-share result is claimed: the inherited vintage hook observes the automatic-servicing path and is not validated for E/E2.

The cure amendment changes timing and some macro paths but does not bring loss levels close to the comparison bands. It produces small differences between 60+ and 90+ at Q12; it does not solve the distribution/spending problem or the remaining firm losses. No further cure/default parameter was tuned after failure.

## 5. Net-surplus gate and IO handoff

The corrected comparison is 100 × [(p-unit_cost_including_CFC)/p - (IO GOS-observed CFC)/output], with tolerance 1 pp. An above-price cost is permitted when observed NOS is negative. Zero-output rows are reported separately and are not divided by zero; IO comparison uses the mapped source GOS, rather than mistaking gross for net surplus.

{table(cost.drop(columns=['source_sha256']))}

Every exception, including its industry/province, price, cost, output, source GOS/CFC and signed margin gap, is in `F_CFC_net_margin_gate.csv` and `FB_unaccepted_net_margin_gate.csv`. The FB cost criterion now passes; its **74.883B/year expenditure imbalance and failed regional GDP construction checks remain unresolved**. This does not promote or modify FB. See `IO_HANDOFF_{DATE}.md` for the independent pipeline handoff; the pipeline was not changed.

## Provenance, verification and recommendation

Benchmarks: `benchmarks/IH/provenance.json`, exact selected source rows and vectors in `DHEA_components_2022.csv` and `nonres_investment_CFC_2022.csv`; inherited raw retrieval dates and full-file hashes are retained. The DHEA source was retrieved 2026-10-24; investment/CFC source was retrieved 2026-10-24. Canadian credit benchmark URLs, dates, account-versus-balance definitions and hashes remain frozen in `benchmarks/QE/credit_benchmarks.json`. Inputs and accepted pickle hashes are checked in `outputs/IH/audit.json`. Monetary tables use B CAD unless stated; runs and report date use UTC, rather than implying the user's local calendar date.

Full suite via `run_pre_D3_tests.py`, sampler **one worker**: **{test['passed']} passed, {len(test['failures'])} failures, {test['tests']} cases**, {test['seconds']:.1f}s. Every failure is a known `Nan in transactor_total_real_supply` case; zero additional failures. Final results are in `{('verification_final' if final.exists() else 'verification')}/full_test_execution.json`. All primary runs pass the 1e-8 accounting battery. Rejected diagnostic classifications and superseded extracts remain identified rather than silently overwritten.

Recommendation: retain the housing reporting fix. Keep F_CFC as the accepted **diagnostic baseline**, not a validated equilibrium. Do not promote E2 or FB and do not start Phase B. Prioritise the observed-GFCF allocation and expansion specification jointly with the cash/SNA income bridge. The buffer-stock household rule remains an option for an explicit user decision after that reconciliation. Cure alone does not make household losses, firm losses or recapitalisations plausible. Stop here for review; no investment or income change, Phase B run, or C_dp_005 port has been started.
'''
    (HERE/f'CLOSURE_IH_{DATE}.md').write_text(report,encoding='utf-8')
    io=json.loads((HERE/'outputs/QE/bridge/provenance.json').read_text());t=pd.read_csv(HERE/'outputs/QE/bridge/GDP_bridge.csv');tax=t[['input_product_tax','other_production_tax','row_column_adjustment','expenditure_residual']].sum()*4/1e9
    handoff=f'''# IO pipeline handoff — {DATE} (UTC)

Read-only handoff from `macroabm-ca-validation/feature/validation-2022`. The `macroabm-io2022` pipeline, accepted input files and original model repository were not modified. FB remains an unaccepted experiment. Passing its revised **net**-surplus cost gate does not repair the independent GDP imbalance.

## Outstanding national 2022 valuation bridge

| Item | B CAD/year | Treatment needed |
|---|---:|---|
| Sales row/column adjustment | {tax.row_column_adjustment:.6f} | Identify and reconcile actual product/industry supply-use transactions; do not invent buyers. |
| Input-product taxes less subsidies | {tax.input_product_tax:.6f} | Reconcile purchaser/basic valuation and tax allocation across intermediate/final uses. They are not other taxes on production. |
| Expenditure excess | {tax.expenditure_residual:.6f} | The two preceding items sum, up to rounding, to this unresolved excess. No cash, trade or inventory plug is approved. |
| Other taxes less subsidies on production | {tax.other_production_tax:.6f} | Preserve signed taxes/subsidies in the income/value-added bridge; do not confuse with product taxes or force positive NOS. |

Source: 2022 provincial detailed SUT, StatCan **36-10-0478**, mapped to OECD50. Canonical vectors PRM100000/200000/300000/400000/500000/600000/700000/800000; exact source metadata retained in `outputs/QE/bridge/provenance.json`, checked {io['checked_UTC']}.

Source hashes (read-only):

'''+''.join(f'- `{Path(k).name}`: `{v}`\n' for k,v in io['source_files'].items())+f'''
The accepted F_CFC pickle SHA256 is `{io['source_sha256']}`; unaccepted FB SHA256 `{io['new_pickle_sha256']}`. Source GOS is gross; the corrected cost test subtracts observed CFC. FB passes that revised criterion (maximum gap under .001 pp, zero above-price/nonnegative-NOS exceptions). F_CFC does not. Do not repeat the rejected gross-GOS criterion.

## A balanced SUT needs

1. A province/product/industry reconciliation of basic-price output and intermediate uses with final C, government consumption, GFCF, inventories, exports and imports, on a common annual reference and institutional/housing scope.
2. Explicit purchaser-to-basic-price bridges for trade/transport margins, product taxes/subsidies and import valuation, with taxes allocated to their actual uses. Preserve separate signed other-production taxes in GVA/income.
3. A documented treatment of the 48.338B row/column adjustment: reconcile its sources rather than moving it into fictional sales, profits, cash, inventory or trade.
4. Source-zero industries should not become operating producers through positive placeholders. Inactive holders retain outstanding financial obligations and capital; no debt forgiveness is implied by zero source output.
5. Initial investment must be benchmarked independently: current F_CFC t0 acquisitions retain a **depreciation proxy**, not observed GFCF. Reconcile private business, government, NPISH and household/dwelling scopes, and actual capital formation versus CFC. The IH read-only mapping residual of 1.658B/year must also remain visible.
6. Validate all 13 regional supply-use, production/income and expenditure identities independently, then the national sum. The legacy initializer's second output/income assertion repeats the output/expenditure operands; passing that repeated check is not independent income validation.

The IH housing correction removes the extra 64.132B/quarter t0 housing memo from GDP when sector L already contains housing services. It does not provide additional supply-use transactions or cure the 74.883B/year imbalance. Cash rent remains in household/landlord ledgers. No pipeline implementation or additional build is authorised by this handoff.
'''
    (HERE/f'IO_HANDOFF_{DATE}.md').write_text(handoff,encoding='utf-8')
    print('Reports written; final suite:',final.exists())
if __name__=='__main__':main()
