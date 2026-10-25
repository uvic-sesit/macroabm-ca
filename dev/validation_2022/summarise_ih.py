"""Aggregate frozen IH evidence; no simulation or calibration."""
import json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;OUT=HERE/'outputs/IH'
def main():
    headlines=[];quarters=[];changes=[];decomps=[];investments=[];gates=[];incomes=[];entrants=[];resolutions=[];matches=[]
    mapping=pd.read_csv(HERE/'outputs/B2/firm_data/cfc_cost_bridge.csv')[['region','firm','industry']].rename(columns={'industry':'industry_code'})
    obs=pd.read_csv(HERE/'benchmarks/IH/DHEA_components_2022.csv');value=obs[obs.Statistics=='Value'];taxrates=json.loads((OUT/'tax_rates.json').read_text());tax=next(iter(taxrates.values()))['income_tax'];assert all(v['income_tax']==tax for v in taxrates.values())
    for p in sorted((OUT/'runs').glob('*_q12_s*/manifest.json')):
        m=json.loads(p.read_text());arm=m['variant'].removeprefix('IH_');seed=m['seed'];d=p.parent
        h=pd.read_csv(d/'headline.csv').groupby('quarter').sum(numeric_only=True);q0=h.loc[0];q12=h.loc[12]
        for t,r in h.iterrows():headlines.append(dict(arm=arm,seed=seed,quarter=t,**r.to_dict()))
        o=pd.read_csv(d/'outcomes.csv');q=o.groupby('quarter').sum(numeric_only=True)
        for k in ['min_capital_ratio','min_resolution_ratio']:q[k]=o.groupby('quarter')[k].min()
        q['cash_saving_rate']=1-q.consumption/q.cash_DI;q['constrained_share']=q.constrained_households/q.represented_households
        for t,r in q.iterrows():quarters.append(dict(arm=arm,seed=seed,quarter=t,**r.to_dict()))
        for k in ['gdp','gdp_PPI_deflated','C','C_CPI_deflated','I','I_CFPI_deflated','employment']:
            changes.append(dict(arm=arm,seed=seed,metric=k,Q0=q0[k],Q1=h.loc[1,k],Q12=q12[k],Q0_Q12_pct=100*(q12[k]/q0[k]-1),Q1_Q12_pct=100*(q12[k]/h.loc[1,k]-1)))
        dif=q12-q0
        for k,sign in [('C',1),('G',1),('I',1),('inventories',1),('X',1),('M',-1)]:decomps.append(dict(arm=arm,seed=seed,component=k,delta_CAD=sign*dif[k],share_GDP_change=sign*dif[k]/dif.gdp))
        residual=dif.gdp_expenditure-(dif.C+dif.G+dif.I+dif.inventories+dif.X-dif.M)
        gates.append(dict(arm=arm,seed=seed,gate='H-G1',passed=bool(abs(q0.expenditure_unallocated)<1 and abs(residual)<1 and m['max_accounting_error']<=1e-8),value=abs(residual),accounting_error=m['max_accounting_error']))
        if arm in ['F_CFC','E']:
            prev=HERE/'outputs/QE/runs'/f'{arm}_{"base" if arm=="F_CFC" else "complete"}_q12_s{seed}'
            old=pd.read_csv(prev/'outcomes.csv');exact=o.equals(old);a=pd.read_csv(d/'headline.csv');b=pd.read_csv(prev/'headline.csv');cols=[k for k in b if k not in ['gdp','gdp_income','gdp_expenditure','gdp_PPI_deflated','expenditure_unallocated']]
            hp=np.allclose(a[cols].select_dtypes('number'),b[cols].select_dtypes('number'),rtol=0,atol=0,equal_nan=True)
            matches.append(dict(arm=arm,seed=seed,outcomes_exact=exact,other_headline_paths_exact=hp,t0_GDP_reduction=(b.query('quarter==0').gdp.sum()-a.query('quarter==0').gdp.sum()),dynamic_GDP_exact=np.array_equal(a.query('quarter>0').gdp,b.query('quarter>0').gdp)))
            gates.append(dict(arm=arm,seed=seed,gate='H-G2',passed=exact and hp,value=0. if exact and hp else 1.))
        f=pd.read_csv(d/'investment_cells.csv').merge(mapping,on=['region','firm'],validate='many_to_one')
        initial=f[f.quarter==0].set_index(['region','firm']).net_investment
        f['initial_net_investment']=pd.MultiIndex.from_frame(f[['region','firm']]).map(initial)
        f['hold_initial_net_accounting']=f.CFC+f.initial_net_investment
        f['arm']=arm;f['seed']=seed;investments.append(f)
        inc=pd.read_csv(d/'income_quintiles.csv');inc['arm']=arm;inc['seed']=seed
        inc['DI_share']=inc.DI/inc.groupby('quarter').DI.transform('sum');inc['DI_per_HH_annual']=4*inc.DI/inc.weight;inc['mean_equivalised_DI_per_HH_annual']=4*inc.equivalised_DI_weighted/inc.weight
        inc['nonpositive_DI_share']=inc.zero_DI_households/inc.weight;inc['negative_DI_share']=inc.negative_DI_households/inc.weight
        # Exact gross-up under the common income tax rate; wage compensation excludes employer SSC.
        inc['mixed_gross']=inc.mixed_net/(1-tax);inc['property_gross_ex_deposit_interest']=(inc.dividends_net+inc.rent_net)/(1-tax);inc['corporate_transfers_gross']=inc.corporate_transfers_net/(1-tax);inc['current_transfers_gross']=inc.government_transfers+inc.corporate_transfers_gross
        incomes.append(inc)
        if (d/'arrears_entrants.csv').exists():
            x=pd.read_csv(d/'arrears_entrants.csv');x['arm']=arm;x['seed']=seed;entrants.append(x)
        try:
            x=pd.read_csv(d/'resolutions.csv');x['arm']=arm;x['seed']=seed;resolutions.append(x)
        except pd.errors.EmptyDataError:pass
        if arm in ['E','E2']:
            ratio=100*(q.household_writeoffs.sum()/3)/(h.household_debt+q.overdraft_liability.reindex(h.index,fill_value=0)).mean()
            a60=100*h.loc[1:12,'mortgage_60plus']/h.loc[1:12,'mortgage_borrowers'];a90=100*h.loc[1:12,'mortgage_90plus']/h.loc[1:12,'mortgage_borrowers']
            passed=bool(a60.between(.125,.5).all() and a90.between(.075,.3).all() and .05<=ratio<=.28)
            gates.extend([dict(arm=arm,seed=seed,gate='E-G1',passed=passed,value=ratio,Q12_60plus_pct=a60.iloc[-1],Q12_90plus_pct=a90.iloc[-1]),dict(arm=arm,seed=seed,gate='E-G2',passed=bool(q.loc[1,'household_writeoffs']<=2*q.loc[4:12,'household_writeoffs'].mean()+1e-3),value=q.loc[1,'household_writeoffs']),dict(arm=arm,seed=seed,gate='E-G3',passed=m['max_accounting_error']<=1e-8,value=m['max_accounting_error'])])
    for name,data in [('headline',headlines),('quarterly',quarters),('changes',changes),('GDP_decomposition',decomps),('gates',gates),('behaviour_comparison',matches)]:pd.DataFrame(data).to_csv(OUT/(name+'.csv'),index=False)
    f=pd.concat(investments,ignore_index=True);f.to_csv(OUT/'investment_industry_province.csv',index=False)
    numeric=['replacement_planned','stock_adjustment_and_clipping','unconstrained','planned','credit_cut','realised','clearing_price_residual','CFC','net_investment','initial_net_investment','hold_initial_net_accounting','wages','long_credit_target','long_credit_received']
    g=f.groupby(['arm','seed','quarter'])[numeric].sum();g.to_csv(OUT/'investment_national.csv')
    f['producer_scope']=np.where(f.industry_code.isin(['O','P','Q']),'O_P_Q','other_industries');f.groupby(['arm','seed','quarter','producer_scope'])[numeric].sum().to_csv(OUT/'investment_scope.csv')
    inc=pd.concat(incomes,ignore_index=True);inc.to_csv(OUT/'income_quintiles.csv',index=False)
    bridge=[];names={'wages_gross':'Compensation of employees','mixed_gross':'Net mixed income','property_gross_ex_deposit_interest':'Property income received','current_transfers_gross':'Current transfers received','taxes_contributions':'Less: current transfers paid','net_interest':'Less: property income paid','DI':'Household disposable income'}
    for r in inc[(inc.arm=='F_CFC')&inc.quarter.isin([0,12])].itertuples():
        for model,source in names.items():
            row=value[(value.quintile==r.quintile)&(value['Income, consumption and savings']==source)].iloc[0]
            bridge.append(dict(seed=r.seed,quarter=r.quarter,quintile=r.quintile,model_line=model,source_line=source,model_annual_B=4*getattr(r,model)/1e9,DHEA_annual_B=row.VALUE/1e3,gap_B=4*getattr(r,model)/1e9-row.VALUE/1e3,vector=row.VECTOR,scope_note='corporate transfers are part of transfers received; do not add duplicate benchmark. Wages exclude employer SSC; mixed omits imputed housing; net interest excludes received deposit interest from gross property line. Model PIT/employee SSC omit DHEA noncash contributions.'))
    pd.DataFrame(bridge).to_csv(OUT/'DHEA_component_bridge.csv',index=False)
    compare=[]
    for r in inc[(inc.arm=='F_CFC')&inc.quarter.isin([0,12])].itertuples():
        z=obs[(obs.quintile==r.quintile)&(obs['Income, consumption and savings']=='Household disposable income')]
        val=z[z.Statistics=='Value'].iloc[0];per=z[z.Statistics=='Value per household'].iloc[0];unit=z[z.Statistics=='Value per consumption unit'].iloc[0]
        compare.append(dict(seed=r.seed,quarter=r.quarter,quintile=r.quintile,model_DI_share=r.DI_share,DHEA_DI_share=val.VALUE/value[value['Income, consumption and savings']=='Household disposable income'].VALUE.sum(),model_per_HH=r.DI_per_HH_annual,DHEA_per_HH=per.VALUE,nonpositive_DI_share=r.nonpositive_DI_share,negative_DI_share=r.negative_DI_share,DI_vector=val.VECTOR,per_HH_vector=per.VECTOR))
    pd.DataFrame(compare).to_csv(OUT/'DHEA_DI_comparison.csv',index=False)
    if entrants:pd.concat(entrants,ignore_index=True).to_csv(OUT/'arrears_entrants.csv',index=False)
    if resolutions:pd.concat(resolutions,ignore_index=True).to_csv(OUT/'resolution_log.csv',index=False)
    print(pd.DataFrame(gates).to_string(index=False))
if __name__=='__main__':main()
