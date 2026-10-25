"""Exact source OOH totals, explicit owner allocation; no closure change or iteration."""
import json
import numpy as np,pandas as pd
from macro_data import DataWrapper
from macromodel.simulation import Simulation
from macromodel.configurations import CountryConfiguration,SimulationConfiguration
from qe_baseline import PICKLE,configuration
from build_hi_cis import TARGET as CIS
from sg_households import households
from b2_instrumentation import fixed_groups
from prepare_za import BENCH,OUT,sha
def main():
    o=pd.read_csv(BENCH/'canonical/ooh_by_province_basic.csv').set_index('region');inputs=pd.read_csv(BENCH/'canonical/ooh_inputs_by_province_commodity_basic.csv');assert np.allclose(inputs.total_basic,inputs[['domestic','interprovincial_imports','international_imports']].sum(axis=1),atol=1e-7,rtol=1e-9)
    groups=[];national=[];L=[];province=[]
    for arm,path in [('F_CFC',PICKLE),('CIS_candidate',CIS)]:
        data=DataWrapper.init_from_pickle(path);names=[n for n in data.all_country_names if str(n).startswith('CAN_')];cfg={n:CountryConfiguration.n_industry_default(n_industries=data.n_industries) for n in names}
        for c in cfg.values():c.household_closure=configuration()
        sim=Simulation.from_datawrapper(data,SimulationConfiguration(country_configurations=cfg,t_max=2,seed=0));a=households(sim,arm);a['OOH_removed']=0.;a['owner_cash_costs_added']=0.
        for n in names:
            name=str(n);r=o.loc[name];mask=(a.region==name)&a.owner;weights=a.loc[mask,'imputed_memo'];assert weights.sum()>0
            cash=(r.ooh_intermediate_inputs_basic+r.ooh_net_product_tax_on_inputs+r.ooh_tax_production+r.ooh_subsidy_production)*1e6
            output=r.ooh_output_basic*1e6;assert abs(output-cash-r.ooh_gross_mixed_income*1e6)<1.
            assert abs(inputs[inputs.region==name].total_basic.sum()-r.ooh_intermediate_inputs_basic)<1e-5
            a.loc[mask,'OOH_removed']=output*weights/weights.sum();a.loc[mask,'owner_cash_costs_added']=cash*weights/weights.sum()
            province.append(dict(arm=arm,region=name,OOH_removed=output,owner_cash_costs_added=cash,noncash_gross_mixed_income=r.ooh_gross_mixed_income*1e6,source_memo_difference=output-weights.sum()))
            if arm=='F_CFC':
                c=data.synthetic_countries[n];f=c.firms;j=list(data.industries).index('L');idx=np.flatnonzero(f.firm_data.Industry.to_numpy(int)==j);assert len(idx)==1;i=idx[0];d=f.firm_data.iloc[i]
                revenue=d.Production*d.Price*4;gos=(d.Production*d.Price-f.used_intermediate_inputs[i].sum()-d['Total Wages Paid']-d['Taxes paid on Production'])*4;profit=d.Profits*4
                # F_CFC omits D29/D39: the OOH property tax remains in L surplus.
                ooh_model_contribution=output-(r.ooh_intermediate_inputs_basic+r.ooh_net_product_tax_on_inputs)*1e6
                L.append(dict(region=name,model_L_revenue=revenue,model_L_GOS=gos,model_L_profit=profit,model_L_nonres_CFC=4*f.used_capital_inputs[i].sum(),model_L_net_interest=4*d['Interest paid'],OOH_source_revenue=output,OOH_source_cash_costs=cash,OOH_source_mixed_income=r.ooh_gross_mixed_income*1e6,OOH_model_gross_surplus_contribution=ooh_model_contribution,market_L_model_revenue_residual=revenue-output,market_L_GOS_residual=gos-ooh_model_contribution,market_L_profit_residual_if_modeled_nonres_CFC_and_firm_interest_remain_here=profit-ooh_model_contribution,market_L_source_revenue=r.L_market_output_basic*1e6,market_L_source_VA=r.L_market_va_basic*1e6,OOH_dwelling_CFC=np.nan,OOH_actual_net_profit=np.nan))
        a['cash_C_exact_split']=a.C-a.OOH_removed+a.owner_cash_costs_added;a['decile']=fixed_groups(a.after_tax.to_numpy()/a.weight.to_numpy(),a.weight.to_numpy(),10)
        for (dec,tenure),g in a.groupby(['decile','tenure']):
            row=dict(arm=arm,decile=int(dec),tenure=tenure,households=float(g.weight.sum()))
            for key in ['C','DI','OOH_removed','owner_cash_costs_added','cash_C_exact_split']:row[key]=float(g[key].sum())
            row['old_dissaver_households']=float(g.loc[g.C>g.DI,'weight'].sum());row['new_dissaver_households']=float(g.loc[g.cash_C_exact_split>g.DI,'weight'].sum());row['negative_residual_households']=float(g.loc[g.cash_C_exact_split<0,'weight'].sum());row['negative_residual_C']=float(g.cash_C_exact_split.clip(upper=0).sum());groups.append(row)
        national.append(dict(arm=arm,source_pickle_sha256=sha(path),C=float(a.C.sum()),DI=float(a.DI.sum()),old_gap=float((a.C-a.DI).sum()),OOH_removed=float(a.OOH_removed.sum()),owner_cash_costs_added=float(a.owner_cash_costs_added.sum()),new_cash_C=float(a.cash_C_exact_split.sum()),new_gap=float((a.cash_C_exact_split-a.DI).sum()),old_dissaver_share=float(a.loc[a.C>a.DI,'weight'].sum()/a.weight.sum()),new_dissaver_share=float(a.loc[a.cash_C_exact_split>a.DI,'weight'].sum()/a.weight.sum()),negative_residual_households=float(a.loc[a.cash_C_exact_split<0,'weight'].sum()),negative_residual_C=float(a.cash_C_exact_split.clip(upper=0).sum())))
        print('ZA exact-source housing diagnostic complete',arm,flush=True)
    pd.DataFrame(groups).to_csv(OUT/'OOH_cash_by_decile_tenure.csv',index=False);pd.DataFrame(national).to_csv(OUT/'OOH_cash_national.csv',index=False);pd.DataFrame(province).to_csv(OUT/'OOH_owner_allocation_by_province.csv',index=False);pd.DataFrame(L).to_csv(OUT/'OOH_L_profit_bridge.csv',index=False)
    (OUT/'OOH_method.json').write_text(json.dumps(dict(source_commit='eb40128',source_table='2022 provincial SUT BS5311A0, HFCE PEC04200',allocation='Exact provincial source OOH output and cash-cost totals allocated to owner households in proportion to their existing imputed-rent memos within each province. Survey weights unchanged. Household attribution is an explicit assumption; source totals are exact.',no_closure_change=True,no_VAT_grossup=True,negative_residuals='Retained and reported, never clipped or redistributed to obtain a result.',profit_identification='OOH gross contribution identifiable. Dwelling CFC absent, and firm interest not attributed to OOH; actual OOH net profit is not identified. Market-profit residual keeps all modeled nonresidential CFC and firm interest in market L, an explicit diagnostic convention, not a sourced OOH net profit.',dwelling_CFC_source_needed='StatCan36-10-0099-01, Current prices/Geometric depreciation/Total residential/province/2022; then owner-occupied vs rented tenure allocation.36-10-0096/0098 extracts are non-residential; no dwelling CFC number assumed.',CFC_reference='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610009901',reference_checked_UTC='2026-10-25'),indent=2)+'\n')
if __name__=='__main__':main()
