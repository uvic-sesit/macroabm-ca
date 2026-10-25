"""Generate the B2 review report from unrounded measurements; no refitting."""
import json
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent
OUT=HERE/'outputs/B2'

def table(df):
    def fmt(v):
        return f'{v:,.3f}' if isinstance(v,float) else str(v)
    return '| '+' | '.join(map(str,df.columns))+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+'\n'.join('| '+' | '.join(fmt(v) for v in r)+' |' for r in df.itertuples(index=False,name=None))+'\n'

def main():
    gates=pd.read_csv(OUT/'gates.csv');base=gates.query("variant=='base'")
    benchmark=json.loads((HERE/'benchmarks/B2/distribution_provenance.json').read_text())
    dhea_rows=pd.read_csv(HERE/'benchmarks/B2/dhea_hfce_2022.csv')
    source_order=['Lowest income quintile','Second income quintile','Third income quintile','Fourth income quintile','Highest income quintile']
    dhea_levels=dhea_rows.query('Statistics=="Value"').set_index('Characteristics').loc[source_order].VALUE.to_numpy()/1000
    dhea_means=dhea_rows.query('Statistics=="Value per household"').set_index('Characteristics').loc[source_order].VALUE.to_numpy()
    io=json.loads((OUT/'firm_data/io_build_provenance.json').read_text())
    cfc=json.loads((OUT/'firm_data/cfc_build_provenance.json').read_text())
    costs=pd.read_csv(OUT/'firm_data/cfc_cost_bridge.csv')
    io_rows=pd.read_csv(OUT/'firm_data/io_cost_bridge.csv')
    # The CFC-only build retains accepted placeholder output. Distinguish its
    # zero-output flag from zero activity in the observed supply-use source.
    if 'model_zero_activity' not in costs:
        costs=costs.rename(columns={'source_zero_activity':'model_zero_activity'})
    zero=io_rows.set_index(['region','firm']).source_zero_activity
    costs['observed_zero_activity']=zero.reindex(pd.MultiIndex.from_frame(costs[['region','firm']])).to_numpy()
    costs.to_csv(OUT/'firm_data/cfc_cost_bridge.csv',index=False)
    # Reproduce the national and source bridges from the authoritative builder
    # outputs. The early scratch bridge omitted input-product valuation in GO;
    # it is superseded here, with basic intermediate use preserved exactly.
    merge=io_rows.merge(costs,on=['region','industry','firm'],suffixes=('_io','_cfc'),validate='one_to_one')
    source_bridge=pd.DataFrame(dict(region=merge.region,industry=merge.industry,
        model_GO=4*merge.old_output,source_GO=4*merge.new_output,
        model_W=4*merge.compensation,source_W=4*merge.wages,
        model_M=4*merge.intermediate_cfc,source_M=4*merge.intermediate_io,
        model_T_product=4*merge.taxes,source_T_product=4*merge.input_product_tax,
        source_T_other=4*merge.other_production_tax,model_GOS=4*merge.GOS,
        source_GOS=4*merge.source_GOS,residual_after_output_tax_fix=4*(merge.model_GOS-merge.source_GOS)))
    source_bridge.to_csv(OUT/'firm_t0_source_bridge.csv',index=False)
    national=costs.groupby('industry')[['output','intermediate','compensation','taxes','old_CFC','new_CFC','interest','IO_GOS']].sum()
    national['old_unit_cost']=national[['intermediate','compensation','taxes','old_CFC']].sum(axis=1)/national.output
    national['new_unit_cost']=national[['intermediate','compensation','taxes','new_CFC']].sum(axis=1)/national.output
    national.to_csv(OUT/'firm_data/national_industry_bridge.csv')
    costs[costs.above_price_positive_IO_GOS].to_csv(OUT/'firm_data/unit_cost_exceptions.csv',index=False)
    allowed=costs[(costs.unit_cost>costs.price+1e-8)&(costs.IO_GOS<0)&(~costs.model_zero_activity)].copy()
    allowed.to_csv(OUT/'firm_data/negative_IO_GOS_cost_cases.csv',index=False)
    gaps=pd.read_csv(OUT/'final/B2_base_q12_s0/initial_wealth_gaps.csv')
    distribution=pd.read_csv(OUT/'quintile_comparisons.csv')
    q=pd.read_csv(OUT/'quarterly.csv')
    diag=pd.read_csv(OUT/'final/constraint_diagnosis.csv')
    diagnosis=diag.query("arm=='B2' and variant=='base' and quarter==12").groupby(['seed','decile','asset_band','diagnosis'],as_index=False).sum(numeric_only=True)
    diagnosis.to_csv(OUT/'constraint_diagnosis_Q12.csv',index=False)
    mechanisms=diagnosis.groupby(['seed','diagnosis'],as_index=False)[['households','constrained','income_change','wage_change','firm_receipts_change','consumption_cut']].sum()
    mechanisms.to_csv(OUT/'constraint_mechanisms_Q12.csv',index=False)
    summary=pd.read_csv(OUT/'final/summary.csv')
    texts=['# Household closure B2 and independent firm-data reconciliation — 2026-10-24\n',
        'Review outcome: **B2 fails; E is not started. Phase B and C_dp_005 remain on hold.** The independent firm step uses accepted FE arm F (e386f4e lineage), as clarified. Observed CFC is tested separately; the wider output/tax experiment is not accepted. No parameter was tuned after a gate failure. P remains off. Original B remains retained and failed.\n',
        'All money is CAD billions unless labelled otherwise; quarterly flows are not annualised except explicitly. Seeds 0–2 are used for every reported 12-quarter candidate. Accepted inputs are protected; new builds have new names. No push.\n',
        '## Decisions, commits and gates\n',
        '| Step | Commit(s) | Regression evidence | Gate/result |\n|---|---|---|---|\n'
        '| B2 form and fixed wealth response | c2c3eb8 | 4 B2 regressions | One multiplicative propensity factor; no additive intercept |\n'
        '| Frozen gates and source definitions | ea3485a | 2 diagnostic/gate regressions | G1 passes; base G2, G3 and G4 fail on all seeds |\n'
        '| National per-household quintile ranks | d40e353 | 1 scale-invariance regression | Regional expansion factors removed from rank income; 15 read-only replays must reproduce macro paths exactly |\n'
        '| Firm-data reconciliation | 55fb64a, b3227ea | 5 firm-account regressions in final tree | IO-column bridge matches gross margins, but combined build fails GDP initialisation; not promoted |\n'
        '| Separate initial acquisitions from CFC | 2237cb1 | 1 regression | Depreciation replacement leaves accepted initial capital purchases unchanged; legacy fallback preserved |\n'
        '| Observed CFC allocation | c3df2d9 | 2 allocation regressions | CFC-only input on accepted F; unit-cost and full IO-margin gates fail |\n'
        '| E | none | not run | Held by Step 1 gates |\n',
        '## B2 specification and initial liquid-wealth audit\n',
        '`C=max(0,c0*Yperm+kappa*(L-b*Yperm))`. The common rescale of arm-C propensities is **0.961350238407** for base kappa .01/q. Initial account consumption is exactly **377.8455B/q** (1,511.382B/year; 36-10-0112, v62305982). The intercept is zero. Permanent-income smoothing stays .25. The below-target asymmetric response uses .02; above-target .005. The .005–.02 quarterly wealth-response range is a labelled assumption, not an estimated Canadian MPC. No kappa or SFS buffer was fitted to a gate.\n',
        'The SFS definition and model L both comprise deposits plus non-pension financial assets. The accepted adapter pools non-pension securities/funds/other holdings into the legacy “Mutual Funds” field; the other legacy financial categories are zero. Initial deposits are 2,035.768B, non-pension OFA 4,196.926B and protected pensions 2,840.657B. Real estate and pensions are excluded from L. This is a broad liquidatable-financial-assets assumption: actual immediate liquidity of pooled investments is uncertain. SFS 2023 fixed decile/age median buffers are retained; no rescale of b. Nonpositive permanent income uses the existing fixed CAD fallback buffer.\n',
        f'Across households the initial mean gap is {(gaps.mean_gap_CAD*gaps.households).sum()/gaps.households.sum():,.2f} CAD; {(gaps.negative_share*gaps.households).sum()/gaps.households.sum():.2%} have a negative gap. Aggregate base kappa × gap is {gaps.kappa_gap.sum()/1e9:.3f}B, or {gaps.kappa_gap.sum()/377845500000:.2%} of initial consumption. This audit is descriptive; clipping and D1/rent mean the term is not an additive national expenditure identity.\n',
        '[Full initial decile × age table](outputs/B2/final/B2_base_q12_s0/initial_wealth_gaps.csv) gives mean, weighted median, negative share, household counts, L, permanent income, and kappa × gap. Age and income cells come from the retained SFS concordance in benchmarks/BE; its source hash and extraction are unchanged.\n',
        '## B2 seed and sensitivity gates\n',
        'G1: positive-income zero-goods share strictly below 2% at t0 and every quarter. G2: existing Gate B (Q4–Q12 constrained-share OLS ≤ .25 pp/q, Q12 saving −5.6% to 4.4%, Q1 consumption ≥95% of benchmark, accounting ≤1e-8). G3: **relative difference in quintile shares**, `model_share / benchmark_share − 1`, within ±15%; t0 and all quarters are reported/tested. G4: Q12 consumption and GDP each within 5% of same-seed **accepted F**, not failed B.\n',
        table(gates[['variant','seed','constrained_slope_pp','Q12_saving_pct','max_zero_positive_pct','Q12_C_vs_F_pct','Q12_GDP_vs_F_pct','G1','G2','G3','G4']]),
        'All twelve 12-quarter B2 base/sensitivity runs fail the joint gates. The .02 sensitivity passes G2 on all seeds but still fails G3; it is not selected as a repair. The base zero-goods maximum is 1.686%, compared with the retained failed B arm’s widespread zero clipping. Base Q1 consumption is 373.164B (1.24% below target); the remaining failures are not a Q1 aggregate calibration failure.\n',
        '## G3: national-accounts shares primary, SHS shares secondary\n',
        'Primary: [DHEA 36-10-0587-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610058701), 2022 household final consumption expenditure, excluding social transfers in kind. Values are 202,282 / 240,675 / 293,624 / 327,863 / 446,937 million CAD/year. Vectors: **v116884012, v116884035, v116884058, v116884081, v116884104**. Unrounded shares from these values are used, rather than rounded distribution vectors. Quintiles are household-weighted, ranked by equivalised household disposable income; OECD-modified units 1 for first adult, .5 additional persons aged 14+, .3 children under 14. Official definition pages and retrieval hashes are cached.\n',
        'The current downloaded table metadata, footnote 1, independently confirms the OECD-modified income-quintile definition; [metadata and hashes](benchmarks/B2/raw/table_definitions_provenance.json) are preserved from the same ZIP as the values.\n',
        'Model matching: re-rank households nationally each quarter by cash disposable income divided by those units, using linked member ages and household expansion weights. Cash income minus net interest is a **proxy for full DHEA disposable income**: noncash national-account items, including imputed owner income, are not individually reconciled. The linked age/membership skeleton is inherited. This limits exact source comparability and is disclosed rather than filled with invented income. Thus the reported G3 failure is on the available model income proxy; a fully concept-matched DHEA income allocation remains unvalidated. DHEA values sum to 1,511.381B/year versus the retained 1,511.382B consumption target: the 1M source rounding/vintage difference is recorded without rescaling either series.\n',
        'Secondary: [SHS 11-10-0223-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110022301), 2023 total current consumption, household before-tax total-income quintiles, **not equivalised**. Vectors **v54529951, v54529993, v54530035, v54530077, v54530119**; annual average household levels 40,091 / 57,503 / 71,570 / 88,993 / 122,479 CAD. These are the revised 2026-09-18 release with updated weights; no use of the superseded 76,750 national mean. Model gross-income ranks reconstruct wages and taxed D2/rent receipts before tax, retain transfers and deposit interest. Differences in income concepts remain explicit.\n',
        'SHS 2023 survey cash/current-expenditure scope differs from 2022 national accounts: owner-occupied imputed rent, financial-services imputations and other national-account adjustments, reference year, coverage and survey reporting. The model cannot isolate executed imputed housing services from its sector-L bundle. The imputed-rent memo is not a separately identified goods purchase, so it is **not subtracted** to fabricate SHS-comparable shares. Owner-imputed rent, where included, raises upper-quintile shares relative to SHS. Raw levels below are descriptive only, never a gate or a rescaling target.\n']
    texts += ['SHS secondary shares normalise the five published quintile means, treating quintiles as equal household fifths. Table 11-10-0223 publishes means, not quintile household counts; this is an approximation to aggregate expenditure shares. The published all-household mean differs slightly from the mean of the five quintile means. DHEA primary shares instead use published aggregate values directly. No survey weights or expenditure levels are adjusted.\n']
    for scheme in ['DHEA_equivalised_DI','SHS_gross_household_income']:
        d=distribution.query('scheme==@scheme and variant=="base" and seed==0 and quarter in [0,12]').copy()
        d['model_share_pct']=100*d.share;d['benchmark_share_pct']=100*d.benchmark_share;d['relative_gap_pct']=100*d.relative_deviation
        d['model_annual_total_B']=4*d.consumption/1e9
        texts += [f'### {scheme}: seed 0 initial and Q12\n',table(d[['quarter','quintile','model_share_pct','benchmark_share_pct','relative_gap_pct']])]
        d['model_annual_per_HH']=d.annual_model_consumption_per_household
        means=dhea_means if scheme=='DHEA_equivalised_DI' else benchmark['secondary_annual_means']
        d['benchmark_annual_per_HH']=d.quintile.map(dict(zip(range(1,6),means)))
        rawcols=['quarter','quintile','model_annual_per_HH','benchmark_annual_per_HH']
        if scheme=='DHEA_equivalised_DI':
            d['benchmark_annual_total_B']=d.quintile.map(dict(zip(range(1,6),dhea_levels)))
            rawcols=['quarter','quintile','model_annual_total_B','benchmark_annual_total_B','model_annual_per_HH','benchmark_annual_per_HH']
        texts += ['Raw levels: model quarter ×4, nominal and annualised; source calendar-year levels. Per-household amounts are CAD/year and totals B/year. These levels are never gating.\n',table(d[rawcols])]
    texts += ['DHEA per-household raw-level vectors: **v116884978, v116885001, v116885024, v116885047, v116885070**, retained in the same hashed 2022 extract. Different source/model household expansion totals also affect raw per-household comparisons; no weights are rescaled.\n']
    texts += ['[Every quarter, seed and sensitivity: shares, relative gaps and raw levels](outputs/B2/quintile_comparisons.csv). All DHEA and SHS source ZIP/CSV hashes, retrieval timestamps (2026-10-24 UTC), vectors and extract hashes are in [distribution_provenance.json](benchmarks/B2/distribution_provenance.json).\n',
        '## Independent Step 2: observed capital consumption and IO bridge\n',
        'Data source: [36-10-0096-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610009601), reference 2022, current prices, geometric depreciation, total non-residential assets. Observed Canada CFC is **377.319B/year**. Each province/industry vector is retained in [observed rows](outputs/B2/firm_data/observed_nonres_CFC_2022.csv) and [mapping](outputs/B2/firm_data/cfc_allocation.csv). Nearest NAICS groups are split by fixed initial output; suppressed province detail uses national group CFC × regional output share. Some ISIC industries receive pieces of multiple NAICS aggregates. These are concordance assumptions, not precise industry observations.\n',
        f'CFC-only build replaces {cfc["CFC_before_annual"]/1e9:.3f}B/year of inherited proxy depreciation with {cfc["CFC_after_annual"]/1e9:.3f}B/year of observed allocation. The remaining {(377319e6-cfc["CFC_after_annual"])/1e9:.6f}B/year is explicitly unallocated where modeled capital stock/composition is absent. No asset is invented. A capital-stock composition fallback is recorded for Ontario forestry. [All boundaries](outputs/B2/firm_data/cfc_boundaries.csv).\n',
        'Residential depreciation is outside this firm non-residential stock: [36-10-0099-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610009901), v91665018 =151.751B/year (components v91665019, v91665020, v101283600). It is a scope check, not added to firms that do not own household dwellings. The bridge to sector-account CFC and a housing-producer ownership boundary remain unresolved; no national rescale.\n',
        'The mechanical acquisition/depreciation separation preserves t0 accepted gross capital purchases while changing only CFC. Runtime investment behaviour is unchanged. Accepted fiscal initialisation is preserved; only changed corporate-tax receipts and their revenue counterpart are updated. Two rejected snapshots are retained: the first CFC-only build reused both CFC as purchases and the legacy wholesale fiscal initializer, failing GDP at t0; v2 corrects these initialisation paths.\n']
    z=pd.read_csv(OUT/'firm_data/national_industry_bridge.csv').query('industry in ["I","H53","A02"]').copy()
    for col in ['output','intermediate','compensation','taxes','old_CFC','new_CFC','interest','IO_GOS']:z[col]/=1e9
    texts += [table(z),
        'These national focus-industry unit costs fall below price after observed CFC. Interest is reported separately; stored operating unit cost excludes financing. Every province/industry cost component is in [cfc_cost_bridge.csv](outputs/B2/firm_data/cfc_cost_bridge.csv); all exceptions with nonnegative observed IO GOS are in [unit_cost_exceptions.csv](outputs/B2/firm_data/unit_cost_exceptions.csv).\n',
        f'**Step 2 gate fails:** the runnable CFC-only build has {int((costs.margin_gap_pp.abs()>1).sum())} cells with gross-margin deviations over 1 pp and {int(costs.above_price_positive_IO_GOS.sum())} above-price cells despite nonnegative observed IO surplus. Maximum gross-margin gap is {costs.margin_gap_pp.abs().max():.3f} pp; 100-pp cases include inherited placeholder production where source activity is zero. These are reported, not fitted away.\n',
        f'F-A1: observed signed other production taxes (D29−D39) are **{io["signed_other_tax_annual"]/1e9:.3f}B/year**, absent from the accepted firm charge. F-D1: accepted sales-row output exceeds the cost-side supply-use column by **{io["retained_sales_row_discrepancy_annual"]/1e9:.3f}B/year**. The canonical input’s `output_basic` is basic intermediate use plus VA; input-product valuation must be added for this column identity. Source PRM100000–800000 codes, concordance and hashes are in [IO provenance](outputs/B2/firm_data/io_build_provenance.json).\n',
        'An experimental new IO input re-expresses technology per observed column output, preserves physical inputs and financial stocks, and includes signed taxes. Gross-margin residuals then fall to 0.000978 pp. It retains source-zero producers as inactive balance-sheet holders without forgiving debt. However its combined IO/CFC build fails output/expenditure GDP initialisation (first region ratio 0.928633), so **it is not used for results or accepted as a validated fix**. The remaining uses/supply discrepancy is not booked as a fictional buyer, inventory flow or cash transfer. GDP valuation also combines input-product taxes and other production taxes, so the wider correction needs a consistent expenditure/income/production bridge before promotion.\n',
        'The independent completed simulation arm below is explicitly **F + observed CFC only**. It does not claim the unfinished F-A1/F-D1 correction has passed. Bank and borrower financial stocks are retained; payout rule P is off.\n']
    allowed['IO_GOS_B']=allowed.IO_GOS/1e9
    texts += ['Above-price cases with negative observed IO GOS (permitted by the stated gate; IO GOS in B/q):\n',
        table(allowed[['region','industry','unit_cost','IO_GOS_B']])]
    components=pd.DataFrame(dict(component=['gross output','intermediates','compensation','input-product taxes',
        'other production taxes net of subsidies','gross operating surplus + mixed income'],
        accepted_B=[4*costs.output.sum(),4*costs.intermediate.sum(),4*costs.compensation.sum(),4*costs.taxes.sum(),0.,4*costs.GOS.sum()],
        observed_column_bridge_B=[4*io_rows.new_output.sum(),4*io_rows.intermediate.sum(),4*io_rows.wages.sum(),
            4*io_rows.input_product_tax.sum(),4*io_rows.other_production_tax.sum(),4*io_rows.source_GOS.sum()]))
    components[['accepted_B','observed_column_bridge_B']]/=1e9
    texts += ['Annual national gross-cost bridge (CFC remains a separate below-gross-surplus charge):\n',table(components),
        'Positive gross operating surplus does not itself imply positive net surplus after CFC. The user’s unit-cost gate is applied unchanged; the exceptions are not all identified data errors merely because that gate fails.\n']
    new=summary.query('arm=="F_CFC"').copy()
    if len(new)==3:
        hh_share=new.household_writeoffs/new.bank_losses
        texts += [f'Under the retained old household rule, household write-offs now account for {hh_share.min():.1%}–{hh_share.max():.1%} of total bank losses. They exceed firm losses in every CFC-only seed. This strengthens the case for a payment-based household default specification, but does not release E from the failed Step 1 gate.\n']
        events=pd.read_csv(OUT/'final/firm_events.csv').query('arm=="F_CFC"').copy()
        codes=json.loads((HERE/'outputs/pre_D3_checks/industry_mapping.json').read_text())
        events['industry_code']=events.industry.astype(str).map(codes)
        industry=events.groupby(['seed','quarter','industry_code'],as_index=False).agg(
            default_events=('firm','size'),formal_losses=('loan_debt','sum'),overdraft_losses=('overdraft_cancelled','sum'),
            retained_contract=('retained_contract','sum'),recovery_cash=('recovery_cash','sum'))
        industry.to_csv(OUT/'firm_losses_by_industry_quarter.csv',index=False)
        totals=industry.groupby(['seed','industry_code'],as_index=False)[['formal_losses','overdraft_losses','default_events']].sum()
        totals['loss_B']=(totals.formal_losses+totals.overdraft_losses)/1e9
        top=totals.sort_values(['seed','loss_B'],ascending=[True,False]).groupby('seed').head(5)
        diagnostic=events.merge(costs[['region','firm','profit','IO_GOS','unit_cost']],on=['region','firm'],
            suffixes=('_event','_initial'),validate='many_to_one')
        diagnostic['initial_condition']=diagnostic.apply(lambda r:'negative observed IO GOS' if r.IO_GOS<0 else
            ('initial loss despite nonnegative IO GOS' if r.profit<0 else 'initially nonnegative; later distress'),axis=1)
        initial_loss=diagnostic.groupby(['seed','initial_condition'],as_index=False)[['loan_debt','overdraft_cancelled']].sum()
        initial_loss['total_loss_B']=(initial_loss.loan_debt+initial_loss.overdraft_cancelled)/1e9
        initial_loss.to_csv(OUT/'firm_loss_initial_condition.csv',index=False)
        accepted=pd.read_csv(HERE/'outputs/FE/summary.csv').query('quarters==12').copy()
        accepted['firm_total_B']=(accepted.firm_loan_losses+accepted.overdraft_losses)/1e9
        comparison=new[['seed']].copy()
        comparison['F_firm_losses_B']=comparison.seed.map(accepted.set_index('seed').firm_total_B)
        comparison['CFC_firm_losses_B']=new.firm_loan_losses.to_numpy()/1e9+new.overdraft_losses.to_numpy()/1e9
        comparison['loss_change_pct']=100*(comparison.CFC_firm_losses_B/comparison.F_firm_losses_B-1)
        comparison['F_recap_B']=comparison.seed.map(accepted.set_index('seed').recapitalisation)/1e9
        comparison['CFC_recap_B']=new.recapitalisation.to_numpy()/1e9
        comparison['GDP_change_pct']=100*(new.Q12_GDP.to_numpy()/comparison.seed.map(accepted.set_index('seed').Q12_GDP)-1)
        comparison['C_change_pct']=100*(new.Q12_consumption.to_numpy()/comparison.seed.map(accepted.set_index('seed').Q12_consumption)-1)
        comparison.to_csv(OUT/'F_CFC_seed_comparison.csv',index=False)
        texts += ['### Same-seed accepted F versus CFC-only data correction\n',table(comparison)]
        for col in ['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','Q12_GDP','Q12_consumption']:new[col]/=1e9
        texts += ['## CFC-only seed comparison and losses\n',table(new[['seed','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','Q12_GDP','Q12_consumption','Q12_saving_pct','Q12_constrained_pct']])]
        texts += ['Lower losses coexist with lower Q12 GDP and consumption, while roughly half of households remain constrained under accepted F’s spending rule. CFC changes both cost accounting and subsequent capital replacement requirements; profit, demand and income feedback also change. These runs identify the total data-package effect, not the contribution of each channel. No behavioural coefficient is changed to offset the output decline.\n']
        texts += ['[Industry × quarter losses and default events](outputs/B2/firm_losses_by_industry_quarter.csv) use labelled industry codes. These are restructuring events; a continuing producer can recur. Under retained F, recoverable debt stays as a contract: collateral capacity is not an executed asset sale or a cash recovery.\n']
        texts += ['Largest remaining industry losses per seed:\n',table(top[['seed','industry_code','default_events','loss_B']])]
        texts += [table(initial_loss[['seed','initial_condition','total_loss_B']]),
            'This initial-condition split is descriptive. Later distress among initially profitable producers combines demand, prices, income feedback and unresolved initial IO financing/valuation; it does not identify a pure behavioural causal effect.\n']
        fq=q.query('arm=="F_CFC"').copy()
        cols=['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','gdp','consumption']
        for col in cols:fq[col]/=1e9
        texts += [table(fq[['seed','quarter']+cols]),'[Firm losses by province, industry and quarter](outputs/B2/final/firm_events.csv), [resolution log](outputs/B2/final/resolution_log.csv), and [quarterly macro paths](outputs/B2/quarterly.csv). Firm loan principal and firm overdraft cancellation are separate bank-loss components; household write-offs complete the total. No residual is assigned to a fabricated loss category.\n']
        metrics=[]
        for seed in range(3):
            path=OUT/'final'/f'F_CFC_base_q12_s{seed}'
            raw=pd.read_csv(path/'outcomes.csv');events=pd.read_csv(path/'resolutions.csv')
            metrics.append(dict(seed=seed,resolutions=len(events),min_equity_loans_ratio=raw.min_capital_ratio.min(),
                min_resolution_ratio=raw.min_resolution_ratio.min()))
        texts += [table(pd.DataFrame(metrics)), 'Capital minima are after same-quarter bridge-bank resolution. Negative pre-resolution capital and recapitalisation remain visible in the event log; a positive post-resolution minimum does not establish solvency without fiscal support.\n']
    texts += ['## Remaining household and firm limitations\n',
        '[Q12 decile × asset-band diagnosis](outputs/B2/constraint_diagnosis_Q12.csv) separates persistent planned-spending gaps with asset drawdown from cases where restoring initial income would cover the budget, and retains combined cases. “Income restoration sufficient” is a counterfactual accounting classification, not causal identification: wages, employment and firm receipts interact. Detailed income changes and cuts are retained; they are not explained away by the aggregate saving match.\n',
        'B2 removes the large additive-intercept clipping but still gives a steep consumption distribution and rising constraints in the base. Further household behavioural specification requires review; no buffer coefficient is selected from the sensitivities to pass the gates. E remains needed conceptually because negative net worth is not payment default, but implementing it now would mix that change with failed spending-distribution and firm-data gates.\n',
        'Firm losses after CFC cannot all be labelled behavioural. Unresolved source-zero producers, IO/tax valuation, aggregate CFC concordance, non-residential ownership boundaries and financing remain data/concept limitations. Conditional on those inputs, price noise, demand/employment feedback, the payment-default trigger and continued production/restructuring also affect losses. The CFC-only comparison identifies a data-package effect, not a full causal decomposition. Do not declare household losses, firm losses or bank recapitalisations plausible from accounting closure alone. **The model is not ready for Phase B.**\n']
    texts += ['### Base B2 Q12 constraint mechanisms\n',table(mechanisms[['seed','diagnosis','households','constrained']]),
        'Counts are represented households. Income/wage/firm-receipt changes and cuts by decile and assets are retained in the linked diagnosis files; categories can contain offsetting income components.\n']
    texts += ['### Distribution measurement correction\n',
        'The first quintile diagnostic ranked regional aggregate balances rather than income per household. This affected national comparisons across regions with different expansion factors. Commit d40e353 divides rank income by each region’s factor, retaining the household weights and aggregate consumption. All 15 twelve-quarter configurations were replayed serially with only the corrected read-only diagnostic, requiring GDP, consumption, receipts, constraints, cash DI, household write-offs and bank losses to match every original region/quarter at 1e-12 relative tolerance. Original misranked CSVs are retained for provenance and are **not used for the gate**. Corrected source-specific distributions, replay comparisons and hashes are in [distribution_replays](outputs/B2/distribution_replays_v2). No model parameter or macro path changed.\n']
    tests=OUT/'verification/full_test_execution.json'
    if tests.exists():
        t=json.loads(tests.read_text());texts += ['## Verification\n',f'Full `tests/` via `run_pre_D3_tests.py`: **{t["passed"]} passed, {len(t["failures"])} failures, {t["tests"]} cases**. Failures are checked against the exact known 30 “Nan in transactor_total_real_supply” IDs; sampler uses one worker. See [test execution](outputs/B2/verification/full_test_execution.json) and [audit](outputs/B2/audit.json). No overlapping validation simulations.\n']
    (HERE/'CLOSURE_B2_2026-10-24.md').write_text('\n'.join(texts),encoding='utf-8')

if __name__=='__main__':main()
