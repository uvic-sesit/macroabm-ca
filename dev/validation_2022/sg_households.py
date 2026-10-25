"""Read-only t0 housing scope and CIS tax-concept probes. Never iterate or pay cash."""
import json
import numpy as np,pandas as pd
from macro_data import DataWrapper
from macromodel.simulation import Simulation
from macromodel.configurations import CountryConfiguration,SimulationConfiguration
from closure_diagnostics import cur
from b2_instrumentation import fixed_groups,gross_wages_from_net
from qe_baseline import PICKLE,configuration
from build_hi_cis import TARGET
from hi_income_audit import cis_households,PUMF
from prepare_sg import HERE,OUT,sha

def households(sim,arm):
    blocks=[]
    for name,c in sim.countries.items():
        h=c.households;g=c.central_government;cl=c.household_closure;tax=g.states['Income Tax'];ssc=g.states['Employee Social Insurance Tax'];n=len(cur(h,'income'))
        wage=cur(h,'income_employee');gross=gross_wages_from_net(wage,tax,ssc);mixed=cl.planned_mixed;div=cl.planned_dividends;corp=cl.planned_transfers
        income=cur(h,'income')-cur(h,'income_financial_assets')+mixed+div+corp
        li=sum(c.credit_market.states[k][1].sum(axis=0) for k in ['cons_loans','mort_loans']);dep=cur(h,'wealth_deposits');ids=h.states['Corresponding Bank ID']
        received=np.maximum(0,dep)*cur(c.banks,'interest_rate_on_household_deposits')[ids];interest=li+np.maximum(0,-dep)*cur(c.banks,'overdraft_rate_on_household_deposits')[ids]-received;di=income-interest
        fn=h.functions['consumption'];goods=fn.compute_target_consumption(expected_inflation=0.,current_cpi=1.,initial_cpi=1.,historic_consumption_sum=np.asarray(h.ts.historic('consumption')),saving_rates=np.full(n,h.states['average_saving_rate']),income=income,household_benefits=h.states['Number of Adults']*cur(g,'unemployment_benefits_by_individual')[0]+cur(h,'income_social_transfers'),consumption_weights=h.consumption_weights,consumption_weights_by_income=h.consumption_weights_by_income,exogenous_total_consumption=np.zeros(1),current_time=1,take_consumption_weights_by_income_quantile=h.use_consumption_weights_by_income,tau_vat=g.states['Value-added Tax'])
        L=41;vat=g.states['Value-added Tax'];props=c.housing_market.states['properties'];rented=props[(props['Is Owner-Occupied']==0)&(props['Corresponding Inhabitant Household ID']>=0)&(props['Corresponding Owner Household ID']>=0)];private=np.zeros(n);np.add.at(private,rented['Corresponding Inhabitant Household ID'].to_numpy(int),rented.Rent.to_numpy());private=np.minimum(private,cur(h,'rent'))
        offset=np.minimum(np.maximum(0,goods[:,L]),private/(1+vat));goods=goods.copy();goods[:,L]-=offset
        C=goods.sum(axis=1)*(1+vat)+cur(h,'rent');imp=cur(h,'rent_imputed');owner=np.isin(np.asarray(h.states['Tenure Status of the Main Residence']),[1,2,4])
        # The L purchase bundle does not identify imputed rent. This is an explicit upper-bound diagnostic, not a new allocation.
        owner_L=np.where(owner,goods[:,L]*(1+vat),0.);memo_proxy=np.minimum(owner_L,np.maximum(0,imp));C_proxy=C-memo_proxy;C_upper=C-owner_L
        cis_net=income+ssc*gross
        public=cur(h,'income_social_transfers')+cur(h,'income_unemployment_benefits')
        pretax=gross+public+(cur(h,'income_rental')+mixed+div+corp)/(1-tax)
        blocks.append(pd.DataFrame(dict(arm=arm,region=str(name),weight=c.scale,owner=owner,tenure=np.where(owner,'owner','renter_or_other'),C=4*C,DI=4*di,planned_L=4*goods[:,L]*(1+vat),owner_L=4*owner_L,imputed_memo=4*imp,imputed_cash_income=0.,private_rent_offset=4*offset*(1+vat),actual_rent=4*cur(h,'rent'),memo_proxy_removed=4*memo_proxy,C_memo_proxy=4*C_proxy,C_all_owner_L_removed=4*C_upper,after_tax=4*cis_net,before_tax=4*pretax,model_PIT=4*(pretax-cis_net))))
    return pd.concat(blocks,ignore_index=True)

