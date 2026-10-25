"""Render ZA from measurements, including build failures and missing values."""
import json
import pandas as pd
from prepare_za import HERE,OUT

def table(frame,digits=3):
    def cell(v):
        if pd.isna(v):return 'not identified'
        if isinstance(v,float):return f'{v:.{digits}f}'
        return str(v).replace('|','/')
    rows=['| '+' | '.join(map(str,frame.columns))+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    rows+=['| '+' | '.join(cell(v) for v in row)+' |' for row in frame.itertuples(index=False,name=None)]
    return '\n'.join(rows)

def main():
    seed=pd.read_csv(OUT/'seed_comparison.csv');q=pd.read_csv(OUT/'quarterly_comparison.csv')
    components=pd.read_csv(OUT/'GDP_component_changes.csv')
    pre=json.loads((OUT/'FS_T_pre_run_gates.json').read_text());fallback=json.loads((OUT/'FS_pre_run_gates.json').read_text())
    short=json.loads((OUT/'FS_T_short_certificate.json').read_text());failed=json.loads((OUT/'FSG_build_gate.json').read_text())
    tests=json.loads((OUT/'full_test_execution.json').read_text()) if (OUT/'full_test_execution.json').exists() else None
    testline=(f"{tests['passed']} passed, {len(tests['failures'])} failures, {tests['tests']} cases; {tests['additional_failures']} additional failures against the exact SG test IDs. Sampler one worker." if tests else 'Full suite running; draft verification only.')
    gdp=pd.read_csv(OUT/'FS_T/gfcf_GDP_initialization.csv');gdp[['output','expenditure','income']]/=1e9
    t0=pd.read_csv(OUT/'FS_T_t0_industry_annual_B.csv');t0['GOS_change']=t0.new_GOS-t0.old_GOS
    losses=pd.read_csv(OUT/'firm_losses_by_industry_quarter.csv');losses['total_loss']=losses.loan_debt+losses.overdraft_cancelled
    industry=losses.groupby(['industry_code','arm']).total_loss.sum().unstack('arm').div(3e9)
    industry['change']=industry.FS_T-industry.F_CFC;industry=industry.sort_values('FS_T',ascending=False).head(12).reset_index()
    h=pd.read_csv(OUT/'OOH_cash_national.csv')
    for c in ['C','DI','old_gap','new_cash_C','new_gap']:h[c]/=1e9
    for c in ['old_dissaver_share','new_dissaver_share']:h[c]*=100
    l=pd.read_csv(OUT/'OOH_L_profit_bridge.csv')
    lt=l[['region','model_L_revenue','model_L_GOS','model_L_profit','OOH_source_revenue','OOH_model_gross_surplus_contribution','market_L_model_revenue_residual','market_L_GOS_residual','market_L_profit_residual_if_modeled_nonres_CFC_and_firm_interest_remain_here']].copy()
    lt.iloc[:,1:]/=1e9;lt.columns=['region','L revenue','L GOS','L profit','OOH revenue','OOH model GOS','market L revenue','market L GOS','market L profit residual*']
    groups=pd.read_csv(OUT/'OOH_cash_by_decile_tenure.csv')
    groups['old_dissaver_pct']=100*groups.old_dissaver_households/groups.households;groups['new_dissaver_pct']=100*groups.new_dissaver_households/groups.households
    groups['new_gap_B']=(groups.cash_C_exact_split-groups.DI)/1e9
    scope=pd.read_csv(OUT/'FSG_source_scope.csv').groupby('sector')[['observed_quarterly_purchaser_CAD','normalized_IO_basic_CAD']].sum().mul(4/1e9).reset_index()
    negative=pd.read_csv(OUT/'FSG_negative_products.csv').sort_values('IO_fixed_quarterly_CAD').head(8);negative['fixed_B_q']=negative.IO_fixed_quarterly_CAD/1e9
    investor=json.loads((OUT/'FSG_investor_diagnostic.json').read_text())
    legacy_tax=pd.read_csv(OUT/'FSG_legacy_tax_scope_diagnostic.csv')
    residential_legacy_tax_annual=4*legacy_tax.residential_with_legacy_tax.sum()/1e9
    residential_legacy_tax_gap=4*legacy_tax.purchaser_gap_if_legacy_tax_reused.sum()/1e9
    costs=pd.DataFrame([dict(arm=r['arm'],source_positive_margin_exceptions=r['positive_source_margin_exceptions'],source_positive_max_pp=r['positive_source_max_gap_pp'],above_price=r['positive_source_above_price_exceptions'],old_universal_exceptions=r['old_universal_margin_exceptions'],old_universal_max_pp=r['old_universal_max_gap_pp']) for r in [pre,fallback]])
    sources=json.loads((HERE/'benchmarks/ZA/provenance.json').read_text())['sources']
    sources.append(dict(commit='d847fb2',file='canonical/product_taxes_final_gross_by_province.csv',sha256=failed['provenance']['tax_sha256'],retrieved_utc='2026-10-25'))
    regional=[]
    for s in range(3):
        a=pd.read_csv(OUT/f'F_CFC_seed{s}_regional_paths_wide.csv').set_index('region');b=pd.read_csv(OUT/f'FS_T_seed{s}_regional_paths_wide.csv').set_index('region')
        regional.append(pd.DataFrame(dict(region=a.index,seed=s,F_CFC_Q12_B=a.gdp_Q12.to_numpy()/1e9,FS_T_Q12_B=b.gdp_Q12.to_numpy()/1e9,change_B=(b.gdp_Q12-a.gdp_Q12).to_numpy()/1e9)))
    regional=pd.concat(regional).groupby('region')[['F_CFC_Q12_B','FS_T_Q12_B','change_B']].mean().reset_index().sort_values('change_B')
    text=f'''# Closure ZA review — 2026-10-25 UTC

Base §ca33da2§, branch §feature/validation-2022§. **FS_T v4 passes the specified source, cost, all-13-region GDP and accounting gates; seeds 0–2 complete. FSG is not built: source preflight exposes material signed negative fixed-capital uses that the nonnegative purchase allocator cannot represent.** No source entries were clipped, reassigned to inventories, redistributed or fitted. The independent exact housing split is complete and read-only. Stop for review; Phase B, C_dp_005, household noncash-layer changes and investment expansion remain on hold.

Passing these gates does not validate the no-shock dynamics. FS_T's nominal contraction worsens on seed0 and improves on seeds1–2; losses and roughly50% constrained households remain substantial. Recommend FS_T as the corrected diagnostic input subject to review, retaining F_CFC as its historical comparator.

## Steps, commits and checks

| Step | Commit / verification | Result |
| --- | --- | --- |
| 1: source-zero convention / effort guard | §1ffdc06§; three regressions; F_CFC seed0 before/after2Q replay | Same1M/year output=VA=domestic-FCF path for all68 exact source-zero cells; zero-target/zero-capacity effort0; contracts/jobs held at build. |
| 2: predeclared cost specification | §a9fee55§; two regressions | Unchanged1pp margin threshold on source-positive nonfloor cells; separate floor check. Old universal result retained. |
| 3: FS_T v4 | §a9fee55§;13 GDP initializations;2Q plus3×12Q | Pass; maximum long-run battery error {seed[seed.arm=='FS_T'].max_accounting_error.max():.3g}, tolerance1e-8. |
| Floor audit schema | §f599a9d§; one regression | Exclude only intentionally unset Q0 target forecast; all defined states and later forecasts still checked. |
| 4: FSG source preflight | §7f9789c§; three budget/rejection regressions |20 negative net-product uses, −3.502B/year; no executable FSG candidate or dependent runs. |
| 5: exact OOH | §41d4e68§; read-only §za_housing.py§; source/allocation reconciliations | Exact provincial source totals, assumed within-province owner allocation; no closure implementation. |
| 6: report / full suite | §run_za_full_tests.py§ | {testline} |

The nine final focused checks pass. The zero-firm unit regression exercises two successive zero-target/capacity effort/production updates. Full v4 integration separately verifies the previously failing NL C21 path and all source-zero holders through two simulation quarters. F_CFC seed0 before/after replay compares **4,082 numeric per-firm arrays per run**, dtype, shape and bytes after both quarters: identical, both accounting errors4.07e-15. Aggregate noisy Hill-tail estimators are excluded from this per-firm economic-state claim; the original overbroad estimator-comparison attempt is retained.

In the full short integration, **all68 source-zero firms have actual production0 and productivity0 in bothQ1 andQ2**, with finite captured state and passing accounting. The forecast target is capacity-clamped inside the effort calculation. §zero_runtime_integration_certificate.json§ records this direct runtime check; it is not inferred merely from the1M initialization convention.

## Zero-activity path and cost gates

§_floor_empty_provincial_sectors§ uses the existing §CAN_2022_EMPTY_SECTOR_FLOOR=1e6§ CAD/year. Exact canonical source-zero classification clears tiny allocation remnants before that same path.29 inherited plus39 newly zero cells give **68M/year output and68M/year GOS**, {100*pre['floor_output_national_share']:.6f}% of national output, below0.01%. The additional39M/year is also domestic FCF, using the existing sector fractions (firm58.6508%, household26.5476%, government14.8016%) and investor shares. Dummy acquisition flows change; installed capital, CFC, loans/deposits, bank stocks, household records and job/employer contracts are held. No forgiveness, deletion or reassignment.

§gate_specification_before_runs.json§ was frozen in1ffdc06 before rebuilding/measuring v4. Source-positive max margin gap **{pre['positive_source_max_gap_pp']:.6f}pp**, zero exceptions above1pp, zero prohibited above-price cases. Old universal gate: **68 exceptions, max100pp**, exactly floor cells. Every defined captured floor state is finite in2Q and all3 long runs. Contracts/jobs are held initially; subsequent endogenous employment/default dynamics remain active.

Cost results, including the unnecessary FS diagnostic (margin deviations in percentage points):

{table(costs)}

The build-provenance §margin_passed§ and §max_margin_gap_pp§ fields retain the old universal diagnostic. The separately declared §*_pre_run_gates.json§ files are the authoritative source-positive/floor adoption checks; historical universal failures are not overwritten.

The first short simulation completed with accounting error {short['max_accounting_error']:.3g}, then its wrapper failed on Q0 target_production, intentionally initializedNaN for all firms and defined fromQ1. Original raw output and failed wrapper are retained; a separate certificate excludes only this unset forecast. No economic value, tolerance or parameter changed. The first controller unnecessarily ran FS fallback prechecks:13 GDP checks pass, but{fallback['positive_source_margin_exceptions']} positive-source margin and{fallback['positive_source_above_price_exceptions']} above-price exceptions fail. No FS macro run followed. That controller's §adoption_result.json§ is superseded by **§adoption_final_result.json§**, which certifies FS_T.

## Initial FS_T accounts and GDP

New input §dev/pkl_files/io2022_fs_t_za_v4_2026_10_25.pkl§, SHA256 §{pre['pickle_sha256']}§.

Extra unadopted FS diagnostic input §io2022_fs_za_v4_2026_10_25.pkl§, SHA256 §{fallback['pickle_sha256']}§. Accepted pickles unchanged.

GOS is **1336.184→1187.287B/year**, down148.896B:48.431914B re-export correction plus100.503564B signed producer taxes, less0.039B incremental floors. Explicit VA6 is unchanged except floors; reader-implied residual VA falls. Physical inputs and CFC are preserved while coefficients are expressed in corrected output units. Taxes have the government counterpart, exports the ROW import counterpart. No cash, trade or stock plug.

Largest industry changes, annual B:

{table(t0.sort_values('GOS_change').head(10)[['industry','output_change','old_GOS','new_GOS','GOS_change','signed_other_tax']])}

All13 GDP checks: levels B/quarter, residuals CAD/quarter; unchanged np.isclose tolerance:

{table(gdp[['region','passed','output','expenditure','income','expenditure_gap','income_gap']],6)}

## Twelve-quarter results

F_CFC is the historical IH comparator; FS_T is newly measured, seeds0–2 serially. No baseline resampling or seed selection. GDP nominal B; real GDP uses each run's PPI deflator.

{table(seed[['arm','seed','GDP_Q0_B','GDP_Q1_B','GDP_Q12_B','GDP_Q0_Q12_pct','GDP_Q1_Q12_pct','GDP_real_Q0_Q12_pct']])}

Loss and recapitalisation totals over12 quarters, B:

{table(seed[['arm','seed','household_loss_B','firm_loan_loss_B','overdraft_loss_B','bank_loss_B','recap_B','Q12_constrained_pct']])}

Q12 consumption, investment and employment:

{table(seed[['arm','seed','Q12_C_B','Q12_HH_I_B','Q12_firm_I_B','Q12_employment']])}

FS_T lowers starting GDP12.098B/quarter. Seed0 Q12 nominal difference is−33.534B: C+8.120, G−15.370, I+0.043, inventory−8.166, exports−26.241 and imports−8.043B (lower imports add GDP). This is an expenditure decomposition, not identification of each feedback mechanism. Seed1's nominal improvement is much larger than its small real-GDP improvement: prices matter. Seed2 improves both. Tax, profit, fiscal and external-demand feedbacks interact; corrected accounting does not stabilize the unchanged spending rule by itself.

Seed0 also shows the importance of prices: real contraction is7.61% versus7.32%, much closer than the nominal10.81% versus7.59%. The correction changes the level and price path as well as quantities.

Within-run nominal GDP decomposition, B. Each row compares Q12 with its start quarter; the last import column is already signed as a GDP contribution. Full reconciliation residuals, below0.05CAD, are retained in §GDP_component_changes.csv§.

{table(components.drop(columns=['end','component_gap_B']))}

Regional Q12 GDP means across matched seeds, B (all per-seed regional paths retained separately):

{table(regional)}

Firm loan+overdraft losses, mean12-quarter B across seeds:

{table(industry)}

Construction remains the largest loss industry. Computer/professional services, miscellaneous manufacturing, motor vehicles and other transport equipment worsen. The correction does not universally lower firm losses. Full industry×quarter×seed loan/overdraft losses: §firm_losses_by_industry_quarter.csv§. Bank/quarter resolutions and recaps: §resolution_comparison.csv§. Both arms' full quarterly GDP, deflated quantities, losses, cash DI/saving, constrained share, household/firm investment, CFC, employment and minimum bank ratios: §quarterly_comparison.csv§. Cash saving is not treated as SNA saving without the previously documented scope adjustments.

'''
    for s in range(3):
        z=q[(q.arm=='FS_T')&(q.seed==s)].copy();z['firm_all_loss_B']=z.firm_loan_loss_B+z.overdraft_loss_B
        text+=f'### FS_T seed{s}, quarterly\n\n'+table(z[['quarter','GDP_B','C_B','HH_loss_B','firm_all_loss_B','bank_loss_B','recap_B','constrained_pct','cash_saving_pct']])+'\n\n'
    text+=f'''## FSG source reconciliation: no executable build

IO fixed capital is **624.510840B/year including68M floors** (unfloored624.442840B), separate from55.631098B inventory change.36-10-0096 investor observations and36-10-0099 residential observations supply **shares**, not a second regional level. Scope budgets below are diagnostic allocations, never adopted inputs.

{table(scope)}

The13-region observed purchaser-price total is661.119B/year (Canada661.120B, rounding); source GFCF net product taxes36.651344B/year. With68M floors retained, the residual price/scope gap is−43.184M/year; unfloored it is+24.816M. Reported, not allocated as a business-investment plug. Government is98.480B, NPISH1.517B in the13-region sum, business residual311.343B, residential249.779B. Actual source vectors and regional budgets are cached.

An additional independent valuation check is retained in §FSG_legacy_tax_scope_diagnostic.csv§. Applying the existing24.4738997% household capital-formation tax to the diagnostic235.041603B basic residential budget would yield **{residential_legacy_tax_annual:.6f}B purchaser spending**, {residential_legacy_tax_gap:.6f}B above the249.779B residential source. No rate, price or fiscal flow was changed. Also, total residential investment across all sectors is not identical to household-sector GFCF: the previously accepted household benchmark v62305994 is242.393B/year, a7.386B scope difference. A future executable FSG needs a sector/asset and product-tax valuation crosswalk as well as a signed-use accounting path. Reusing the legacy rate and relabelling all residential formation household investment would not establish a source-consistent scope bridge.

The7.386B difference is not an estimate of corporate residential investment: household-sector fixed capital also includes unincorporated-enterprise nonresidential assets, while the residential table covers an asset class across sectors. Prior benchmark provenance is [the IFE source record](benchmarks/IFE/provenance.json):36-10-0112 v62305994,2022 quarterly SAAR annual mean, retrieved2026-10-23, selected CSV SHA256 c579dbedd2fe33449d43eab7d565b552fab61b17d0a9ac08e6c2e9448b46584c; source zip b577daa453e1527602f55000d301624143bdaf3dba87bfbd458f44d6ab797d1e. Its exact quarterly source rows remain in §benchmarks/IFE/household_gfcf_2022.csv§.

**20 negative product×destination-region net uses total−3.501614B/year.** Largest entries, B/quarter:

{table(negative[['region','product','fixed_B_q']],6)}

These signed entries are not rounding remnants. Distributing them to investors creates negative household purchase weights, incompatible with the nonnegative goods allocator. Clipping inflates fixed capital3.502B/year; offsetting with inventories violates the requested separation. Neither is done. No FSG pickle or opening stock/cash change. The >50M/q mapped-group2% gate, FSG GDP/accounting checks and dependent12Q runs are **not evaluated**, not falsely marked passed or assigned numerical failures. This is a source-to-model representation blocker; it does not show failure of the investor-share gate.

This constraint comes from the existing implementation, not a new statistical acceptance threshold: §macromodel/agents/agent/agent.py§ clips recorded negative purchases, and §macromodel/markets/goods_market/func/settlement.py:104§ explicitly requires negative buyer spending to be zero. §ICIOReader._prefold_capital_composition§ already distinguishes signed accounting investment from nonnegative capital-technology weights; its technology-only clipping is not an exact signed-GFCF accounting path. Copying that clip into the new accounting budget would lose the3.502B net-use term.

Next decision: establish these negative net uses' source meaning, including the commodity/valuation bridge; then specify the appropriate signed non-purchase or disposal account and counterparties if valid. Correct source only if an independently demonstrated source error exists. No disposal rule, rescale or capital basket invented. Initial failed build trace and complete preflight retained in logs/.

The independent investor concordance was nevertheless completed. §FSG_investor_groups_diagnostic.csv§ and §FSG_investor_industries_diagnostic.csv§ retain every actual vector, missing-regional fallback, scope normalization, source group and within-group canonical-output share. Government education/health are separated from private P/Q, government residual maps to O, NPISH to P/Q/R/S. The normalized nonresidential target is{investor['annual_normalized_nonres_target']/1e9:.6f}B/year; {investor['material_groups']} mapped groups exceed50M/quarter. No material target lacks an existing capital-stock/acquisition support total; residuals are floating-point noise (national{investor['annual_unsupported']:.3g}CAD/year). This is an allocation-only support check, not an executable product-flow or adoption-gate pass; no new product basket is assigned to any firm.

## Exact owner-occupied housing, read-only

Pinned IO commit **eb40128**, SUT BS5311A0/HFCE PEC04200 inside L. Annual exact source output/imputed consumption **235.939587B**, owner cash costs **66.623975B**, noncash gross mixed income **169.315612B**. Cash costs are basic inputs, net product taxes on inputs and net property/production taxes. The existing model memo differs nationally1.587M; provincial differences are larger because its regional allocation differs (full differences in §OOH_owner_allocation_by_province.csv§).

F_CFC L revenue404.928565B, GOS288.982141B, profit271.532846B/year. Attributable OOH revenue235.939587B and current model gross-surplus contribution**204.725982B**, including the35.410370B property/production tax F_CFC omits from costs. FS_T charges that tax; source noncash mixed income is169.315612B. Source OOH has no employee compensation or corporate GOS; the model embeds it in the mixed L corporate producer. Actual OOH **net profit cannot be identified** without dwelling CFC and interest/ownership allocation.

Province bridge, annual B. *Market profit residual retains all modeled nonresidential L CFC and firm interest in market L: a diagnostic convention, not an observed OOH profit.*

{table(lt)}

Read-only calculation: remove each province's exact OOH consumption from existing owners, add its exact owner cash costs, both **proportional to existing owner imputed memos within that province**. Survey weights, cash DI, consumption target, firms and all actual flows unchanged. No VAT gross-up, clipping or calibration. Income deciles are model unequivalised household after-tax income per represented household, household-weighted, not a new source-income fit.

National annual B, gap=planned C−cash DI (positive means planned dissaving):

{table(h[['arm','C','DI','old_gap','new_cash_C','new_gap','old_dissaver_share','new_dissaver_share','negative_residual_households']])}

Gap falls exactly169.315612B/year. But proportional attribution gives **206,250 F_CFC households negative residual cash consumption (−5.540B/year)**; CIS candidate189,170 (−5.246B). Retained, never clipped. Exact provincial totals do not identify exact household imputed purchases: this cannot simply be installed as a cash rule. A matched noncash layer needs coherent household/memo allocation, cash inputs, dwelling stocks/CFC and fiscal ownership boundaries. No closure change here.

Cash DI is held fixed solely to size the initial accounting boundary. An implemented closure would also change L cash sales, the corporate-profit/payout base and the counterparties for owner expenses; these results are not a general-equilibrium forecast of that implementation.

Decile×tenure planned-dissaver shares and new annual gap B; full components/counts in §OOH_cash_by_decile_tenure.csv§:

'''
    for arm in ['F_CFC','CIS_candidate']:
        text+=f'### {arm}\n\n'+table(groups[groups.arm==arm][['decile','tenure','households','old_dissaver_pct','new_dissaver_pct','new_gap_B','negative_residual_households']])+'\n\n'
    text+=f'''Dwelling CFC is **missing, not zero**.36-10-0096/0098 extracts are nonresidential. Required residential source: [StatCan36-10-0099-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610009901), Current prices / Geometric depreciation / Total residential / province /2022, followed by owner-occupied versus rented allocation. No number assumed or imported. §OOH_dwelling_CFC§ and §OOH_actual_net_profit§ remain missing provincially and nationally.

## Provenance and final review

All IO reads use immutable git show, never the working tree. Native v-numbers do not exist for the mapped custom SUT/OOH split; industry/use/component codes and pinned blobs supply identifiers. IO source:2022 provincial detailed SUT/[StatCan36-10-0478-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610047801) handoff (table identification checked2026-10-25; the actual numeric input remains the pinned git blob). Blob hashes and dates:

{table(pd.DataFrame(sources))}

The compatibility LF blob f0004ad3… and handoff CRLF representation41590fdb… were reconciled byte-for-byte in SG. FSG caches actual regional vectors. Examples:36-10-0096 Canada2022 Current prices/Investment/Total nonresidential v90968052 (411.341B), Government v90970252 (98.480B), NPISH v90970012 (1.519B), Government education v90970292, Hospitals v90970332, Nursing/residential care v90970372. Residential36-10-0099 v91665012 (249.779B). Investment observations are not dwelling CFC.

Nonresidential downloaded2026-10-24T19:59:02.951130Z, zip SHA256b5ec714f9eef4cedf80759f1ed5bf0f08ed1b18f2753f6933aee8a68fb1f0bd6; fullCSV e790e88e5808acc587c33b7e6f4de32b7ab046a839c48ae9ad1065f31255b8e0; selected2022CSV c80839b83259cdce64e053e1a5172f73d82845a682935eb90ce7d4140e45ddfd. Residential downloaded2026-10-24T20:22:32.343037Z, zip f6d5ed033f4e902d91e9fd747b564d41cc2d66b9bfdc03de51474acdec482d37; fullCSV ff5992b66c3127a24c56eb9484051ec8afb436f2843e5dd4d263f24590502f76. URLs/dates/hashes in §FSG_build_gate.json§ and benchmarks/ZA.

{testline} Exact IDs/messages and sampler worker property in §full_test_execution.json§, full log/XML retained. §audit.json§ and §artifact_manifest.json§ verify protected input/source/candidate hashes, floor certificates, sequential long-run order and frozen aggregate evidence. No pickles or household microdata in the evidence commit; no push or original/ITC writes.

**Recommendation:** retain the zero-activity mechanical correction and corrected gate specification; review FS_T as the corrected diagnostic starting input. Keep FSG blocked on signed source-use representation. Housing makes the cash/noncash question material, but negative household residuals preclude adopting the aggregate subtraction as a rule. Passing accounting does not validate household losses/default or spending dynamics. Phase B and C_dp_005 remain on hold.
'''
    for old,new in [('seeds0','seeds 0'),('seed0','seed 0'),('seeds1','seeds 1'),('all68','all 68'),('roughly50','roughly 50'),('Same1M','Same 1M'),('threshold1','threshold 1'),('all13','all 13'),('All13','All 13'),('below0.01','below 0.01'),('above1pp','above 1pp'),('max100pp','max 100pp'),('than1','than 1'),('over12','over 12'),('across3','across 3'),('all3','all 3')]:
        text=text.replace(old,new)
    (HERE/'CLOSURE_ZA_2026-10-25.md').write_text(text.replace('§',chr(96)),encoding='utf-8')
    entry=f'''

<!-- ZA-2026-10-25 -->
## ZA review - 2026-10-25 UTC

Report: [CLOSURE_ZA_2026-10-25.md](CLOSURE_ZA_2026-10-25.md). FS_T v4 passes the corrected source-positive/floor cost specification, all13 GDP initializations,2Q and seeds0-2 twelve-quarter accounting. Review it as the corrected diagnostic input; this does not validate the household spending/default dynamics. FSG remains blocked before building. Phase B, C_dp_005, housing closure implementation and investment expansion stay on hold.

| Issue / step | Commit / evidence / finding | Review decision |
| --- | --- | --- |
| SG-Z / ZA-zero convention | 1ffdc06; three regressions plus serial positive F_CFC2Q bit replay. All68 exact canonical zero-source cells receive the inherited1M/year output=VA=domestic-FCF floor (29 old +39 new). Zero-target/zero-capacity work effort0; contracts/jobs preserved initially. 4082 numeric per-firm arrays per replay run identical. | Mechanical correction retained. Aggregate floors68M/year,0.001345% of output. |
| ZA cost specification | a9fee55; two regressions; declaration frozen before v4. Positive-source max margin0.771775pp, zero1pp and above-price exceptions. Old universal gate68 exceptions100pp, all floors. | Corrected specification passes; old universal result remains visible. FS fallback has211 positive-source exceptions and6 above-price cases. |
| ZA short audit schema | f599a9d; one regression. Actual short-run accounting passes4.55e-15; first wrapper failed only on intentionally unset Q0 target forecast. Raw failed output retained, separate certificate excludes only that placeholder. | No economic value or tolerance changed. Final adoption certificate supersedes the earlier failed wrapper controller result. |
| FS_T adoption retry | New v4 SHA0ef644b38f2ab6945a4af868406ede0f28b03d6237ddc54519c4cfa8e86cc2a6. All13 GDP checks,2Q and3x12Q pass; largest battery1.10e-14. GOS falls148.896B/year. Nominal Q0-Q12 GDP changes -10.8/-5.1/-12.3% vs historical F_CFC -7.6/-8.9/-17.4%; household losses234-235B, constrained share about50%. | Corrected accounts, mixed dynamic effect; no claim that losses/default or demand collapse are validated. |
| ZA-FSG signed fixed-capital uses | 7f9789c; three regressions; separate IO GFCF624.511B/year incl68M floors and inventories55.631B.20 net-product uses negative, -3.502B/year; existing purchase recording clips negatives. Sector/price bridge and source vectors recorded without replacing IO levels. | No FSG pickle or material-group/GDP/accounting pass. Dependent runs skipped. Establish source meaning and signed non-purchase/disposal counterpart treatment; no clipping/rescale/inventory offset. |
| ZA-FSG valuation / sector scope | Independent read-only bridge: reusing the legacy24.4739% household capital tax on the diagnostic residential basic budget yields292.565B/year purchaser spending vs249.779B source, a42.786B gap. Total residential scope also differs7.386B from the242.393B household-sector GFCF benchmark. | No tax-rate tuning or fiscal change. Reconcile sector/asset scope and product-tax valuation before an executable FSG build. |
| ZA-OOH exact split | 41d4e68; read-only eb40128 source. Remove235.939587B source imputed consumption, add66.623975B cash costs, allocated by existing provincial owner memos. F_CFC planned gap95.884B ->-73.432B, dissaver share71.94% ->37.11%; CIS gap87.519B ->-81.796B,70.10% ->35.88%. | Source totals exact, household allocation assumed.206250/189170 negative household residuals retained; cannot install as a cash rule without coherent household attribution. No closure change. |
| ZA-OOH profit / CFC identification | Current F_CFC OOH gross contribution204.726B includes35.410B omitted property taxes; source gross mixed income169.316B. Dwelling CFC and OOH net profit remain missing in provincial and national files. Residential CFC source36-10-0099 plus tenure allocation needed. | No zero depreciation assumption or invented net-profit allocation. Market-profit residual is a labelled convention. |

{testline} Protected inputs/source hashes audited; aggregate evidence only, no pickles or household microdata. Stop for review.
'''
    register=HERE/'ISSUE_REGISTER.md';old=register.read_text(encoding='utf-8')
    marker='<!-- ZA-2026-10-25 -->'
    if marker in old:old=old[:old.index(marker)].rstrip()
    register.write_text(old+entry,encoding='utf-8')
    print('ZA report rendered',len(text),'characters')

if __name__=='__main__':main()