def main():
    cis=cis_households();cis['before_tax']=cis.income+cis.taxes;cis['after_tax']=cis.income
    comparisons=[];housing=[];national=[];rates=[];coverage=[]
    cis['gross_decile']=fixed_groups(cis.before_tax.to_numpy(),cis.weight.to_numpy(),10)
    for dec,g in cis.groupby('gross_decile'):
        rate=float((g.taxes*g.weight).sum()/(g.before_tax*g.weight).sum());rates.append(dict(decile=int(dec),effective_PIT=rate,source='CIS 2022 PUMF EFATINC + EFINCTX; combined observed income taxes, not a statutory schedule'))
    rate_map={r['decile']:r['effective_PIT'] for r in rates}
    for arm,path in [('F_CFC',PICKLE),('CIS_candidate',TARGET)]:
        d=DataWrapper.init_from_pickle(path);assert list(d.industries).index('L')==41;names=[n for n in d.all_country_names if str(n).startswith('CAN_')];configs={n:CountryConfiguration.n_industry_default(n_industries=d.n_industries) for n in names}
        for c in configs.values():c.household_closure=configuration()
        sim=Simulation.from_datawrapper(d,SimulationConfiguration(country_configurations=configs,t_max=2,seed=0));a=households(sim,arm)
        a['decile']=fixed_groups(a.after_tax.to_numpy()/a.weight,a.weight.to_numpy(),10)
        for (dec,tenure),g in a.groupby(['decile','tenure']):
            z=dict(arm=arm,decile=int(dec),tenure=tenure,households=float(g.weight.sum()))
            for k in ['C','DI','planned_L','owner_L','imputed_memo','imputed_cash_income','private_rent_offset','actual_rent','memo_proxy_removed']:z[k]=float(g[k].sum())
            for k in ['C','C_memo_proxy','C_all_owner_L_removed']:z[k+'_dissavers']=float(g.loc[g[k]>g.DI,'weight'].sum())
            housing.append(z)
        nation=dict(arm=arm,source_sha256=sha(path),C=float(a.C.sum()),DI=float(a.DI.sum()),gap=float((a.C-a.DI).sum()),imputed_memo=float(a.imputed_memo.sum()),owner_L=float(a.owner_L.sum()),memo_proxy=float(a.memo_proxy_removed.sum()),households=float(a.weight.sum()))
        for k in ['C','C_memo_proxy','C_all_owner_L_removed']:nation[k+'_dissaver_share']=float(a.loc[a[k]>a.DI,'weight'].sum()/a.weight.sum())
        national.append(nation)
        for concept in ['before_tax','after_tax']:
            a['group']=fixed_groups(a[concept].to_numpy()/a.weight,a.weight.to_numpy(),10);cis['group']=fixed_groups(cis[concept].to_numpy(),cis.weight.to_numpy(),10)
            model=a.groupby('group')[concept].sum();bench=cis.assign(value=cis[concept]*cis.weight).groupby('group').value.sum()
            if concept=='after_tax':bench=pd.read_csv(HERE/'benchmarks/HI/cis_household_deciles_2022.csv').set_index('decile').income
            for j in range(1,11):comparisons.append(dict(arm=arm,concept=concept,decile=j,model_income=float(model[j]),CIS_income=float(bench[j]),model_share=float(model[j]/model.sum()),CIS_share=float(bench[j]/bench.sum()),relative_gap=float((model[j]/model.sum())/(bench[j]/bench.sum())-1)))
        a['gross_decile']=fixed_groups(a.before_tax.to_numpy()/a.weight,a.weight.to_numpy(),10);a['progressive_income']=a.before_tax*(1-a.gross_decile.map(rate_map));a['group']=fixed_groups(a.progressive_income.to_numpy()/a.weight,a.weight.to_numpy(),10);cis['group']=fixed_groups(cis.after_tax.to_numpy(),cis.weight.to_numpy(),10)
        model=a.groupby('group').progressive_income.sum();bench=pd.read_csv(HERE/'benchmarks/HI/cis_household_deciles_2022.csv').set_index('decile').income
        for j in range(1,11):comparisons.append(dict(arm=arm,concept='empirical_progressive_read_only',decile=j,model_income=float(model[j]),CIS_income=float(bench[j]),model_share=float(model[j]/model.sum()),CIS_share=float(bench[j]/bench.sum()),relative_gap=float((model[j]/model.sum())/(bench[j]/bench.sum())-1)))
        coverage.append(dict(arm=arm,flat_PIT=float(a.model_PIT.sum()),counterfactual_PIT=float((a.before_tax-a.progressive_income).sum()),before_tax_income=float(a.before_tax.sum()),counterfactual_after_tax_income=float(a.progressive_income.sum())))
        print('Read-only household checks complete',arm,flush=True)
    pd.DataFrame(housing).to_csv(OUT/'housing_by_decile_tenure.csv',index=False);pd.DataFrame(national).to_csv(OUT/'housing_national.csv',index=False);pd.DataFrame(comparisons).to_csv(OUT/'CIS_concepts.csv',index=False);pd.DataFrame(rates).to_csv(OUT/'CIS_effective_PIT.csv',index=False);pd.DataFrame(coverage).to_csv(OUT/'PIT_counterfactual_national.csv',index=False)
    (OUT/'household_provenance.json').write_text(json.dumps(dict(PUMF_sha256=sha(PUMF),reference='CIS2022 PUMF 72M0003X, household custom tabulation; EFATINC and EFINCTX unique economic families aggregated once by PUMFID, FWEIGHT household weight. No vector IDs for custom microdata aggregation.',date='2026-10-25',tax_counterfactual='Observed combined federal/provincial effective PIT by before-tax household-income decile, applied read-only to model gross cash income; descriptive incidence mapping, not a statutory tax-benefit model or a fitted schedule. No national revenue rescale. Transfers are not uniformly taxed in the existing model; before/after shares need not be identical.',housing_identification='Sector L is a mixed bundle without an owner-imputed-rent purchase line. Report owner L spending as an upper bound; min(owner L, imputed memo) as a labelled attribution proxy, never exact identification or a behavioral candidate.'),indent=2)+'\n')
if __name__=='__main__':main()
